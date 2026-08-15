from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any, Iterable, Optional, Sequence

from src.validators import (
    validate_amount,
    validate_card_number,
    validate_cvv,
    validate_expiry,
    normalize_card_number,
    is_masked_card,
)


class PaymentValidationError(ValueError):
    """Raised only when a payment validation check explicitly fails."""


@dataclass(frozen=True)
class PaymentValidationResult:
    is_valid: bool
    amount: Optional[Decimal] = None
    card_number: Optional[str] = None
    masked_card_number: Optional[str] = None
    errors: tuple[str, ...] = ()
    full_balance_requested: bool = False

    def __bool__(self) -> bool:
        return self.is_valid


def _word_to_decimal(text: str) -> Optional[Decimal]:
    lower = (text or "").lower().strip()
    if not lower:
        return None

    cleaned = re.sub(r"[^a-z\s]", " ", lower)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    if not cleaned:
        return None

    small = {
        "zero": 0,
        "one": 1,
        "two": 2,
        "three": 3,
        "four": 4,
        "five": 5,
        "six": 6,
        "seven": 7,
        "eight": 8,
        "nine": 9,
        "ten": 10,
        "eleven": 11,
        "twelve": 12,
        "thirteen": 13,
        "fourteen": 14,
        "fifteen": 15,
        "sixteen": 16,
        "seventeen": 17,
        "eighteen": 18,
        "nineteen": 19,
        "twenty": 20,
        "thirty": 30,
        "forty": 40,
        "fifty": 50,
        "sixty": 60,
        "seventy": 70,
        "eighty": 80,
        "ninety": 90,
    }

    total = 0
    current = 0
    for word in re.findall(r"[a-z]+", cleaned):
        if word in {"and", "point", "rupees", "rupee", "for", "now", "pay", "clear", "amount", "the", "full", "everything"}:
            continue
        if word in {"hundred", "thousand", "million"}:
            if word == "hundred":
                current *= 100
            elif word == "thousand":
                current *= 1000
                total += current
                current = 0
            elif word == "million":
                current *= 1000000
                total += current
                current = 0
            continue
        if word in small:
            current += small[word]
        elif word in {"a", "an"}:
            current += 1
        else:
            return None
    total += current
    if total <= 0:
        return None
    return Decimal(total)


def parse_payment_amount(value: Any, *, balance: Optional[Decimal] = None, full_balance_requested: bool = False) -> PaymentValidationResult:
    if full_balance_requested:
        if balance is None:
            return PaymentValidationResult(False, errors=("balance_unavailable",))
        normalized = balance
        if normalized <= 0:
            return PaymentValidationResult(False, amount=normalized, errors=("amount_must_be_positive",), full_balance_requested=True)
        return PaymentValidationResult(True, amount=normalized, full_balance_requested=True)

    if value is None:
        return PaymentValidationResult(False, errors=("amount_required",))

    text = str(value).strip()
    if not text:
        return PaymentValidationResult(False, errors=("amount_required",))

    if re.search(r"\b(?:full\s+amount|pay\s+everything|clear\s+the\s+full\s+amount)\b", text, re.IGNORECASE):
        if balance is None:
            return PaymentValidationResult(False, errors=("balance_unavailable",))
        normalized = balance
        if normalized <= 0:
            return PaymentValidationResult(False, amount=normalized, errors=("amount_must_be_positive",), full_balance_requested=True)
        return PaymentValidationResult(True, amount=normalized, full_balance_requested=True)

    numeric_match = re.search(r"[-+]?\d+(?:\.\d+)?", text)
    if numeric_match:
        try:
            amount = Decimal(numeric_match.group(0))
        except InvalidOperation:
            amount = None
    else:
        amount = None

    if amount is None:
        amount = _word_to_decimal(text)
        if amount is None:
            return PaymentValidationResult(False, errors=("invalid_amount",))

    if not validate_amount(amount):
        return PaymentValidationResult(False, amount=amount, errors=("invalid_amount",))
    if balance is not None and amount > balance:
        return PaymentValidationResult(False, amount=amount, errors=("amount_exceeds_balance",))
    if amount <= 0:
        return PaymentValidationResult(False, amount=amount, errors=("amount_must_be_positive",))
    return PaymentValidationResult(True, amount=amount)


def validate_cardholder_name(value: Any) -> bool:
    if value is None:
        return False
    text = str(value).strip()
    if not text or len(text) < 2 or len(text) > 80:
        return False
    if re.fullmatch(r"[A-Za-z][A-Za-z'\-\. ]+", text) is None:
        return False
    return True


