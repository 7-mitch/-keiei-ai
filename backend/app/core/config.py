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
    secret_key:            str = "change-me-in-production"
    algorithm:             str = "HS256"
    access_token_expire:   int = 60

    # CORS
    allowed_origins:       list[str] = ["http://localhost:3000"]

    # 環境
    environment:           str = "development"

    # Redis
    redis_url:             str = "redis://localhost:6379"

    class Config:
        env_file = ".env"

@lru_cache()
def get_settings() -> Settings:
    return Settings()

settings = get_settings()