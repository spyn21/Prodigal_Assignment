REQUIREMENTS for Payment Collection AI Agent

Source used: IMPLEMENTATION_PLAN.md in repository (IMPLEMENTATION_PLAN.md appears to mirror the assignment). The authoritative PDF (Agent_Engineer_-_payment_agent_assignment.pdf) could not be read programmatically in this session; this REQUIREMENTS.md is produced from the repository plan and must be validated against the original PDF before implementation.

Purpose
- Convert the assignment into a formal engineering + evaluation contract.
- Organize requirements under seven evaluation dimensions.
- For each dimension provide: Requirement; Implementation expectation; Testable behavior; Failure condition; Evidence that should exist in the repository.
- Capture all hard requirements verbatim.
- Produce a traceability matrix mapping assignment requirements to code locations, test locations, and evaluation metrics.

---

Seven evaluation dimensions

1) Prompt Engineering

Requirement
- LLM usage must be strictly limited to structured field extraction. Prompts must require structured JSON outputs and explicitly forbid invented fields and actions.

Implementation expectation
- src/prompts.py module containing extraction prompt templates and a strict schema definition that the LLM must return (see example extraction schema in IMPLEMENTATION_PLAN.md).
- Prompt text includes clear "allowed" and "forbidden" sections, a JSON schema, and instructions to treat all outputs as untrusted.
- LLM path is optional and configurable via environment; deterministic fallback is always available.

Testable behavior
- Unit tests that call the prompt generator and validate the prompt content (test_prompt_contract.py).
- Integration tests that mock the LLM and verify outputs are parsed only when they match the required JSON schema; invalid or partial outputs are rejected and trigger deterministic validation errors (test_prompt_injection.py).

Failure condition
- Any prompt that allows free-text responses that include verification decisions, or that causes the system to accept unvalidated fields.
- Acceptance of LLM output without schema validation.

Evidence that should exist in the repository
- src/prompts.py
- tests/test_prompt_contract.py
- tests/test_prompt_injection.py
- docs or README describing the LLM contract and how to enable/disable it


2) Evals Rigor

Requirement
- Build a scenario-based evaluation harness and a pytest suite. Key metrics must be defined: extraction accuracy, context retention, state transition correctness, verification correctness, false verification rate (must be zero), premature payment calls (must be zero), duplicate successful payments (must be zero), sensitive-data leakage (must be zero), failure recovery, and unnecessary re-asking.

Implementation expectation
- evaluation/ directory with scenarios.json and evaluate.py that runs scenario sequences against Agent.next and computes the metrics above.
- pytest suite covering unit-level correctness and safety invariants.

Testable behavior
- evaluate.py runs JSON scenarios and produces a report with the metric values.
- Pytest suite must pass on CI and include tests covering extraction, verification logic, and safety invariants (e.g., duplicate payments prevented).

Failure condition
- Any scenario with non-zero false verification rate, premature payment call, duplicate successful payments, or sensitive-data leakage.
- Missing tests for critical flows (no tests for verification or payment gating).

Evidence that should exist in the repository
- evaluation/scenarios.json
- evaluation/evaluate.py
- tests/ directory with the listed tests (test_verification.py, test_api_client.py, test_end_to_end.py, etc.)
- CI configuration that runs tests and evaluation harness (optional but recommended)


3) Agent Architecture

Requirement
- Public Agent API: Agent.next(user_input: str) -> dict. The agent must be stateful and persist conversation state across calls. The architecture must separate deterministic logic from optional LLM extraction.

Implementation expectation
- agent.py exposing an Agent class with method next(user_input: str) -> dict.
- src/state.py or src/models.py implementing ConversationState and explicit state machine with named states (WAITING_FOR_ACCOUNT_ID, WAITING_FOR_IDENTITY, VERIFIED, WAITING_FOR_AMOUNT, WAITING_FOR_CARD_DETAILS, READY_TO_PAY, PROCESSING_PAYMENT, PAYMENT_RETRY, SUCCESS, VERIFICATION_LOCKED, CLOSED).
- InputInterpreter abstraction (parser/interpreter) and validators in src/validators.py.
- API client wrapper in src/api_client.py and payment orchestration in src/payment.py.
- Deterministic verification engine in src/verification.py.

