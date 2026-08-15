from decimal import Decimal

from agent import Agent
from src.api_client import PaymentResult


class FakeApiClient:
    def __init__(self):
        self.calls = []

    def process_payment(self, payload):
        self.calls.append(payload)
        return PaymentResult(ok=True, success=True, transaction_id="txn_agent_1")


def test_agent_calls_process_payment_once_and_handles_success():
    client = FakeApiClient()
    agent = Agent(api_client=client)

    # prepare state as if lookup and verification already done
    agent.state.context['account_id'] = 'ACC1001'
    agent.state.context['balance'] = '1250.75'
    agent.state.context['full_name'] = 'Nithin Jain'
    from src.models import AgentState
    agent.state.transition_to(AgentState.WAITING_FOR_IDENTITY)
    agent.state.transition_to(AgentState.VERIFIED)

    # set amount and card details
    agent.state.payment_context['amount'] = Decimal('500')
    agent.state.payment_context['cardholder_name'] = 'Nithin Jain'
    agent.state.payment_context['card_number'] = '4532015112830366'
    agent.state.payment_context['cvv'] = '123'
    agent.state.payment_context['expiry_month'] = 12
    agent.state.payment_context['expiry_year'] = 2027

    # move through amount/card states to READY_TO_PAY
    from src.models import AgentState
    agent.state.transition_to(AgentState.WAITING_FOR_AMOUNT)
    agent.state.transition_to(AgentState.WAITING_FOR_CARD_DETAILS)
    agent.state.transition_to(AgentState.READY_TO_PAY)

    resp = agent.next('process payment')
    assert client.calls and len(client.calls) == 1
    assert agent.state.payment_completed is True
    assert agent.state.transaction_id == 'txn_agent_1'
    assert 'successful' in resp['message'].lower()

    # repeated attempt should not call API again
    resp2 = agent.next('process payment')
    assert len(client.calls) == 1
    assert 'already' in resp2['message'].lower()
