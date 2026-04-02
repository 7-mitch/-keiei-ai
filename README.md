# KEIEI-AI — 経営者支援AIシステム

> **ローカルLLM × RAG × マルチエージェントで実現する、完全オンプレ型の経営支援プラットフォーム**

[![Python](https://img.shields.io/badge/Python-3.11-blue?logo=python)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.135-green?logo=fastapi)](https://fastapi.tiangolo.com)
[![Next.js](https://img.shields.io/badge/Next.js-16.2-black?logo=next.js)](https://nextjs.org)
[![LangGraph](https://img.shields.io/badge/LangGraph-1.1-orange)](https://langchain-ai.github.io/langgraph/)
[![Docker](https://img.shields.io/badge/Docker-Compose-blue?logo=docker)](https://docker.com)
[![AWS](https://img.shields.io/badge/AWS-ECS_Fargate-orange?logo=amazon-aws)](https://aws.amazon.com)
[![Security](https://img.shields.io/badge/Security-AIGIS_336-red)](https://github.com/7-mitch/keiei-ai)
[![HuggingFace](https://img.shields.io/badge/HuggingFace-multilingual--e5-yellow)](https://huggingface.co)

---

## 概要

KEIEI-AIは、**社内データをクラウドに送ることなく**、ローカルLLMとRAGを活用して経営者の意思決定を支援するAIシステムです。

- 機密情報をクラウドに出さない**完全オンプレ運用**
- チャット1行で財務・工程・セキュリティ情報を横断検索
- Word・PDF・Excel・PowerPointを自動でベクトルDB化
- **AIGIS 336監査項目**によるLLM攻撃防御を実装
- Docker Composeで**社内サーバーにワンコマンドで展開可能**
- 環境変数1つで**ローカルLLM ⇔ Claude API**を切り替え可能
- **業界別RAG**（介護・医療・建設・製造・法律）に対応
- **HuggingFace類似度ルーター**によるAPIコストゼロのインテント分類

---

## 主要機能

| 機能 | 説明 |
|---|---|
| 💬 **AIチャット** | LangGraph + Ollama（ローカルLLM）によるマルチエージェント対話 |
| 📋 **工程管理** | スケジュール表を入力するとAIが工程表・タスク・リスクを自動生成 |
| 📚 **RAG検索** | 社内規定・手順書・技術文書をベクトル化して自然言語で検索 |
| 🏭 **業界別RAG** | 介護・医療・建設・製造・法律の業界特化ドキュメント検索 |
| 📊 **経営ダッシュボード** | KPI・取引データ・アラートをリアルタイム可視化 |
| 💰 **資金繰り監視** | 月次収支集計・30日予測・インボイス対応アラート自動生成 |
| 🚨 **不正検知** | ルールベース + パターン認識 + LLM + MLの4層構造で不正を検知 |
| 👥 **人事・適性診断** | 適性診断結果の読み込み・強みアドバイス・チームマッチング・学習パス生成 |
| 🔒 **LLM攻撃防御** | Gate1（キーワード）+ Gate2（LLM）+ AIGIS 336監査項目の3層セキュリティ |
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
│  │  🔒 3層セキュリティ検査（入口）          │    │
│  │  Gate1: キーワード検知                  │    │
│  │  Gate2: LLM（Claude Haiku）検査         │    │
│  │  Gate3: AIGIS 336監査項目スコアリング   │    │
│  └──────────────────┬──────────────────────┘    │
│                     ↓                           │
│  ┌─────────────────────────────────────────┐    │
│  │     LangGraph Supervisor（ハイブリッド） │    │
│  │  Step1: 明確キーワード → 即決定          │    │
│  │  Step2: スコアリング → 複数マッチで決定  │    │
│  │  Step3: HuggingFace類似度ルーター        │    │
│  └──┬───┬───┬───┬───┬───┬───┬─────────────┘    │
│     │   │   │   │   │   │   │                  │
│   SQL RAG Fraud Web Proj HR CashFlow            │
└──┬──────┬──────────────────────────────────────┘
   │      │
   ▼      ▼
PostgreSQL  ChromaDB/FAISS  BigQuery  Ollama/Claude
```

---

## マルチエージェント設計
```
ユーザーの質問
    ↓
🔒 3層セキュリティ検査（全ルート共通）
    ↓
Supervisor Agent（ハイブリッドルーティング）
    ├── 「売上は？」「KPIは？」          → SQL Agent
    ├── 「規程を教えて」「安全管理は？」  → RAG Agent（業界別対応）
    ├── 「不正チェック」「アラート」      → Fraud Agent（4層検知）
    ├── 「市場動向は？」                 → Web Agent
    ├── 「工程の進捗は？」               → Project Agent
    ├── 「資金繰りは？」「試算表は？」    → CashFlow Agent
    └── 「評価コメント」「適性診断」      → HR Agent
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

## セキュリティ設計 — 3層構造
```
質問入力
    ↓
Gate 1: キーワード検知（高速・0ms）
   プロンプトインジェクション / 機密情報漏洩 / AIGISリスクスコア
    ↓
Gate 2: LLM検査（高精度）
   Claude Haiku が SAFE / UNSAFE を判定
   多言語・迂回攻撃・Base64エンコード攻撃に対応
    ↓
Gate 3: Confidential Computing（将来実装）
   プロンプトを暗号化したまま推論
   TEE（Trusted Execution Environment）内で処理
    ↓
エージェント実行（問題なしの場合のみ）
```

---

## ハイブリッドルーティング — KI-VI構成
```
質問
 ↓
Step1: 明確キーワード辞書マッチ（複合語・専門用語）→ 0ms・最高信頼
 ↓ マッチしない
Step2: 曖昧キーワードスコアリング（2件以上で決定）
 ↓ スコア不足
Step3: HuggingFace multilingual-e5-small
       コサイン類似度ベース意図分類
       APIコストゼロ・外部送信なし
```

**ルーティング精度: 90%（10問中9問正解・曖昧表現含む）**

---

## 業界別RAG対応
```
docs_data/
├── 介護/      → 介護記録・ケアプラン・介護保険法令
├── 医療/      → カルテ・診療ガイドライン・医療安全
├── 建設/      → 建築基準法・安全管理・点検規程
├── 製造/      → ISO規格・品質基準・設備点検
└── 法律/      → 判例・契約書テンプレート・法令

ドキュメントを追加するだけで業界特化RAGが完成
vector_store/ 配下に英語フォルダ名で自動保存
（日本語パス問題を回避）
```

---

## 適性診断 × 人事エージェント
```
適性診断結果（独創性・俊敏性・継続力など）
    ↓
hr_agent が読み込み
    ├── 強みに合わせたアドバイス生成
    ├── チームマッチング提案
    ├── 個人別3ヶ月ラーニングパス生成
    └── 人事評価コメント自動生成

業種問わず汎用：IT・介護・製造・建設・医療・法律
```

---

## 将来ロードマップ
```
Phase 1（完了）：
LLM + RAG + sklearn + ハイブリッドルーター

Phase 2（次）：
DPOファインチューニング
→ Qwen3-4B × 業界専門用語特化モデル

Phase 3：
マルチモーダル統合
├── 画像 → Vision Transformer
├── ファイル突合 → Document AI
└── テキスト → 既存LLM

Phase 4：
GNN（グラフニューラルネットワーク）統合
├── 取引ネットワーク不正検知
├── 組織図 × 人材最適化
└── サプライチェーンリスク分析 × Confidential Computing
```

---

## LLM環境切り替え

| 環境 | LLM | 用途 |
|---|---|---|
| `development` | Ollama（Qwen3:8b） | ローカル・オンプレ・無料・完全セキュア |
| `production` | Claude API（Sonnet） | クラウド・外部公開・デモ用 |

---

## 技術スタック

### バックエンド
| 技術 | 用途 |
|---|---|
| Python 3.11 / FastAPI | APIサーバー |
| LangGraph | マルチエージェントオーケストレーション |
| Ollama（Qwen3:8b） | ローカルLLM |
| Claude API（Anthropic） | クラウドLLM（本番切り替え用） |
| ChromaDB / FAISS | ベクトルDB（業界別対応） |
| HuggingFace multilingual-e5 | 日本語埋め込み・ルーティング |
| asyncpg / PostgreSQL | データベース |
| Google BigQuery | データウェアハウス |
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
| `POST /api/chat` | AIチャット（3層セキュリティ検査付き） |
| `POST /api/rag/search` | RAG検索（業界別対応） |
| `GET  /api/projects/{id}/tasks` | タスク一覧 |
| `POST /api/projects/{id}/tasks` | タスク追加 |
| `PUT  /api/projects/{id}/tasks/{tid}` | タスク更新 |
| `DELETE /api/projects/{id}/tasks/{tid}` | タスク削除 |
| `GET  /api/projects/{id}/summary` | 進捗サマリー |
| `POST /api/fraud/check` | 不正検知（4層構造） |
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
│   │   │   ├── supervisor.py        # ハイブリッドルーティング + 3層セキュリティ
│   │   │   ├── hf_router.py         # HuggingFace類似度ルーター
│   │   │   ├── rag_agent.py         # RAG検索（業界別 + AIGIS連携）
│   │   │   ├── sql_agent.py         # SQL分析
│   │   │   ├── fraud_agent.py       # 不正検知（4層構造）
│   │   │   ├── fraud_ml_model.py    # MLモデル学習・評価
│   │   │   ├── project_agent.py     # 工程管理
│   │   │   ├── cash_flow_agent.py   # 資金繰り監視・予測
│   │   │   ├── hr_agent.py          # 人事・適性診断・育成
│   │   │   └── web_agent.py         # Web情報収集
│   │   ├── api/
│   │   ├── core/
│   │   │   ├── config.py
│   │   │   └── security.py          # 3層セキュリティ（Gate1+2）
│   │   └── db/
│   ├── docs_data/                   # 業界別ドキュメント
│   │   ├── 介護/
│   │   ├── 医療/
│   │   ├── 建設/
│   │   ├── 製造/
│   │   └── 法律/
│   ├── vector_store/                # FAISSインデックス（業界別）
│   ├── migrations/
│   └── requirements.txt
├── frontend/
├── docker-compose.yml
└── README.md
```

---

## ライセンス

Private — 無断転用・複製を禁じます。