Testable behavior
- tests/test_agent_interface.py validates method signature, return schema, and state persistence across calls.
- tests/test_interpreter.py and tests/test_parser.py validate extraction of fields from natural language.
- tests/test_state_machine transition tests (test_context.py/test_verification.py).

Failure condition
- Agent.next not matching signature or not persisting state.
- State transitions not enforced or bypassable.
- Mixing verification decisions into LLM output.

Evidence that should exist in the repository
- agent.py
- src/state.py, src/models.py, src/interpreter.py, src/parser.py, src/verification.py, src/validators.py, src/api_client.py, src/payment.py
- tests/test_agent_interface.py, tests/test_state*.py, tests/test_interpreter.py


4) Validation Discipline

Requirement
- Deterministic validators must gate every action: account ID format, exact full-name matching, DOB, Aadhaar last 4, pincode, payment amount validation, card validation (Luhn, CVV length, expiry not expired), and amount boundaries (no >outstanding balance, no <=0, limited decimals). No fuzzy name matching.

Implementation expectation
- src/validators.py with precise implementations: Luhn check, Decimal-based amount parsing, card format cleanup, CVV numeric checks, expiry validation, and account ID regex.
- Use of Decimal for money.
- All external API calls only after local validation passes.

Testable behavior
- tests/test_validators.py asserts acceptance of valid inputs and rejection of invalid ones.
- Tests for edge-cases: masked numbers rejected, weird spacing/formatting handled, expiry boundary tests.

Failure condition
- Any payment attempt with invalid/unchecked data.
- Acceptance of masked numbers or fuzzy name matches.

Evidence that should exist in the repository
- src/validators.py
- tests/test_validators.py with coverage of money/card/account validations


5) API Integration

Requirement
- Implement account lookup API (POST /api/lookup-account) and payment API (POST /api/process-payment). The agent must handle API errors robustly, handle network timeouts/5xx/malformed responses, and never call payment API before verification.

Implementation expectation
- src/api_client.py wrapping account lookup and payment calls with retries for recoverable errors, timeouts, response schema validation, and secure logging.
- Tests mocking API responses for success, 4xx business errors (account not found), 5xx/timeouts, and malformed payload responses.

Testable behavior
- tests/test_api_client.py verifies client behavior on success and failure modes.
- evaluate.py scenarios include API error scenarios and ensure appropriate state transitions (e.g., PROCESSING_PAYMENT -> PAYMENT_RETRY) and metrics (recoverable failure counts).

Failure condition
- Payment API called before verification.
- API errors not handled; uncaught exceptions bubble to user or cause duplicate payments.

Evidence that should exist in the repository
- src/api_client.py
- tests/test_api_client.py
- tests/test_api_contract.py or mocks in tests/fixtures
- documentation for expected API contract (README or DESIGN.md)


6) Security Measures

Requirement
- Strict identity verification: exact full-name match plus at least one secondary factor (DOB, Aadhaar last 4, or pincode). Maximum retry limit (e.g., 3 attempts). No payment before verification. No sensitive-data disclosure (DOB, Aadhaar digits, pincode, full card numbers, CVV). No LLM authority to verify.

Implementation expectation
- src/verification.py contains deterministic logic to compare stored account data to supplied fields, enforces exact match on full_name (case-sensitive as specified), and requires name+at_least_one_secondary_factor. Tracking attempts counter and locking (VERIFICATION_LOCKED) after retry exhaustion.
- src/security.py implements redaction helpers and filters for any user-facing outputs.
- Logging controls ensuring no sensitive data is written in cleartext.

Testable behavior
- tests/test_verification.py verifying exact name matches, secondary factor acceptance, retry counting, and lockout behavior.
- tests/test_security.py verifying no sensitive fields are present in outputs or logs.

