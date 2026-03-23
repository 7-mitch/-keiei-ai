# KEIEI-AI 経営者支援AIシステム

## 概要
LangGraph + Claude APIを使った経営者向けAIアシスタント。
財務分析・不正検知・KPI管理を自動化します。

## 技術スタック
### Backend
- Python / FastAPI
- LangGraph（マルチエージェント）
- Claude API（Anthropic）
- PostgreSQL（Neon）

### Frontend
- TypeScript / Next.js
- Vercel（デプロイ）

### Infrastructure
- AWS ECS Fargate（バックエンド）
- AWS ECR（Dockerレジストリ）
- AWS SSM（シークレット管理）
- GitHub Actions（CI/CD）
- LangSmith（AI監視・トレース）

## 機能
- AIチャット（LangGraph + Claude）
- 不正アラート検知
- KPIダッシュボード
- RAG検索
- レポート自動生成
- Web情報収集

## アーキテクチャ
```
Vercel（Frontend）
    ↓ HTTPS
AWS ECS Fargate（Backend: FastAPI）
    ↓
Neon PostgreSQL（DB）
    ↓
LangSmith（監視）
```

## デプロイ
mainブランチへのpushで自動デプロイ（GitHub Actions）

## URL
- Frontend: https://keiei-ai-frontend.vercel.app
- Domain: https://nvisio-ai.online（設定中）