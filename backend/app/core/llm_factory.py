"""
llm_factory.py — LLM環境切り替えファクトリー
ENVIRONMENT変数で自動切り替え

development → Ollama（ローカル・無料）
production  → Claude API（クラウド）
vllm        → vLLM（オンプレ高速・GPU）
qlora       → DPOファインチューニング済みモデル（vLLM経由）

モード別モデル・パラメータ：
  標準モード     → gemma3:4b  temperature=0.7
  詳細分析モード → gemma3:4b  temperature=0.3
  推論モード     → qwen3:8b   temperature=0.1
  専門家モード   → qwen3:8b   temperature=0.0
"""
from functools import lru_cache
from app.core.config import settings

# ===== ローカルモデル設定 =====
LOCAL_MODEL_FAST = "gemma3:4b"  # 標準・詳細分析（高速）
LOCAL_MODEL_DEEP = "qwen3:8b"   # 推論・専門家（高精度）

# ===== パラメータ設定 =====
# temperature: 高い→創造的・低い→正確
# top_p:       高い→多様→低い→集中
# repeat_penalty: 繰り返し抑制（1.0=無効・1.1=軽度抑制）

PARAMS = {
    "standard": {          # 標準モード：自然な会話
        "temperature":    0.7,
        "top_p":          0.9,
        "repeat_penalty": 1.1,
    },
    "analysis": {          # 詳細分析モード：バランス
        "temperature":    0.3,
        "top_p":          0.8,
        "repeat_penalty": 1.1,
    },
    "reasoning": {         # 推論モード：高精度
        "temperature":    0.1,
        "top_p":          0.7,
        "repeat_penalty": 1.05,
    },
    "expert": {            # 専門家モード：最高精度
        "temperature":    0.0,
        "top_p":          0.5,
        "repeat_penalty": 1.0,
    },
}


@lru_cache(maxsize=1)
def get_llm(max_tokens: int = 2048):
    """標準モード用LLM（gemma3:4b・temperature=0.7）"""
    env = settings.environment

    if env == "production":
        from langchain_anthropic import ChatAnthropic
        print("[LLM] Claude API（標準モード）")
        return ChatAnthropic(
            model       = "claude-sonnet-4-20250514",
            max_tokens  = max_tokens,
            temperature = PARAMS["standard"]["temperature"],
            api_key     = settings.anthropic_api_key,
        )

    elif env == "vllm":
        from langchain_openai import ChatOpenAI
        print(f"[LLM] vLLM（{settings.vllm_model}）")
        return ChatOpenAI(
            base_url    = settings.vllm_base_url,
            api_key     = "dummy",
            model       = settings.vllm_model,
            max_tokens  = max_tokens,
            temperature = PARAMS["standard"]["temperature"],
        )

    elif env == "qlora":
        from langchain_openai import ChatOpenAI
        print(f"[LLM] QLoRA/DPOモデル（{settings.qlora_model}）")
        return ChatOpenAI(
            base_url    = settings.vllm_base_url,
            api_key     = "dummy",
            model       = settings.qlora_model,
            max_tokens  = max_tokens,
            temperature = PARAMS["standard"]["temperature"],
        )

    else:
        from langchain_ollama import ChatOllama
        p = PARAMS["standard"]
        print(f"[LLM] Ollama {LOCAL_MODEL_FAST}（標準モード temp={p['temperature']}）")
        return ChatOllama(
            model          = LOCAL_MODEL_FAST,
            base_url       = "http://ollama:11434",
            temperature    = p["temperature"],
            top_p          = p["top_p"],
            repeat_penalty = p["repeat_penalty"],
        )


