# 🧾 LedgerLens — Document Intelligence

Receipt/invoice image → **schema-validated structured data** with **per-field confidence scores** and a **human review queue** for anything the model isn't sure about.

> Design principle: *the system knows what it doesn't know.* Every extracted field carries a confidence score; fields below the threshold are routed to a human instead of silently entering the ledger. Arithmetic cross-checks (`subtotal + tax ≈ total`, `Σ line items ≈ subtotal`) cap confidence independently of the model's self-report.

## Architecture

```
┌─────────────┐     ┌──────────────────────── FastAPI ────────────────────────┐
│  Streamlit  │     │  POST /ingest                                            │
│     UI      │────▶│   1. Moderation gate  (provider-aware, fail-closed)      │
│             │     │   2. PIL pre-process  (resize ≤2048px → base64 data URI) │
│  upload     │◀────│   3. Vision extraction (LLMProvider.extract → schema)    │
│  review     │     │   4. Confidence router (< threshold → review_queue)      │
│  approve    │     │   5. PII redaction     (log filter — before ANY logging) │
└─────────────┘     │   6. Watermark + store (PIL stamp → uploads/ + SQLite)   │
                    │   7. Metrics           (Prometheus counters/histograms)  │
                    │                                                          │
                    │  GET /review · POST /approve · GET /documents            │
                    │  GET /metrics · GET /health                              │
                    └──────────────────────────────────────────────────────────┘
                                  │                        │
                          ┌───────▼───────┐        ┌───────▼────────┐
                          │  LLMProvider  │        │  SQLite / GCS  │
                          │ openai · groq │        │  documents     │
                          │ ollama · rtr  │        │  review_queue  │
                          └───────────────┘        └────────────────┘
```

Every provider-specific decision lives behind one interface (`LLMProvider`). The rest of the app — routing, redaction, storage, metrics — never knows which vendor served the model. Switching vendors is a one-line `.env` edit + restart.

## Provider matrix

| Capability | OpenAI | Groq | Ollama | OpenRouter |
|---|---|---|---|---|
| Vision input | ✅ | ✅ (Llama vision) | ✅ (llama3.2-vision, llava) | ✅ (model-dependent) |
| Structured outputs | ✅ native Pydantic parse | JSON mode + retry | JSON mode + retry | JSON mode + retry |
| Moderation endpoint | ✅ omni-moderation | ❌ | ❌ | ❌ |
| Cost | $$ | free tier | free (local) | varies |

Two consequences:

1. **Structured output strategy is per-provider.** OpenAI gets native `client.beta.chat.completions.parse(response_format=InvoiceSchema)`. Everyone else gets JSON mode + `InvoiceSchema.model_validate_json()` + a bounded retry loop that feeds the validation error back into the prompt. Same schema guarantee at the boundary, different enforcement path.
2. **Moderation is decoupled from extraction.** Only OpenAI has an image moderation endpoint, so `MODERATION_BACKEND` is independent of `LLM_PROVIDER` — Groq for cheap extraction + OpenAI for moderation is a first-class configuration. `MODERATION_BACKEND=off` is dev-only and **rejected in production** by config validation. If the moderation API errors, the gate **fails closed** in production (503) and open in development.

> ⚠️ Vision model availability on Groq/OpenRouter changes frequently — verify current model names in their docs and set `EXTRACTION_MODEL` accordingly.

## Quickstart

```bash
git clone <repo> && cd ledgerlens
cp .env.example .env            # then fill in your key(s)
pip install -r requirements.txt

# API
uvicorn app.main:app --port 8080

# UI (second terminal)
streamlit run ui/streamlit_app.py
```

Or the full local stack (API + UI + Prometheus + Grafana):

```bash
docker compose up --build
# API http://localhost:8080 · UI http://localhost:8501
# Prometheus http://localhost:9090 · Grafana http://localhost:3000 (admin/admin)
```

### Switching providers

