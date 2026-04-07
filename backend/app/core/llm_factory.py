"""
llm_factory.py — LLM環境切り替えファクトリー
ENVIRONMENT変数で自動切り替え

development → Ollama（ローカル・無料）
production  → Claude API（クラウド）
openai      → OpenAI API
gemini      → Google Gemini API
vllm        → vLLM（オンプレ高速・GPU）
qlora       → DPOファインチューニング済みモデル（vLLM経由）
"""
from functools import lru_cache
from app.core.config import settings

LOCAL_MODEL_FAST = "gemma3:4b"
LOCAL_MODEL_DEEP = "qwen3:8b"

CLAUDE_MODELS = {
    "haiku":  "claude-haiku-4-5-20251001",
    "sonnet": "claude-sonnet-4-6",
    "opus":   "claude-opus-4-6",
}
OPENAI_MODELS = {
    "mini":  "gpt-4o-mini",
    "gpt4o": "gpt-4o",
    "o1":    "o1-preview",
}
GEMINI_MODELS = {
    "flash": "gemini-2.0-flash",
    "pro":   "gemini-1.5-pro",
    "ultra": "gemini-1.5-ultra",
}

PARAMS = {
    "standard":  {"temperature": 0.7, "top_p": 0.9,  "repeat_penalty": 1.1},
    "analysis":  {"temperature": 0.3, "top_p": 0.8,  "repeat_penalty": 1.1},
    "reasoning": {"temperature": 0.1, "top_p": 0.7,  "repeat_penalty": 1.05},
    "expert":    {"temperature": 0.0, "top_p": 0.5,  "repeat_penalty": 1.0},
}


def _get_claude(model_key="sonnet", temperature=0.7, max_tokens=2048):
    from langchain_anthropic import ChatAnthropic
    model = CLAUDE_MODELS.get(model_key, CLAUDE_MODELS["sonnet"])
    print(f"[LLM] Claude API ({model}) temp={temperature}")
    return ChatAnthropic(model=model, max_tokens=max_tokens, temperature=temperature, api_key=settings.anthropic_api_key)


def _get_openai(model_key="gpt4o", temperature=0.7, max_tokens=2048):
    from langchain_openai import ChatOpenAI
    model = OPENAI_MODELS.get(model_key, OPENAI_MODELS["gpt4o"])
    print(f"[LLM] OpenAI ({model}) temp={temperature}")
    return ChatOpenAI(model=model, max_tokens=max_tokens, temperature=temperature, api_key=settings.openai_api_key)


def _get_gemini(model_key="pro", temperature=0.7, max_tokens=2048):
    from langchain_google_genai import ChatGoogleGenerativeAI
    model = GEMINI_MODELS.get(model_key, GEMINI_MODELS["pro"])
    print(f"[LLM] Gemini ({model}) temp={temperature}")
    return ChatGoogleGenerativeAI(model=model, max_output_tokens=max_tokens, temperature=temperature, google_api_key=settings.gemini_api_key)


def _get_ollama(model=None, temperature=0.7, top_p=0.9):
    from langchain_ollama import ChatOllama
    m = model or LOCAL_MODEL_FAST
    print(f"[LLM] Ollama ({m}) temp={temperature}")
    return ChatOllama(model=m, base_url="http://localhost:11434", temperature=temperature, top_p=top_p, repeat_penalty=1.1)


def get_llm_dynamic(provider=None, model_key=None, temperature=None, top_p=None, max_tokens=2048):
    """動的LLM取得（フロントエンドからのパラメータ対応）"""
    env  = provider or settings.environment
    temp = temperature if temperature is not None else PARAMS["standard"]["temperature"]
    tp   = top_p      if top_p      is not None else PARAMS["standard"]["top_p"]

    if env == "production":
        return _get_claude(model_key or "sonnet", temp, max_tokens)
    elif env == "openai":
        return _get_openai(model_key or "gpt4o", temp, max_tokens)
    elif env == "gemini":
        return _get_gemini(model_key or "pro", temp, max_tokens)
    elif env in ("vllm", "qlora"):
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(base_url=settings.vllm_base_url, api_key="dummy", model=settings.vllm_model, max_tokens=max_tokens, temperature=temp)
    else:
        return _get_ollama(LOCAL_MODEL_FAST, temp, tp)


@lru_cache(maxsize=1)
def get_llm(max_tokens: int = 2048):
    return get_llm_dynamic(max_tokens=max_tokens)


def get_llm_analysis(max_tokens: int = 2048):
    p = PARAMS["analysis"]
    return get_llm_dynamic(temperature=p["temperature"], top_p=p["top_p"], max_tokens=max_tokens)


def get_llm_deep(max_tokens: int = 4096):
    p = PARAMS["reasoning"]
    return get_llm_dynamic(temperature=p["temperature"], top_p=p["top_p"], max_tokens=max_tokens)


def get_llm_expert(max_tokens: int = 4096):
    p = PARAMS["expert"]
    return get_llm_dynamic(temperature=p["temperature"], top_p=p["top_p"], max_tokens=max_tokens)


def get_llm_light():
    env = settings.environment
    if env == "production":
        return _get_claude("haiku", 0.0, 100)
    elif env == "openai":
        return _get_openai("mini", 0.0, 100)
    elif env == "gemini":
        return _get_gemini("flash", 0.0, 100)
    elif env in ("vllm", "qlora"):
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(base_url=settings.vllm_base_url, api_key="dummy", model=settings.vllm_model, max_tokens=100, temperature=0)
    else:
        return _get_ollama(LOCAL_MODEL_FAST, 0.0, 1.0)
