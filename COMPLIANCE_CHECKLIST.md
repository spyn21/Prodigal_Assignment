# Payment Collection Agent Compliance Checklist

This checklist is a requirement-by-requirement audit of the repository against the assignment. It records the final verified status after fixes. Each item includes evidence in the form of file path, class/function/test, and explanation.

## 1. AGENT INTERFACE

- PASS — Agent exists
  - Evidence: [agent.py](agent.py), `class Agent`, `__init__`, `next()`
  - Explanation: The public agent is implemented and exposes the required conversational API.

- PASS — `next(user_input: str) -> dict`
  - Evidence: [agent.py](agent.py), `Agent.next(self, user_input: str) -> dict`
  - Explanation: The method signature accepts a single string input and returns a dictionary with the required schema.

- PASS — exactly `{"message": str}`
  - Evidence: [tests/test_phase1.py](tests/test_phase1.py), `test_agent_interface_exact_schema`
  - Explanation: The test asserts the result is a dict with exactly one key, `message`, and that it is a string.

- PASS — state persists
  - Evidence: [tests/test_phase1.py](tests/test_phase1.py), `test_state_persistence_across_turns`
  - Explanation: The agent keeps state across calls and updates internal context over multiple turns.

- PASS — no manual reset required
  - Evidence: [agent.py](agent.py), `self.state = ConversationState()` in `__init__` only; `next()` uses internal persistence
  - Explanation: The same `Agent()` instance persists state without a reset API.

- PASS — deterministic behavior
  - Evidence: [src/verification.py](src/verification.py), `verify_identity()`; [src/state.py](src/state.py), `ConversationState`
  - Explanation: Verification and payment authorization are controlled by deterministic logic instead of ad hoc LLM decisions.

## 2. CONTEXT MANAGEMENT

- PASS — multi-turn state
  - Evidence: [src/state.py](src/state.py), `ConversationState`; [tests/test_phase1.py](tests/test_phase1.py), `test_state_persistence_across_turns`
  - Explanation: The conversation state and payment context persist across turns.

- PASS — no unnecessary re-asking
  - Evidence: [agent.py](agent.py), the agent stores gathered identity and payment data and reuses it; [tests/test_e2e_conversation.py](tests/test_e2e_conversation.py)
  - Explanation: Valid information already received is retained and not re-asked unnecessarily.

- PASS — out-of-order information
  - Evidence: [agent.py](agent.py), `_store_identity_candidates()` and same-message handling in `next()`
  - Explanation: The agent can capture identity information supplied early or in a single turn and evaluates it after lookup.

- PASS — corrections
  - Evidence: [agent.py](agent.py), date extraction prefers the latest valid candidate; [tests/test_e2e_conversation.py](tests/test_e2e_conversation.py)
  - Explanation: Corrections are handled by selecting the most recent valid date-like value.

- PASS — repeated inputs
  - Evidence: [agent.py](agent.py), state gating and duplicate-payment protections; [tests/test_phase1.py](tests/test_phase1.py), `test_duplicate_success_protection`
  - Explanation: Repeated requests are handled without re-triggering a payment after success.

## 3. ACCOUNT LOOKUP

- PASS — correct API
  - Evidence: [src/api_client.py](src/api_client.py), `HttpAccountLookupClient.lookup_account`
  - Explanation: Uses the assignment-specified account lookup endpoint and payload structure.

- PASS — validation before API
  - Evidence: [src/api_client.py](src/api_client.py), `validate_account_id` guard at the start of `lookup_account()`
  - Explanation: Invalid account IDs are rejected locally before making the HTTP call.

- PASS — 404
  - Evidence: [src/api_client.py](src/api_client.py), `if response.status_code == 404`
  - Explanation: 404 responses are mapped to `account_not_found` handling.

- PASS — failures and timeout handling
  - Evidence: [src/api_client.py](src/api_client.py), `requests.exceptions.Timeout`, `ConnectionError`, non-2xx branches
  - Explanation: Timeouts, connection errors, malformed JSON, and unexpected statuses are handled safely.

## 4. VERIFICATION

- PASS — exact full name
  - Evidence: [src/verification.py](src/verification.py), `verify_identity()` `name_match = str(provided_name) == str(expected_name)`
  - Explanation: Name verification requires exact equality; no fuzzy matching is used.

