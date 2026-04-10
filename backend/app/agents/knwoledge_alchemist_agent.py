"""
knwoledge_alchemist_agent.py — KEIEI-AI 攻め：現場ナレッジ錬成
機能:
  - テキスト・音声文字起こしから暗黙知を抽出
  - 4軸構造化（手順・判断基準・例外・失敗事例）
  - RAGへの保存
  - eラーニングシラバス自動生成（syllabus_agent連携）
"""
from __future__ import annotations
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from langchain_core.messages import HumanMessage, SystemMessage
from app.core.llm_factory import get_llm_analysis


# =====================================================
# 1. データモデル
# =====================================================

@dataclass
class KnowledgeItem:
    """抽出された知識1件"""
    title: str
    category: str  # procedure / judgment / exception / failure
    content: str
    skill_level: str = "general"  # beginner / intermediate / advanced / general
    tags: list[str] = field(default_factory=list)
    source: str = ""
    created_at: str = ""


@dataclass
class AlchemyResult:
    """錬成結果"""
    items: list[KnowledgeItem] = field(default_factory=list)
    summary: str = ""
    knowledge_weight: float = 0.0  # kg換算

    def to_markdown(self) -> str:
        if not self.items:
            return "## ナレッジ錬成結果\n\nナレッジを抽出できませんでした。"

        lines = [
            "## ナレッジ錬成結果 ✨",
            f"**抽出件数**: {len(self.items)}件",
            f"**知識の重み**: +{self.knowledge_weight:.1f}kg",
            f"**概要**: {self.summary}",
            "",
        ]

        category_label = {
            "procedure": "[手順] 手順",
            "judgment": "[判断] 判断基準",
            "exception": "[注意] 例外対応",
            "failure": "[失敗] 失敗事例",
        }

        for item in self.items:
            label = category_label.get(item.category, item.category)
            lines += [
                f"### {label}：{item.title}",
                f"**スキルレベル**: {item.skill_level}",
                f"{item.content}",
                "",
            ]

        lines.append("\n> [ヒント] このナレッジからeラーニングを作成しますか？「シラバスを作って」と入力してください。")
        return "\n".join(lines)


# =====================================================
# 2. 知識抽出プロンプト
# =====================================================

EXTRACTION_PROMPT = """あなたはKEIEI-AIのナレッジ錬成エージェントです。
現場の文章・会話・メモから「暗黙知」を「形式知」に変換します。

【4軸で構造化してください】
1. procedure（手順）: 作業の順番・やり方
2. judgment（判断基準）: 「こういう時はこうする」という経験則
3. exception（例外対応）: イレギュラーな状況への対処
4. failure（失敗事例）: やってはいけないこと・失敗から学んだこと

【出力フォーマット（JSON）】
{
  "summary": "全体の要約（50文字以内）",
  "items": [
    {
      "title": "知識のタイトル（20文字以内）",
      "category": "procedure|judgment|exception|failure",
      "content": "具体的な内容（100文字以内）",
      "skill_level": "beginner|intermediate|advanced|general",
      "tags": ["タグ1", "タグ2"]
    }
  ]
}

必ずJSONのみを返してください。"""


# =====================================================
# 3. メイン処理
# =====================================================

async def extract_knowledge(text: str) -> AlchemyResult:
    """テキストから知識を抽出"""
    llm = get_llm_analysis()

    response = await llm.ainvoke([
        SystemMessage(content=EXTRACTION_PROMPT),
        HumanMessage(content=f"以下のテキストから知識を抽出してください：\n\n{text[:3000]}"),
    ])

    content = str(response.content).strip()

    import re
    content = re.sub(r"```json|```", "", content).strip()

    try:
        data = json.loads(content)
        items = [
            KnowledgeItem(
                title=item.get("title", ""),
                category=item.get("category", "general"),
                content=item.get("content", ""),
                skill_level=item.get("skill_level", "general"),
                tags=item.get("tags", []),
                source="user_input",
                created_at=datetime.now(timezone.utc).isoformat(),
            )
            for item in data.get("items", [])
        ]
        # 知識の重み = 件数 × 0.1kg
        weight = len(items) * 0.1

        return AlchemyResult(
            items=items,
            summary=data.get("summary", ""),
            knowledge_weight=weight,
        )

    except json.JSONDecodeError:
        # フォールバック
        return AlchemyResult(
            items=[
                KnowledgeItem(
                    title="ナレッジ",
                    category="procedure",
                    content=text[:200],
                    source="user_input",
                )
            ],
            summary="テキストからナレッジを抽出しました",
            knowledge_weight=0.1,
        )


async def save_to_rag(result: AlchemyResult) -> bool:
    """抽出したナレッジをRAGに保存"""
    try:
        import os
        from langchain_community.vectorstores import FAISS
        from langchain_huggingface import HuggingFaceEmbeddings
        from langchain.schema import Document

        cache_dir = os.getenv("HF_CACHE_DIR", "/tmp/huggingface")
        embeddings = HuggingFaceEmbeddings(
            model_name="intfloat/multilingual-e5-small",
            cache_folder=cache_dir,
            model_kwargs={"device": "cpu"},
            encode_kwargs={"normalize_embeddings": True},
        )

        docs = [
            Document(
                page_content=f"{item.title}\n{item.content}",
                metadata={
                    "category": item.category,
                    "skill_level": item.skill_level,
                    "tags": ",".join(item.tags),
                    "source": item.source,
                    "type": "company_knowledge",
                },
            )
            for item in result.items
        ]

        vector_dir = "vector_store/company_assets"
        if os.path.exists(vector_dir):
            store = FAISS.load_local(vector_dir, embeddings, allow_dangerous_deserialization=True)
            store.add_documents(docs)
            store.save_local(vector_dir)
        else:
            store = FAISS.from_documents(docs, embeddings)
            os.makedirs(vector_dir, exist_ok=True)
            store.save_local(vector_dir)

        print(f"[ALCHEMY] RAG保存完了: {len(docs)}件")
        return True

    except Exception as e:
        print(f"[ALCHEMY] RAG保存エラー: {e}")
        return False


# =====================================================
# 4. メインエントリーポイント
# =====================================================

async def run_knowledge_alchemist_agent(question: str, session_id: str) -> str:
    """supervisor.py から呼ばれるメインエントリー"""
    result = await extract_knowledge(question)
    await save_to_rag(result)
    return result.to_markdown()
