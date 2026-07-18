# LedgerLens — Build Note

Capstone C·02 (Document Intelligence), IITR-SE-2509 Cohort C.

## What shipped

A deployable document-intelligence service: receipt/invoice image in, schema-validated structured data out, with per-field confidence scores and a human review queue for anything the model isn't sure about.

- **FastAPI pipeline** (`POST /ingest`): upload validation (magic bytes, 10 MB cap) → OpenAI moderation gate → PIL preprocess (resize ≤2048px, base64 data URI) → vision extraction into a Pydantic `InvoiceSchema` → date normalization + arithmetic cross-checks → confidence-threshold routing → PIL provenance watermark → SQLite persistence → Prometheus metrics.
- **Review workflow**: `GET /review` (pending flagged fields), `POST /approve` (apply corrections, drain queue, mark document approved), `GET /documents` (+ per-document watermarked image).
- **Batch mode**: `POST /batch` processes a set of images sequentially and returns a CSV summary (auto-approved / pending_review / blocked / failed per file), with a `throughput_docs_per_minute` gauge.
- **Streamlit UI**: Upload page (extraction table with green/amber confidence badges, provider/model/cost footer), Review page (`st.data_editor` inline corrections beside the source image), Documents page.
- **Observability**: Prometheus histograms/counters/gauges for moderation latency, extraction latency, token cost (USD), docs by outcome, moderation blocks, auto-approvals, review queue depth, throughput; provisioned Grafana dashboard (latency percentiles, cost per doc, auto-approval rate, throughput, queue depth).
- **Delivery**: Dockerfile, docker-compose (API + UI + Prometheus + Grafana), GitHub Actions CI running the full pytest suite before a gated Cloud Run deploy.

## Key decisions

1. **Provider abstraction.** Every vendor-specific decision lives behind one `LLMProvider` interface. OpenAI uses native structured outputs (`response_format=InvoiceSchema`); Groq/Ollama/OpenRouter use JSON mode + `model_validate_json` + a bounded retry loop that feeds the validation error back to the model. Switching vendors is a one-line `.env` change. This goes beyond the brief's core (which asks for GPT-4o) but implements its listed Groq alternative as a first-class option.
2. **Confidence next to each field, flat.** `vendor` + `vendor_confidence` rather than nested `{value, confidence}` objects — flat JSON is far more reliable for weaker JSON-mode models.
3. **Don't trust self-reported confidence.** Arithmetic cross-checks (`subtotal + tax ≈ total`, `Σ line items ≈ subtotal`, 1% tolerance) cap confidence independently of the model, forcing inconsistent numbers into the review queue.
4. **Moderation decoupled from extraction.** Only OpenAI has an image moderation endpoint, so `MODERATION_BACKEND` is independent of `LLM_PROVIDER`; the gate fails closed in production (503) and open in development. `off` is rejected in production by startup config validation.
5. **PII redaction at the sink.** A `logging.Filter` on the root logger scrubs SSNs, emails, phones, and card numbers from every record — no call site can forget. The DB keeps the unredacted extraction (it's the business record); only logs are redacted.
6. **Fail fast on misconfiguration.** `Settings.validate_runtime()` runs in the FastAPI lifespan: missing keys, moderation off in prod, or local storage on Cloud Run (ephemeral filesystem) kill the app at startup with a readable error.

## Core vs stretch

**Core (shipped):** everything in the brief's "Core outcomes" list, all "Sample features to build" including batch mode.
**Not built (stretch, per brief):** visual RAG search over archived invoices, Whisper→TTS voice summary, LangGraph review workflow with `interrupt()`, streaming agent responses, incremental index updates.

## Known limitations

- Extraction quality is untested against real API calls in CI — the 51-test suite runs fully offline via a `FakeProvider` (by design: no keys in CI). Real-image accuracy depends on the chosen vision model.
- Confidence scores are model-self-reported except where arithmetic checks intervene; a calibration study (predicted confidence vs observed accuracy) was out of scope.
- The review UI polls; no live push. The LangGraph `interrupt()` stretch would replace this.
- Cost table rates are point-in-time; verify against current provider pricing pages.
- Vision-capable model names on Groq/OpenRouter change frequently — `EXTRACTION_MODEL` is pure config, verify availability at deploy time.
- SQLite is the dev database; production should use Cloud SQL Postgres (`DATABASE_URL` is pluggable via SQLAlchemy).