- PASS — at least one secondary factor
  - Evidence: [src/verification.py](src/verification.py), `verified = dob_match or aadhaar_match or pincode_match`
  - Explanation: Authorization requires exact full-name match and at least one exact secondary match.

- PASS — DOB
  - Evidence: [src/verification.py](src/verification.py), `dob_match`
  - Explanation: DOB is normalized and compared exactly to the canonical account DOB.

- PASS — Aadhaar last 4
  - Evidence: [src/verification.py](src/verification.py), `aadhaar_match`
  - Explanation: The last four digits are compared exactly.

- PASS — pincode
  - Evidence: [src/verification.py](src/verification.py), `pincode_match`
  - Explanation: Pincode comparison is exact after normalization.

- PASS — no fuzzy matching
  - Evidence: [src/verification.py](src/verification.py), exact equality checks; [tests/test_parser_validators_phase2.py](tests/test_parser_validators_phase2.py)
  - Explanation: Lowercasing, fuzzy matching, and semantic identity comparisons are not used.

- PASS — retry limit and lock behavior
  - Evidence: [agent.py](agent.py), `MAX_VERIFICATION_ATTEMPTS` and `VERIFICATION_LOCKED`; [tests/test_verification.py](tests/test_verification.py)
  - Explanation: Failed verification attempts are counted and the conversation is locked after the maximum is reached.

- PASS — no sensitive disclosure
  - Evidence: [tests/test_prompt_injection.py](tests/test_prompt_injection.py), tests requesting DOB, Aadhaar, pincode from the user experience
  - Explanation: The agent does not reveal stored DOB, Aadhaar, or pincode.

- PASS — leap-year DOB
  - Evidence: [src/validators.py](src/validators.py), date normalization/validation; [tests/test_verification.py](tests/test_verification.py)
  - Explanation: Leap-day DOB like `1988-02-29` is accepted when correct.

## 5. PAYMENT

- PASS — amount handling
  - Evidence: [src/payment.py](src/payment.py), `parse_payment_amount()` and `validate_payment_details()`
  - Explanation: Decimal-based amount handling, partial payment, full-balance intent, and bounds checking are implemented.

- PASS — partial and full payment
  - Evidence: [src/payment.py](src/payment.py), `parse_payment_amount()` and [tests/test_payment.py](tests/test_payment.py)
  - Explanation: Full balance and partial amounts are accepted as valid payment intents.

- PASS — cardholder, card number, CVV, expiry
  - Evidence: [src/payment.py](src/payment.py), `validate_cardholder_name()`, `normalize_card_number()`, `validate_cvv()`, `validate_expiry()`; [tests/test_payment.py](tests/test_payment.py)
  - Explanation: All required local fields are parsed and validated.

- PASS — validation
  - Evidence: [src/payment.py](src/payment.py), `validate_payment_details()`, [src/validators.py](src/validators.py)
  - Explanation: Local validation includes amount precedence, Luhn, CVV length, expiry validity, and zero-balance handling.

- PASS — API payload construction
  - Evidence: [src/payment.py](src/payment.py), `prepare_payment_submission()`; [tests/test_api_contract.py](tests/test_api_contract.py)
  - Explanation: The API payload is constructed with the correct endpoint fields and JSON-serializable types.

- PASS — API errors and transaction ID handling
  - Evidence: [src/api_client.py](src/api_client.py), `process_payment()`, [tests/test_api_process_payment.py](tests/test_api_process_payment.py)
  - Explanation: Success requires a truthy `success` field and a transaction ID; errors are mapped safely.

- PASS — duplicate prevention
  - Evidence: [agent.py](agent.py), `self.state.payment_completed`; [tests/test_phase1.py](tests/test_phase1.py), `test_duplicate_success_protection`
  - Explanation: Repeated successful-payment attempts are prevented.

## 6. FAILURE HANDLING

- PASS — actionable user errors
  - Evidence: [agent.py](agent.py), messages returned for invalid amount, invalid card, invalid expiry, etc.
  - Explanation: User-facing responses direct the user to correct input without exposing sensitive details.

- PASS — retryable errors
  - Evidence: [src/api_client.py](src/api_client.py), timeout/connection handling for lookup and payment
  - Explanation: Timeout and connection failures are surfaced as recoverable user errors.

- PASS — terminal errors
  - Evidence: [agent.py](agent.py), terminal states and account-not-found handling
  - Explanation: Failure states are handled without continuing a false verification or payment flow.