def get_llm_analysis(max_tokens: int = 2048):
    """詳細分析モード用LLM（gemma3:4b・temperature=0.3）"""
    env = settings.environment

    if env == "production":
        from langchain_anthropic import ChatAnthropic
        print("[LLM] Claude API（詳細分析モード）")
        return ChatAnthropic(
            model       = "claude-sonnet-4-20250514",
            max_tokens  = max_tokens,
            temperature = PARAMS["analysis"]["temperature"],
            api_key     = settings.anthropic_api_key,
        )

    elif env in ("vllm", "qlora"):
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            base_url    = settings.vllm_base_url,
            api_key     = "dummy",
            model       = settings.vllm_model,
            max_tokens  = max_tokens,
            temperature = PARAMS["analysis"]["temperature"],
        )

    else:
        from langchain_ollama import ChatOllama
        p = PARAMS["analysis"]
        print(f"[LLM] Ollama {LOCAL_MODEL_FAST}（詳細分析モード temp={p['temperature']}）")
        return ChatOllama(
            model          = LOCAL_MODEL_FAST,
            base_url       = "http://ollama:11434",
            temperature    = p["temperature"],
            top_p          = p["top_p"],
            repeat_penalty = p["repeat_penalty"],
        )


def get_llm_deep(max_tokens: int = 4096):
    """推論モード用LLM（qwen3:8b・temperature=0.1）"""
    env = settings.environment

    if env == "production":
        from langchain_anthropic import ChatAnthropic
        print("[LLM] Claude API（推論モード）")
        return ChatAnthropic(
            model       = "claude-sonnet-4-20250514",
            max_tokens  = max_tokens,
            temperature = PARAMS["reasoning"]["temperature"],
            api_key     = settings.anthropic_api_key,
        )

    elif env in ("vllm", "qlora"):
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            base_url    = settings.vllm_base_url,
            api_key     = "dummy",
            model       = settings.vllm_model,
            max_tokens  = max_tokens,
            temperature = PARAMS["reasoning"]["temperature"],
        )

    else:
        from langchain_ollama import ChatOllama
        p = PARAMS["reasoning"]
        print(f"[LLM] Ollama {LOCAL_MODEL_DEEP}（推論モード temp={p['temperature']}）")
        return ChatOllama(
            model          = LOCAL_MODEL_DEEP,
            base_url       = "http://ollama:11434",
            temperature    = p["temperature"],
            top_p          = p["top_p"],
            repeat_penalty = p["repeat_penalty"],
        )


def get_llm_expert(max_tokens: int = 4096):
    """専門家モード用LLM（qwen3:8b・temperature=0.0）"""
    env = settings.environment

    if env == "production":
        from langchain_anthropic import ChatAnthropic
        print("[LLM] Claude API（専門家モード）")
        return ChatAnthropic(
            model       = "claude-sonnet-4-20250514",
            max_tokens  = max_tokens,
            temperature = PARAMS["expert"]["temperature"],
            api_key     = settings.anthropic_api_key,
        )

    elif env in ("vllm", "qlora"):
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            base_url    = settings.vllm_base_url,
            api_key     = "dummy",
            model       = settings.vllm_model,
            max_tokens  = max_tokens,
            temperature = PARAMS["expert"]["temperature"],
        )

    else:
        from langchain_ollama import ChatOllama
        p = PARAMS["expert"]
        print(f"[LLM] Ollama {LOCAL_MODEL_DEEP}（専門家モード temp={p['temperature']}）")
        return ChatOllama(
            model          = LOCAL_MODEL_DEEP,
            base_url       = "http://ollama:11434",
            temperature    = p["temperature"],
            top_p          = p["top_p"],
            repeat_penalty = p["repeat_penalty"],
        )


def get_llm_light():
    """セキュリティ検査用軽量LLM（temperature=0固定）"""
    env = settings.environment

    if env == "production":
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(
            model       = "claude-haiku-4-5-20251001",
            max_tokens  = 100,
            temperature = 0,
            api_key     = settings.anthropic_api_key,
        )

    elif env in ("vllm", "qlora"):
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            base_url    = settings.vllm_base_url,
            api_key     = "dummy",
            model       = settings.vllm_model,
            max_tokens  = 100,
            temperature = 0,
        )

    else:
        from langchain_ollama import ChatOllama
        return ChatOllama(
            model       = LOCAL_MODEL_FAST,
            base_url    = "http://ollama:11434",
            temperature = 0,
        )