from __future__ import annotations

import re
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any, Optional, Union


def normalize_account_id(value: Any) -> Optional[str]:
    if value is None:
        return None
    cleaned = re.sub(r"\s+", "", str(value)).upper()
    if re.fullmatch(r"ACC\d{4}", cleaned):
        return cleaned
    return None


def validate_account_id(value: Any) -> bool:
    return normalize_account_id(value) is not None


def normalize_date(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    text = re.sub(r"\b(\d+)(?:st|nd|rd|th)\b", r"\1", text, flags=re.IGNORECASE)

    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
        try:
            year, month, day = map(int, text.split("-"))
            date(year, month, day)
            return f"{year:04d}-{month:02d}-{day:02d}"
        except ValueError:
            return None

    if re.fullmatch(r"\d{1,2}[/-]\d{1,2}[/-]\d{2,4}", text):
        parts = re.split(r"[/-]", text)
        day, month = int(parts[0]), int(parts[1])
        year_raw = parts[2]
        if len(str(year_raw)) == 2:
            yr = int(year_raw)
            year = 2000 + yr if yr <= 50 else 1900 + yr
        else:
            year = int(year_raw)
        try:
            normalized = date(int(year), month, day)
            return normalized.isoformat()
        except ValueError:
            return None

    match = re.fullmatch(r"(\d{1,2})\s+([A-Za-z]+)\s+(\d{2,4})", text)
    if match:
        day, month_name, year_raw = match.groups()
        month = _month_name_to_number(month_name)
        if month is None:
            return None
        year = int(year_raw)
        if len(year_raw) == 2:
            year = 2000 + year if year <= 50 else 1900 + year
        try:
            normalized = date(int(year), month, int(day))
            return normalized.isoformat()
        except ValueError:
            return None

    match = re.fullmatch(r"([A-Za-z]+)\s+(\d{1,2}),?\s*(\d{2,4})", text)
    if match:
        month_name, day, year_raw = match.groups()
        month = _month_name_to_number(month_name)
        if month is None:
            return None
        year = int(year_raw)
        if len(year_raw) == 2:
            year = 2000 + year if year <= 50 else 1900 + year
        try:
            normalized = date(int(year), month, int(day))
            return normalized.isoformat()
        except ValueError:
            return None

    return None


def validate_date(value: Any) -> bool:
    return normalize_date(value) is not None


def _month_name_to_number(month_name: str) -> Optional[int]:
    months = {
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
    return months.get(month_name.lower().strip())


def validate_aadhaar_last4(value: Any) -> bool:
    if value is None:
        return False
    text = str(value).strip()
    return bool(re.fullmatch(r"\d{4}", text))


def validate_pincode(value: Any) -> bool:
    if value is None:
        return False
    text = re.sub(r"\D", "", str(value))
    return bool(re.fullmatch(r"\d{6}", text))


def validate_amount(value: Any, max_allowed: Optional[Union[str, Decimal, float, int]] = None) -> bool:
    if value is None:
        return False
    text = str(value).strip()
    if not text:
        return False
    try:
        amount = Decimal(text)
    except InvalidOperation:
        text = text.replace("₹", "").replace("Rs", "").replace("INR", "")
        try:
            amount = Decimal(text.strip())
        except InvalidOperation:
            return False
    if not amount.is_finite():
        return False
    if amount <= 0:
        return False
    if abs(amount.as_tuple().exponent) > 2:
        return False
    if max_allowed is not None:
        try:
            max_decimal = Decimal(str(max_allowed))
        except InvalidOperation:
            return False
        if amount > max_decimal:
            return False
    return True


def normalize_card_number(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    normalized = re.sub(r"\s+", "", text).replace("-", "")
    if not re.fullmatch(r"\d{13,19}", normalized):
        return None
    if is_masked_card(text):
        return None
    return normalized


def is_masked_card(value: Any) -> bool:
    if value is None:
        return False
    text = str(value).strip()
    if not text:
        return False
    lowered = text.lower()
    if "x" in lowered or "*" in lowered:
        return True
    if re.fullmatch(r"\d{4}[-\s]*\*{4,}[-\s]*\d{4}", text):
        return True
    return False


def validate_luhn(value: Any) -> bool:
    digits = normalize_card_number(value)
    if digits is None:
        return False
    total = 0
    parity = len(digits) % 2
    for index, char in enumerate(digits):
        digit = int(char)
        if index % 2 == parity:
            digit *= 2
            if digit > 9:
                digit -= 9
        total += digit
    return total % 10 == 0


def validate_card_number(value: Any) -> bool:
    return validate_luhn(value)


def validate_cvv(value: Any) -> bool:
    if value is None:
        return False
    text = str(value).strip()
    if not text:
        return False
    if not re.fullmatch(r"\d{3,4}", text):
        return False
    return True


def normalize_expiry(month: Any, year: Any) -> Optional[tuple[int, int]]:
    try:
        month_int = int(month)
    except (TypeError, ValueError):
        return None
    try:
        year_int = int(year)
    except (TypeError, ValueError):
        return None
    if len(str(year_int)) == 2:
        year_int = 2000 + year_int if year_int <= 50 else 1900 + year_int
    if not 1 <= month_int <= 12:
        return None
    return month_int, year_int


def validate_expiry(month: Any, year: Any, reference_date: Optional[date] = None) -> bool:
    normalized = normalize_expiry(month, year)
    if normalized is None:
        return False
    month_int, year_int = normalized
    today = reference_date or date.today()
    expiry_month_end = date(year_int, month_int, 1).replace(day=28)
    try:
        expiry_month_end = date(year_int, month_int, 1)
        # advance to end of month
        if month_int == 12:
            next_month = date(year_int + 1, 1, 1)
        else:
            next_month = date(year_int, month_int + 1, 1)
        expiry_month_end = next_month.replace(day=1) - __import__("datetime").timedelta(days=1)
    except Exception:
        pass
    return date(year_int, month_int, 1) >= date(today.year, today.month, 1) and expiry_month_end >= today


def validate_expiry_string(value: Any) -> bool:
    if value is None:
        return False
    text = str(value).strip()
    if not text:
        return False
    match = re.search(r"(\d{1,2})\s*[/\-]\s*(\d{2,4})", text)
    if match:
        month = int(match.group(1))
        year = int(match.group(2))
        if len(match.group(2)) == 2:
            year = 2000 + year if year <= 50 else 1900 + year
        return validate_expiry(month, year)

    month_name_match = re.search(r"([A-Za-z]+)\s+(\d{2,4})", text, re.IGNORECASE)
    if month_name_match:
        month_name = month_name_match.group(1)
        month = _month_name_to_number(month_name)
        if month is None:
            return False
        year = int(month_name_match.group(2))
        if len(month_name_match.group(2)) == 2:
            year = 2000 + year if year <= 50 else 1900 + year
        return validate_expiry(month, year)
    return False


__all__ = [
    "normalize_account_id",
    "validate_account_id",
    "normalize_date",
    "validate_date",
    "validate_aadhaar_last4",
    "validate_pincode",
    "validate_amount",
    "normalize_card_number",
    "is_masked_card",
    "validate_luhn",
    "validate_card_number",
    "validate_cvv",
    "normalize_expiry",
    "validate_expiry",
    "validate_expiry_string",
]