- PASS — unexpected API errors
  - Evidence: [src/api_client.py](src/api_client.py), generic fallback branches for malformed JSON and non-2xx responses
  - Explanation: Unexpected errors are converted to safe generic messages, not raw stack traces.

## 7. LLM CAPABILITY

- PASS — useful language interpretation role
  - Evidence: [src/input_interpreter.py](src/input_interpreter.py), `InputInterpreter` and `DeterministicInterpreter`
  - Explanation: The interpretation layer is explicitly designed to convert conversation phrasing into structured fields while remaining separate from authorization.

- PASS — structured extraction
  - Evidence: [src/parser.py](src/parser.py), `parse_message()`
  - Explanation: Raw user text is parsed into structured account, identity, amount, and payment fields.

- PASS — prompt engineering strategy
  - Evidence: [DESIGN.md](DESIGN.md), "Hybrid agent architecture" and "use LLMs only for extraction"
  - Explanation: The design explicitly keeps language understanding decoupled from security decisions.

- PASS — strict schema boundary
  - Evidence: [src/input_interpreter.py](src/input_interpreter.py), `InputInterpreter` abstract contract; `LLMInterpreter` fallback to deterministic parser if the raw LLM output is invalid
  - Explanation: Structured extraction remains valid and deterministic at the boundary.

- PASS — deterministic safety boundary
  - Evidence: [src/verification.py](src/verification.py), [src/state.py](src/state.py), [agent.py](agent.py)
  - Explanation: Security-sensitive actions rely on deterministic verification and state transitions, not the parser or LLM.

- PASS — fallback behavior
  - Evidence: [src/input_interpreter.py](src/input_interpreter.py), `DeterministicInterpreter` default/fallback
  - Explanation: The default interpreter is fully deterministic and does not require external paid APIs.

- PASS — prompt injection protection
  - Evidence: [tests/test_prompt_injection.py](tests/test_prompt_injection.py), [src/parser.py](src/parser.py), `_looks_like_authoritative_instruction()`
  - Explanation: Prompt-injection text is treated as untrusted input and does not become an authorization decision.

## 8. SECURITY

- PASS — payment blocked before verification
  - Evidence: [agent.py](agent.py), `self.state.can_process_payment`; [tests/test_prompt_injection.py](tests/test_prompt_injection.py)
  - Explanation: Payment is prevented until identity is verified and the state machine allows it.

- PASS — account secrets not exposed
  - Evidence: [tests/test_prompt_injection.py](tests/test_prompt_injection.py), sensitive disclosure tests; [src/responses.py](src/responses.py)
  - Explanation: DOB, Aadhaar last4, and pincode are not disclosed in user-facing responses.

- PASS — PAN/CVV not logged
  - Evidence: [src/payment.py](src/payment.py), `redact_sensitive_fields()`; [tests/test_security.py](tests/test_security.py)
  - Explanation: Raw PAN/CVV values are not present in logs or user-facing output.

- PASS — data minimization
  - Evidence: [SECURITY.md](SECURITY.md); [agent.py](agent.py), clear sensitive payment_context fields after success
  - Explanation: Raw sensitive card values are removed from memory after successful payment.

- PASS — duplicate charge protection
  - Evidence: [agent.py](agent.py), `record_successful_payment()` and `payment_completed`; [tests/test_prompt_injection.py](tests/test_prompt_injection.py)
  - Explanation: A second payment is blocked even if the user repeats the payment request.

- PASS — injection resistance
  - Evidence: [tests/test_prompt_injection.py](tests/test_prompt_injection.py), multiple malicious prompt-injection scenarios
  - Explanation: Malicious text is treated as candidate input and cannot override system controls.

## 9. EVALUATION

- PASS — happy path
  - Evidence: [evaluation/scenarios.json](evaluation/scenarios.json), [evaluation/evaluate.py](evaluation/evaluate.py)
  - Explanation: The evaluation harness includes successful flow scenarios.

- PASS — verification failure
  - Evidence: [evaluation/scenarios.json](evaluation/scenarios.json)
  - Explanation: Verification failures and retry exhaustion are represented in scenarios.

- PASS — payment failure
  - Evidence: [evaluation/scenarios.json](evaluation/scenarios.json)
  - Explanation: Payment validation and API error scenarios are covered.

