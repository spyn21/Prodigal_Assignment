import pytest

from agent import Agent
from src.models import AgentState
from src.state import ConversationState


def test_agent_interface_exact_schema():
    agent = Agent()
    result = agent.next("Hi")
    assert isinstance(result, dict)
    assert set(result.keys()) == {"message"}
    assert isinstance(result["message"], str)


def test_state_persistence_across_turns():
    agent = Agent()
    first = agent.next("Hi")
    assert first["message"]

    second = agent.next("account id: ACC1001")
    assert second["message"]
    assert agent.state.context["account_id"] == "ACC1001"
    assert agent.state.state == AgentState.WAITING_FOR_IDENTITY

    third = agent.next("my name is Nithin Jain and DOB is 14 May 1990")
    assert agent.state.is_verified is True
    assert agent.state.state == AgentState.VERIFIED
    assert isinstance(third["message"], str)


def test_legal_transitions():
    state = ConversationState()
    state.transition_to(AgentState.WAITING_FOR_IDENTITY)
    assert state.state == AgentState.WAITING_FOR_IDENTITY

    state.transition_to(AgentState.VERIFIED)
    assert state.state == AgentState.VERIFIED


def test_illegal_transitions_are_blocked():
    state = ConversationState()
    with pytest.raises(ValueError):
        state.transition_to(AgentState.SUCCESS)


def test_verification_gate():
    state = ConversationState(state=AgentState.WAITING_FOR_IDENTITY)
    assert state.can_verify is True
    assert state.is_verified is False

    state.transition_to(AgentState.VERIFIED)
    assert state.can_verify is False
    assert state.is_verified is True


def test_payment_gate():
    state = ConversationState(state=AgentState.VERIFIED)
    assert state.can_collect_payment is True
    state.payment_context["amount"] = "100.00"
    assert state.can_process_payment is True

    state2 = ConversationState()
    assert state2.can_process_payment is False


def test_terminal_state_blocking():
    state = ConversationState()
    state.transition_to(AgentState.CLOSED)
    assert state.is_closed is True
    with pytest.raises(ValueError):
        state.transition_to(AgentState.WAITING_FOR_IDENTITY)


def test_duplicate_success_protection():
    agent = Agent()
    agent.state.payment_completed = True
    agent.state.transaction_id = "txn_123"
    agent.state.state = AgentState.SUCCESS

    response = agent.next("I want to pay again")
    assert "already" in response["message"].lower()
    assert agent.state.payment_completed is True
    assert agent.state.transaction_id == "txn_123"
