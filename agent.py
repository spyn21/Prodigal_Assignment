from __future__ import annotations

import re
from typing import Any, Dict, Optional

from config import MAX_VERIFICATION_ATTEMPTS
from src.api_client import HttpAccountLookupClient
from src.input_interpreter import DeterministicInterpreter
from src.models import AgentState
from src.verification import verify_identity
from src.payment import prepare_payment_submission, redact_sensitive_fields
from src.responses import (
    ACCOUNT_PROMPT,
    CLOSED_MESSAGE,
    GREETING_MESSAGE,
    IDENTITY_PROMPT,
    VERIFIED_MESSAGE,
)
from src.state import ConversationState


class Agent:
    """Deterministic conversational payment agent core for Phase 1."""

    _ACCOUNT_DATA = {
        "ACC1001": {
            "full_name": "Nithin Jain",
            "dob": "1990-05-14",
            "aadhaar_last4": "4321",
            "pincode": "400001",
            "balance": "1250.75",
        },
        "ACC1002": {
            "full_name": "Rajarajeswari Balasubramaniam",
            "dob": "1985-11-23",
            "aadhaar_last4": "9876",
            "pincode": "400002",
            "balance": "540.00",
        },
        "ACC1003": {
            "full_name": "Priya Agarwal",
            "dob": "1992-08-10",
            "aadhaar_last4": "2468",
            "pincode": "400003",
            "balance": "0.00",
        },
        "ACC1004": {
            "full_name": "Rahul Mehta",
            "dob": "1988-02-29",
            "aadhaar_last4": "1357",
            "pincode": "400004",
            "balance": "3200.50",
        },
    }

    def __init__(self, api_client: Optional[HttpAccountLookupClient] = None) -> None:
        self.state = ConversationState()
        self.api_client = api_client or HttpAccountLookupClient()
        self.interpreter = DeterministicInterpreter()

    def next(self, user_input: str) -> dict:
        """Process exactly one conversation turn.

        Args:
            user_input: plain user message.

        Returns:
            {"message": str}
        """
        if user_input is None:
            user_input = ""

        user_input = str(user_input).strip()

        # User input is untrusted candidate data; the interpreter extracts
        # candidates only. Authorization remains in deterministic state logic.
        _ = self.interpreter.interpret(user_input)

        if self.state.payment_completed:
            return {"message": f"Payment already completed for transaction {self.state.transaction_id}. No duplicate charges are allowed."}

        if self.state.is_closed:
            return {"message": CLOSED_MESSAGE}

        if not user_input:
            return {"message": self._default_message()}

        if self.state.state == AgentState.WAITING_FOR_ACCOUNT_ID:
            account_id = self._extract_account_id(user_input)
            if account_id is None:
                return {"message": GREETING_MESSAGE}

            lookup_result = self.api_client.lookup_account(account_id)
            if not lookup_result.ok:
                if lookup_result.error_code == "account_not_found":
                    return {"message": "No account found with the provided account_id. Please try again."}
                return {"message": "I could not access the account information right now. Please try again."}

            # Store the authoritative lookup-account response in conversation state.
            # Verification must use this API data, not a local hardcoded account table.
            self.state.context["account_id"] = lookup_result.account_id
            self.state.context["account_data"] = {
                "account_id": lookup_result.account_id,
                "full_name": lookup_result.full_name,
                "dob": lookup_result.dob,
                "aadhaar_last4": lookup_result.aadhaar_last4,
                "pincode": lookup_result.pincode,
                "balance": lookup_result.balance,
            }
            self.state.context["balance"] = lookup_result.balance
            self.state.transition_to(AgentState.WAITING_FOR_IDENTITY)

            # capture any identity fields supplied in the same message (out-of-order / multi-field)
            self._store_identity_candidates(user_input)
            if self._verify_identity():
                self.state.transition_to(AgentState.VERIFIED)
                return {"message": VERIFIED_MESSAGE}

            return {"message": ACCOUNT_PROMPT}

        if self.state.state == AgentState.WAITING_FOR_IDENTITY:
            self._store_identity_candidates(user_input)
            if self._verify_identity():
                self.state.transition_to(AgentState.VERIFIED)
                return {"message": VERIFIED_MESSAGE}

            self.state.verification_attempts += 1
            if self.state.verification_attempts >= MAX_VERIFICATION_ATTEMPTS:
                self.state.transition_to(AgentState.VERIFICATION_LOCKED)
                self.state.closed = True
                return {"message": "Verification failed too many times. This conversation is locked for security reasons."}

            return {"message": IDENTITY_PROMPT}

        if self.state.state == AgentState.VERIFIED:
            amount = self._extract_amount(user_input)
            if amount is not None:
                self.state.payment_context["amount"] = amount
                # move to WAITING_FOR_AMOUNT first (legal transition)
                if self.state.state != AgentState.WAITING_FOR_AMOUNT:
                    self.state.transition_to(AgentState.WAITING_FOR_AMOUNT)
                # capture any card details supplied in same message
                self._store_card_candidate(user_input)
                if self._card_payload_complete():
                    # move through card details state before READY_TO_PAY
                    self.state.transition_to(AgentState.WAITING_FOR_CARD_DETAILS)
                    self.state.transition_to(AgentState.READY_TO_PAY)
                    return {"message": "Payment details are ready. Say 'process payment' to complete the charge."}
                # otherwise ask for missing card details
                self.state.transition_to(AgentState.WAITING_FOR_CARD_DETAILS)
                return {"message": "Please provide the cardholder name, card number, CVV, and expiry date."}
            return {"message": "Identity has been verified. Please provide the payment amount."}

        if self.state.state == AgentState.WAITING_FOR_AMOUNT:
            amount = self._extract_amount(user_input)
            if amount is not None:
                self.state.payment_context["amount"] = amount
                # capture any card details in same message
                self._store_card_candidate(user_input)
                # move to card details state
                if self.state.state != AgentState.WAITING_FOR_CARD_DETAILS:
                    self.state.transition_to(AgentState.WAITING_FOR_CARD_DETAILS)
                if self._card_payload_complete():
                    self.state.transition_to(AgentState.READY_TO_PAY)
                    return {"message": "Payment details are ready. Say 'process payment' to complete the charge."}
                return {"message": "Please provide the cardholder name, card number, CVV, and expiry date."}
            return {"message": "Please provide a valid payment amount."}

        # Trigger payment processing when user explicitly requests it and all gates are satisfied
        if self.state.state == AgentState.READY_TO_PAY:
            # explicit intent words to confirm charging
            if any(tok in user_input.lower() for tok in ["process payment", "process", "confirm", "pay now", "charge", "pay"]):
                return self._attempt_payment()

        if self.state.state in {AgentState.WAITING_FOR_CARD_DETAILS, AgentState.READY_TO_PAY}:
            self._store_card_candidate(user_input)
            if self._card_payload_complete():
                if self.state.state != AgentState.READY_TO_PAY:
                    self.state.transition_to(AgentState.READY_TO_PAY)
                return {"message": "Payment details are ready. Say 'process payment' to complete the charge."}
            return {"message": "Please provide the full card details to continue safely."}

        if self.state.state == AgentState.SUCCESS:
            self.state.closed = True
            return {"message": "Payment was completed successfully. This conversation is now closed."}

        return {"message": self._default_message()}

    def _default_message(self) -> str:
        if self.state.state == AgentState.WAITING_FOR_ACCOUNT_ID:
            return GREETING_MESSAGE
        if self.state.state == AgentState.WAITING_FOR_IDENTITY:
            return IDENTITY_PROMPT
        if self.state.is_verified:
            return "Identity has been verified. Please provide the payment amount."
        return "Your request is being processed."

    def _extract_account_id(self, user_input: str) -> Optional[str]:
        # Try to find common ACC patterns allowing spaces (ACC 1001) and normalize
        found = re.findall(r"ACC\s*\d{4}", user_input, flags=re.IGNORECASE)
        if found:
            cand = found[-1]
            return re.sub(r"\s+", "", cand).upper()
        # fallback: look for any account mention with contiguous id
        match = re.search(r"\b(?:account(?:\s+id)?|acct)\s*[:=#-]?\s*([A-Za-z0-9]+)\b", user_input, re.IGNORECASE)
        if match:
            candidate = match.group(1).upper()
            # normalize candidate if it looks like ACC + digits with gap
            normalized = re.sub(r"\s+", "", candidate)
            if re.fullmatch(r"ACC\d{4}", normalized):
                return normalized
            if re.fullmatch(r"[A-Z0-9]+", candidate):
                return candidate
        match = re.search(r"\b(ACC\d{4})\b", user_input, re.IGNORECASE)
        if match:
            return match.group(1).upper()
        return None

    def _extract_amount(self, user_input: str) -> Optional[object]:
        # Detect explicit full-balance intents
        if re.search(r"\b(?:full\s+amount|pay\s+everything|clear\s+the\s+full\s+amount|full amount)\b", user_input, re.IGNORECASE):
            return "__FULL_BALANCE__"
        # Try simple numeric capture
        match = re.search(r"(?:rs\.?\s*|rupees?\s*|inr\s*)?(\d+(?:\.\d{1,2})?)", user_input, re.IGNORECASE)
        if match:
            return match.group(1)
        # Fall back to the payment parser which understands words like 'five hundred'
        try:
            from src.payment import parse_payment_amount
            parsed = parse_payment_amount(user_input)
            if parsed and parsed.is_valid:
                return parsed.amount
        except Exception:
            pass
        return None

    def _store_identity_candidates(self, user_input: str) -> None:
        text = user_input.strip()
        if not text:
            return

        lower_text = text.lower()

        # Name
        if any(kw in lower_text for kw in ("my name is", "my full name is", "full name is", "name is")):
            remainder = re.split(r"(?:my\s+full\s+name\s+is|my\s+name\s+is|full\s+name\s+is|name\s+is)", text, flags=re.IGNORECASE, maxsplit=1)[1].strip()
            remainder = re.split(r"\s+(?:and\s+)?(?:dob|date of birth|aadhaar|pincode)\b", remainder, flags=re.IGNORECASE)[0]
            remainder = remainder.strip(" ,;:.-")
            if remainder:
                self.state.context["full_name"] = remainder
                self.state.candidate_info["full_name"] = remainder

        # DOB - prefer the last mentioned date in the message (handle corrections)
        # Find all date-like tokens and pick the last valid normalized one
        # Find date-like tokens using prioritized patterns and prefer the most specific and latest occurrence.
        patterns = [
            (r"\d{4}-\d{2}-\d{2}", 5),
            (r"\d{1,2}[/-]\d{1,2}[/-]\d{2,4}", 5),
            (r"\d{1,2}(?:st|nd|rd|th)?\s+[A-Za-z]+\s+\d{2,4}", 5),
            # month name, day, full 4-digit year (avoid ambiguous splits like 'May 1990')
            (r"[A-Za-z]+\s+\d{1,2},?\s+\d{4}", 5),
            # month + year only (less specific)
            (r"[A-Za-z]+\s+\d{4}", 2),
        ]
        from src.validators import normalize_date
        candidates = []  # tuples of (score, start_index, token, normalized)
        for pat, score in patterns:
            for m in re.finditer(pat, text):
                token = m.group(0)
                norm = normalize_date(token)
                if norm:
                    candidates.append((score, m.start(), token, norm))
        if candidates:
            # pick highest score, then latest occurrence (max start index)
            candidates.sort(key=lambda x: (x[0], x[1]))
            best = candidates[-1]
            self.state.context["dob"] = best[3]
            self.state.candidate_info["dob"] = best[3]

        # Aadhaar
        if "aadhaar" in lower_text or "last four" in lower_text:
            aadhaar_match = re.search(r"(?:aadhaar(?:\s+last\s+4)?|last\s+four)\s*(?:of\s+my)?\s*[:=]?\s*(\d{4})", text, re.IGNORECASE)
            if aadhaar_match:
                self.state.context["aadhaar_last4"] = aadhaar_match.group(1)
                self.state.candidate_info["aadhaar_last4"] = self.state.context["aadhaar_last4"]

        # Pincode
        if "pincode" in lower_text:
            # accept spaced digits like '4 0 0 0 0 1' as well
            pincode_match = re.search(r"pincode\s*(?:[:=]?|is)?\s*([0-9\s\-]{6,})", text, re.IGNORECASE)
            if pincode_match:
                digits = re.sub(r"\D", "", pincode_match.group(1))
                if len(digits) >= 6:
                    digits = digits[:6]
                    self.state.context["pincode"] = digits
                    self.state.candidate_info["pincode"] = digits

        # Direct name detection fallback if not already set
        if "full_name" not in self.state.context and not re.search(r"\b(?:account|dob|aadhaar|pincode|cvv|card|amount)\b", text, re.IGNORECASE):
            direct_name = re.search(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,5}\b", text)
            if direct_name:
                self.state.context["full_name"] = direct_name.group(0).strip()
                self.state.candidate_info["full_name"] = self.state.context["full_name"]

    def _get_authoritative_account(self) -> Optional[dict]:
        account_data = self.state.context.get("account_data")
        if not isinstance(account_data, dict):
            return None

        required = {"full_name", "dob", "aadhaar_last4", "pincode"}
        if not required.issubset(account_data):
            return None

        account_id = self.state.context.get("account_id")
        return {
            "account_id": account_id,
            "full_name": account_data.get("full_name"),
            "dob": account_data.get("dob"),
            "aadhaar_last4": account_data.get("aadhaar_last4"),
            "pincode": account_data.get("pincode"),
            "balance": account_data.get("balance", self.state.context.get("balance")),
        }

    def _verify_identity(self) -> bool:
        account = self._get_authoritative_account()
        if account is None:
            return False

        # Candidate information must come from user-provided candidate_info only.
        candidate = {
            "full_name": self.state.candidate_info.get("full_name"),
            "dob": self.state.candidate_info.get("dob"),
            "aadhaar_last4": self.state.candidate_info.get("aadhaar_last4"),
            "pincode": self.state.candidate_info.get("pincode"),
        }
        verification = verify_identity(account, candidate)
        return verification.verified

    def _normalize_date(self, value: str) -> str:
        value = value.strip()
        if re.fullmatch(r"\d{1,2}[/-]\d{1,2}[/-]\d{2,4}", value):
            parts = re.split(r"[/-]", value)
            if len(parts) == 3:
                if len(parts[2]) == 2:
                    year = "19" + parts[2] if int(parts[2]) < 50 else "20" + parts[2]
                else:
                    year = parts[2]
                month = int(parts[0]) if len(parts[0]) > 1 else int(parts[0])
                day = int(parts[1]) if len(parts[1]) > 1 else int(parts[1])
                return f"{year}-{month:02d}-{day:02d}"
        if re.fullmatch(r"\d{1,2}\s+[A-Za-z]+\s+\d{2,4}", value):
            month_map = {
                "jan": "01", "january": "01", "feb": "02", "february": "02",
                "mar": "03", "march": "03", "apr": "04", "april": "04",
                "may": "05", "jun": "06", "june": "06", "jul": "07", "july": "07",
                "aug": "08", "august": "08", "sep": "09", "sept": "09", "september": "09",
                "oct": "10", "october": "10", "nov": "11", "november": "11",
                "dec": "12", "december": "12",
            }
            parts = value.split()
            if len(parts) >= 3:
                day = int(parts[0])
                month = month_map[parts[1].lower()]
                year = parts[2]
                if len(year) == 2:
                    year = "19" + year if int(year) < 50 else "20" + year
                return f"{year}-{month}-{day:02d}"
        return value

    def _store_card_candidate(self, user_input: str) -> None:
        text = user_input.strip()
        if not text:
            return

        if "cardholder" in text.lower() or "name on card" in text.lower():
            name = re.search(r"(?:cardholder|name on card)\s*(?:is\s*)?[:=]?\s*(.+)", text, re.IGNORECASE)
            if name:
                # strip leading 'is' if captured
                val = name.group(1).strip()
                if val.lower().startswith("is "):
                    val = val[3:].strip()
                # drop trailing digit sequences or comma-separated extra fields (card number) if present
                val = re.split(r"\d", val, maxsplit=1)[0].strip(" ,;:")
                self.state.payment_context["cardholder_name"] = val

        number_match = re.search(r"(?:card\s+number|number)\s*[:=]?\s*(\d[\d\s-]{10,}\d)", text, re.IGNORECASE)
        if number_match:
            cleaned = re.sub(r"[\s-]+", "", number_match.group(1))
            self.state.payment_context["card_number"] = cleaned
        else:
            # fallback: detect a bare long card-number-like sequence in the message
            bare = re.search(r"(\d[\d\s-]{12,}\d)", text)
            if bare:
                cleaned = re.sub(r"[\s-]+", "", bare.group(1))
                if 13 <= len(cleaned) <= 19:
                    self.state.payment_context["card_number"] = cleaned

        cvv_match = re.search(r"(?:cvv)\s*[:=]?\s*(\d{3,4})", text, re.IGNORECASE)
        if cvv_match:
            self.state.payment_context["cvv"] = cvv_match.group(1)
        else:
            # support spelled-out digits like 'one two three' after 'cvv'
            if re.search(r"\bcvv\b", text, re.IGNORECASE):
                words = re.findall(r"(zero|one|two|three|four|five|six|seven|eight|nine)", text, re.IGNORECASE)
                if words:
                    mapping = {
                        "zero": "0", "one": "1", "two": "2", "three": "3",
                        "four": "4", "five": "5", "six": "6", "seven": "7",
                        "eight": "8", "nine": "9",
                    }
                    cvv = ''.join(mapping[w.lower()] for w in words)
                    if 3 <= len(cvv) <= 4:
                        self.state.payment_context["cvv"] = cvv

        expiry_match = re.search(r"(?:expires?|expiry)\s*(?:on)?\s*(\d{1,2})[/\- ]?(\d{2,4})?", text, re.IGNORECASE)
        if expiry_match:
            month = expiry_match.group(1)
            year = expiry_match.group(2)
            if year:
                if len(year) == 2:
                    year = f"20{year}" if int(year) < 50 else f"19{year}"
                self.state.payment_context["expiry_month"] = int(month)
                self.state.payment_context["expiry_year"] = int(year)
        else:
            # try numeric expiry like '12/2027' or '12-27'
            bare_numeric = re.search(r"\b(\d{1,2})[\/\-](\d{2,4})\b", text)
            if bare_numeric:
                m = int(bare_numeric.group(1))
                y = bare_numeric.group(2)
                if len(y) == 2:
                    y = f"20{y}" if int(y) <= 50 else f"19{y}"
                self.state.payment_context["expiry_month"] = int(m)
                self.state.payment_context["expiry_year"] = int(y)
            else:
                # try month name pattern like 'expires December 2027' or 'December 2027'
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
                month_name_match = re.search(r"(?:expires?|expiry)\s*(?:on)?\s*([A-Za-z]+)\s+(\d{2,4})", text, re.IGNORECASE)
                if not month_name_match:
                    month_name_match = re.search(r"([A-Za-z]+)\s+(\d{2,4})", text, re.IGNORECASE)
                if month_name_match:
                    mname = month_name_match.group(1).lower()
                    m = month_names.get(mname)
                    if m is not None:
                        y = int(month_name_match.group(2))
                        if len(month_name_match.group(2)) == 2:
                            y = 2000 + y if y <= 50 else 1900 + y
                        self.state.payment_context["expiry_month"] = int(m)
                        self.state.payment_context["expiry_year"] = int(y)

    def _card_payload_complete(self) -> bool:
        required = ["cardholder_name", "card_number", "cvv", "expiry_month", "expiry_year"]
        return all(key in self.state.payment_context for key in required)

    def _attempt_payment(self) -> dict:
        # Security gates
        if not self.state.can_process_payment:
            return {"message": "Payment is not allowed in the current state."}

        if self.state.payment_completed:
            return {"message": f"Payment already completed for transaction {self.state.transaction_id}. No duplicate charges are allowed."}

        account_id = self.state.context.get("account_id")
        balance = None
        if "balance" in self.state.context:
            try:
                from decimal import Decimal

                balance = Decimal(str(self.state.context.get("balance")))
            except Exception:
                balance = None

        amount = self.state.payment_context.get("amount")
        cardholder_name = self.state.payment_context.get("cardholder_name")
        card_number = self.state.payment_context.get("card_number")
        cvv = self.state.payment_context.get("cvv")
        expiry_month = self.state.payment_context.get("expiry_month")
        expiry_year = self.state.payment_context.get("expiry_year")

        # Build and validate payload without directly sending raw sensitive fields to logs
        # Decide whether full-balance was requested
        full_balance_flag = amount == "__FULL_BALANCE__"
        payload = prepare_payment_submission(
            account_id=account_id,
            amount=amount,
            balance=balance,
            cardholder_name=cardholder_name,
            card_number=card_number,
            cvv=cvv,
            expiry=(expiry_month, expiry_year),
            api_client=None,
            full_balance_requested=full_balance_flag,
        )

        if payload is None:
            return {"message": "Payment details are invalid. Please re-enter the required fields."}

        # Call API
        try:
            result = self.api_client.process_payment(payload)
        except Exception:
            return {"message": "Payment could not be processed due to an unexpected error. Please try again later."}

        # Handle API response
        if result.ok and result.success and result.transaction_id:
            # store transaction id and mark complete
            self.state.record_successful_payment(result.transaction_id)
            # clear sensitive payment context
            for key in ["card_number", "cvv"]:
                if key in self.state.payment_context:
                    del self.state.payment_context[key]
            # prepare recap and close
            amount_str = str(payload.get("amount"))
            self.state.closed = True
            return {"message": f"Payment successful. Transaction ID: {result.transaction_id}. Amount charged: {amount_str}. Conversation closed."}

        # Map known errors
        err = getattr(result, "error_code", None)
        if err in {"invalid_amount", "insufficient_balance"}:
            # clear amount only
            if "amount" in self.state.payment_context:
                del self.state.payment_context["amount"]
            self.state.transition_to(AgentState.WAITING_FOR_AMOUNT)
            return {"message": "Payment amount rejected by the processor. Please provide a different amount."}

        if err in {"invalid_card", "invalid_cvv", "invalid_expiry"}:
            # clear only card sensitive fields
            for key in ["card_number", "cvv", "expiry_month", "expiry_year", "cardholder_name"]:
                if key in self.state.payment_context:
                    del self.state.payment_context[key]
            self.state.transition_to(AgentState.WAITING_FOR_CARD_DETAILS)
            return {"message": "Payment method rejected. Please re-enter card details."}

        if err == "account_not_found":
            # fatal
            self.state.transition_to(AgentState.CLOSED)
            return {"message": "Account not found. The conversation is closed."}

        # Other errors
        return {"message": "Payment failed. Please try again or contact support."}


__all__ = ["Agent"]
