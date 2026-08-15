from __future__ import annotations

from typing import Any, Dict, Optional

from src.models import AgentState

DEFAULT_STATE = AgentState.WAITING_FOR_ACCOUNT_ID


class ConversationState:
    """Explicit state machine for the payment conversation."""

    LEGAL_TRANSITIONS = {
        AgentState.WAITING_FOR_ACCOUNT_ID: {AgentState.WAITING_FOR_IDENTITY, AgentState.VERIFICATION_LOCKED, AgentState.CLOSED},
        AgentState.WAITING_FOR_IDENTITY: {AgentState.WAITING_FOR_IDENTITY, AgentState.VERIFIED, AgentState.VERIFICATION_LOCKED, AgentState.CLOSED},
        AgentState.VERIFIED: {AgentState.WAITING_FOR_AMOUNT, AgentState.CLOSED, AgentState.WAITING_FOR_IDENTITY},
        AgentState.WAITING_FOR_AMOUNT: {AgentState.WAITING_FOR_CARD_DETAILS, AgentState.CLOSED, AgentState.VERIFIED},
        AgentState.WAITING_FOR_CARD_DETAILS: {AgentState.READY_TO_PAY, AgentState.WAITING_FOR_AMOUNT, AgentState.CLOSED},
        AgentState.READY_TO_PAY: {AgentState.PROCESSING_PAYMENT, AgentState.WAITING_FOR_CARD_DETAILS, AgentState.CLOSED},
        AgentState.PROCESSING_PAYMENT: {AgentState.SUCCESS, AgentState.PAYMENT_RETRY, AgentState.CLOSED},
        AgentState.PAYMENT_RETRY: {AgentState.WAITING_FOR_AMOUNT, AgentState.WAITING_FOR_CARD_DETAILS, AgentState.CLOSED},
        AgentState.SUCCESS: {AgentState.CLOSED},
        AgentState.VERIFICATION_LOCKED: {AgentState.CLOSED},
        AgentState.CLOSED: set(),
    }

    def __init__(self, state: AgentState = DEFAULT_STATE, context: Optional[Dict[str, Any]] = None):
        self.state = state
        self.context: Dict[str, Any] = context if context is not None else {}
        self.payment_context: Dict[str, Any] = {}
        self.candidate_info: Dict[str, Any] = {}
        self.verification_attempts = 0
        self.transaction_id: Optional[str] = None
        self.payment_completed = False
        self.closed = self.state == AgentState.CLOSED
        self.last_message = ""

    @property
    def can_verify(self) -> bool:
        return (
            self.state in {AgentState.WAITING_FOR_ACCOUNT_ID, AgentState.WAITING_FOR_IDENTITY}
            and not self.is_closed
            and self.verification_attempts < 3
        )

    @property
    def is_verified(self) -> bool:
        return self.state in {
            AgentState.VERIFIED,
            AgentState.WAITING_FOR_AMOUNT,
            AgentState.WAITING_FOR_CARD_DETAILS,
            AgentState.READY_TO_PAY,
            AgentState.PROCESSING_PAYMENT,
            AgentState.SUCCESS,
        }

    @property
    def can_reveal_balance(self) -> bool:
        return self.is_verified and not self.is_closed

    @property
    def can_collect_payment(self) -> bool:
        return self.is_verified and not self.payment_completed and not self.is_closed

    @property
    def can_process_payment(self) -> bool:
        return (
            self.is_verified
            and not self.payment_completed
            and not self.is_closed
            and "amount" in self.payment_context
        )

    @property
    def is_closed(self) -> bool:
        return self.closed or self.state == AgentState.CLOSED

    def transition_to(self, new_state: AgentState) -> AgentState:
        allowed = self.LEGAL_TRANSITIONS.get(self.state, set())
        if new_state not in allowed:
            raise ValueError(f"Illegal state transition from {self.state.value} to {new_state.value}")

        self.state = new_state
        self.closed = self.state == AgentState.CLOSED
        if self.state == AgentState.CLOSED:
            self.closed = True
        return self.state

    def record_successful_payment(self, transaction_id: str) -> None:
        self.transaction_id = transaction_id
        self.payment_completed = True
        # Move through PROCESSING_PAYMENT to SUCCESS to respect legal transitions
        if AgentState.PROCESSING_PAYMENT in self.LEGAL_TRANSITIONS.get(self.state, set()):
            self.transition_to(AgentState.PROCESSING_PAYMENT)
        # finally mark success
        if AgentState.SUCCESS in self.LEGAL_TRANSITIONS.get(self.state, set()):
            self.transition_to(AgentState.SUCCESS)
        else:
            # fallback: set state directly (last resort)
            self.state = AgentState.SUCCESS
            self.closed = True

    def register_candidate(self, key: str, value: Any) -> None:
        self.candidate_info[key] = value
        if key != "payment_context":
            self.context[key] = value

    def __repr__(self) -> str:
        return f"ConversationState(state={self.state.value}, verification_attempts={self.verification_attempts}, payment_completed={self.payment_completed})"
