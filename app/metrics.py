from prometheus_client import Counter, Gauge, Histogram

MODERATION_LATENCY = Histogram(
    "moderation_latency_seconds", "Moderation gate latency"
)
EXTRACTION_LATENCY = Histogram(
    "extraction_latency_seconds",
    "Vision extraction latency",
    buckets=[0.5, 1, 2, 4, 8, 16, 30],
)
TOKEN_COST = Counter("token_cost_usd_total", "Cumulative LLM spend USD")
DOCS_PROCESSED = Counter(
    "documents_processed_total", "Docs by outcome", ["status"]
)
MODERATION_BLOCKS = Counter(
    "moderation_blocks_total", "Uploads blocked at the gate"
)
AUTO_APPROVALS = Counter("auto_approvals_total", "Docs fully auto-approved")
REVIEW_QUEUE_DEPTH = Gauge("review_queue_depth", "Pending review items")
