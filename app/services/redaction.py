import logging
import re

# Order matters: CARD before PHONE, or a 16-digit card number gets
# matched by the looser phone pattern first.
PATTERNS = {
    "SSN": re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
    "CARD": re.compile(r"\b(?:\d[ -]?){13,16}\b"),
    "EMAIL": re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.]+\b"),
    "PHONE": re.compile(r"\+?\d[\d\s\-()]{8,}\d"),
}


def redact(text: str) -> str:
    for label, pat in PATTERNS.items():
        text = pat.sub(f"[REDACTED_{label}]", text)
    return text


class RedactionFilter(logging.Filter):
    """Scrubs PII from every log record. Installed on the root logger's
    handlers so NO code path can accidentally log raw PII — enforcement
    at the sink, not at each call site."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = redact(str(record.getMessage()))
        record.args = None
        return True


def install_redaction_filter() -> RedactionFilter:
    f = RedactionFilter()
    root = logging.getLogger()
    root.addFilter(f)
    for handler in root.handlers:
        handler.addFilter(f)
    return f
