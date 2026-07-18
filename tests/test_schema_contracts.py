import pytest
from pydantic import ValidationError

from app.schemas import InvoiceSchema
from tests.helpers import make_invoice


def test_round_trips_json():
    inv = make_invoice()
    dumped = inv.model_dump_json()
    restored = InvoiceSchema.model_validate_json(dumped)
    assert restored == inv


def test_confidence_above_one_rejected():
    with pytest.raises(ValidationError):
        make_invoice(vendor_confidence=1.2)


def test_confidence_below_zero_rejected():
    with pytest.raises(ValidationError):
        make_invoice(total_confidence=-0.1)


def test_line_item_confidence_bounds_enforced():
    inv = make_invoice()
    payload = inv.model_dump()
    payload["line_items"][0]["confidence"] = 1.5
    with pytest.raises(ValidationError):
        InvoiceSchema.model_validate(payload)


def test_missing_total_rejected():
    payload = make_invoice().model_dump()
    del payload["total"]
    with pytest.raises(ValidationError):
        InvoiceSchema.model_validate(payload)


def test_nullable_fields_accept_none():
    inv = make_invoice(
        invoice_number=None,
        invoice_number_confidence=0.0,
        date=None,
        date_confidence=0.0,
        subtotal=None,
        tax=None,
    )
    assert inv.invoice_number is None
    assert inv.subtotal is None
