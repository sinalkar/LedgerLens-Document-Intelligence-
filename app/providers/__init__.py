from functools import lru_cache

from app.config import get_settings
from app.providers.base import ExtractionFailedError, ExtractionResult, LLMProvider
from app.providers.groq_provider import GroqProvider
from app.providers.ollama_provider import OllamaProvider
from app.providers.openai_provider import OpenAIProvider
from app.providers.openrouter_provider import OpenRouterProvider

__all__ = [
    "ExtractionFailedError",
    "ExtractionResult",
    "LLMProvider",
    "GroqProvider",
    "OllamaProvider",
    "OpenAIProvider",
    "OpenRouterProvider",
    "get_provider",
]


@lru_cache
def get_provider() -> LLMProvider:
    s = get_settings()
    if s.llm_provider == "openai":
        return OpenAIProvider(
            s.openai_api_key, s.extraction_model, s.extraction_temperature
        )
    if s.llm_provider == "groq":
        return GroqProvider(
            GroqProvider.BASE_URL,
            s.groq_api_key,
            s.extraction_model,
            s.extraction_temperature,
            s.extraction_max_retries,
        )
    if s.llm_provider == "ollama":
        return OllamaProvider(
            s.ollama_base_url,
            "ollama",
            s.ollama_model,
            s.extraction_temperature,
            s.extraction_max_retries,
        )
    if s.llm_provider == "openrouter":
        return OpenRouterProvider(
            OpenRouterProvider.BASE_URL,
            s.openrouter_api_key,
            s.extraction_model,
            s.extraction_temperature,
            s.extraction_max_retries,
        )
    raise ValueError(f"Unknown provider {s.llm_provider}")
