from app.schemas import InvoiceSchema, LineItem


def make_invoice(**overrides) -> InvoiceSchema:
    """A fully consistent, high-confidence invoice; override any field."""
    base = dict(
        vendor="Acme Supplies",
        vendor_confidence=0.98,
        invoice_number="INV-1001",
        invoice_number_confidence=0.97,
        date="2026-07-01",
        date_confidence=0.96,
        currency="USD",
        currency_confidence=0.99,
        subtotal=90.0,
        subtotal_confidence=0.95,
        tax=10.0,
        tax_confidence=0.95,
        total=100.0,
        total_confidence=0.97,
        line_items=[
            LineItem(
                description="Widget",
                quantity=3,
                unit_price=30.0,
                amount=90.0,
                confidence=0.96,
            )
        ],
        overall_confidence=0.96,
    )
    base.update(overrides)
    return InvoiceSchema(**base)


def make_low_confidence_invoice() -> InvoiceSchema:
    return make_invoice(
        vendor_confidence=0.4,
        total_confidence=0.6,
    )