def normalize_card_number(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if is_masked_card(text):
        return None
    digits = re.sub(r"\s+", "", text).replace("-", "")
    if not re.fullmatch(r"\d{13,19}", digits):
        return None
    if not validate_card_number(digits):
        return None
    return digits


def validate_payment_amount(value: Any, *, balance: Optional[Decimal] = None) -> bool:
    result = parse_payment_amount(value, balance=balance)
    return result.is_valid


def normalize_payment_amount(value: Any, *, balance: Optional[Decimal] = None, full_balance_requested: bool = False) -> Optional[Decimal]:
    result = parse_payment_amount(value, balance=balance, full_balance_requested=full_balance_requested)
    return result.amount if result.is_valid else None


def validate_payment_details(
    *,
    amount: Any,
    balance: Optional[Decimal] = None,
    cardholder_name: Any,
    card_number: Any,
    cvv: Any,
    expiry: Any,
    current_date: Optional[date] = None,
    full_balance_requested: bool = False,
) -> PaymentValidationResult:
    amount_result = parse_payment_amount(amount, balance=balance, full_balance_requested=full_balance_requested)
    if not amount_result.is_valid:
        return amount_result
    if not validate_cardholder_name(cardholder_name):
        return PaymentValidationResult(False, amount=amount_result.amount, errors=("invalid_cardholder_name",))
    normalized_card = normalize_card_number(card_number)
    if normalized_card is None:
        return PaymentValidationResult(False, amount=amount_result.amount, errors=("invalid_card_number",))
    if not validate_cvv(cvv):
        return PaymentValidationResult(False, amount=amount_result.amount, errors=("invalid_cvv",))
    if isinstance(expiry, tuple) and len(expiry) == 2:
        expiry_month, expiry_year = expiry
    elif isinstance(expiry, dict):
        expiry_month = expiry.get("month")
        expiry_year = expiry.get("year")
    else:
        expiry_month, expiry_year = None, None
        match = re.search(r"(\d{1,2})\s*[/\-]\s*(\d{2,4})", str(expiry))
        if match:
            expiry_month = int(match.group(1))
            expiry_year = int(match.group(2))
            if len(match.group(2)) == 2:
                expiry_year = 2000 + expiry_year if expiry_year <= 50 else 1900 + expiry_year
        else:
            month_match = re.search(r"([A-Za-z]+)\s+(\d{2,4})", str(expiry), re.IGNORECASE)
            if month_match:
                month_names = {"jan": 1, "january": 1, "feb": 2, "february": 2, "mar": 3, "march": 3, "apr": 4, "april": 4, "may": 5, "jun": 6, "june": 6, "jul": 7, "july": 7, "aug": 8, "august": 8, "sep": 9, "sept": 9, "september": 9, "oct": 10, "october": 10, "nov": 11, "november": 11, "dec": 12, "december": 12}
                expiry_month = month_names.get(month_match.group(1).lower())
                expiry_year = int(month_match.group(2))
                if len(month_match.group(2)) == 2:
                    expiry_year = 2000 + expiry_year if expiry_year <= 50 else 1900 + expiry_year
    if expiry_month is None or expiry_year is None or not validate_expiry(expiry_month, expiry_year, reference_date=current_date):
        return PaymentValidationResult(False, amount=amount_result.amount, errors=("invalid_expiry",))
    return PaymentValidationResult(True, amount=amount_result.amount, card_number=normalized_card, masked_card_number=_safe_mask_card(normalized_card), errors=())


def validate_expiry_string(value: Any, *, reference_date: Optional[date] = None) -> bool:
    if value is None:
        return False
    text = str(value).strip()
    if not text:
        return False

    if re.search(r"/", text) or re.search(r"-", text):
        match = re.search(r"(\d{1,2})\s*[/\-]\s*(\d{2,4})", text)
        if match:
            month = int(match.group(1))
            year = int(match.group(2))
            if len(match.group(2)) == 2:
                year = 2000 + year if year <= 50 else 1900 + year
            return validate_expiry(month, year, reference_date=reference_date)

    month_names = {
        "jan": 1, "january": 1,
        "feb": 2, "february": 2,
        "mar": 3, "march": 3,
        "apr": 4, "april": 4,
        "may": 5,
        "jun": 6, "june": 6,
        "jul": 7, "july": 7,
        "aug": 8, "august": 8,
        "sep": 9, "sept": 9, "september": 9,
        "oct": 10, "october": 10,
        "nov": 11, "november": 11,
        "dec": 12, "december": 12,
    }
    match = re.search(r"([A-Za-z]+)\s+(\d{2,4})", text, re.IGNORECASE)
    if match:
        month = month_names.get(match.group(1).lower())
        if month is None:
            return False
        year = int(match.group(2))
        if len(match.group(2)) == 2:
            year = 2000 + year if year <= 50 else 1900 + year
        return validate_expiry(month, year, reference_date=reference_date)
    return False


def _safe_mask_card(card_number: str) -> str:
    digits = re.sub(r"\D", "", str(card_number or ""))
    if len(digits) <= 4:
        return "****"
    return f"{digits[:4]}******{digits[-4:]}"


def prepare_payment_submission(
    *,
    account_id: Any,
    amount: Any,
    balance: Optional[Decimal] = None,
    cardholder_name: Any,
    card_number: Any,
    cvv: Any,
    expiry: Any,
    current_date: Optional[date] = None,
    api_client: Optional[Any] = None,
    full_balance_requested: bool = False,
):
    """Validate local payment data before any API call. If invalid, the API callback is not invoked."""
    amount_result = parse_payment_amount(amount, balance=balance, full_balance_requested=full_balance_requested)
    if not amount_result.is_valid:
        return None

    if not validate_cardholder_name(cardholder_name):
        return None

    normalized_card = normalize_card_number(card_number)
    if normalized_card is None:
        return None

    if not validate_cvv(cvv):
        return None

    expiry_month = None
    expiry_year = None
    if isinstance(expiry, tuple) and len(expiry) == 2:
        expiry_month, expiry_year = expiry
    elif isinstance(expiry, dict):
        expiry_month = expiry.get("month")
        expiry_year = expiry.get("year")
    else:
        match = re.search(r"(\d{1,2})\s*[/\-]\s*(\d{2,4})", str(expiry))
        if match:
            expiry_month = int(match.group(1))
            expiry_year = int(match.group(2))
            if len(match.group(2)) == 2:
                expiry_year = 2000 + expiry_year if expiry_year <= 50 else 1900 + expiry_year
        else:
            month_names = {
                "jan": 1, "january": 1,
                "feb": 2, "february": 2,
                "mar": 3, "march": 3,
                "apr": 4, "april": 4,
                "may": 5,
                "jun": 6, "june": 6,
                "jul": 7, "july": 7,
                "aug": 8, "august": 8,
                "sep": 9, "sept": 9, "september": 9,
                "oct": 10, "october": 10,
                "nov": 11, "november": 11,
                "dec": 12, "december": 12,
            }
            month_match = re.search(r"([A-Za-z]+)\s+(\d{2,4})", str(expiry), re.IGNORECASE)
            if month_match:
                expiry_month = month_names.get(month_match.group(1).lower())
                expiry_year = int(month_match.group(2))
                if len(month_match.group(2)) == 2:
                    expiry_year = 2000 + expiry_year if expiry_year <= 50 else 1900 + expiry_year

    if expiry_month is None or expiry_year is None:
        return None
    if not validate_expiry(expiry_month, expiry_year, reference_date=current_date):
        return None

    payload = {
        "account_id": str(account_id),
        "amount": amount_result.amount,
        "payment_method": {
            "type": "card",
            "card": {
                "cardholder_name": str(cardholder_name).strip(),
                "card_number": normalized_card,
                "cvv": str(cvv).strip(),
                "expiry_month": int(expiry_month),
                "expiry_year": int(expiry_year),
            },
        },
    }

    if api_client is not None:
        return api_client(payload)
    return payload


mask_card_number = _safe_mask_card


def redact_sensitive_fields(payload: dict) -> dict:
    if not isinstance(payload, dict):
        return payload
    redacted = {}
    for key, value in payload.items():
        if key in {"card_number", "cvv", "card"}:
            redacted[key] = "[REDACTED]"
        elif key == "payment_method" and isinstance(value, dict):
            redacted[key] = {"type": value.get("type"), "card": {"cardholder_name": value.get("card", {}).get("cardholder_name"), "card_number": "[REDACTED]", "cvv": "[REDACTED]", "expiry_month": value.get("card", {}).get("expiry_month"), "expiry_year": value.get("card", {}).get("expiry_year")}}
        else:
            redacted[key] = value
    return redacted


__all__ = [
    "PaymentValidationError",
    "PaymentValidationResult",
    "parse_payment_amount",
    "normalize_payment_amount",
    "validate_payment_details",
    "validate_cardholder_name",
    "normalize_card_number",
    "mask_card_number",
    "redact_sensitive_fields",
    "validate_payment_amount",
    "validate_expiry_string",
    "prepare_payment_submission",
    "_safe_mask_card",
]
