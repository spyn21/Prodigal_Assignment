Payment Collection AI Agent
===========================

1. Project overview
-------------------
This repository implements a deterministic, security-focused conversational agent that collects payments after identity verification. The Agent class exposes a single public API: Agent.next(user_input: str) -> {"message": str}. The system demonstrates a hybrid approach where deterministic parsers and validators control security-sensitive decisions while LLM-style components (if integrated) are constrained to extraction tasks only.

2. Key features
---------------
- Deterministic identity verification (exact-name + one secondary factor).
- Strict verification and payment gates; no payment before verification.
- Local validation of payment card fields (Luhn, expiry, CVV).
- Secure handling of sensitive data (redaction and clearing of PAN/CVV after use).
- API client abstraction with timeout, error mapping, and mockable interface.
- Evaluation harness for scenario-based functional and adversarial testing.

3. Architecture
---------------
- Agent (agent.py): orchestrates conversation, holds ConversationState, delegates parsing and API calls.
- Parsers/validators (src/): normalize and validate account IDs, dates, amounts, cards, CVV.
- API client (src/api_client.py): HTTP client for account lookup and payment processing with safe error handling.
- Payment logic (src/payment.py): amount parsing and preparing payment payloads.
- Verification (src/verification.py): deterministic identity verification logic.
- State machine (src/state.py): explicit legal transitions and security gates.
- Evaluation harness (evaluation/): scenario definitions and runner.

4. Project structure
--------------------
- agent.py - main Agent public interface
- src/ - library modules (api_client, payment, validators, verification, state, models)
- tests/ - pytest test suite including security and adversarial tests
- evaluation/ - evaluation scenarios and harness
- examples/ - sample conversation transcripts (added here)
- SECURITY.md - security controls and threat model
- DESIGN.md - design rationale and architecture

5. Setup
--------
Prerequisites: Python 3.10 or 3.11 (project uses typing features compatible with these versions).

6. Python version
-----------------
- Recommended: Python 3.10 or 3.11

7. Installation
---------------
Create a virtual environment and install test requirements (if any):

python -m venv .venv
.\.venv\Scripts\activate    # Windows
pip install -r requirements.txt  # if present; tests use standard library and pytest

Note: This project is intentionally dependency-light; only 'requests' and 'pytest' are used in tests.

8. Configuration
----------------
- config.py controls global constants such as MAX_VERIFICATION_ATTEMPTS and HTTP timeouts.
- The HttpAccountLookupClient uses BASE_URL in src/api_client.py.

9. Running CLI
--------------
There is no interactive CLI. Use the Agent.next() API or run tests/evaluation as shown below.

10. Using Agent.next()
----------------------
Example:

from agent import Agent
agent = Agent()
print(agent.next("Hi"))        # {"message": "Hi! Please provide your account ID."}
print(agent.next("ACC1001"))  # calls lookup, asks for identity

The Agent.next method processes exactly one user turn and returns a dict with a single "message" key.

11. Running tests
-----------------
Run the full test suite with pytest:

python -m pytest -q

Run security/adversarial tests only:

python -m pytest tests/test_security.py tests/test_prompt_injection.py -q

12. Running evaluation
----------------------
Run the scenario evaluation harness (uses mocked API client):

python evaluation/evaluate.py

It writes evaluation/results.json and prints a scenario-level report.

13. Verification rules
----------------------
- Identity verified only when:
  - Full name matches exactly (case-sensitive, exact string match)
  - AND at least one of: DOB, Aadhaar last4, or pincode matches exactly after normalization
- Max 3 failed verification attempts, then VERIFICATION_LOCKED.
- No fuzzy or LLM-based matching for identity.

14. LLM usage
-------------
LLMs (if plugged in) are constrained to extraction tasks (optional LLMInterpreter). The default DeterministicInterpreter is used in this submission. LLMs are never used to make security-sensitive decisions, comparisons, or authorizations.

15. Security
-----------
See SECURITY.md for detailed threat model, prompt-injection mitigations, data handling, and logging rules.

16. API integration
------------------
The project includes an HTTP client (src/api_client.py) that calls the provided account lookup and payment endpoints using requests with timeouts and robust error handling. The evaluation harness uses a mock ScenarioApiClient to avoid network calls during tests.

17. Assumptions
---------------
- External account lookup returns canonical authoritative data used only for verification comparisons.
- Payment API validates card/CVV/expiry and returns a transaction ID on success; the server does not persist balance changes (test harness mirrors this behavior).

18. Limitations
---------------
- No real LLM integration enabled by default. If integrated, ensure strict schema validation of all LLM outputs.
- Event-level ordering assertions (did payment happen before verification?) are approximated by the evaluator; an append-only agent event log would be required for precise forensic assertions.

Contact
-------
This project was created as part of a technical evaluation. For questions, inspect tests and documentation in the repository.
