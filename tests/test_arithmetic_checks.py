from app.services.extraction import apply_arithmetic_checks, normalize_date
from tests.helpers import make_invoice


def test_subtotal_plus_tax_mismatch_caps_total_confidence():
    inv = make_invoice(subtotal=90.0, tax=10.0, total=150.0, total_confidence=0.99)
    checked = apply_arithmetic_checks(inv)
    assert checked.total_confidence == 0.5


def test_consistent_arithmetic_leaves_confidence_alone():
    inv = make_invoice()  # 90 + 10 == 100
    checked = apply_arithmetic_checks(inv)
    assert checked.total_confidence == inv.total_confidence
    assert checked.subtotal_confidence == inv.subtotal_confidence


def test_line_items_sum_mismatch_caps_subtotal_confidence():
    inv = make_invoice(subtotal=500.0, tax=10.0, total=510.0, subtotal_confidence=0.98)
    checked = apply_arithmetic_checks(inv)  # line items sum to 90, not 500
    assert checked.subtotal_confidence == 0.5


def test_already_low_confidence_not_raised():
    inv = make_invoice(subtotal=90.0, tax=10.0, total=150.0, total_confidence=0.2)
    checked = apply_arithmetic_checks(inv)
    assert checked.total_confidence == 0.2


def test_missing_subtotal_or_tax_skips_check():
    inv = make_invoice(subtotal=None, tax=None, total=100.0, total_confidence=0.9)
    checked = apply_arithmetic_checks(inv)
    assert checked.total_confidence == 0.9


def test_date_normalized_to_iso():
    inv = make_invoice(date="July 1, 2026", date_confidence=0.9)
    out = normalize_date(inv)
    assert out.date == "2026-07-01"
    assert out.date_confidence == 0.9


def test_unparseable_date_degrades_confidence():
    inv = make_invoice(date="the first of Julember", date_confidence=0.9)
    out = normalize_date(inv)
    assert out.date_confidence <= 0.3
