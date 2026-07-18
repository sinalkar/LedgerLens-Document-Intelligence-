import json
from unittest.mock import MagicMock

import pytest

from app.config import get_settings
from app.providers import (
    GroqProvider,
    OllamaProvider,
    OpenAIProvider,
    OpenRouterProvider,
    get_provider,
)
from app.providers.base import ExtractionFailedError
from app.providers.json_mode import JsonModeProvider
from tests.helpers import make_invoice


def _select(monkeypatch, provider: str, **env):
    monkeypatch.setenv("LLM_PROVIDER", provider)
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    get_settings.cache_clear()
    get_provider.cache_clear()


def test_factory_returns_openai(monkeypatch):
    _select(monkeypatch, "openai")
    assert isinstance(get_provider(), OpenAIProvider)


def test_factory_returns_groq(monkeypatch):
    _select(monkeypatch, "groq", GROQ_API_KEY="gsk_test")
    assert isinstance(get_provider(), GroqProvider)


def test_factory_returns_ollama(monkeypatch):
    _select(monkeypatch, "ollama")
    assert isinstance(get_provider(), OllamaProvider)


def test_factory_returns_openrouter(monkeypatch):
    _select(monkeypatch, "openrouter", OPENROUTER_API_KEY="sk-or-test")
    assert isinstance(get_provider(), OpenRouterProvider)


def test_missing_key_fails_fast(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "groq")
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    get_settings.cache_clear()
    get_provider.cache_clear()
    with pytest.raises(RuntimeError, match="GROQ_API_KEY"):
        get_provider()


def test_moderation_off_rejected_in_production(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("MODERATION_BACKEND", "off")
    monkeypatch.setenv("STORAGE_BACKEND", "gcs")
    monkeypatch.setenv("GCS_BUCKET_NAME", "b")
    get_settings.cache_clear()
    with pytest.raises(RuntimeError, match="Moderation"):
        get_settings()


def test_local_storage_rejected_in_production(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("MODERATION_BACKEND", "openai")
    monkeypatch.setenv("STORAGE_BACKEND", "local")
    get_settings.cache_clear()
    with pytest.raises(RuntimeError, match="ephemeral"):
        get_settings()


def _mock_response(content: str):
    resp = MagicMock()
    resp.usage.prompt_tokens = 100
    resp.usage.completion_tokens = 50
    resp.choices = [MagicMock()]
    resp.choices[0].message.content = content
    return resp


def test_json_mode_retry_recovers_from_one_bad_json():
    provider = JsonModeProvider(
        base_url="http://fake", api_key="fake", model="fake-model",
        temperature=0.0, max_retries=2,
    )
    bad = json.dumps({"vendor": "Acme"})  # missing required fields
    good = make_invoice().model_dump_json()
    provider.client = MagicMock()
    provider.client.chat.completions.create.side_effect = [
        _mock_response(bad),
        _mock_response(good),
    ]
    result = provider.extract_invoice("data:image/png;base64,AAAA")
    assert result.attempts == 2
    assert result.invoice.vendor == "Acme Supplies"
    assert result.prompt_tokens == 200  # both attempts counted


def test_json_mode_exhausted_retries_raises():
    provider = JsonModeProvider(
        base_url="http://fake", api_key="fake", model="fake-model",
        temperature=0.0, max_retries=1,
    )
    bad = json.dumps({"vendor": "Acme"})
    provider.client = MagicMock()
    provider.client.chat.completions.create.side_effect = [
        _mock_response(bad),
        _mock_response(bad),
    ]
    with pytest.raises(ExtractionFailedError):
        provider.extract_invoice("data:image/png;base64,AAAA")
