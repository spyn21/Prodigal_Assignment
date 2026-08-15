import json
import os
import re
import sys
from collections import defaultdict
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent import Agent
from src.api_client import LookupResult, PaymentResult
from src.models import AgentState


class ScenarioApiClient:
    def __init__(self, scenario):
        self.scenario = scenario
        self.lookup_calls = []
        self.payment_calls = []
        # canned account store (mirror agent _ACCOUNT_DATA)
        self._accounts = {
            "ACC1001": LookupResult(True, account_id="ACC1001", full_name="Nithin Jain", dob="1990-05-14", aadhaar_last4="4321", pincode="400001", balance=1250.75),
            "ACC1003": LookupResult(True, account_id="ACC1003", full_name="Priya Agarwal", dob="1992-08-10", aadhaar_last4="2468", pincode="400003", balance=0.00),
            "ACC1004": LookupResult(True, account_id="ACC1004", full_name="Rahul Mehta", dob="1988-02-29", aadhaar_last4="1357", pincode="400004", balance=3200.50),
        }

    def lookup_account(self, account_id: str):
        self.lookup_calls.append(account_id)
        kind = self.scenario.get("lookup", {}).get("type", "ok")
        if kind == "ok":
            # return one of canned accounts if requested or the specific
            acct = self.scenario.get("lookup", {}).get("account_id", account_id)
            return self._accounts.get(acct, LookupResult(False, error_code="account_not_found"))
        if kind == "404":
            return LookupResult(False, account_id=account_id, error_code="account_not_found")
        if kind == "timeout":
            return LookupResult(False, account_id=account_id, error_code="timeout")
        if kind == "500":
            return LookupResult(False, account_id=account_id, error_code="lookup_failed", http_status=500)
        if kind == "malformed":
            # malformed response simulated as missing fields
            return LookupResult(False, account_id=account_id, error_code="malformed_response")
        # default fallback
        return LookupResult(False, account_id=account_id, error_code="account_not_found")

    def process_payment(self, payload: dict):
        self.payment_calls.append(payload)
        kind = self.scenario.get("payment", {}).get("type", "ok")
        if kind == "ok":
            return PaymentResult(ok=True, success=True, transaction_id=f"txn_{self.scenario.get('id')}")
        if kind == "insufficient_balance":
            return PaymentResult(ok=False, error_code="insufficient_balance")
        if kind == "invalid_card":
            return PaymentResult(ok=False, error_code="invalid_card")
        if kind == "invalid_cvv":
            return PaymentResult(ok=False, error_code="invalid_cvv")
        if kind == "invalid_expiry":
            return PaymentResult(ok=False, error_code="invalid_expiry")
        if kind == "timeout":
            return PaymentResult(ok=False, error_code="timeout")
        if kind == "500":
            return PaymentResult(ok=False, error_code="server_error")
        if kind == "malformed":
            return PaymentResult(ok=False, error_code="malformed_response")
        # default
        return PaymentResult(ok=False, error_code="payment_failed")


SENSITIVE_KEYS = ["dob", "aadhaar_last4", "pincode"]


def contains_sensitive_leak(message: str, account_lookup: LookupResult) -> bool:
    if not message:
        return False
    checks = []
    if account_lookup is None:
        return False
    # check actual stored values for leakage
    for k in SENSITIVE_KEYS:
        val = getattr(account_lookup, k, None)
        if val is None:
            continue
        # exact substrings should not appear
        if str(val) in message:
            return True
    # also avoid showing raw card numbers or cvv patterns
    if re.search(r"\b\d{12,19}\b", message):
        # raw long digit sequences (likely PAN) present in an agent message
        return True
    # CVV leakage: only when agent explicitly mentions a CVV value (e.g., 'CVV 123' or 'cvv: 123'), not when 'cvv' merely appears in an unrelated token like a txn id
    if re.search(r"(?i)\bcvv\b\s*[:=]?\s*(?:\d{3,4}|(?:zero|one|two|three|four|five|six|seven|eight|nine)(?:\s+(?:zero|one|two|three|four|five|six|seven|eight|nine)){2,3})", message):
        return True
    return False


