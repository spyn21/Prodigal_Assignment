from datetime import date
from decimal import Decimal

import pytest

from src.payment import (
    parse_payment_amount,
    prepare_payment_submission,
    validate_cardholder_name,
    validate_expiry_string,
    validate_payment_amount,
)


def test_parse_numeric_amounts():
    cases = [
        ("500", Decimal("500")),
        ("500.00", Decimal("500.00")),
        ("₹500", Decimal("500")),
        ("500 rupees", Decimal("500")),
        ("five hundred", Decimal("500")),
        ("a thousand", Decimal("1000")),
        ("pay 500 for now", Decimal("500")),
    ]
    for raw, expected in cases:
        result = parse_payment_amount(raw)
        assert result.is_valid is True
        assert result.amount == expected


def test_parse_full_balance_intent_uses_verified_balance():
    result = parse_payment_amount("clear the full amount", balance=Decimal("1250.75"), full_balance_requested=True)
    assert result.is_valid is True
    assert result.amount == Decimal("1250.75")
    assert result.full_balance_requested is True


def test_zero_balance_account_is_rejected_gracefully():
    result = parse_payment_amount("clear the full amount", balance=Decimal("0.00"), full_balance_requested=True)
    assert result.is_valid is False
    assert "amount_must_be_positive" in result.errors


def test_amount_validation_rejects_bad_values():
    assert validate_payment_amount("-1") is False
    assert validate_payment_amount("0") is False
    assert validate_payment_amount("123.456") is False
    assert validate_payment_amount("abc") is False


def test_cardholder_name_is_validated():
    assert validate_cardholder_name("Nithin Jain") is True
    assert validate_cardholder_name("Raja") is True
    assert validate_cardholder_name("") is False
    assert validate_cardholder_name("123") is False


def test_expiry_validation_accepts_supported_strings():
    assert validate_expiry_string("12/27") is True
    assert validate_expiry_string("12/2027") is True
    assert validate_expiry_string("December 2027") is True
    assert validate_expiry_string("expires December 2027") is True


def test_expiry_validation_rejects_expired_and_invalid_months():
    assert validate_expiry_string("12/2020") is False
    assert validate_expiry_string("13/2027") is False
    assert validate_expiry_string("00/2027") is False


def test_prepare_payment_submission_rejects_invalid_local_input_before_api_call():
    calls = []

    def fake_api(payload):
        calls.append(payload)
        return {"success": True, "transaction_id": "txn_123"}

    request = prepare_payment_submission(
        account_id="ACC1001",
        amount="-10",
        balance=Decimal("1250.75"),
        cardholder_name="Nithin Jain",
        card_number="4532015112830366",
        cvv="123",
        expiry="12/2027",
        api_client=fake_api,
    )
    assert request is None
    assert calls == []


def test_prepare_payment_submission_builds_valid_payload_when_local_validation_passes():
    payload = prepare_payment_submission(
        account_id="ACC1001",
        amount="500",
        balance=Decimal("1250.75"),
        cardholder_name="Nithin Jain",
        card_number="4532 0151 1283 0366",
        cvv="123",
        expiry="12/2027",
        current_date=date(2025, 1, 1),
    )
    assert payload is not None
    assert payload["account_id"] == "ACC1001"
    assert payload["amount"] == Decimal("500")
    assert payload["payment_method"]["card"]["card_number"] == "4532015112830366"
    assert payload["payment_method"]["card"]["expiry_month"] == 12
    assert payload["payment_method"]["card"]["expiry_year"] == 2027


def test_prepare_payment_submission_rejects_masked_card_number():
    payload = prepare_payment_submission(
        account_id="ACC1001",
        amount="500",
        balance=Decimal("1250.75"),
        cardholder_name="Nithin Jain",
        card_number="4532********0366",
        cvv="123",
        expiry="12/2027",
    )
    assert payload is None