Failure condition
- Acceptance of fuzzy name matches or LLM decision to verify.
- Sensitive data returned to the user or written to logs.
- Exceeding retry limits without lockout.

Evidence that should exist in the repository
- src/verification.py
- src/security.py
- tests/test_verification.py
- tests/test_security.py
- examples/verification_failure.txt and examples/sensitive_leak_attempt.txt


7) Effective Use of LLM Capabilities

Requirement
- Use LLMs only as bounded field extractors and intent detectors. Treat all LLM outputs as untrusted and validate all structured outputs deterministically. Keep LLM optional and behind an environment toggle.

Implementation expectation
- src/interpreter.py contains DeterministicInterpreter and optional LLMInterpreter. env-config toggles LLM use.
- prompts.py provides strict JSON schema and instructions.
- LLM outputs pass through parser + validators before state updates.

Testable behavior
- tests/test_interpreter.py includes deterministic parser tests and tests with mocked LLM outputs to ensure validation rejects malformed data.

Failure condition
- Using LLM for verification decisions, payment eligibility, or any action requiring authoritative validation.

Evidence that should exist in the repository
- src/interpreter.py, src/prompts.py
- tests/test_interpreter.py, tests/test_prompt_injection.py


---

Hard requirements explicitly captured (verbatim)
- Agent.next(user_input: str) -> dict
- state persistence
- natural-language inputs
- account lookup
- strict identity verification
- exact full-name matching
- name + at least one secondary factor
- retry limit
- no payment before verification
- no sensitive-data disclosure
- payment amount validation
- card validation
- payment API
- API error handling
- successful transaction ID
- partial payments
- sample conversations
- evaluation approach
- metrics
- design document

(Each of the above must be directly verifiable in code, tests, examples, or docs.)

---

Traceability matrix (high-level)

Assignment Requirement -> Code Location -> Test Location -> Evaluation Metric

1. Agent.next(user_input: str) -> dict
   -> agent.py:Agent.next
   -> tests/test_agent_interface.py
   -> evaluation: interface correctness metric; scenario success rate

2. state persistence
   -> src/state.py / src/models.py ConversationState
   -> tests/test_context.py, tests/test_state_machine.py
   -> evaluation: context retention metric, state transition correctness

3. natural-language inputs
   -> src/parser.py / src/interpreter.py
   -> tests/test_parser.py, tests/test_interpreter.py
   -> evaluation: extraction accuracy

4. account lookup
   -> src/api_client.py -> lookup_account()
   -> tests/test_api_client.py (mocked 404 and success)
   -> evaluation: correct handling of 404, premature API calls = 0

5. strict identity verification (exact name + 1 secondary)
   -> src/verification.py
   -> tests/test_verification.py
   -> evaluation: verification correctness; false verification rate = 0

6. retry limit
   -> src/verification.py (attempt tracking, lock)
   -> tests/test_verification.py
   -> evaluation: retry exhaustion behavior; locked state occurrences

7. no payment before verification
   -> src/payment.py gating + src/verification.py checks
   -> tests/test_payment.py, test_verification_gate.py
   -> evaluation: premature payment call count = 0

8. no sensitive-data disclosure
   -> src/security.py redaction + response filters
   -> tests/test_security.py, tests/test_failures.py
   -> evaluation: sensitive-data leakage = 0

9. payment amount validation
   -> src/validators.py, src/payment.py
   -> tests/test_validators.py, tests/test_payment.py
   -> evaluation: payment amount validation failures; incorrect amounts rejected

10. card validation
    -> src/validators.py (Luhn, length, masked number rejection)
    -> tests/test_validators.py
    -> evaluation: invalid card rejection rate

11. payment API
    -> src/api_client.py.process_payment()
    -> tests/test_api_client.py, test_payment_integration.py
    -> evaluation: API call success rate, retry counts, duplicate prevention

12. API error handling
    -> src/api_client.py (retry/backoff, classify errors)
    -> tests/test_api_client.py (mock 5xx/timeouts)
    -> evaluation: recoverable failure handling, retry metrics

