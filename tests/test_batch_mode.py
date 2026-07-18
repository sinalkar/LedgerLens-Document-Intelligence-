import csv
import io

from tests.conftest import FakeProvider
from tests.helpers import make_invoice, make_low_confidence_invoice


class CyclingProvider(FakeProvider):
    """Returns a different canned invoice on each call."""

    def __init__(self, invoices):
        super().__init__()
        self.invoices = invoices

    def extract_invoice(self, image_data_uri):
        self.invoice = self.invoices[self.calls % len(self.invoices)]
        return super().extract_invoice(image_data_uri)


def _parse_csv(text: str) -> list[dict]:
    return list(csv.DictReader(io.StringIO(text)))


def test_batch_summarizes_each_document(make_client, png_bytes):
    provider = CyclingProvider([make_invoice(), make_low_confidence_invoice()])
    client = make_client(provider)
    resp = client.post(
        "/batch",
        files=[
            ("files", ("clean.png", png_bytes, "image/png")),
            ("files", ("fuzzy.png", png_bytes, "image/png")),
            ("files", ("garbage.png", b"not an image", "image/png")),
        ],
    )
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/csv")

    rows = {r["filename"]: r for r in _parse_csv(resp.text)}
    assert rows["clean.png"]["status"] == "auto_approved"
    assert rows["clean.png"]["flagged_fields"] == ""
    assert rows["fuzzy.png"]["status"] == "pending_review"
    assert set(rows["fuzzy.png"]["flagged_fields"].split(";")) == {"vendor", "total"}
    assert rows["garbage.png"]["status"] == "failed"
    assert rows["garbage.png"]["doc_id"] == ""
    # one call per valid image; the invalid one never reached the provider
    assert provider.calls == 2


def test_batch_documents_are_persisted(make_client, png_bytes):
    provider = FakeProvider(invoice=make_invoice())
    client = make_client(provider)
    resp = client.post(
        "/batch",
        files=[
            ("files", ("a.png", png_bytes, "image/png")),
            ("files", ("b.png", png_bytes, "image/png")),
        ],
    )
    doc_ids = [r["doc_id"] for r in _parse_csv(resp.text)]
    listed = {d["doc_id"] for d in client.get("/documents").json()}
    assert set(doc_ids) <= listed


def test_throughput_gauge_exposed(make_client, png_bytes):
    provider = FakeProvider(invoice=make_invoice())
    client = make_client(provider)
    client.post("/ingest", files={"file": ("r.png", png_bytes, "image/png")})
    metrics = client.get("/metrics").text
    assert "throughput_docs_per_minute" in metrics
