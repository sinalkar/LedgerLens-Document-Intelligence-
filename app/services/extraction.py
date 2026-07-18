from dateutil import parser as date_parser

from app.schemas import InvoiceSchema

# Relative tolerance for arithmetic cross-checks (1%)
_TOLERANCE = 0.01

# Confidence assigned to a date the model returned but we couldn't parse
_UNPARSEABLE_DATE_CONFIDENCE = 0.3


def normalize_date(invoice: InvoiceSchema) -> InvoiceSchema:
    """Vision models emit many date formats; normalize to ISO 8601 in a
    post-step so a weird format degrades to low confidence instead of a
    hard validation failure."""
    inv = invoice.model_copy(deep=True)
    if not inv.date:
        return inv
    try:
        parsed = date_parser.parse(inv.date, dayfirst=False)
        inv.date = parsed.date().isoformat()
    except (ValueError, OverflowError):
        inv.date_confidence = min(inv.date_confidence, _UNPARSEABLE_DATE_CONFIDENCE)
    return inv


def apply_arithmetic_checks(invoice: InvoiceSchema) -> InvoiceSchema:
    """Cheap arithmetic beats trusting the model's self-reported certainty:
    if the numbers don't add up, cap the relevant confidence so the field
    lands in the review queue regardless of what the model claimed."""
    inv = invoice.model_copy(deep=True)

    if inv.subtotal is not None and inv.tax is not None:
        expected_total = inv.subtotal + inv.tax
        if abs(expected_total - inv.total) > _TOLERANCE * max(abs(inv.total), 1e-9):
            inv.total_confidence = min(inv.total_confidence, 0.5)

    if inv.line_items and inv.subtotal is not None:
        items_sum = sum(li.amount for li in inv.line_items)
        if abs(items_sum - inv.subtotal) > _TOLERANCE * max(abs(inv.subtotal), 1e-9):
            inv.subtotal_confidence = min(inv.subtotal_confidence, 0.5)

    return inv
