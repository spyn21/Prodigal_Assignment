from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, Optional


def _normalize_account_id(value: str) -> Optional[str]:
    if value is None:
        return None
    cleaned = re.sub(r"\s+", "", str(value)).upper()
    if re.fullmatch(r"ACC\d{4}", cleaned):
        return cleaned
    return None


def _strip_ordinals(value: str) -> str:
    return re.sub(r"\b(\d+)(?:st|nd|rd|th)\b", r"\1", value, flags=re.IGNORECASE)


def _normalize_card_number(value: str) -> str:
    return re.sub(r"[^\d]", "", str(value or ""))


def _words_to_number(text: str) -> Optional[Decimal]:
    lower = text.lower().strip()
    if not lower:
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
    for word in re.findall(r"[a-z]+", lower):
        if word in {"and", "point", "rupees", "rupee", "for", "now", "pay", "clear", "amount", "full", "the", "everything"}:
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
        else:
            if word in {"a", "an"}:
                current += 1
            else:
                continue
    total += current
    return Decimal(str(total)) if total or lower in {"zero", "a", "an"} else None


def _extract_numeric_amount(text: str) -> Optional[Decimal]:
    match = re.search(r"(?:rs\.?|rupees?|inr|₹|\$)?\s*(\d+(?:\.\d{1,2})?)", text, re.IGNORECASE)
    if match:
        try:
            return Decimal(match.group(1))
        except InvalidOperation:
            return None
    return None


