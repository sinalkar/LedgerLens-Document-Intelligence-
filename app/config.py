from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Provider selection
    llm_provider: Literal["openai", "groq", "ollama", "openrouter"] = "openai"
    extraction_model: str = "gpt-4o-mini"
    extraction_model_fallback: str = "gpt-4o-mini"

    # Keys / endpoints
    openai_api_key: str | None = None
    groq_api_key: str | None = None
    openrouter_api_key: str | None = None
    ollama_base_url: str = "http://localhost:11434/v1"
    ollama_model: str = "llama3.2-vision"

    # Moderation
    moderation_backend: Literal["openai", "off"] = "openai"
    moderation_block_threshold: float = 0.5

    # Extraction tuning
    review_confidence_threshold: float = 0.75
    max_image_dimension: int = 2048
    extraction_max_retries: int = 2
    extraction_temperature: float = 0.0

    # Storage
    storage_backend: Literal["local", "gcs"] = "local"
    upload_dir: str = "./uploads"
    database_url: str = "sqlite:///./ledgerlens.db"
    gcs_bucket_name: str | None = None

    # Service
    api_host: str = "0.0.0.0"
    api_port: int = 8080
    log_level: str = "INFO"
    environment: Literal["development", "production"] = "development"
    pii_redaction_enabled: bool = True
    metrics_enabled: bool = True

    def validate_runtime(self) -> None:
        """Fail fast at startup, not on first request."""
        if self.llm_provider == "openai" and not self.openai_api_key:
            raise RuntimeError("LLM_PROVIDER=openai but OPENAI_API_KEY is missing")
        if self.llm_provider == "groq" and not self.groq_api_key:
            raise RuntimeError("LLM_PROVIDER=groq but GROQ_API_KEY is missing")
        if self.llm_provider == "openrouter" and not self.openrouter_api_key:
            raise RuntimeError("LLM_PROVIDER=openrouter but OPENROUTER_API_KEY is missing")
        if self.moderation_backend == "openai" and not self.openai_api_key:
            raise RuntimeError("MODERATION_BACKEND=openai requires OPENAI_API_KEY")
        if self.environment == "production" and self.moderation_backend == "off":
            raise RuntimeError("Moderation cannot be off in production")
        if self.environment == "production" and self.storage_backend == "local":
            raise RuntimeError(
                "Cloud Run filesystem is ephemeral — use STORAGE_BACKEND=gcs"
            )
        if self.storage_backend == "gcs" and not self.gcs_bucket_name:
            raise RuntimeError("STORAGE_BACKEND=gcs requires GCS_BUCKET_NAME")


@lru_cache
def get_settings() -> Settings:
    s = Settings()
    s.validate_runtime()
    return s