13. successful transaction ID
    -> src/payment.py persists transaction id in ConversationState
    -> tests/test_payment.py
    -> evaluation: transaction id presence on SUCCESS

14. partial payments
    -> src/payment.py supports amount < full balance and pay_full_balance flag
    -> tests/test_payment.py, examples/allowed_partial_payment.txt
    -> evaluation: correct partial payment handling

15. sample conversations
    -> examples/*.txt (successful_flow.txt, verification_failure.txt, payment_failure.txt, edge_case.txt)
    -> tests/scenario-based evaluation
    -> evaluation: scenario coverage and human-readable examples

16. evaluation approach & metrics
    -> evaluation/evaluate.py, evaluation/scenarios.json, EVALUATION.md
    -> evaluation run artifacts (reports)
    -> evaluation: extraction accuracy, false verification rate, premature payment calls etc.

17. design document
    -> DESIGN.md and IMPLEMENTATION_PLAN.md
    -> tests: design-level checks are informal; code matches design
    -> evaluation: design-to-implementation traceability checks

---

Review for missing or uncertain items (must confirm against authoritative PDF)

The following items were not unambiguously available from IMPLEMENTATION_PLAN.md or are described at a high level in the plan and therefore require confirmation from the original assignment PDF:

1. Exact required secondary factors: IMPLEMENTATION_PLAN.md lists DOB, Aadhaar last 4, pincode as candidate secondary factors, and requires "name + at least one secondary factor". The assignment may specify which secondary factors are required by priority or whether multiple are required for certain account types. Confirm exact allowed/required secondary factors and any per-account-type rules.

2. Exact case-sensitivity and normalization rules for "exact full-name matching" — e.g., whether leading/trailing whitespace or lettercase differences are allowed. IMPLEMENTATION_PLAN.md states "No fuzzy or case-insensitive name matching" but the official assignment may define precise string normalization rules.

3. Retry limit numeric value: IMPLEMENTATION_PLAN.md suggests "Maximum 3 failed verification attempts" — confirm that the assignment requires 3 or a different number.

4. Payment API schema details: field names, authentication, status codes, and transaction ID format — IMPLEMENTATION_PLAN.md gives paths (/api/lookup-account, /api/process-payment) and payload guidance but not full contract details. Confirm exact API contract if the assignment provides it.

5. Partial payments policy: whether partial payments are allowed by default or only for certain account types and whether there are minimum amount constraints.

6. Sample conversation transcripts: IMPLEMENTATION_PLAN.md references examples in examples/*.txt. Confirm that the assignment includes required sample conversations and their exact wording if they must be reproduced.

7. Exact evaluation scoring thresholds: the plan lists metrics and zeros for some categories (false verification rate = 0, premature payment call count = 0, sensitive-data leakage = 0) but does not provide numeric thresholds for extraction accuracy, state-transition correctness, or context retention. Confirm scoring rules and pass/fail thresholds from the assignment.

8. Identity storage/PII handling specifics: retention periods, encryption-at-rest, or secure key requirements for payment/card metadata may be present in the assignment; confirm storage and encryption requirements.

9. Logging policy: which events must be logged and which must be redacted — IMPLEMENTATION_PLAN.md lists logging controls but the assignment may provide more detail.

10. Exact transaction retry behaviour (idempotency keys, duplicate detection) — plan suggests persisting transaction id, but confirm whether the API provides idempotency keys or if the implementation must provide them.

11. Any non-functional requirements such as response-time SLAs, scale, or maximum token usage for LLM calls.

12. Any localization requirements (currency, date formats) beyond the assumption of rupees with two-decimal precision.

Action items / next steps
- Confirm the above uncertain items by reviewing Agent_Engineer_-_payment_agent_assignment.pdf or paste the authoritative assignment text here. Once confirmed, implementation can begin.

If the authoritative PDF cannot be programmatically read from this environment, the fastest path is for the user to paste the assignment text (or confirm the list above). Alternatively, allow the assistant to attempt OCR extraction here and continue (may require installing tools and could introduce OCR errors that need manual verification).

---

End of REQUIREMENTS.md
