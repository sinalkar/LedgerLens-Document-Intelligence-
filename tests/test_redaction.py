import io
import logging

from app.services.redaction import RedactionFilter, redact


def test_ssn_redacted():
    assert redact("SSN: 123-45-6789 on file") == "SSN: [REDACTED_SSN] on file"


def test_email_redacted():
    assert "[REDACTED_EMAIL]" in redact("contact billing@acme.com today")
    assert "billing@acme.com" not in redact("contact billing@acme.com today")


def test_phone_redacted():
    out = redact("call +1 415 555 0132 now")
    assert "[REDACTED_PHONE]" in out
    assert "415" not in out


def test_card_redacted_as_card_not_phone():
    out = redact("card 4111 1111 1111 1111 charged")
    assert "[REDACTED_CARD]" in out
    assert "4111" not in out


def test_clean_text_untouched():
    text = "Invoice INV-1001 total 100.00 USD from Acme"
    assert redact(text) == text


def test_logging_filter_scrubs_records():
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.addFilter(RedactionFilter())
    logger = logging.getLogger("test.redaction")
    logger.setLevel(logging.INFO)
    logger.addHandler(handler)
    logger.propagate = False
    try:
        logger.info("customer ssn %s email %s", "123-45-6789", "a@b.com")
    finally:
        logger.removeHandler(handler)
    logged = stream.getvalue()
    assert "[REDACTED_SSN]" in logged
    assert "[REDACTED_EMAIL]" in logged
    assert "123-45-6789" not in logged
