# KEIEI-AI — 経営者支援AIシステム

> **ローカルLLM × RAG × マルチエージェントで実現する、完全オンプレ型の経営支援プラットフォーム**

[![Python](https://img.shields.io/badge/Python-3.11-blue?logo=python)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.135-green?logo=fastapi)](https://fastapi.tiangolo.com)
[![Next.js](https://img.shields.io/badge/Next.js-16.2-black?logo=next.js)](https://nextjs.org)
[![LangGraph](https://img.shields.io/badge/LangGraph-1.1-orange)](https://langchain-ai.github.io/langgraph/)
[![Docker](https://img.shields.io/badge/Docker-Compose-blue?logo=docker)](https://docker.com)
[![AWS](https://img.shields.io/badge/AWS-ECS_Fargate-orange?logo=amazon-aws)](https://aws.amazon.com)

---

## 概要

KEIEI-AIは、**社内データをクラウドに送ることなく**、ローカルLLMとRAGを活用して経営者の意思決定を支援するAIシステムです。

- 機密情報をクラウドに出さない**完全オンプレ運用**
- チャット1行で財務・工程・セキュリティ情報を横断検索
- Word・PDF・Excel・PowerPointを自動でベクトルDB化
- Docker Composeで**社内サーバーにワンコマンドで展開可能**

---

## 主要機能

| 機能 | 説明 |
|---|---|
| 💬 **AIチャット** | LangGraph + Ollama（ローカルLLM）によるマルチエージェント対話 |
| 📋 **工程管理** | スケジュール表を入力するとAIが工程表・タスク・リスクを自動生成 |
| 📚 **RAG検索** | 社内規定・手順書・技術文書をベクトル化して自然言語で検索 |
| 📊 **経営ダッシュボード** | KPI・取引データ・アラートをリアルタイム可視化 |
| 🚨 **不正検知** | ルールベース + MLモデル + LLMの三層構造で不正を検知 |
| 🌐 **Web収集** | 市場・競合情報を自動収集してRAGに組み込む |
| 📥 **データ収集** | Zendesk / kintone / AWSからBigQueryにデータを自動同期 |

---

## システムアーキテクチャ

```
┌─────────────────────────────────────────────────┐
│  ユーザー（チャット・ダッシュボード・工程管理）   │
│  Next.js フロントエンド（Vercel / Docker）        │
└────────────────────┬────────────────────────────┘
                     │ HTTPS
┌────────────────────▼────────────────────────────┐
│            FastAPI バックエンド                   │
│         （AWS ECS Fargate / Docker）             │
│                                                  │
│  ┌─────────────────────────────────────────┐    │
│  │          LangGraph Supervisor            │    │
│  │  質問を解析して最適なエージェントへ振分け │    │
│  └──┬──────┬──────┬──────┬───────┬────────┘    │
│     │      │      │      │       │              │
│   SQL    RAG  Fraud  Web  Project               │
│  Agent  Agent Agent Agent  Agent                │
└──┬───────┬──────────────────────────────────────┘
   │       │
   ▼       ▼
PostgreSQL  ChromaDB/FAISS  BigQuery  Ollama(LLM)
```

---

## マルチエージェント設計

```
ユーザーの質問
    ↓
Supervisor Agent（ルーティング判定）
    ├── 「売上は？」「KPIは？」      → SQL Agent     → PostgreSQL
    ├── 「規程を教えて」「手順は？」  → RAG Agent     → ChromaDB / FAISS
    ├── 「不正チェック」「アラート」  → Fraud Agent   → ML Model + LLM
    ├── 「市場動向は？」             → Web Agent     → Playwright
    └── 「工程の進捗は？」           → Project Agent → PostgreSQL（工程DB）
```

### 工程管理エージェント（新機能）

チャットで「このプロジェクトの進捗を教えて」と入力するだけで、
DBのタスクデータをAIが分析して回答します。

```
質問 →「このプロジェクトの進捗を教えて」
         ↓
   Project Agent 起動
         ↓
   PostgreSQL からタスク・メンバー情報取得
         ↓
   AIが分析・コメント生成
         ↓
回答 →「フェーズ2のAPI実装が遅延リスクです。
        全体進捗: 1/5タスク完了（20%）」
```

---

## ドキュメントRAG（多形式対応）

社内のあらゆるドキュメントを自然言語で検索できます。

| 対応形式 | 用途例 |
|---|---|
| `.docx` | 社内規定・契約書・手順書 |
| `.pdf` | 技術仕様書・報告書 |
| `.xlsx` | データ一覧・管理台帳 |
| `.pptx` | 提案資料・研修資料 |
| `.txt` | ログ・メモ |

`docs_ingest/` フォルダにファイルを置くだけで自動インデックス化されます。

---

## 技術スタック

### バックエンド
| 技術 | 用途 |
|---|---|
| Python 3.11 / FastAPI | APIサーバー |
| LangGraph | マルチエージェントオーケストレーション |
| Ollama（Qwen3:8b） | ローカルLLM |
| ChromaDB / FAISS | ベクトルDB |
| HuggingFace multilingual-e5 | 日本語埋め込みモデル |
| asyncpg / PostgreSQL | データベース |
| Google BigQuery | データウェアハウス |
| scikit-learn | 不正検知MLモデル |

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

## セキュリティ設計

### 認証・認可
- **JWT認証**（HS256、有効期限設定）
- **bcrypt**（コスト係数12）によるパスワードハッシュ化
- **RBAC**（ロールベースアクセス制御）

```
executive  → 全機能アクセス可能
manager    → アラート更新・モデル学習可能
operator   → 閲覧のみ
```

### オンプレ運用の安全性
- 社内データは外部クラウドに送信されない
- LLM推論はローカルOllamaで完結
- ベクトルDBも社内サーバー内に保持

---

## ローカル起動

### 必要環境
- Docker Desktop
- Git

### 起動手順

```bash
# クローン
git clone https://github.com/7-mitch/keiei-ai.git
cd keiei-ai

# 環境変数設定
cp backend/.env.example backend/.env
# .env を編集してAPIキーを設定

# 一発起動
docker-compose up --build

# アクセス
# フロントエンド:  http://localhost:3001
# バックエンドAPI: http://localhost:8000
# Swagger UI:     http://localhost:8000/docs（開発環境のみ）
```

### ドキュメントRAGの使い方

```bash
# docs_ingest/ に社内ドキュメントを配置
cp 社内規定.docx backend/docs_ingest/
cp 手順書.pdf    backend/docs_ingest/

# チャットで検索
# 「情報セキュリティのルールを教えて」→ 該当箇所を自動回答
```

---

## APIエンドポイント

| エンドポイント | 機能 |
|---|---|
| `POST /api/auth/login` | ログイン |
| `POST /api/chat` | AIチャット |
| `POST /api/rag/search` | RAG検索 |
| `GET  /api/projects/{id}/tasks` | タスク一覧 |
| `POST /api/projects/{id}/tasks` | タスク追加 |
| `PUT  /api/projects/{id}/tasks/{tid}` | タスク更新 |
| `DELETE /api/projects/{id}/tasks/{tid}` | タスク削除 |
| `GET  /api/projects/{id}/members` | メンバー一覧 |
| `GET  /api/projects/{id}/summary` | 進捗サマリー |
| `POST /api/fraud/check` | 不正検知 |
| `GET  /api/report/kpi` | KPI取得 |

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
│   │   │   ├── supervisor.py        # ルーティング
│   │   │   ├── rag_agent.py         # RAG検索
│   │   │   ├── sql_agent.py         # SQL分析
│   │   │   ├── fraud_agent.py       # 不正検知
│   │   │   ├── project_agent.py     # 工程管理（新規）
│   │   │   └── universal_ingest.py  # 多形式RAG投入（新規）
│   │   ├── api/
│   │   │   ├── chat.py
│   │   │   ├── projects.py          # 工程管理API（新規）
│   │   │   └── ...
│   │   ├── core/
│   │   └── db/
│   ├── docs_ingest/   # ← ここにドキュメントを配置
│   ├── migrations/    # DBマイグレーションSQL
│   └── requirements.txt
├── frontend/
│   └── src/
│       ├── app/
│       │   ├── projects/  # 工程管理画面（新規）
│       │   └── ...
│       └── components/
├── docker-compose.yml
└── README.md
```

---

## ライセンス

Private — 無断転用・複製を禁じます。
