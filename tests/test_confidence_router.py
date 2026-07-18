from app.services.router import route_fields
from tests.helpers import make_invoice

THRESHOLD = 0.75


def test_field_just_below_threshold_is_flagged():
    inv = make_invoice(vendor_confidence=0.74)
    status, flagged = route_fields(inv, THRESHOLD)
    assert status == "pending_review"
    assert "vendor" in flagged


def test_field_just_above_threshold_is_not_flagged():
    inv = make_invoice(vendor_confidence=0.76)
    status, flagged = route_fields(inv, THRESHOLD)
    assert "vendor" not in flagged


def test_all_high_confidence_auto_approves():
    status, flagged = route_fields(make_invoice(), THRESHOLD)
    assert status == "auto_approved"
    assert flagged == []


def test_low_line_item_flags_indexed_name():
    inv = make_invoice()
    inv.line_items[0].confidence = 0.3
    status, flagged = route_fields(inv, THRESHOLD)
    assert status == "pending_review"
    assert "line_items[0]" in flagged


def test_multiple_low_fields_all_flagged():
    inv = make_invoice(vendor_confidence=0.1, tax_confidence=0.2)
    status, flagged = route_fields(inv, THRESHOLD)
    assert set(flagged) >= {"vendor", "tax"}
    assert status == "pending_review"
