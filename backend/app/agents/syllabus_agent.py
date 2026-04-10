"""
syllabus_agent.py — KEIEI-AI 攻め：eラーニングシラバス自動生成
機能:
  - RAGのナレッジからシラバスを自動生成
  - 初級・中級・上級に分類
  - テスト問題・チェックリスト自動生成
  - 従業員進捗管理
"""
from __future__ import annotations
import json
from dataclasses import dataclass, field
from langchain_core.messages import HumanMessage, SystemMessage
from app.core.llm_factory import get_llm_analysis


@dataclass
class Lesson:
    title: str
    level: str  # beginner / intermediate / advanced
    objectives: list[str]
    content: str
    quiz: list[dict]
    checklist: list[str]


@dataclass
class Syllabus:
    title: str
    description: str
    lessons: list[Lesson] = field(default_factory=list)
    total_time: str = ""

    def to_markdown(self) -> str:
        lines = [
            f"## [教材] {self.title}",
            f"**概要**: {self.description}",
            f"**想定学習時間**: {self.total_time}",
            "",
        ]
        level_label = {"beginner": "[初級] 初級", "intermediate": "[注意] 中級", "advanced": "[緊急] 上級"}
        for i, lesson in enumerate(self.lessons, 1):
            label = level_label.get(lesson.level, lesson.level)
            lines += [
                f"### レッスン{i}：{lesson.title} {label}",
                f"**学習目標**: {', '.join(lesson.objectives)}",
                f"{lesson.content}",
                "",
            ]
            if lesson.checklist:
                lines.append("**チェックリスト**")
                for check in lesson.checklist:
                    lines.append(f"- [ ] {check}")
                lines.append("")

        return "\n".join(lines)


SYLLABUS_PROMPT = """あなたはKEIEI-AIのeラーニングシラバス生成エージェントです。
提供されたナレッジから、実践的な研修シラバスを作成します。

【出力フォーマット（JSON）】
{
  "title": "研修タイトル",
  "description": "研修の概要（50文字以内）",
  "total_time": "想定学習時間",
  "lessons": [
    {
      "title": "レッスンタイトル",
      "level": "beginner|intermediate|advanced",
      "objectives": ["学習目標1", "学習目標2"],
      "content": "レッスン内容（200文字以内）",
      "quiz": [{"question": "問題", "answer": "答え"}],
      "checklist": ["確認項目1", "確認項目2"]
    }
  ]
}

必ずJSONのみを返してください。"""


async def generate_syllabus(knowledge_text: str) -> Syllabus:
    llm = get_llm_analysis()
    response = await llm.ainvoke([
        SystemMessage(content=SYLLABUS_PROMPT),
        HumanMessage(content=f"以下のナレッジからシラバスを作成してください：\n\n{knowledge_text[:3000]}"),
    ])

    import re
    content = str(response.content).strip()
    content = re.sub(r"```json|```", "", content).strip()

    try:
        data = json.loads(content)
        lessons = [
            Lesson(
                title=l.get("title", ""),
                level=l.get("level", "beginner"),
                objectives=l.get("objectives", []),
                content=l.get("content", ""),
                quiz=l.get("quiz", []),
                checklist=l.get("checklist", []),
            )
            for l in data.get("lessons", [])
        ]
        return Syllabus(
            title=data.get("title", "研修プログラム"),
            description=data.get("description", ""),
            lessons=lessons,
            total_time=data.get("total_time", "約2時間"),
        )
    except json.JSONDecodeError:
        return Syllabus(
            title="研修プログラム",
            description="ナレッジベース研修",
            lessons=[
                Lesson(
                    title="基礎知識",
                    level="beginner",
                    objectives=["基本を理解する"],
                    content=knowledge_text[:300],
                    quiz=[],
                    checklist=["内容を理解した"],
                )
            ],
            total_time="約1時間",
        )


async def run_syllabus_agent(question: str, session_id: str) -> str:
    syllabus = await generate_syllabus(question)
    return syllabus.to_markdown()
