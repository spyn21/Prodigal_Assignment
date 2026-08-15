from __future__ import annotations

from unittest.mock import Mock

import pytest

from src.api_client import HttpAccountLookupClient, LookupResult


class DummyResponse:
    def __init__(self, status_code, payload=None, json_error=False):
        self.status_code = status_code
        self._payload = payload
        self._json_error = json_error

    def json(self):
        if self._json_error:
            raise ValueError("bad json")
        return self._payload


@pytest.fixture
def client():
    return HttpAccountLookupClient(base_url="https://example.com", timeout=5)


def test_lookup_account_uses_endpoint_and_payload(client):
    mock_response = DummyResponse(200, {
        "account_id": "ACC1001",
        "full_name": "Nithin Jain",
        "dob": "1990-05-14",
        "aadhaar_last4": "4321",
        "pincode": "400001",
        "balance": 1250.75,
    })

    client.session = Mock()
    client.session.post.return_value = mock_response

    result = client.lookup_account("ACC1001")

    client.session.post.assert_called_once_with(
        "https://example.com/api/lookup-account",
        json={"account_id": "ACC1001"},
        timeout=5,
    )
    assert result.ok is True
    assert result.account_id == "ACC1001"
    assert result.full_name == "Nithin Jain"


def test_lookup_account_rejects_invalid_account_id_locally(client):
    result = client.lookup_account("BAD")
    assert result.ok is False
    assert result.error_code == "invalid_account_id"
    assert result.message == "Account ID is invalid."


def test_lookup_account_handles_404(client):
    mock_response = DummyResponse(404, {"error_code": "account_not_found", "message": "No account found with the provided account_id."})
    client.session = Mock()
    client.session.post.return_value = mock_response

    result = client.lookup_account("ACC9999")

    assert result.ok is False
    assert result.error_code == "account_not_found"
    assert result.message == "No account found with the provided account_id."


def test_lookup_account_handles_malformed_response(client):
    mock_response = DummyResponse(200, "not-a-dict", json_error=False)
    client.session = Mock()
    client.session.post.return_value = mock_response

    result = client.lookup_account("ACC1001")

    assert result.ok is False
    assert result.error_code == "malformed_response"


def test_lookup_account_handles_timeout(client):
    client.session = Mock()
    client.session.post.side_effect = TimeoutError()

    result = client.lookup_account("ACC1001")

    assert result.ok is False
    assert result.error_code in {"timeout", "connection_error"}


def test_lookup_account_handles_connection_failure(client):
    client.session = Mock()
    client.session.post.side_effect = ConnectionError()

    result = client.lookup_account("ACC1001")

    assert result.ok is False
    assert result.error_code in {"timeout", "connection_error"}


def test_lookup_account_handles_500(client):
    mock_response = DummyResponse(500, {"error": "server error"})
    client.session = Mock()
    client.session.post.return_value = mock_response

    result = client.lookup_account("ACC1001")

    assert result.ok is False
    assert result.error_code == "lookup_failed"


@pytest.mark.parametrize(
    "side_effect, expected_code",
    [
        (TimeoutError(), "timeout"),
        (ConnectionError(), "connection_error"),
    ],
)
def test_lookup_account_handles_transport_failures(client, side_effect, expected_code):
    client.session = Mock()
    client.session.post.side_effect = side_effect

    result = client.lookup_account("ACC1001")

    assert result.ok is False
    assert result.error_code == expected_code
