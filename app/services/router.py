from app.schemas import InvoiceSchema


def route_fields(invoice: InvoiceSchema, threshold: float) -> tuple[str, list[str]]:
    """Returns (status, flagged_field_names).

    Pure function, zero I/O — the system knows what it doesn't know:
    any field the model is unsure about goes to a human instead of
    silently entering the ledger.
    """
    flagged: list[str] = []
    pairs = [
        ("vendor", invoice.vendor_confidence),
        ("invoice_number", invoice.invoice_number_confidence),
        ("date", invoice.date_confidence),
        ("currency", invoice.currency_confidence),
        ("subtotal", invoice.subtotal_confidence),
        ("tax", invoice.tax_confidence),
        ("total", invoice.total_confidence),
    ]
    flagged += [name for name, conf in pairs if conf < threshold]
    flagged += [
        f"line_items[{i}]"
        for i, li in enumerate(invoice.line_items)
        if li.confidence < threshold
    ]
    status = "pending_review" if flagged else "auto_approved"
    return status, flagged
