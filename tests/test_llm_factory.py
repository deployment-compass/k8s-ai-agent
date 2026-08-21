import pytest

from app.config import Settings
from app.llm.factory import PROVIDER_PRESETS, create_llm_client
from app.llm.mock import MockLLMClient
from app.llm.openai_compatible import OpenAICompatibleClient


def _settings(**overrides) -> Settings:
    defaults = {
        "llm_provider": "mock",
        "llm_api_key": "",
        "llm_base_url": "",
        "llm_model": "",
    }
    return Settings(**{**defaults, **overrides})


def test_mock_provider_returns_mock_client():
    client = create_llm_client(_settings(llm_provider="mock"))
    assert isinstance(client, MockLLMClient)


@pytest.mark.parametrize("provider", ["openrouter", "groq", "gemini", "ollama", "openai"])
def test_openai_compatible_providers_use_presets(provider):
    client = create_llm_client(_settings(llm_provider=provider))
    assert isinstance(client, OpenAICompatibleClient)
    assert client.model == PROVIDER_PRESETS[provider]["default_model"]


def test_explicit_base_url_and_model_override_preset():
    client = create_llm_client(
        _settings(
            llm_provider="openrouter",
            llm_api_key="test-key",
            llm_base_url="https://custom.example.com/v1",
            llm_model="custom/model",
        )
    )
    assert client.model == "custom/model"
    assert client._client.base_url.host == "custom.example.com"


def test_unknown_provider_raises():
    with pytest.raises(ValueError, match="Unknown LLM provider"):
        create_llm_client(_settings(llm_provider="nonexistent"))
