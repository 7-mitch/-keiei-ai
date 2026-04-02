"""
llm_factory.py — LLM環境切り替えファクトリー
ENVIRONMENT変数で自動切り替え

development → Ollama（ローカル・無料）
production  → Claude API（クラウド）
vllm        → vLLM（オンプレ高速・GPU）
qlora       → DPOファインチューニング済みモデル（vLLM経由）
"""
import os
from functools import lru_cache
from app.core.config import settings


@lru_cache(maxsize=1)
def get_llm(max_tokens: int = 2048):
    """
    環境変数に応じたLLMインスタンスを返す
    lru_cache で起動時に1回だけ初期化
    """
    env = settings.environment

    if env == "production":
        from langchain_anthropic import ChatAnthropic
        print("[LLM] Claude API（本番モード）")
        return ChatAnthropic(
            model      = "claude-sonnet-4-20250514",
            max_tokens = max_tokens,
            api_key    = settings.anthropic_api_key,
        )

    elif env == "vllm":
        from langchain_openai import ChatOpenAI
        print(f"[LLM] vLLM（{settings.vllm_model}）")
        return ChatOpenAI(
            base_url  = settings.vllm_base_url,
            api_key   = "dummy",  # vLLMはAPIキー不要
            model     = settings.vllm_model,
            max_tokens = max_tokens,
        )

    elif env == "qlora":
        from langchain_openai import ChatOpenAI
        print(f"[LLM] QLoRA/DPOモデル（{settings.qlora_model}）")
        return ChatOpenAI(
            base_url  = settings.vllm_base_url,
            api_key   = "dummy",
            model     = settings.qlora_model,
            max_tokens = max_tokens,
        )

    else:
        from langchain_ollama import ChatOllama
        print("[LLM] Ollama Qwen3（ローカルモード）")
        return ChatOllama(
            model    = "qwen3:8b",
            base_url = "http://host.docker.internal:11434",
        )


def get_llm_light():
    """
    軽量・高速なLLM（セキュリティ検査・ルーティング用）
    本番: Claude Haiku / vLLM: 同じモデル / ローカル: Ollama
    """
    env = settings.environment

    if env == "production":
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(
            model      = "claude-haiku-4-5-20251001",
            max_tokens = 100,
            temperature= 0,
            api_key    = settings.anthropic_api_key,
        )

    elif env in ("vllm", "qlora"):
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            base_url   = settings.vllm_base_url,
            api_key    = "dummy",
            model      = settings.vllm_model,
            max_tokens = 100,
        )

    else:
        from langchain_ollama import ChatOllama
        return ChatOllama(
            model    = "qwen3:8b",
            base_url = "http://host.docker.internal:11434",
        )