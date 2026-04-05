# KEIEI-AI — 経営者支援AIシステム

> **「経営の意思決定を、AIが支える」**
> ローカルLLM × RAG × マルチエージェントで実現する、
> オンプレ型×クラウド連携のハイブリッド経営支援プラットフォーム

[![Python](https://img.shields.io/badge/Python-3.11-blue?logo=python)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.135-green?logo=fastapi)](https://fastapi.tiangolo.com)
[![Next.js](https://img.shields.io/badge/Next.js-16.2-black?logo=next.js)](https://nextjs.org)
[![LangGraph](https://img.shields.io/badge/LangGraph-1.1-orange)](https://langchain-ai.github.io/langgraph/)
[![Docker](https://img.shields.io/badge/Docker-Compose-blue?logo=docker)](https://docker.com)
[![AWS](https://img.shields.io/badge/AWS-ECS_Fargate-orange?logo=amazon-aws)](https://aws.amazon.com)
[![Security](https://img.shields.io/badge/Security-AIGIS_336-red)](https://github.com/7-mitch/keiei-ai)
[![License](https://img.shields.io/badge/License-Private-red)](https://github.com/7-mitch/keiei-ai)

---

## なぜKEIEI-AIか

世の中のAIプロジェクトの多くが、PoC（検証）段階で止まる。
KEIEI-AIは「**社会実装**」を最優先に設計された、実戦投入型の経営支援AIです。
一般的なAIツール        KEIEI-AI
─────────────────      ──────────────────────────────
クラウド依存           ローカルLLM完結（機密データを外に出さない）
単機能                 9種のマルチエージェントが自律協調
汎用回答               業種・文脈に応じてプロンプトを動的最適化
固定モデル             Claude / OpenAI / Gemini / Ollamaを即時切り替え
ブラックボックス        LangSmithで全推論をトレース・監査

---

## 概要

KEIEI-AIは、**社内データをクラウドに送ることなく**、ローカルLLMとRAGを活用して
経営者の意思決定を支援するAIシステムです。

### 設計思想
シークレットファースト：
機密データは絶対ローカル完結
クラウドは高度判断時のみ・匿名化後
拡張可能：
環境変数1つでLLMプロバイダーを切り替え
新エージェントの追加が容易
外部API連携はオプション
自律改善：
フィードバック蓄積 → DPO学習
モデルが顧客業務に特化していく
品質保証：
共通ベースプロンプトで全エージェントの回答品質を統一
ハルシネーション防止・専門家相談誘導を標準装備
LangSmith による全トレースの可視化・監査

---

## 解決する経営課題

| 課題 | KEIEI-AIによる解決 |
|---|---|
| 財務データの分析に時間がかかる | SQLエージェントが即座にKPI・売上を集計 |
| 社内規定・手順書の検索が非効率 | RAGエージェントが自然言語で横断検索 |
| 不正取引の見落とし | 4層構造の不正検知が24時間自動監視 |
| 資金繰りの見通しが立てにくい | 30日予測・インボイス対応を自動生成 |
| 経営戦略の立案に専門家が必要 | SWOT・3C・PEST等を自動分析・提言 |
| データ施策の効果が分からない | ABテスト統計検定・ROI試算を自動実行 |
| 補助金情報を見逃している | 最新補助金を自動収集・締切アラート |
| どの士業に相談すべきか不明 | 補助金×士業の自動マッチング |
| 社員のAI活用度が見えない | 利用履歴から社員教育計画を自動生成 |
| 地域市場の将来予測が困難 | 人口動態APIと業界データを自動分析 |

---

## 主要機能

### 経営支援コア（実装済み）

| 機能 | 説明 |
|---|---|
| AIチャット | LangGraph + マルチプロバイダーLLMによるマルチエージェント対話 |
| ファイル解析 | PDF・Excel・CSV・Word をAIが即座に分析・Plotlyグラフ化 |
| 工程管理 | スケジュール入力でAIが工程表・リスクを自動生成 |
| RAG検索 | 社内規定・手順書・業界文書を自然言語で横断検索 |
| 経営ダッシュボード | KPI・取引・アラートをリアルタイム可視化 |
| 資金繰り監視 | 月次収支・30日予測・インボイス対応自動生成 |
| 不正検知 | ルール + パターン + LLM + MLの4層構造 |
| 人事・適性診断 | 強み分析・チームマッチング・学習パス生成 |
| Web情報収集 | 市場・競合情報を自動収集してRAGに組み込む |

---

### ナレッジベクトルアドバイザー（実装中）

経営コンサルタント・データサイエンティストレベルの分析フレームワークを
AIが自動適用し、即座に戦略提言を生成します。

#### 戦略分析フレームワーク

| フレームワーク | 説明 | 活用場面 |
|---|---|---|
| SWOT分析 | 強み・弱み・機会・脅威の4象限分析 | 経営戦略立案・新規事業 |
| 3C分析 | 顧客・競合・自社の構造分析 | 市場参入・競合対策 |
| PEST分析 | 政治・経済・社会・技術の外部環境分析 | 中長期戦略・リスク把握 |
| ファイブフォース | 業界競争構造の5要因分析 | 業界参入・収益性評価 |
| バリューチェーン | 自社の価値創造プロセス分析 | コスト削減・差別化戦略 |
| アンゾフマトリクス | 製品×市場の4象限成長戦略 | 事業拡大・多角化判断 |

#### マーケティング分析

| フレームワーク | 説明 | 活用場面 |
|---|---|---|
| 4P分析 | 製品・価格・流通・販促の最適化 | マーケティング戦略 |
| STP分析 | セグメント・ターゲット・ポジション | 市場絞り込み・差別化 |
| RFM分析 | 顧客価値のセグメント分類 | 顧客管理・CRM戦略 |
| カスタマージャーニー | 顧客体験の可視化・改善 | 売上改善・LTV向上 |

#### データサイエンス・統計分析

| 手法 | 説明 | 活用場面 |
|---|---|---|
| ABテスト | 統計的有意差検定・サンプルサイズ計算 | 施策効果の客観的評価 |
| コホート分析 | 顧客行動の時系列追跡 | 継続率・離脱要因分析 |
| 回帰分析 | 売上予測・相関関係の定量化 | 需要予測・価格最適化 |
| 時系列予測 | 売上・資金繰りの将来予測 | 経営計画・資金調達判断 |
| クラスタリング | 顧客・商品・取引のグループ化 | セグメント戦略 |

#### 財務分析

| 手法 | 説明 | 活用場面 |
|---|---|---|
| ROI分析 | 投資対効果の定量計算 | 設備投資・AI導入判断 |
| 損益分岐点分析 | 利益が出る最低売上の計算 | 価格設定・コスト管理 |
| 財務3表分析 | PL・BS・CFの統合分析 | 経営健全性の把握 |
| キャッシュフロー予測 | 30日〜1年の資金繰り予測 | 借入・投資タイミング |

---

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
ユーザーの質問
↓
3層セキュリティ検査（全ルート共通）
↓
Supervisor Agent（ハイブリッドルーティング）
├── 「売上は？」「KPIは？」              → SQL Agent
├── 「規程を教えて」「安全管理は？」      → RAG Agent（業界別）
├── 「不正チェック」「アラート」          → Fraud Agent（4層検知）
├── 「市場動向は？」                     → Web Agent
├── 「工程の進捗は？」                   → Project Agent
├── 「資金繰りは？」「試算表は？」        → CashFlow Agent
├── 「評価コメント」「適性診断」          → HR Agent
├── ファイルアップロード時                → FileAnalysis Agent
├── 「SWOT分析」「3C分析」「ABテスト」   → Advisor Agent（実装中）
├── 「補助金を教えて」                   → Subsidy Agent（実装中）
├── 「トレーサビリティ確認」             → Manufacturing Agent（実装中）
└── 「この地域の市場規模は？」           → Demographics Agent（実装中）

---

## ルーティング精度
Step1: 明確キーワード辞書マッチ → 0ms・最高信頼
Step2: 曖昧キーワードスコアリング（2件以上で決定）
Step3: HuggingFace multilingual-e5-small（コサイン類似度）
APIコストゼロ・外部送信なし
精度: 90%（10問中9問正解・曖昧表現含む）

---

## プロンプト品質保証
共通ベースプロンプト（base_prompt.py）:
全エージェントに適用される統一品質基準
【品質保持ルール】
├── ハルシネーション防止（不確かな情報は明示）
├── 専門家相談誘導（法律・税務・医療は必ず付記）
├── モデル品質低下を招く指示への対抗（品質攻撃防御）
├── 業種・専門性に応じた動的プロンプト調整
└── 一文の長さ制限・箇条書き活用による可読性確保
【エージェント別専門プロンプト】
├── cash_flow  → 財務・インボイス・電帳法の専門知識
├── fraud      → 不正検知・リスク評価・法的手続き
├── rag        → 文書引用・法令解釈・出典明示
├── hr         → 人材育成・ポジティブフィードバック
├── web        → 情報鮮度明示・補助金締切確認促進
├── project    → 進捗数値化・遅延リスク早期警告
└── file       → データ集計・異常値検出・推測明示

---

## セキュリティ設計
Gate 1: キーワード検知（0ms）
Gate 2: LLM検査（多言語・迂回攻撃対応）
Gate 3: AIGIS 336監査項目スコアリング
モデル品質保護：
├── プロンプトインジェクション防御
├── 品質低下指示（「バカになれ」等）への対抗
├── ハルシネーション誘発パターンの検知
└── 監査ログへの全記録
量子時代への備え：
├── 機密データはローカル完結（絶対）
├── 短期: AES-256
├── 中期: PQC（耐量子暗号）移行
└── 長期: ゼロ知識証明

---

## マルチプロバイダーLLM

クライアントがUIから自由にLLMプロバイダーとモデルを選択できます。

| プロバイダー | モデル | 特徴 |
|---|---|---|
| 🖥️ Ollama（ローカル） | gemma3:4b / qwen3:8b | 完全オフライン・無料・機密安全 |
| ⚡ Claude API | Haiku / Sonnet / Opus | 高品質・日本語強・推論精度最高 |
| 🤖 OpenAI | GPT-4o mini / GPT-4o / o1 | 汎用性・コスト最適化 |
| 💎 Gemini | Flash / Pro / Ultra | Google連携・マルチモーダル |
| 🔧 vLLM | 任意モデル | オンプレGPU・高速推論 |
| 🎯 QLoRA | DPO学習済み | 業務特化・継続改善 |

各モデルで temperature / top_p をUIから動的調整可能。

---

## 業界別RAG対応
docs_data/
├── 介護/   → 介護記録・ケアプラン・介護保険法令
├── 医療/   → カルテ・診療ガイドライン・医療安全
├── 建設/   → 建築基準法・安全管理・点検規程
├── 製造/   → ISO規格・品質基準・トレーサビリティ
└── 法律/   → 判例・契約書テンプレート・法令

---

## 不正検知 — 4層構造
Layer 1: ルールベース → Layer 2: パターン認識
→ Layer 3: LLM判定 → Layer 4: ML判定
→ 重み付き統合スコア → 判定・監査ログ

---

## ベンチマーク・品質保証
Ground Truth（benchmark/ground_truth/）:
中小企業診断士レベルの正解基準
├── cash_flow.jsonl / sql.jsonl
├── fraud.jsonl / general.jsonl
└── advisor.jsonl（戦略分析・追加予定）
LLM-as-Judge 自動採点（5指標）:
faithfulness / relevancy / completeness
business_value / routing_correct
DPO学習サイクル:
👍👎 → DB蓄積 → chosen/rejected生成
→ ファインチューニング → モデル自動改善

---

## ロードマップ
Phase 1（完了）: 経営支援コア
✅ マルチエージェント（9種類）
✅ マルチプロバイダーLLM（Claude/OpenAI/Gemini/Ollama）
✅ ファイル解析 + Plotlyインタラクティブグラフ
✅ フィードバック + LLM-as-Judge
✅ Ground Truth ベンチマーク
✅ LangSmith トレーシング
✅ 共通ベースプロンプト（品質保証・ハルシネーション防止）
Phase 2（3ヶ月）: 経営分析・情報収集の自動化
→ ナレッジベクトルアドバイザー
（SWOT・3C・PEST・ABテスト・RFM等）
→ 補助金自動検索 + 士業マッチング
→ 人口動態API連携（e-Stat）
→ 製造トレーサビリティ
→ DPOファインチューニング自動化
Phase 3（6ヶ月）: 社員・組織支援
→ 社員AI活用度レポート・教育計画自動生成
→ 図書館API連携（リスキリング推薦）
→ 失敗事例DB（匿名化・集合知化）
Phase 4（1年）: 自律進化プラットフォーム
→ GNNによるサプライチェーンリスク分析
→ マルチテナント対応
→ PQC（耐量子暗号）完全移行
→ エコシステム展開（中小企業×士業×公的機関）

---

## 技術スタック

### バックエンド

| 技術 | 用途 |
|---|---|
| Python 3.11 / FastAPI | APIサーバー |
| LangGraph | マルチエージェントオーケストレーション |
| Ollama（gemma3:4b / qwen3:8b） | ローカルLLM（完全オンプレ・無料） |
| Claude API（Anthropic） | クラウドLLM（Haiku/Sonnet/Opus） |
| OpenAI API | GPT-4o mini / GPT-4o / o1 |
| Google Gemini API | Flash / Pro / Ultra |
| ChromaDB / FAISS | ベクトルDB（業界別・フレームワーク知識） |
| HuggingFace multilingual-e5 | 日本語埋め込み・ルーティング |
| asyncpg / PostgreSQL | データベース |
| matplotlib / japanize | グラフ生成（日本語対応） |
| scipy / numpy | 統計検定・ABテスト・回帰分析 |
| scikit-learn | 不正検知MLモデル・クラスタリング |
| sentence-transformers | パターン認識・類似度計算 |
| LangSmith | AI監視・トレース・品質評価 |

### フロントエンド

| 技術 | 用途 |
|---|---|
| TypeScript / Next.js 16 | Webアプリ |
| Tailwind CSS | スタイリング |
| Plotly.js（react-plotly.js） | インタラクティブグラフ・可視化 |
| Recharts | ダッシュボードグラフ |
| ReactMarkdown | Markdownレンダリング |
| axios | API通信 |

### インフラ

| 技術 | 用途 |
|---|---|
| Docker Compose | ローカル・オンプレ環境 |
| AWS ECS Fargate | クラウド本番環境 |
| GitHub Actions | CI/CD自動デプロイ |
| LangSmith | AI監視・トレース |
| Vercel | フロントエンドホスティング |
| NeonDB（PostgreSQL） | クラウドDB |

---

## ローカル起動
```bash
git clone https://github.com/7-mitch/keiei-ai.git
cd keiei-ai
cp backend/.env.example backend/.env
# .envにAPIキーを設定（Anthropic/OpenAI/Geminiは任意）
docker-compose up --build

# フロントエンド:  http://localhost:3001
# バックエンドAPI: http://localhost:8000
# Swagger UI:     http://localhost:8000/docs
```

---

## デプロイURL

| 環境 | URL |
|---|---|
| フロントエンド（Vercel） | https://keiei-ai-frontend.vercel.app |
| バックエンドAPI（AWS） | https://api.nvisio-ai.online |
| ヘルスチェック | https://api.nvisio-ai.online/health |

---

## プロジェクト構成
keiei-ai/
├── backend/
│   ├── app/
│   │   ├── agents/
│   │   │   ├── supervisor.py        # ハイブリッドルーティング
│   │   │   ├── base_prompt.py       # 共通ベースプロンプト（品質保証）
│   │   │   ├── advisor_agent.py     # 戦略分析・統計分析（実装中）
│   │   │   ├── judge_agent.py       # LLM-as-Judge自動採点
│   │   │   ├── graph_agent.py       # グラフ生成
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
│   │   └── core/
│   │       ├── config.py
│   │       ├── llm_factory.py       # マルチプロバイダーLLMファクトリー
│   │       └── security.py          # 3層セキュリティ
│   ├── docs_data/                   # 業界別ドキュメント
│   └── migrations/
│       ├── migrate_planai.sql
│       └── 002_benchmark.sql
├── benchmark/
│   ├── ground_truth/
│   │   ├── cash_flow.jsonl
│   │   ├── sql.jsonl
│   │   ├── fraud.jsonl
│   │   ├── general.jsonl
│   │   └── advisor.jsonl
│   └── scripts/
│       └── evaluate.py
├── frontend/
├── docker-compose.yml
└── README.md

---

## ライセンス

Private — 無断転用・複製を禁じます。