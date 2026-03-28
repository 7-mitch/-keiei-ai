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
- Docker Compose（ローカル環境）

## 機能一覧
- 💬 AIチャット（LangGraph + Claude）
- 📊 経営ダッシュボード（KPI管理）
- 🚨 不正アラート検知
- 🔍 不正検知（MLモデル）
- 📚 RAG検索（FAISS + BigQuery統合）
- 📝 レポート自動生成
- 🌐 Web情報収集
- 📥 データ収集・DWH同期

---

## エージェント詳細設計

### Supervisor Agent
全エージェントを統括するオーケストレーター。
ユーザーの質問を解析し、最適なエージェントにルーティングする。
```
入力 → Supervisor → ルーティング判定
                ├── "売上は？"      → SQL Agent
                ├── "規程を調べて"  → RAG Agent
                ├── "不正チェック"  → Fraud Agent
                └── "最新ニュース"  → Web Agent
```

### SQL Agent
PostgreSQL（NeonDB）に対してSQLを生成・実行する。
- 取引データの集計
- KPI計算
- 異常値検出

### RAG Agent
FAISSベクトルストアを使った社内文書検索。
- HuggingFace multilingual-e5-largeで埋め込み生成
- コサイン類似度で関連文書を検索
- 検索品質をevaluate_relevanceで評価
```
クエリ → Embedding → FAISS検索 → 関連文書取得 → LLM回答生成
```

### Fraud Agent
多層構造の不正検知システム。
```
取引データ
    ↓
ルールベース検知（閾値・パターン）
    ↓
MLモデル検知（scikit-learn）
    ↓
LLM判定（Claude）
    ↓
総合リスクスコア算出（0.0〜1.0）
    ↓
severity判定（low/medium/high/critical）
```

### Web Agent
Playwright + Tavily を使ったWeb情報収集。
- 金融ニュースの自動収集
- 指定URLのコンテンツ取得
- 収集ログをPostgreSQLに保存

---

## セキュリティ設計

### 認証フロー（JWT）
```
1. POST /api/auth/login
   └── email + password を受け取る

2. bcryptでパスワード検証
   └── checkpw(plain, hashed)

3. JWTトークン生成
   └── payload: { sub, id, role, name, exp }
   └── アルゴリズム: HS256
   └── 有効期限: settings.access_token_expire（分）

4. Bearer tokenとしてリクエストヘッダーに付与
   └── Authorization: Bearer eyJhbG...

5. get_current_user() で毎回検証
   └── 期限切れ・改ざん検知 → 401 Unauthorized
```

### ロールベースアクセス制御（RBAC）
```
executive  → 全機能アクセス可能
manager    → アラート更新・モデル学習可能
operator   → 閲覧のみ
```

### CORS設定
```python
allow_origins = [
    "http://localhost:3000",
    "http://localhost:3001",
    "https://keiei-ai-frontend.vercel.app",
    "https://*.vercel.app",
]
```

### パスワードセキュリティ
- bcrypt（コスト係数12）でハッシュ化
- 元のパスワードは保存しない
- 8文字以上を必須とする（フロントバリデーション）

---

## DB設計（テーブル定義）

### users
```sql
id            SERIAL PRIMARY KEY
name          VARCHAR
email         VARCHAR UNIQUE
password_hash VARCHAR
role          VARCHAR  -- executive / manager / operator
is_active     BOOLEAN DEFAULT true
created_at    TIMESTAMP
```

### accounts
```sql
id         SERIAL PRIMARY KEY
user_id    INTEGER REFERENCES users(id)
balance    NUMERIC
created_at TIMESTAMP
```

### transactions
```sql
id               SERIAL PRIMARY KEY
account_id       INTEGER REFERENCES accounts(id)
amount           NUMERIC
transaction_type VARCHAR  -- debit / credit / transfer
description      VARCHAR
created_at       TIMESTAMP
```

### fraud_alerts
```sql
id             SERIAL PRIMARY KEY
transaction_id INTEGER REFERENCES transactions(id)
alert_type     VARCHAR
severity       VARCHAR  -- low / medium / high / critical
description    VARCHAR
status         VARCHAR  -- open / investigating / resolved / false_positive
created_at     TIMESTAMP
resolved_at    TIMESTAMP
```

### audit_logs
```sql
id            SERIAL PRIMARY KEY
operator_id   INTEGER
operator_type VARCHAR  -- human / ai
target_type   VARCHAR
target_id     INTEGER
action        VARCHAR
before_value  JSONB
after_value   JSONB
created_at    TIMESTAMP
```

### kpi_metrics
```sql
id           SERIAL PRIMARY KEY
metric_name  VARCHAR
metric_value NUMERIC
unit         VARCHAR
period       VARCHAR
created_at   TIMESTAMP
```

### web_collection_logs
```sql
id           SERIAL PRIMARY KEY
url          VARCHAR
status       VARCHAR
data_type    VARCHAR
processed_at TIMESTAMP
```

### reports
```sql
id         SERIAL PRIMARY KEY
title      VARCHAR
content    TEXT
created_at TIMESTAMP
```

