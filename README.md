# KEIEI-AI 経営者支援AIシステム

## 概要
LangGraph + Claude APIを使った経営者向けAIアシスタント。
財務分析・不正検知・KPI管理を自動化します。
Zendesk/kintone等の外部データをBigQueryに集約し、RAGで活用します。

## 技術スタック
### Backend
- Python / FastAPI
- LangGraph（マルチエージェント）
- Claude API（Anthropic）
- PostgreSQL（Neon）
- Google BigQuery（DWH）
- FAISS（ベクトル検索）
- HuggingFace Embeddings（multilingual-e5-large）

### Frontend
- TypeScript / Next.js
- Vercel（デプロイ）

### Infrastructure
- AWS ECS Fargate（バックエンド）
- AWS ECR（Dockerレジストリ）
- AWS SSM（シークレット管理）
- GitHub Actions（CI/CD）
- LangSmith（AI監視・トレース）
- Ollama（ローカルLLM対応予定）

## 機能
- AIチャット（LangGraph + Claude）
- 不正アラート検知
- KPIダッシュボード
- RAG検索（FAISS + BigQuery統合）
- レポート自動生成
- Web情報収集
- データ収集・DWH同期（Zendesk/kintone/AWS）

## アーキテクチャ
```
Vercel（Frontend: Next.js）
    ↓ HTTPS
AWS ECS Fargate（Backend: FastAPI + LangGraph）
    ↓
Neon PostgreSQL（トランザクションDB）
    ↓
Google BigQuery（DWH・分析）
    ↓
FAISS + BigQuery（RAG統合検索）
    ↓
LangSmith（監視・トレース）
```

## データフロー
```
Zendesk / kintone / AWS
    ↓
FastAPI（data_collector）
    ↓
BigQuery（DWH）
    ↓
RAGエージェント（FAISS + BigQuery統合検索）
    ↓
AIチャット応答
```

## API エンドポイント
- `/api/auth` 認証
- `/api/chat` AIチャット
- `/api/rag` RAG検索
- `/api/collect` データ収集・DWH同期
- `/api/fraud` 不正検知
- `/api/alert` アラート管理
- `/api/report` レポート生成
- `/api/web` Web情報収集

## デプロイ
mainブランチへのpushで自動デプロイ（GitHub Actions）

## URL
- Frontend: https://keiei-ai-frontend.vercel.app
- Domain: https://nvisio-ai.online（設定中）

## ローカル開発
```bash
cd backend
pip install -r requirements.txt
python -m uvicorn app.main:app --reload
```

起動後: http://localhost:8000/docs でSwagger UIを確認できます