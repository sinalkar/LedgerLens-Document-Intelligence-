import io

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.config import get_settings
from app.providers import get_provider
from app.providers.base import ExtractionResult
from app.schemas import InvoiceSchema


@pytest.fixture(autouse=True)
def base_env(tmp_path, monkeypatch):
    """Isolated, valid dev configuration for every test; caches cleared so
    each test sees its own settings/provider."""
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key-not-used")
    monkeypatch.setenv("MODERATION_BACKEND", "off")
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("STORAGE_BACKEND", "local")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path}/test.db")
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path / "uploads"))
    monkeypatch.setenv("REVIEW_CONFIDENCE_THRESHOLD", "0.75")
    get_settings.cache_clear()
    get_provider.cache_clear()
    yield
    get_settings.cache_clear()
    get_provider.cache_clear()


class FakeProvider:
    """Canned extraction results — no network, no keys."""

    name = "fake"

    def __init__(self, invoice: InvoiceSchema | None = None, error: Exception | None = None):
        self.invoice = invoice
        self.error = error
        self.calls = 0

    def extract_invoice(self, image_data_uri: str) -> ExtractionResult:
        self.calls += 1
        if self.error is not None:
            raise self.error
        return ExtractionResult(
            invoice=self.invoice,
            prompt_tokens=1000,
            completion_tokens=200,
            model="fake-model",
            provider=self.name,
            attempts=1,
        )

    def health_check(self) -> bool:
        return True


@pytest.fixture
def make_client():
    from app.main import app

    clients: list[TestClient] = []

    def _make(provider: FakeProvider) -> TestClient:
        app.dependency_overrides[get_provider] = lambda: provider
        client = TestClient(app)
        client.__enter__()  # run lifespan (init_db etc.)
        clients.append(client)
        return client

    yield _make

    for c in clients:
        c.__exit__(None, None, None)
    app.dependency_overrides.clear()


@pytest.fixture
def png_bytes() -> bytes:
    img = Image.new("RGB", (400, 300), "white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()
