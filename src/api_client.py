from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict, Optional, Protocol

import requests

from src.validators import validate_account_id

BASE_URL = "https://se-payment-verification-api.service.external.usea2.aws.prodigaltech.com"


class ApiClient(Protocol):
    def lookup_account(self, account_id: str) -> "LookupResult":
        ...


@dataclass
class LookupResult:
    ok: bool
    account_id: Optional[str] = None
    full_name: Optional[str] = None
    dob: Optional[str] = None
    aadhaar_last4: Optional[str] = None
    pincode: Optional[str] = None
    balance: Optional[float] = None
    error_code: Optional[str] = None
    message: Optional[str] = None
    http_status: Optional[int] = None


class PaymentResult:
    def __init__(self, ok: bool, success: bool = False, transaction_id: Optional[str] = None, error_code: Optional[str] = None, message: Optional[str] = None, http_status: Optional[int] = None):
        self.ok = ok
        self.success = success
        self.transaction_id = transaction_id
        self.error_code = error_code
        self.message = message
        self.http_status = http_status


class HttpAccountLookupClient:
    """Account lookup client with focused validation and safe error handling. Also includes a process_payment helper."""

    def __init__(
        self,
        base_url: str = BASE_URL,
        timeout: int = 10,
        session: Optional[requests.Session] = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.session = session or requests.Session()

    def lookup_account(self, account_id: str) -> LookupResult:
        if not validate_account_id(account_id):
            return LookupResult(ok=False, error_code="invalid_account_id", message="Account ID is invalid.")

        payload = {"account_id": account_id}
        url = f"{self.base_url}/api/lookup-account"

        try:
            response = self.session.post(url, json=payload, timeout=self.timeout)
        except (requests.exceptions.Timeout, TimeoutError):
            return LookupResult(ok=False, error_code="timeout", message="The account lookup timed out. Please try again.")
        except (requests.exceptions.ConnectionError, ConnectionError):
            return LookupResult(ok=False, error_code="connection_error", message="The account service is temporarily unavailable. Please try again.")

        if response.status_code == 404:
            try:
                body = response.json()
            except ValueError:
                body = {}
            error_code = body.get("error_code") or "account_not_found"
            message = body.get("message") or "No account found with the provided account_id."
            return LookupResult(ok=False, account_id=account_id, error_code=error_code, message=message, http_status=response.status_code)

        if response.status_code != 200:
            return LookupResult(ok=False, account_id=account_id, error_code="lookup_failed", message="Unable to access the account information right now.", http_status=response.status_code)

        try:
            body = response.json()
        except ValueError:
            return LookupResult(ok=False, account_id=account_id, error_code="malformed_response", message="The account response was invalid.", http_status=response.status_code)

        if not isinstance(body, dict):
            return LookupResult(ok=False, account_id=account_id, error_code="malformed_response", message="The account response was invalid.", http_status=response.status_code)

        required = {"account_id", "full_name", "dob", "aadhaar_last4", "pincode", "balance"}
        if not required.issubset(body):
            return LookupResult(ok=False, account_id=account_id, error_code="malformed_response", message="The account response was invalid.", http_status=response.status_code)

        return LookupResult(
            ok=True,
            account_id=str(body.get("account_id")),
            full_name=str(body.get("full_name")),
            dob=str(body.get("dob")),
            aadhaar_last4=str(body.get("aadhaar_last4")),
            pincode=str(body.get("pincode")),
            balance=float(body.get("balance")),
            http_status=response.status_code,
        )

    def process_payment(self, payload: Dict[str, Any]) -> PaymentResult:
        # Basic payload validation to avoid sending malformed requests
        if not isinstance(payload, dict):
            return PaymentResult(ok=False, error_code="invalid_payload", message="Payload must be a JSON object.")
        if "account_id" not in payload or "amount" not in payload or "payment_method" not in payload:
            return PaymentResult(ok=False, error_code="invalid_payload", message="Missing required payment fields.")

        # Ensure amount is JSON-serializable (convert Decimal to float)
        send_payload = payload.copy()
        amount = send_payload.get("amount")
        try:
            # convert Decimal to float safely
            if hasattr(amount, "quantize"):
                send_payload["amount"] = float(amount)
            else:
                send_payload["amount"] = float(amount)
        except Exception:
            return PaymentResult(ok=False, error_code="invalid_amount", message="Amount is invalid.")

        url = f"{self.base_url}/api/process-payment"
        try:
            response = self.session.post(url, json=send_payload, timeout=self.timeout)
        except (requests.exceptions.Timeout, TimeoutError):
            return PaymentResult(ok=False, error_code="timeout", message="Payment request timed out.")
        except (requests.exceptions.ConnectionError, ConnectionError):
            return PaymentResult(ok=False, error_code="connection_error", message="Payment service unavailable.")

        if response.status_code >= 500:
            return PaymentResult(ok=False, error_code="server_error", message="Payment service error.", http_status=response.status_code)

        try:
            body = response.json()
        except ValueError:
            return PaymentResult(ok=False, error_code="malformed_response", message="Payment response malformed.", http_status=response.status_code)

        if not isinstance(body, dict):
            return PaymentResult(ok=False, error_code="malformed_response", message="Payment response malformed.", http_status=response.status_code)

        if body.get("success") is True:
            txn = body.get("transaction_id")
            if not txn:
                return PaymentResult(ok=False, error_code="missing_transaction_id", message="Payment succeeded but transaction id missing.")
            return PaymentResult(ok=True, success=True, transaction_id=str(txn), http_status=response.status_code)

        # error cases
        err = body.get("error_code") or "payment_failed"
        return PaymentResult(ok=False, error_code=err, message=body.get("message"), http_status=response.status_code)


__all__ = ["BASE_URL", "ApiClient", "LookupResult", "HttpAccountLookupClient", "PaymentResult"]
