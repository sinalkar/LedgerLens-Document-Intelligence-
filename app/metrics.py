import time
from collections import deque

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
THROUGHPUT_DOCS_PER_MINUTE = Gauge(
    "throughput_docs_per_minute", "Documents processed in the last 60 seconds"
)

_recent_docs: deque[float] = deque()


def record_doc_processed() -> None:
    """Rolling one-minute window feeding the throughput gauge."""
    now = time.monotonic()
    _recent_docs.append(now)
    while _recent_docs and now - _recent_docs[0] > 60:
        _recent_docs.popleft()
    THROUGHPUT_DOCS_PER_MINUTE.set(len(_recent_docs))
