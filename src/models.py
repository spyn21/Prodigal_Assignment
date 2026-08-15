from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Optional


class AgentState(str, Enum):
    WAITING_FOR_ACCOUNT_ID = "WAITING_FOR_ACCOUNT_ID"
    WAITING_FOR_IDENTITY = "WAITING_FOR_IDENTITY"
    VERIFIED = "VERIFIED"
    WAITING_FOR_AMOUNT = "WAITING_FOR_AMOUNT"
    WAITING_FOR_CARD_DETAILS = "WAITING_FOR_CARD_DETAILS"
    READY_TO_PAY = "READY_TO_PAY"
    PROCESSING_PAYMENT = "PROCESSING_PAYMENT"
    PAYMENT_RETRY = "PAYMENT_RETRY"
    SUCCESS = "SUCCESS"
    VERIFICATION_LOCKED = "VERIFICATION_LOCKED"
    CLOSED = "CLOSED"


@dataclass
class PaymentContext:
    cardholder_name: Optional[str] = None
    card_number: Optional[str] = None
    cvv: Optional[str] = None
    expiry_month: Optional[int] = None
    expiry_year: Optional[int] = None
    amount: Optional[str] = None


@dataclass
class ConversationContext:
    account_id: Optional[str] = None
    full_name: Optional[str] = None
    dob: Optional[str] = None
    aadhaar_last4: Optional[str] = None
    pincode: Optional[str] = None
    candidate_info: Dict[str, Any] = field(default_factory=dict)
    payment_context: PaymentContext = field(default_factory=PaymentContext)
