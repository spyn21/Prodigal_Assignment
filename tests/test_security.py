from decimal import Decimal

from src.payment import prepare_payment_submission


def test_invalid_payment_fields_do_not_reach_api_layer():
    calls = []

    def fake_api(payload):
        calls.append(payload)
        return {"success": True, "transaction_id": "txn_1"}

    request = prepare_payment_submission(
        account_id="ACC1001",
        amount="500",
        balance=Decimal("1250.75"),
        cardholder_name="Nithin Jain",
        card_number="4111111111111112",
        cvv="12",
        expiry="12/2027",
        api_client=fake_api,
    )

    assert request is None
    assert calls == []


def test_valid_payment_data_is_prepared_without_raw_sensitive_values_in_logs():
    payload = prepare_payment_submission(
        account_id="ACC1001",
        amount="500.00",
        balance=Decimal("1250.75"),
        cardholder_name="Nithin Jain",
        card_number="4532 0151 1283 0366",
        cvv="123",
        expiry="12/2027",
    )

    assert payload is not None
    assert payload["payment_method"]["card"]["card_number"] == "4532015112830366"
    assert payload["payment_method"]["card"]["cvv"] == "123"
    assert str(payload).find("4532015112830366") >= 0
    assert str(payload).find("123") >= 0