```bash
# .env
LLM_PROVIDER=groq                     # openai | groq | ollama | openrouter
EXTRACTION_MODEL=<vision-capable model for that provider>
GROQ_API_KEY=gsk_...
MODERATION_BACKEND=openai             # still OpenAI — needs OPENAI_API_KEY
```

Misconfiguration (missing key, moderation off in prod, local storage on Cloud Run) kills the app **at startup** with a readable error — never on the first request.

## API

| Endpoint | Purpose |
|---|---|
| `POST /ingest` | Upload JPEG/PNG (≤10 MB) → moderation → extraction → routing. Returns doc id, status (`auto_approved` / `pending_review`), extracted schema, flagged fields, cost |
| `POST /batch` | Upload multiple images; processed sequentially through the same pipeline. Returns a CSV summary (status, flagged fields, cost, error per file) |
| `GET /review` | Pending review items (field, extracted value, confidence, image URL) |
| `POST /approve` | Submit corrections for a document; drains its queue and marks it `approved` |
| `GET /documents` | Paginated list of processed documents |
| `GET /documents/{id}` | Full record incl. reviewed values |
| `GET /documents/{id}/image` | Watermarked image (signed GCS URL in prod) |
| `GET /health` | DB ping + active provider + provider health |
| `GET /metrics` | Prometheus scrape |

A moderation block returns **422** with `{"blocked_reason": ...}` and the LLM is never called.

## Safety rails

- **Moderation gate** before any LLM call; fail-closed in production.
- **PII redaction**: a logging `Filter` on the root logger scrubs SSNs, emails, phone numbers, and card numbers from every log record — enforcement at the sink, so no code path can accidentally log raw PII. The DB keeps the unredacted extraction (it's the business record); only logs are redacted.
- **Upload validation** by magic bytes (not filename), 10 MB cap, JPEG/PNG only.
- **Watermarking**: every stored image is stamped with doc id + timestamp for provenance.
- **Arithmetic cross-checks** cap confidence when the numbers don't add up.

## Observability

Prometheus metrics: extraction/moderation latency histograms, cumulative token spend (USD), docs processed by outcome, moderation blocks, auto-approvals, review queue depth. The provisioned Grafana dashboard (`grafana/dashboards/ledgerlens.json`) shows latency percentiles, cost per document, throughput, queue depth, and the headline **auto-approval rate** — the direct measure of human labor saved.

## Tests

```bash
pytest tests/ -v
```

All tests run **without real API calls** via a `FakeProvider` — no keys needed. Coverage: schema contracts, confidence routing boundaries, arithmetic cross-checks, PII redaction + log filter, moderation gate (block / pass / fail-closed / fail-open), watermarking, provider factory, and the JSON-mode retry loop.

## Deployment (GCP Cloud Run)

`.github/workflows/deploy.yml` runs the test suite on every push/PR, and deploys `main` to Cloud Run when the `ENABLE_DEPLOY` repo variable is `true` and `GCP_SA_KEY` / `GCP_PROJECT` / `GCS_BUCKET` secrets are set. Keys live in **GCP Secret Manager** (`--set-secrets`) — never in the image or repo.

Cloud Run's filesystem is **ephemeral**: production requires `STORAGE_BACKEND=gcs` (config validation enforces this) and a persistent `DATABASE_URL` (Cloud SQL Postgres).

## Repository layout

```
app/
├── main.py            # app factory, lifespan (fail-fast config), /health, /metrics
├── config.py          # pydantic-settings + startup validation
├── schemas.py         # InvoiceSchema with per-field confidence
├── providers/         # LLMProvider protocol, OpenAI native + JSON-mode base, factory
├── services/          # moderation, preprocess, router, extraction checks,
│                      # redaction, watermark, cost
├── storage/           # SQLAlchemy models/engine, local vs GCS file store
└── routers/           # /ingest, /review + /approve, /documents
ui/streamlit_app.py    # upload · review · documents pages
tests/                 # 48 tests, zero network calls
```
