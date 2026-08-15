from __future__ import annotations

from types import SimpleNamespace

from src.api_client import HttpAccountLookupClient


class MockSession:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def post(self, url, json=None, timeout=None):
        self.calls.append({"url": url, "json": json, "timeout": timeout})
        return self.response


def test_lookup_contract_uses_account_endpoint_and_json_payload():
    response = SimpleNamespace(
        status_code=200,
        json=lambda: {
            "account_id": "ACC1001",
            "full_name": "Nithin Jain",
            "dob": "1990-05-14",
            "aadhaar_last4": "4321",
            "pincode": "400001",
            "balance": 1250.75,
        },
    )
    session = MockSession(response)
    client = HttpAccountLookupClient(base_url="https://example.com", timeout=7, session=session)

    result = client.lookup_account("ACC1001")

    assert session.calls[0]["url"] == "https://example.com/api/lookup-account"
    assert session.calls[0]["json"] == {"account_id": "ACC1001"}
    assert session.calls[0]["timeout"] == 7
    assert result.ok is True


def test_lookup_contract_handles_not_found_error_payload():
    response = SimpleNamespace(
        status_code=404,
        json=lambda: {"error_code": "account_not_found", "message": "No account found with the provided account_id."},
    )
    session = MockSession(response)
    client = HttpAccountLookupClient(base_url="https://example.com", timeout=7, session=session)

    result = client.lookup_account("ACC9999")

    assert result.ok is False
    assert result.error_code == "account_not_found"
    assert result.message == "No account found with the provided account_id."


def test_lookup_contract_rejects_local_invalid_account_id_before_http_call():
    session = MockSession(SimpleNamespace(status_code=200, json=lambda: {}))
    client = HttpAccountLookupClient(base_url="https://example.com", timeout=7, session=session)

    result = client.lookup_account("BAD")

    assert result.ok is False
    assert result.error_code == "invalid_account_id"
    assert len(session.calls) == 0
