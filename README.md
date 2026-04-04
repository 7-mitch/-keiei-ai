# KEIEI-AI — 経営者支援AIシステム

> **「経営の意思決定を、AIが支える」**
> ローカルLLM × RAG × マルチエージェントで実現する、
> 完全オンプレ型の経営支援プラットフォーム

[![Python](https://img.shields.io/badge/Python-3.11-blue?logo=python)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.135-green?logo=fastapi)](https://fastapi.tiangolo.com)
[![Next.js](https://img.shields.io/badge/Next.js-16.2-black?logo=next.js)](https://nextjs.org)
[![LangGraph](https://img.shields.io/badge/LangGraph-1.1-orange)](https://langchain-ai.github.io/langgraph/)
[![Docker](https://img.shields.io/badge/Docker-Compose-blue?logo=docker)](https://docker.com)
[![AWS](https://img.shields.io/badge/AWS-ECS_Fargate-orange?logo=amazon-aws)](https://aws.amazon.com)
[![Security](https://img.shields.io/badge/Security-AIGIS_336-red)](https://github.com/7-mitch/keiei-ai)
[![License](https://img.shields.io/badge/License-Private-red)](https://github.com/7-mitch/keiei-ai)

---

## 概要

KEIEI-AIは、**社内データをクラウドに送ることなく**、ローカルLLMとRAGを活用して
経営者の意思決定を支援するAIシステムです。

### 設計思想

```
シークレットファースト：
  機密データは絶対ローカル完結
  クラウドは高度判断時のみ・匿名化後

拡張可能：
  環境変数1つでLLM切り替え
  新エージェントの追加が容易
  外部API連携はオプション

自律改善：
  フィードバック蓄積 → DPO学習
  モデルが顧客業務に特化していく
```

---

## 解決する経営課題

| 課題 | KEIEI-AIによる解決 |
|---|---|
| 財務データの分析に時間がかかる | SQLエージェントが即座にKPI・売上を集計 |
| 社内規定・手順書の検索が非効率 | RAGエージェントが自然言語で横断検索 |
| 不正取引の見落とし | 4層構造の不正検知が24時間自動監視 |
| 資金繰りの見通しが立てにくい | 30日予測・インボイス対応を自動生成 |
| 補助金情報を見逃している | 最新補助金を自動収集・締切アラート |
| どの士業に相談すべきか不明 | 補助金×士業の自動マッチング |
| 社員のAI活用度が見えない | 利用履歴から社員教育計画を自動生成 |
| 地域市場の将来予測が困難 | 人口動態APIと業界データを自動分析 |

---

## 主要機能

### 経営支援コア（実装済み）

| 機能 | 説明 |
|---|---|
| AIチャット | LangGraph + Ollama によるマルチエージェント対話 |
| ファイル解析 | PDF・Excel・CSV・Word をAIが即座に分析・グラフ化 |
| 工程管理 | スケジュール入力でAIが工程表・リスクを自動生成 |
| RAG検索 | 社内規定・手順書・業界文書を自然言語で横断検索 |
| 経営ダッシュボード | KPI・取引・アラートをリアルタイム可視化 |
| 資金繰り監視 | 月次収支・30日予測・インボイス対応自動生成 |
| 不正検知 | ルール + パターン + LLM + MLの4層構造 |
| 人事・適性診断 | 強み分析・チームマッチング・学習パス生成 |
| Web情報収集 | 市場・競合情報を自動収集してRAGに組み込む |

### 評価・改善機能（実装済み）

| 機能 | 説明 |
|---|---|
| フィードバック | 👍👎ボタンでDPO学習データを自動蓄積 |
| LLM-as-Judge | 回答品質を5指標で自動採点（1〜5点） |
| Ground Truth評価 | 中小企業診断士レベルの正解基準で自動検証 |
| レイテンシ計測 | 全エージェントの応答時間をDBに記録 |
| ベンチマークDB | faithfulness・relevancy・completenessを蓄積 |

### 拡張機能（実装中）

| 機能 | 説明 |
|---|---|
| 補助金自動検索 | e-Stat・中小企業庁・経産省を毎日クロール |
| 士業マッチング | 補助金種別×地域×専門性で最適な士業を紹介 |
| 製造トレーサビリティ | ロット追跡・品質検査・法令対応の自動化 |
| 人口動態分析 | e-Stat APIで地域市場の将来予測を自動生成 |
| 社員AIレポート | 利用頻度・品質スコアから教育計画を自動提案 |
| DPO自動パイプライン | フィードバックデータからモデルを自動改善 |

---

## エージェント設計

```
ユーザーの質問
    ↓
3層セキュリティ検査（全ルート共通）
    ↓
Supervisor Agent（ハイブリッドルーティング）
    ├── 「売上は？」「KPIは？」           → SQL Agent
    ├── 「規程を教えて」「安全管理は？」   → RAG Agent（業界別）
    ├── 「不正チェック」「アラート」       → Fraud Agent（4層検知）
    ├── 「市場動向は？」                  → Web Agent
    ├── 「工程の進捗は？」                → Project Agent
    ├── 「資金繰りは？」「試算表は？」     → CashFlow Agent
    ├── 「評価コメント」「適性診断」       → HR Agent
    ├── ファイルアップロード時             → FileAnalysis Agent
    ├── 「補助金を教えて」                → Subsidy Agent（実装中）
    ├── 「トレーサビリティ確認」          → Manufacturing Agent（実装中）
    └── 「この地域の市場規模は？」        → Demographics Agent（実装中）
```

---

## ルーティング精度

```
Step1: 明確キーワード辞書マッチ（複合語・専門用語）→ 0ms・最高信頼
    ↓ マッチしない
Step2: 曖昧キーワードスコアリング（2件以上で決定）
    ↓ スコア不足
Step3: HuggingFace multilingual-e5-small
       コサイン類似度ベース意図分類
       APIコストゼロ・外部送信なし

精度: 90%（10問中9問正解・曖昧表現含む）
```

---

## セキュリティ設計

```
設計思想：「暗号化に頼りすぎない」
    ↓
データそのものを最小化・分散・匿名化

Gate 1: キーワード検知（0ms）
   プロンプトインジェクション / 機密情報漏洩
    ↓
Gate 2: LLM検査（高精度）
   SAFE / UNSAFE を判定
   多言語・迂回攻撃・Base64エンコード攻撃対応
    ↓
Gate 3: AIGIS 336監査項目スコアリング
    ↓
エージェント実行（問題なしの場合のみ）

量子時代への備え：
├── 機密データはローカル完結（絶対）
├── クラウド送信前に自動匿名化
├── 短期: AES-256
├── 中期: PQC（耐量子暗号）移行
└── 長期: ゼロ知識証明
```

---

## LLM環境切り替え

| 環境変数 | LLM | 用途 |
|---|---|---|
| `development` | Ollama（Qwen3:8b） | ローカル・完全セキュア・無料 |
| `production` | Claude API（Sonnet） | クラウド・外部公開・高品質 |
| `vllm` | vLLM | オンプレ高速推論・GPU必須 |
| `qlora` | DPO学習済みモデル | 業務特化・継続改善 |

---

## 業界別RAG対応

```
docs_data/
├── 介護/      → 介護記録・ケアプラン・介護保険法令
├── 医療/      → カルテ・診療ガイドライン・医療安全
├── 建設/      → 建築基準法・安全管理・点検規程
├── 製造/      → ISO規格・品質基準・設備点検・トレーサビリティ
└── 法律/      → 判例・契約書テンプレート・法令

ドキュメントを追加するだけで業界特化RAGが完成
```

---

## 不正検知 — 4層構造

```
取引データ
    ↓
Layer 1: ルールベース（高額・深夜・疑わしいキーワード）
    ↓
Layer 2: パターン認識（FAISS + sentence-transformers）
    ↓
Layer 3: LLM判定（Claude Sonnet）
    ↓
Layer 4: ML判定（RandomForest / scikit-learn）
    ↓
重み付き統合スコア → 最終判定・DB保存・監査ログ
```

---

## ベンチマーク・品質保証

```
Ground Truth データセット（benchmark/ground_truth/）：
  中小企業診断士レベルの正解基準を定義
    ├── cash_flow.jsonl  資金繰り質問の正解
    ├── sql.jsonl        DB検索質問の正解
    ├── fraud.jsonl      不正検知質問の正解
    └── general.jsonl    一般経営相談の正解

LLM-as-Judge 自動採点（5指標）：
    ├── faithfulness    事実との一致
    ├── relevancy       質問への関連性
    ├── completeness    回答の完全性
    ├── business_value  ビジネス価値
    └── routing_correct ルーティング正誤

DPO学習サイクル：
    👍👎フィードバック → DB蓄積 → chosen/rejected生成
    → DPOファインチューニング → モデル自動改善
```

---

## ロードマップ

```
Phase 1（完了）: 経営支援コア
  ✅ マルチエージェント（9種類）
  ✅ ハイブリッドルーティング
  ✅ ファイル解析 + グラフ生成
  ✅ フィードバック + LLM-as-Judge
  ✅ Ground Truth ベンチマーク
  ✅ セキュリティ3層構造

Phase 2（3ヶ月）: 経営情報の自動収集
  → 補助金自動検索エージェント
    （デジタル化・AI導入補助金 / ものづくり補助金）
  → 士業マッチング機能
  → 人口動態API連携（e-Stat）
  → 製造トレーサビリティエージェント
  → DPOファインチューニング自動化

Phase 3（6ヶ月）: 社員・組織支援
  → 社員AI活用度レポート
  → 教育計画の自動生成
  → 図書館API連携（リスキリング推薦）
  → 失敗事例DBの構築（匿名化・集合知化）

Phase 4（1年）: 自律進化プラットフォーム
  → GNNによるサプライチェーンリスク分析
  → マルチテナント対応（顧客ごとに特化）
  → PQC（耐量子暗号）完全移行
  → エコシステム展開
    （中小企業 × 士業 × 公的機関）
```

---

## システムアーキテクチャ

```
┌─────────────────────────────────────────────────┐
│  Next.js フロントエンド（Vercel / Docker）        │
└────────────────────┬────────────────────────────┘
                     │ HTTPS
┌────────────────────▼────────────────────────────┐
│            FastAPI バックエンド                   │
│         （AWS ECS Fargate / Docker）             │
│                                                  │
│  3層セキュリティ検査                              │
│          ↓                                       │
│  LangGraph Supervisor（ハイブリッドルーティング）  │
│  ├── SQL / RAG / Fraud / Web                     │
│  ├── Project / HR / CashFlow / FileAnalysis      │
│  └── Subsidy / Manufacturing / Demographics      │
│      （実装中）                                   │
└──┬──────┬──────────────────────────────────────┘
   │      │
   ▼      ▼
PostgreSQL  ChromaDB/FAISS  Ollama/Claude  e-Stat API
```

---

## 技術スタック

### バックエンド

| 技術 | 用途 |
|---|---|
| Python 3.11 / FastAPI | APIサーバー |
| LangGraph | マルチエージェントオーケストレーション |
| Ollama（Qwen3:8b） | ローカルLLM（完全オンプレ・無料） |
| Claude API（Anthropic） | クラウドLLM（高度判断時のみ） |
| ChromaDB / FAISS | ベクトルDB（業界別対応） |
| HuggingFace multilingual-e5 | 日本語埋め込み・ルーティング |
| asyncpg / PostgreSQL | データベース |
| matplotlib / japanize | グラフ生成（日本語対応） |
| scikit-learn | 不正検知MLモデル（4層構造） |
| sentence-transformers | パターン認識・類似度計算 |

### フロントエンド

| 技術 | 用途 |
|---|---|
| TypeScript / Next.js 16 | Webアプリ |
| Tailwind CSS | スタイリング |
| Recharts | グラフ・可視化 |
| axios | API通信 |

### インフラ

| 技術 | 用途 |
|---|---|
| Docker Compose | ローカル・オンプレ環境 |
| AWS ECS Fargate | クラウド本番環境 |
| AWS ECR | Dockerイメージ管理 |
| AWS SSM | シークレット管理 |
| GitHub Actions | CI/CD自動デプロイ |
| LangSmith | AI監視・トレース |
| Vercel | フロントエンドホスティング |

---

## ローカル起動

```bash
git clone https://github.com/7-mitch/keiei-ai.git
cd keiei-ai
cp backend/.env.example backend/.env
docker-compose up --build

# フロントエンド:  http://localhost:3001
# バックエンドAPI: http://localhost:8000
# Swagger UI:     http://localhost:8000/docs
```

---

## APIエンドポイント

| エンドポイント | 機能 |
|---|---|
| `POST /api/auth/login` | ログイン |
| `POST /api/chat` | AIチャット（セキュリティ検査付き） |
| `POST /api/chat/upload` | ファイルアップロード・解析 |
| `POST /api/feedback` | フィードバック送信・自動採点 |
| `GET  /api/feedback/stats` | フィードバック統計取得 |
| `POST /api/rag/search` | RAG検索（業界別対応） |
| `GET  /api/report/kpi` | KPI取得 |
| `POST /api/fraud/check` | 不正検知（4層構造） |
| `GET  /api/projects/{id}/summary` | 工程進捗サマリー |
| `GET  /health` | ヘルスチェック |

---

## デプロイURL

| 環境 | URL |
|---|---|
| フロントエンド（Vercel） | https://keiei-ai-frontend.vercel.app |
| バックエンドAPI（AWS） | https://api.nvisio-ai.online |
| ヘルスチェック | https://api.nvisio-ai.online/health |

---

## プロジェクト構成

```
keiei-ai/
├── backend/
│   ├── app/
│   │   ├── agents/
│   │   │   ├── supervisor.py        # ハイブリッドルーティング
│   │   │   ├── hf_router.py         # HuggingFace類似度ルーター
│   │   │   ├── judge_agent.py       # LLM-as-Judge自動採点
│   │   │   ├── graph_agent.py       # グラフ生成（matplotlib）
│   │   │   ├── rag_agent.py         # RAG検索（業界別）
│   │   │   ├── sql_agent.py         # SQL分析
│   │   │   ├── fraud_agent.py       # 不正検知（4層構造）
│   │   │   ├── project_agent.py     # 工程管理
│   │   │   ├── cash_flow_agent.py   # 資金繰り監視
│   │   │   ├── hr_agent.py          # 人事・適性診断
│   │   │   └── web_agent.py         # Web情報収集
│   │   ├── api/
│   │   │   ├── chat.py              # チャット・ファイルアップロード
│   │   │   ├── feedback.py          # フィードバック・ベンチマーク
│   │   │   └── ...
│   │   ├── core/
│   │   │   ├── config.py
│   │   │   └── security.py          # 3層セキュリティ
│   │   └── db/
│   ├── docs_data/                   # 業界別ドキュメント
│   └── migrations/
│       ├── migrate_planai.sql       # 基本スキーマ
│       └── 002_benchmark.sql        # ベンチマークDB
├── benchmark/
│   ├── ground_truth/                # 正解データセット
│   │   ├── cash_flow.jsonl
│   │   ├── sql.jsonl
│   │   ├── fraud.jsonl
│   │   └── general.jsonl
│   └── scripts/
│       └── evaluate.py              # 自動評価スクリプト
├── frontend/
├── docker-compose.yml
└── README.md
```

---

## ライセンス

Private — 無断転用・複製を禁じます。