---

## CI/CDパイプライン（GitHub Actions）

### 全体フロー
```
git push origin main
    ↓
GitHub Actions トリガー
    ↓
┌─────────────────────────────┐
│ 1. Checkout                 │
│ 2. AWS認証（OIDC）          │
│ 3. ECRログイン              │
│ 4. Dockerイメージビルド     │
│ 5. ECRにpush                │
│ 6. ECS タスク定義更新       │
│ 7. ECS サービス更新         │
│    （ローリングデプロイ）    │
└─────────────────────────────┘
    ↓
ECS Fargate 本番環境に反映
```

### ワークフロー設定（`.github/workflows/deploy.yml`）
```yaml
on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: aws-actions/configure-aws-credentials@v2
      - uses: aws-actions/amazon-ecr-login@v1
      - name: Build & Push
        run: |
          docker build -t $ECR_REGISTRY/$ECR_REPOSITORY:latest .
          docker push $ECR_REGISTRY/$ECR_REPOSITORY:latest
      - name: Deploy to ECS
        run: |
          aws ecs update-service \
            --cluster consul-ai-cluster \
            --service keiei-ai-service \
            --force-new-deployment
```

### シークレット管理
```
GitHub Secrets:
├── AWS_ACCESS_KEY_ID
├── AWS_SECRET_ACCESS_KEY
├── ECR_REGISTRY
└── ECR_REPOSITORY

AWS SSM Parameter Store:
├── ANTHROPIC_API_KEY
├── DATABASE_URL
├── SECRET_KEY
└── LANGCHAIN_API_KEY
```

---

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

## プロジェクト構成
```
keiei-ai/
├── backend/
│   ├── app/
│   │   ├── agents/      # LangGraphエージェント
│   │   │   ├── supervisor.py
│   │   │   ├── rag_agent.py
│   │   │   ├── sql_agent.py
│   │   │   ├── fraud_agent.py
│   │   │   ├── fraud_ml_model.py
│   │   │   └── web_agent.py
│   │   ├── api/         # FastAPIルーター
│   │   │   ├── auth.py
│   │   │   ├── chat.py
│   │   │   ├── alert.py
│   │   │   ├── fraud.py
│   │   │   ├── rag.py
│   │   │   ├── web.py
│   │   │   ├── collect.py
│   │   │   └── report.py
│   │   ├── core/        # 認証・設定
│   │   │   ├── security.py
│   │   │   └── config.py
│   │   └── db/          # DB接続
│   │       ├── connection.py
│   │       └── audit.py
│   ├── docs_data/       # RAG用文書
│   ├── vector_store/    # FAISSインデックス
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── app/         # Next.jsページ
│   │   │   ├── dashboard/
│   │   │   ├── chat/
│   │   │   ├── alerts/
│   │   │   ├── fraud/
│   │   │   ├── rag/
│   │   │   ├── web/
│   │   │   ├── collect/
│   │   │   ├── login/
│   │   │   └── setup/
│   │   ├── components/  # UIコンポーネント
│   │   └── lib/
│   │       └── api.ts   # API関数
│   └── Dockerfile
├── docker-compose.yml
└── README.md
```

## API エンドポイント
- `/api/auth`    認証・ユーザー管理
- `/api/chat`    AIチャット
- `/api/rag`     RAG検索
- `/api/collect` データ収集・DWH同期
- `/api/fraud`   不正検知
- `/api/alert`   アラート管理
- `/api/report`  レポート生成
- `/api/web`     Web情報収集

---

## ローカル起動方法

### 必要環境
- Docker Desktop
- Git

### 起動手順
```bash
# リポジトリをクローン
git clone https://github.com/7-mitch/keiei-ai.git
cd keiei-ai

# 環境変数を設定
cp backend/.env.example backend/.env
# .envを編集してAPIキーを設定

# Docker Composeで一発起動
docker-compose up --build

# ブラウザでアクセス
# フロントエンド: http://localhost:3000
# バックエンドAPI: http://localhost:8000
# Swagger UI:     http://localhost:8000/docs
```

### 初回セットアップ
```
1. http://localhost:3000/setup にアクセス
2. 管理者アカウントを作成
3. http://localhost:3000/login でログイン
```

### 個別起動（開発時）
```bash
# バックエンド
cd backend
pip install -r requirements.txt
python -m uvicorn app.main:app --reload

# フロントエンド
cd frontend
npm install
npm run dev
```

## 環境変数

`backend/.env.example`を参考に設定してください。
```
DATABASE_URL=postgresql://...
SECRET_KEY=your-secret-key
ANTHROPIC_API_KEY=your-api-key
LANGCHAIN_API_KEY=your-langsmith-key
LANGCHAIN_PROJECT=keiei-ai
ENVIRONMENT=development
```

## デプロイ

mainブランチへのpushで自動デプロイ（GitHub Actions）

## URL

- Frontend: https://keiei-ai-frontend.vercel.app
- Backend:  https://api.nvisio-ai.online
- Domain:   https://nvisio-ai.online（設定中）

## ライセンス

Private