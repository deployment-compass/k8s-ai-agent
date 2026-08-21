from app.config import Settings
from app.llm.base import BaseLLMClient
from app.llm.mock import MockLLMClient
from app.llm.openai_compatible import OpenAICompatibleClient

PROVIDER_PRESETS: dict[str, dict[str, str]] = {
    "openrouter": {
        "base_url": "https://openrouter.ai/api/v1",
        "default_model": "deepseek/deepseek-r1:free",
    },
    "groq": {
        "base_url": "https://api.groq.com/openai/v1",
        "default_model": "llama-3.3-70b-versatile",
    },
    "gemini": {
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
        "default_model": "gemini-2.5-flash",
    },
    "ollama": {
        "base_url": "http://localhost:11434/v1",
        "default_model": "llama3.1",
    },
    "openai": {
        "base_url": "https://api.openai.com/v1",
        "default_model": "gpt-4o-mini",
    },
}


def create_llm_client(settings: Settings) -> BaseLLMClient:
    """Select the LLM backend from configuration.

    Explicit LLM_BASE_URL / LLM_MODEL values override the presets.
    """
    provider = settings.llm_provider.strip().lower()

    if provider == "mock":
        return MockLLMClient()

    if provider not in PROVIDER_PRESETS:
        known = ", ".join(["mock", *PROVIDER_PRESETS])
        raise ValueError(f"Unknown LLM provider '{provider}'. Known providers: {known}")

    preset = PROVIDER_PRESETS[provider]
    return OpenAICompatibleClient(
        base_url=settings.llm_base_url or preset["base_url"],
        api_key=settings.llm_api_key,
        model=settings.llm_model or preset["default_model"],
        temperature=settings.llm_temperature,
        timeout_seconds=settings.llm_timeout_seconds,
        max_retries=settings.llm_max_retries,
    )
