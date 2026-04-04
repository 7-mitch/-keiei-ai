from pydantic_settings import BaseSettings
from functools import lru_cache

class Settings(BaseSettings):
    # DB
    database_url: str

    # AI APIキー
    anthropic_api_key: str
    openai_api_key:    str = ""
    tavily_api_key:    str = ""

    # LangSmith
    langchain_api_key:     str = ""
    langchain_tracing_v2:  str = "false"
    langchain_project:     str = "keiei-ai"

    # JWT認証
    secret_key:          str = "change-me-in-production"
    algorithm:           str = "HS256"
    access_token_expire: int = 720

    # CORS
    allowed_origins: list[str] = [
        "http://localhost:3000",
        "http://localhost:3001",
    ]

    # 環境
    # development → Ollama（ローカル・無料・完全オンプレ）
    # production  → Claude API（クラウド・外部公開）
    # vllm        → vLLM（オンプレ高速・GPU必須）
    # qlora       → DPOファインチューニング済みモデル（vLLM経由）
    environment: str = "development"

    # Redis
    redis_url: str = "redis://localhost:6379"

    # GCP
    gcp_project_id:                 str = ""
    bq_dataset_id:                  str = "keiei_ai_dw"
    google_application_credentials: str = ""

    # HuggingFace
    hf_cache_dir: str = "/tmp/huggingface"

    # vLLM設定（ENVIRONMENT=vllm または qlora の場合に使用）
    vllm_base_url:  str = "http://localhost:8001/v1"
    vllm_model:     str = "Qwen/Qwen3-8B"

    # QLoRA/DPOファインチューニング済みモデル
    # ENVIRONMENT=qlora の場合に vllm_model をこちらに切り替える
    qlora_model:    str = "your-hf-username/keiei-ai-qwen3-dpo"

    class Config:
        env_file = ".env"

@lru_cache()
def get_settings() -> Settings:
    return Settings()

settings = get_settings()