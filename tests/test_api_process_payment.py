from decimal import Decimal
import json

from src.api_client import HttpAccountLookupClient, PaymentResult


class FakeResponse:
    def __init__(self, status_code:int, body:dict):
        self.status_code = status_code
        self._body = body

    def json(self):
        return self._body


def test_api_client_process_payment_sends_correct_payload(monkeypatch):
    captured = {}

    def fake_post(url, json=None, timeout=None):
        captured['url'] = url
        captured['json'] = json
        return FakeResponse(200, {"success": True, "transaction_id": "txn_abc"})

    client = HttpAccountLookupClient()
    client.session.post = fake_post

    payload = {
        "account_id": "ACC1001",
        "amount": Decimal('500.00'),
        "payment_method": {
            "type": "card",
            "card": {
                "cardholder_name": "Nithin Jain",
                "card_number": "4532015112830366",
                "cvv": "123",
                "expiry_month": 12,
                "expiry_year": 2027,
            }
        }
    }

    result = client.process_payment(payload)
    assert result.ok is True
    assert result.success is True
    assert result.transaction_id == "txn_abc"

    assert captured['url'].endswith('/api/process-payment')
    sent = captured['json']
    # amount must be JSON-serializable (float)
    assert isinstance(sent['amount'], float)
    assert sent['amount'] == 500.0
    assert sent['account_id'] == 'ACC1001'
    card = sent['payment_method']['card']
    assert card['cardholder_name'] == 'Nithin Jain'
    assert card['card_number'] == '4532015112830366'
    assert card['cvv'] == '123'
    assert card['expiry_month'] == 12
    assert card['expiry_year'] == 2027
