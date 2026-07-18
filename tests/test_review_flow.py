from tests.conftest import FakeProvider
from tests.helpers import make_low_confidence_invoice


def test_full_review_and_approve_flow(make_client, png_bytes):
    provider = FakeProvider(invoice=make_low_confidence_invoice())
    client = make_client(provider)

    # Ingest a document whose vendor + total confidence are below threshold
    resp = client.post(
        "/ingest", files={"file": ("receipt.png", png_bytes, "image/png")}
    )
    assert resp.status_code == 200
    body = resp.json()
    doc_id = body["doc_id"]
    assert body["status"] == "pending_review"
    assert set(body["flagged_fields"]) == {"vendor", "total"}

    # Flagged fields are now in the review queue
    queue = client.get("/review").json()
    doc_items = [i for i in queue if i["doc_id"] == doc_id]
    assert {i["field_name"] for i in doc_items} == {"vendor", "total"}
    assert all(i["image_url"].endswith("/image") for i in doc_items)

    # Approve with a correction for vendor; total accepted as-is
    resp = client.post(
        "/approve",
        json={"doc_id": doc_id, "corrections": {"vendor": "Acme Corp Ltd"}},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "approved"
    assert resp.json()["remaining_pending"] == 0

    # Document reflects the corrected record and queue is drained
    doc = client.get(f"/documents/{doc_id}").json()
    assert doc["status"] == "approved"
    assert doc["reviewed"]["vendor"] == "Acme Corp Ltd"
    assert [i for i in client.get("/review").json() if i["doc_id"] == doc_id] == []

    # The watermarked image is retrievable
    img = client.get(f"/documents/{doc_id}/image")
    assert img.status_code == 200
    assert img.headers["content-type"] == "image/png"


def test_numeric_correction_coerced(make_client, png_bytes):
    provider = FakeProvider(invoice=make_low_confidence_invoice())
    client = make_client(provider)
    doc_id = client.post(
        "/ingest", files={"file": ("r.png", png_bytes, "image/png")}
    ).json()["doc_id"]

    resp = client.post(
        "/approve", json={"doc_id": doc_id, "corrections": {"total": "123.45"}}
    )
    assert resp.status_code == 200
    doc = client.get(f"/documents/{doc_id}").json()
    assert doc["reviewed"]["total"] == 123.45


def test_health_endpoint(make_client, png_bytes):
    provider = FakeProvider(invoice=make_low_confidence_invoice())
    client = make_client(provider)
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["database"] == "ok"


def test_metrics_endpoint(make_client):
    provider = FakeProvider()
    client = make_client(provider)
    resp = client.get("/metrics")
    assert resp.status_code == 200
    assert b"documents_processed_total" in resp.content