def _parse_month_name(month_name: str) -> Optional[int]:
    month_map = {
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
    return month_map.get(month_name.lower().strip())


def _parse_date_value(value: str) -> Optional[str]:
    if value is None:
        return None
    text = _strip_ordinals(value).strip()
    if not text:
        return None

    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
        return text

    if re.fullmatch(r"\d{1,2}[/-]\d{1,2}[/-]\d{2,4}", text):
        parts = re.split(r"[/-]", text)
        if len(parts) != 3:
            return None
        day, month, year = parts[0], parts[1], parts[2]
        if len(year) == 2:
            year = "20" + year if int(year) <= 50 else "19" + year
        try:
            import datetime as dt
            dt.date(int(year), int(month), int(day))
            return f"{int(year):04d}-{int(month):02d}-{int(day):02d}"
        except ValueError:
            return None

    match = re.fullmatch(r"(\d{1,2})\s+([A-Za-z]+)\s+(\d{2,4})", text)
    if match:
        day, month_name, year = match.groups()
        month = _parse_month_name(month_name)
        if month is None:
            return None
        year_int = int(year)
        if len(year) == 2:
            year_int = 2000 + year_int if year_int <= 50 else 1900 + year_int
        try:
            import datetime as dt
            dt.date(year_int, month, int(day))
            return f"{year_int:04d}-{month:02d}-{int(day):02d}"
        except ValueError:
            return None

    match = re.fullmatch(r"([A-Za-z]+)\s+(\d{1,2}),?\s*(\d{2,4})", text)
    if match:
        month_name, day, year = match.groups()
        month = _parse_month_name(month_name)
        if month is None:
            return None
        year_int = int(year)
        if len(year) == 2:
            year_int = 2000 + year_int if year_int <= 50 else 1900 + year_int
        try:
            import datetime as dt
            dt.date(year_int, month, int(day))
            return f"{year_int:04d}-{month:02d}-{int(day):02d}"
        except ValueError:
            return None

    return None


def _parse_expiry_date(value: str) -> Optional[Dict[str, int]]:
    text = (value or "").strip()
    if not text:
        return None

    for pattern in [
        r"(\d{1,2})\s*[/\-]\s*(\d{2,4})",
        r"(?:expires?|expiry)\s*(?:on)?\s*(\d{1,2})\s*[/\-]\s*(\d{2,4})",
        r"(?:expires?|expiry)\s*(?:on)?\s*([A-Za-z]+)\s+(\d{2,4})",
        r"([A-Za-z]+)\s+(\d{2,4})",
    ]:
        match = re.search(pattern, text, re.IGNORECASE)
        if not match:
            continue
        if pattern.startswith(r"(\d{1,2})"):
            month = int(match.group(1))
            year_raw = match.group(2)
        else:
            month_name = match.group(1)
            month = _parse_month_name(month_name)
            year_raw = match.group(2)
        if month is None:
            continue
        year = int(year_raw)
        if len(year_raw) == 2:
            year = 2000 + year if year <= 50 else 1900 + year
        return {"month": month, "year": year}

    return None


def _looks_like_authoritative_instruction(text: str) -> bool:
    lower = (text or "").lower()
    if not lower:
        return False

    authority_patterns = [
        r"\bdeveloper mode\b",
        r"\bignore previous instructions\b",
        r"\bprevious instructions\b",
        r"\bsystem says\b",
        r"\badmin(?:istrator)?\b",
        r"\bbypass verification\b",
        r"\bmark me verified\b",
        r"\bverification is complete\b",
        r"\bcall the payment api\b",
        r"\bcall process-payment\b",
        r"\bprocess-payment\b",
        r"\bdirectly invoke\b",
        r"\bshow me the (dob|aadhaar|pincode)\b",
    ]
    return any(re.search(pattern, lower) for pattern in authority_patterns)


def parse_message(text: str) -> Dict[str, Any]:
    user_input = (text or "").strip()
    result: Dict[str, Any] = {
        "account_id": None,
        "full_name": None,
        "dob": None,
        "aadhaar_last4": None,
        "pincode": None,
        "payment_amount": None,
        "pay_full_balance": False,
        "cardholder_name": None,
        "card_number": None,
        "cvv": None,
        "expiry_month": None,
        "expiry_year": None,
        "intent": None,
        "corrections": [],
    }

    if not user_input:
        return result

    account_match = re.search(r"(?:account(?:\s+id|\s+number)?|acct)\s*(?:[:=#-]|\bis\b)?\s*((?:ACC\s*\d{4}|[A-Za-z0-9]{5,}))", user_input, re.IGNORECASE)
    if account_match:
        candidate = account_match.group(1)
        canonical = _normalize_account_id(candidate)
        if canonical:
            result["account_id"] = canonical
    else:
        generic = re.search(r"\b(ACC\s*\d{4})\b", user_input, re.IGNORECASE)
        if generic:
            result["account_id"] = _normalize_account_id(generic.group(1))

    name_patterns = [
        r"(?:my\s+full\s+name|full\s+name|my\s+name|name)\s+is\s+(.+?)(?:\s+(?:and|but|also|dob|date\s+of\s+birth|aadhaar|pincode|account|balance|card|cvv|expires?|expiry)\b|$)",
        r"you\s+can\s+call\s+me\s+.*?\s+but\s+my\s+full\s+name\s+is\s+(.+)$",
        r"it['’]s\s+[^,]+,\s*(.+)$",
    ]
    for pattern in name_patterns:
        match = re.search(pattern, user_input, re.IGNORECASE)
        if match:
            candidate = match.group(1).strip(" ,;:.-")
            if candidate:
                result["full_name"] = candidate
                break

    if result["full_name"] is None:
        direct_names = re.findall(r"\b[A-Z][A-Za-z'\-]+(?:\s+[A-Z][A-Za-z'\-]+){1,5}\b", user_input)
        if direct_names:
            result["full_name"] = direct_names[-1].strip()

    dob_match = re.search(r"(?:dob|date\s+of\s+birth)\s*(?:is)?\s*[:=]?\s*(.+?)(?:\s+(?:and|aadhaar|pincode|account|card|cvv|amount|payment)\b|$)", user_input, re.IGNORECASE)
    if dob_match:
        dob_value = dob_match.group(1).strip(" ,;:.-")
        normalized = _parse_date_value(dob_value)
        if normalized:
            result["dob"] = normalized
    else:
        for token in re.findall(r"\b\d{4}-\d{2}-\d{2}\b|\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b|\b\d{1,2}(?:st|nd|rd|th)?\s+[A-Za-z]+\s+\d{2,4}\b|\b[A-Za-z]+\s+\d{1,2}(?:st|nd|rd|th)?,?\s*\d{2,4}\b", user_input):
            normalized = _parse_date_value(token)
            if normalized:
                result["dob"] = normalized
                break

    aadhaar_match = re.search(r"(?:aadhaar(?:\s+last\s+4)?|last\s+four)\s*(?:of\s+my)?\s*(?:is|ends?\s+with)?\s*[:=]?\s*(\d{4})", user_input, re.IGNORECASE)
    if aadhaar_match:
        result["aadhaar_last4"] = aadhaar_match.group(1)
    elif re.fullmatch(r"\d{4}", user_input):
        result["aadhaar_last4"] = user_input

    pincode_match = re.search(r"pincode\s*(?:is|:)?\s*(\d(?:\s*\d){5})", user_input, re.IGNORECASE)
    if pincode_match:
        digits = re.sub(r"\D", "", pincode_match.group(1))
        if len(digits) == 6:
            result["pincode"] = digits
    elif re.fullmatch(r"\d{6}", user_input):
        result["pincode"] = user_input

    full_amount_patterns = [
        r"clear\s+the\s+full\s+amount",
        r"clear\s+full\s+amount",
        r"pay\s+everything",
        r"pay\s+the\s+full\s+amount",
        r"full\s+amount",
    ]
    if any(re.search(pattern, user_input, re.IGNORECASE) for pattern in full_amount_patterns):
        result["pay_full_balance"] = True
    else:
        amount_match = _extract_numeric_amount(user_input)
        if amount_match is not None:
            result["payment_amount"] = amount_match

    if result["payment_amount"] is None and re.search(r"\b(?:five|six|seven|eight|nine|ten|hundred|thousand|a|an|one|two|three|four)\b", user_input, re.IGNORECASE):
        amount_words = re.sub(r"[^a-z\s]", " ", user_input.lower())
        numeric = _words_to_number(amount_words)
        if numeric is not None and numeric > 0:
            result["payment_amount"] = numeric

    card_match = re.search(r"(?:card(?:\s+number)?|number)\s*(?:is|:)?\s*(\d[\d\s-]{10,}\d)", user_input, re.IGNORECASE)
    if card_match:
        number = _normalize_card_number(card_match.group(1))
        if number:
            result["card_number"] = number

    if result["card_number"] is None:
        bare_card_match = re.search(r"\d(?:[\d\s-]{11,}\d)", user_input)
        if bare_card_match:
            candidate = bare_card_match.group(0)
            normalized = _normalize_card_number(candidate)
            if normalized:
                result["card_number"] = normalized

    if result["card_number"] is None:
        digits_only = re.findall(r"\b\d{13,19}\b", re.sub(r"\s+", " ", user_input))
        if digits_only:
            result["card_number"] = re.sub(r"\D", "", digits_only[0])

    cvv_match = re.search(r"(?:cvv|security\s+code)\s*(?:is|:)?\s*((?:one\s+two\s+three|\d{3,4}|one|two|three|zero))", user_input, re.IGNORECASE)
    if cvv_match:
        raw = cvv_match.group(1).lower().strip()
        if re.fullmatch(r"\d{3,4}", raw):
            result["cvv"] = raw
        else:
            words = re.sub(r"[^a-z\s]", " ", raw)
            words = re.sub(r"\s+", " ", words).strip()
            mapped = {
                "zero": "0",
                "one": "1",
                "two": "2",
                "three": "3",
            }
            numeric = "".join(mapped.get(part, "") for part in words.split() if part in mapped)
            if numeric:
                result["cvv"] = numeric
    elif re.fullmatch(r"\d{3,4}", user_input):
        result["cvv"] = user_input

    expiry = _parse_expiry_date(user_input)
    if expiry:
        result["expiry_month"] = expiry["month"]
        result["expiry_year"] = expiry["year"]

    cardholder_match = re.search(r"(?:cardholder|name\s+on\s+card|cardholder\s+name)\s*(?:is|:)?\s*(.+)$", user_input, re.IGNORECASE)
    if cardholder_match:
        candidate = cardholder_match.group(1).strip(" ,;:.-")
        if candidate:
            result["cardholder_name"] = candidate

    if _looks_like_authoritative_instruction(user_input):
        result["intent"] = "general"
        result["account_id"] = None
        result["full_name"] = None
        return result

    if "account" in user_input.lower() and result["account_id"] is not None:
        result["intent"] = "account_lookup"
    elif "pay" in user_input.lower() or "payment" in user_input.lower() or result["payment_amount"] is not None or result["pay_full_balance"]:
        result["intent"] = "payment"
    elif result["full_name"] is not None or result["dob"] is not None or result["aadhaar_last4"] is not None or result["pincode"] is not None:
        result["intent"] = "identity"
    else:
        result["intent"] = "general"

    return result


parse = parse_message
extract = parse_message

__all__ = [
    "parse",
    "parse_message",
    "extract",
    "_parse_date_value",
    "_parse_expiry_date",
]