- PASS — edge cases
  - Evidence: [evaluation/scenarios.json](evaluation/scenarios.json), [examples/edge_case.txt](examples/edge_case.txt)
  - Explanation: Spaced account IDs, spoken CVV, natural language DOB, and amount words appear in the evaluation corpus.

- PASS — metrics
  - Evidence: [evaluation/evaluate.py](evaluation/evaluate.py), `run_evaluation()`
  - Explanation: The harness aggregates pass/fail totals and overall success rate.

- PASS — API correctness
  - Evidence: [tests/test_api_contract.py](tests/test_api_contract.py), [tests/test_api_client.py](tests/test_api_client.py)
  - Explanation: The tests verify endpoint, method, payload, timeout, and response handling.

- PASS — security invariants
  - Evidence: [evaluation/evaluate.py](evaluation/evaluate.py), `contains_sensitive_leak()` and strict pass/fail logic
  - Explanation: The evaluator treats false verification, premature payment, secret leakage, and duplicate payment as critical failure conditions.

- PASS — automated evaluation
  - Evidence: [evaluation/evaluate.py](evaluation/evaluate.py), [run_eval.py](run_eval.py)
  - Explanation: The evaluation is runnable and deterministic without live external API access.

## 10. DELIVERABLES

- PASS — `agent.py`
  - Evidence: [agent.py](agent.py)
  - Explanation: Main public interface implemented.

- PASS — support modules
  - Evidence: [src](src)
  - Explanation: Core modules exist for API client, parser, validation, verification, state, models, and payment logic.

- PASS — `requirements.txt`
  - Evidence: [requirements.txt](requirements.txt)
  - Explanation: The file exists and includes required runtime/test dependencies.

- PASS — `README.md`
  - Evidence: [README.md](README.md)
  - Explanation: Project overview, architecture, setup, tests, evaluation, verification rules, and security are documented.

- PASS — CLI
  - Evidence: [README.md](README.md), setup and test commands; no interactive CLI is required by the assignment
  - Explanation: The assignment requires the Agent public API; there is no requirement for a custom CLI binary beyond documented commands.

- PASS — sample conversations
  - Evidence: [examples/successful_flow.txt](examples/successful_flow.txt), [examples/verification_failure.txt](examples/verification_failure.txt), [examples/payment_failure.txt](examples/payment_failure.txt), [examples/edge_case.txt](examples/edge_case.txt)
  - Explanation: Realistic sample flows are included.

- PASS — design document
  - Evidence: [DESIGN.md](DESIGN.md)
  - Explanation: Design rationale and architecture are documented.

- PASS — evaluation approach
  - Evidence: [EVALUATION.md](EVALUATION.md), [evaluation/evaluate.py](evaluation/evaluate.py)
  - Explanation: The evaluation philosophy and scenario-based harness are documented.

- PASS — evaluation script
  - Evidence: [evaluation/evaluate.py](evaluation/evaluate.py), [run_eval.py](run_eval.py)
  - Explanation: The script is runnable from the repository root.

## 11. CODE QUALITY

- PASS — modular
  - Evidence: [src](src), [agent.py](agent.py)
  - Explanation: Functional responsibilities are separated across modules.

- PASS — readable
  - Evidence: [agent.py](agent.py), [src/parser.py](src/parser.py), [src/payment.py](src/payment.py)
  - Explanation: The code is organized around clear functional concerns and testable logic.

- PASS — typed where useful
  - Evidence: [src/payment.py](src/payment.py), [src/api_client.py](src/api_client.py), [src/verification.py](src/verification.py)
  - Explanation: Data classes and typed return values are used for key logic paths.

- PASS — maintainable
  - Evidence: [src/input_interpreter.py](src/input_interpreter.py), [src/state.py](src/state.py), [tests](tests)
  - Explanation: The architecture cleanly separates parsing, validation, verification, and tool invocation.

- PASS — no unnecessary dependencies
  - Evidence: [requirements.txt](requirements.txt)
  - Explanation: Minimal dependencies are used (requests, pytest).

- PASS — no secrets
  - Evidence: [src/api_client.py](src/api_client.py), [README.md](README.md)
  - Explanation: No hardcoded secrets or sensitive production credentials are included.

## Final status

The repository is in a compliant state for the assignment after the required fixes were applied.

Remaining issues: none.