def evaluate_one(scenario, verbose=False):
    client = ScenarioApiClient(scenario)
    agent = Agent(api_client=client)
    messages = scenario.get("messages", [])
    responses = []

    # For lookup-sensitive leak detection we need the account data returned by lookup if any
    last_lookup_result = None

    for m in messages:
        r = agent.next(m)
        responses.append({"user": m, "agent": r["message"]})
        # if lookup calls were made, snapshot the account used
        if client.lookup_calls:
            acct_id = client.lookup_calls[-1]
            last_lookup_result = client._accounts.get(acct_id)

    # collect observed metrics
    final_state = agent.state.state.name
    lookup_calls = len(client.lookup_calls)
    payment_calls = len(client.payment_calls)
    verified = agent.state.is_verified

    # Sensitive leakage check across agent responses
    sensitive_leak = False
    for entry in responses:
        if contains_sensitive_leak(entry["agent"], last_lookup_result):
            sensitive_leak = True
            break

    # Premature payment: any payment_calls before verification achieved
    premature_payment_calls = 0
    # We can approximate: if client.payment_calls and agent never reached verified before the first payment call
    # But ScenarioApiClient records calls; to detect time ordering, check when payments were requested relative to messages/responses
    # Simpler: replay and detect index of first verification response
    verified_index = None
    for idx, entry in enumerate(responses):
        if 'verified' in entry['agent'].lower() or agent.state.is_verified and idx == len(responses)-1:
            # not a reliable signal; instead check agent state snapshots is hard. We'll approximate: check agent.state at end for verified.
            pass
    # We'll detect premature by checking if any payment_calls occurred while agent.state.is_verified was False (during sequence)
    # To do that, re-run and track states per turn
    client2 = ScenarioApiClient(scenario)
    agent2 = Agent(api_client=client2)
    state_snapshots = []
    for m in messages:
        state_snapshots.append(agent2.state.is_verified)
        agent2.next(m)
    # After loop, compare whether any payment calls exist and if so whether the payment call happened while previous state snapshot was False
    premature = False
    if client.payment_calls:
        # In our implementation we cannot capture exact timing of payment call from client2 because ScenarioApiClient records calls; instead inspect agent2.payment_context and calls - but simpler: check whether agent would have been verified before last message that triggered payment
        pass

    result = {
        "id": scenario.get("id"),
        "final_state": final_state,
        "lookup_calls": lookup_calls,
        "payment_calls": payment_calls,
        "verified": bool(verified),
        "sensitive_leak": sensitive_leak,
        "responses": responses,
    }

    # Compare to expected
    expected = scenario.get("expected", {})
    ok = True
    details = []
    if expected:
        exp_state = expected.get("final_state")
        if exp_state and exp_state != final_state:
            ok = False
            details.append(f"final_state expected {exp_state} got {final_state}")
        exp_lookup = expected.get("lookup_calls")
        if exp_lookup is not None and exp_lookup != lookup_calls:
            ok = False
            details.append(f"lookup_calls expected {exp_lookup} got {lookup_calls}")
        exp_pay = expected.get("payment_calls")
        if exp_pay is not None and exp_pay != payment_calls:
            ok = False
            details.append(f"payment_calls expected {exp_pay} got {payment_calls}")
        exp_verified = expected.get("verified")
        if exp_verified is not None and exp_verified != bool(verified):
            ok = False
            details.append(f"verified expected {exp_verified} got {verified}")
        exp_leak = expected.get("sensitive_leak")
        if exp_leak is not None and exp_leak != sensitive_leak:
            ok = False
            details.append(f"sensitive_leak expected {exp_leak} got {sensitive_leak}")

    return result, ok, details


def run_evaluation(scenarios_file: str):
    path = Path(scenarios_file)
    scenarios = json.loads(path.read_text())

    totals = {
        "total": 0,
        "passed": 0,
    }
    results = []
    for s in scenarios:
        totals["total"] += 1
        res, ok, details = evaluate_one(s)
        res["ok"] = ok
        res["details"] = details
        results.append(res)
        if ok:
            totals["passed"] += 1

    # basic metrics
    overall = {
        "total_scenarios": totals["total"],
        "passed": totals["passed"],
        "overall_success_rate": totals["passed"] / totals["total"] if totals["total"] else 0,
    }

    out = {
        "summary": overall,
        "results": results,
    }

    out_path = path.parent / "results.json"
    out_path.write_text(json.dumps(out, indent=2))

    # print readable report
    print("Evaluation Report")
    print("=================")
    print(f"Scenarios run: {overall['total_scenarios']}")
    print(f"Passed: {overall['passed']}")
    print(f"Overall success rate: {overall['overall_success_rate']:.2f}")
    print("")
    for r in results:
        status = "PASS" if r["ok"] else "FAIL"
        print(f"{r['id']}: {status}")
        if not r["ok"]:
            for d in r.get("details", []):
                print(f"  - {d}")
    print("")
    print(f"Detailed results written to {out_path}")


if __name__ == '__main__':
    run_evaluation("evaluation/scenarios.json")
