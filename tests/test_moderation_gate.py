from unittest.mock import MagicMock

import pytest

from app.config import get_settings
from app.services.moderation import (
    ModerationUnavailableError,
    ModerationVerdict,
    moderate_image,
)
from tests.conftest import FakeProvider
from tests.helpers import make_invoice, make_low_confidence_invoice


def _upload(client, png_bytes):
    return client.post(
        "/ingest", files={"file": ("receipt.png", png_bytes, "image/png")}
    )


def test_blocked_upload_returns_422_and_never_calls_provider(
    make_client, png_bytes, monkeypatch
):
    provider = FakeProvider(invoice=make_invoice())
    client = make_client(provider)
    monkeypatch.setattr(
        "app.routers.ingest.moderate_image",
        lambda uri: ModerationVerdict(False, "blocked: violence", 0.9),
    )
    resp = _upload(client, png_bytes)
    assert resp.status_code == 422
    assert resp.json()["detail"]["blocked_reason"] == "blocked: violence"
    assert provider.calls == 0


def test_allowed_upload_continues_pipeline(make_client, png_bytes, monkeypatch):
    provider = FakeProvider(invoice=make_invoice())
    client = make_client(provider)
    monkeypatch.setattr(
        "app.routers.ingest.moderate_image",
        lambda uri: ModerationVerdict(True, None, 0.01),
    )
    resp = _upload(client, png_bytes)
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "auto_approved"
    assert provider.calls == 1


def test_low_confidence_extraction_lands_in_review(make_client, png_bytes):
    provider = FakeProvider(invoice=make_low_confidence_invoice())
    client = make_client(provider)
    resp = _upload(client, png_bytes)
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "pending_review"
    assert "vendor" in body["flagged_fields"]
    assert "total" in body["flagged_fields"]


def test_moderation_backend_error_fails_closed_in_production(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("MODERATION_BACKEND", "openai")
    monkeypatch.setenv("STORAGE_BACKEND", "gcs")
    monkeypatch.setenv("GCS_BUCKET_NAME", "test-bucket")
    get_settings.cache_clear()

    broken_client = MagicMock()
    broken_client.moderations.create.side_effect = RuntimeError("api down")
    monkeypatch.setattr(
        "app.services.moderation.OpenAI", lambda api_key: broken_client
    )
    with pytest.raises(ModerationUnavailableError):
        moderate_image("data:image/png;base64,AAAA")


def test_moderation_backend_error_fails_open_in_development(monkeypatch):
    monkeypatch.setenv("MODERATION_BACKEND", "openai")
    get_settings.cache_clear()

    broken_client = MagicMock()
    broken_client.moderations.create.side_effect = RuntimeError("api down")
    monkeypatch.setattr(
        "app.services.moderation.OpenAI", lambda api_key: broken_client
    )
    verdict = moderate_image("data:image/png;base64,AAAA")
    assert verdict.allowed is True


def test_moderation_scores_above_threshold_block(monkeypatch):
    monkeypatch.setenv("MODERATION_BACKEND", "openai")
    get_settings.cache_clear()

    mock_client = MagicMock()
    result = MagicMock()
    result.category_scores.model_dump.return_value = {
        "violence": 0.92,
        "self_harm": 0.01,
    }
    mock_client.moderations.create.return_value.results = [result]
    monkeypatch.setattr(
        "app.services.moderation.OpenAI", lambda api_key: mock_client
    )
    verdict = moderate_image("data:image/png;base64,AAAA")
    assert verdict.allowed is False
    assert "violence" in verdict.reason


def test_moderation_error_maps_to_503_at_route(make_client, png_bytes, monkeypatch):
    provider = FakeProvider(invoice=make_invoice())
    client = make_client(provider)

    def _raise(uri):
        raise ModerationUnavailableError("api down")

    monkeypatch.setattr("app.routers.ingest.moderate_image", _raise)
    resp = _upload(client, png_bytes)
    assert resp.status_code == 503
    assert provider.calls == 0


def test_non_image_upload_rejected(make_client, png_bytes):
    provider = FakeProvider(invoice=make_invoice())
    client = make_client(provider)
    resp = client.post(
        "/ingest", files={"file": ("evil.png", b"not an image at all", "image/png")}
    )
    assert resp.status_code == 415
    assert provider.calls == 0
