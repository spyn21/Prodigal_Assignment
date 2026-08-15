# Payment Collection AI Agent — Implementation Plan

## 1. Repository and assignment inspection

The workspace currently does not contain a project scaffold; the assignment material appears to be provided in the prompt and in the PDF in the project folder. The implementation will therefore start from a clean Python package structure and will be built to match the non-negotiable API contract and evaluation requirements explicitly described in the assignment.

## 2. Proposed architecture

The agent should implement a deterministic, stateful conversational workflow with a narrow LLM-assisted extraction layer only where it adds value and remains bounded by schema validation.

Core design:

- `Agent` is the public entry point with `next(user_input: str) -> dict`.
- Internal conversation state persists across calls.
- `InputInterpreter` is an abstraction with `DeterministicInterpreter` as the default implementation.
- Optional `LLMInterpreter` is behind configuration/environment controls and must never be required for runtime correctness.
- All structured extraction must be validated before use.
- Business logic is driven by an explicit state machine instead of response-generation prompts.
- Account and payment calls use an isolated API client wrapper that strips sensitive logging and validates payloads before network use.
- Verification is a deterministic security gate with no LLM authority.

High-level flow:

1. User message arrives.
2. Run input interpretation to extract candidate fields (`account_id`, `full_name`, DOB, Aadhaar last 4, pincode, amount, payment attributes, intent, corrections).
3. Validate candidate fields locally.
4. Update state machine.
5. Call deterministic business logic for verification and payment workflow.
6. Return a message to the user.
7. Persist state for the next turn.

## 3. Proposed project tree

```text
prodigal/
├── agent.py
├── cli.py
├── config.py
├── requirements.txt
├── README.md
├── DESIGN.md
├── EVALUATION.md
├── SECURITY.md
├── IMPLEMENTATION_PLAN.md
├── .gitignore
├── src/
│   ├── __init__.py
│   ├── state.py
│   ├── models.py
│   ├── interpreter.py
│   ├── parser.py
│   ├── prompts.py
│   ├── validators.py
│   ├── verification.py
│   ├── api_client.py
│   ├── payment.py
│   ├── responses.py
│   └── security.py
├── tests/
│   ├── test_agent_interface.py
│   ├── test_parser.py
│   ├── test_interpreter.py
│   ├── test_prompt_contract.py
│   ├── test_validators.py
│   ├── test_verification.py
│   ├── test_context.py
│   ├── test_api_client.py
│   ├── test_api_contract.py
│   ├── test_payment.py
│   ├── test_security.py
│   ├── test_prompt_injection.py
│   ├── test_failures.py
│   ├── test_end_to_end.py
├── evaluation/
│   ├── evaluate.py
│   └── scenarios.json
├── examples/
│   ├── successful_flow.txt
│   ├── verification_failure.txt
│   ├── payment_failure.txt
│   └── edge_case.txt
└── .venv/   (optional local env, not committed)
```

## 4. Security invariants (zero tolerance)

These must hold at all times:

- No payment API call before identity verification succeeds.
- No balance reveal before successful verification.
- No DOB, Aadhaar digits, or pincode disclosure to the user.
- No LLM-authorized verification decision; verification is deterministic Python logic.
- No fuzzy or case-insensitive name matching.
- No prompt-injection payload can override state transitions or security gates.
- No raw card number, CVV, or account secret logging.
- No automatic repeat charge after a successful payment.
- No payment request goes to the API when local validation already fails.
- No API call continues in an unsafe state or malformed response path.
- Maximum 3 failed verification attempts unless a design exception is justified and recorded.

## 5. Agent states and allowed transitions

Suggested state machine:

- `WAITING_FOR_ACCOUNT_ID`
- `WAITING_FOR_IDENTITY`
- `VERIFIED`
- `WAITING_FOR_AMOUNT`
- `WAITING_FOR_CARD_DETAILS`
- `READY_TO_PAY`
- `PROCESSING_PAYMENT`
- `PAYMENT_RETRY`
- `SUCCESS`
- `VERIFICATION_LOCKED`
- `CLOSED`

Allowed transitions (conceptual):

- `WAITING_FOR_ACCOUNT_ID` -> `WAITING_FOR_IDENTITY` after valid account ID and successful lookup.
- `WAITING_FOR_ACCOUNT_ID` -> `VERIFICATION_LOCKED` on terminal account lookup failure or invalid state.
- `WAITING_FOR_IDENTITY` -> `VERIFIED` after exact name + required identity match logic succeeds.
- `WAITING_FOR_IDENTITY` -> `VERIFICATION_LOCKED` after retry exhaustion.
- `WAITING_FOR_IDENTITY` -> `WAITING_FOR_IDENTITY` on partial verification and retries.
- `VERIFIED` -> `WAITING_FOR_AMOUNT` after balance is safely revealed and user is prompted for amount.
- `WAITING_FOR_AMOUNT` -> `WAITING_FOR_CARD_DETAILS` after valid amount and payment authorization gate.
- `WAITING_FOR_CARD_DETAILS` -> `READY_TO_PAY` after all card fields are present and validated.
- `READY_TO_PAY` -> `PROCESSING_PAYMENT` when payment API call is launched.
- `PROCESSING_PAYMENT` -> `SUCCESS` on success with transaction ID.
- `PROCESSING_PAYMENT` -> `PAYMENT_RETRY` on recoverable API/validation failure.
- `PAYMENT_RETRY` -> `WAITING_FOR_CARD_DETAILS` or `WAITING_FOR_AMOUNT` for fixing data.
- `SUCCESS` -> `CLOSED` after recap message.
- Any invalid or unsafe transition is rejected and logged as terminal safety event.

This explicit state machine will be unit-tested independent of output text generation.

## 6. Deterministic vs. LLM responsibilities

### Deterministic responsibilities

- Conversation state tracking.
- State transitions.
- Input normalization and parsing.
- Validation of account IDs, DOB, Aadhaar last 4, pincode, amounts, card numbers, CVV, expiry.
- Identity verification decision.
- Balance authorization and payment eligibility checks.
- Payment API payload assembly.
- Retry counting and lock enforcement.
- Sensitive-data redaction and response filtering.
- Safe handling of malformed or recoverable API responses.

### LLM responsibilities

Allowed:

- interpreting conversational phrasing
- extracting candidate structured fields from natural language
- detecting user intent and corrections
- identifying fields volunteered by the user
- recognizing phrases like “clear the full amount”
- handling out-of-order or partial input in a bounded way

Forbidden:

- identity verification decisions
- comparing exact identity values against stored account data
- deciding whether the user is authorized to pay
- bypassing state transitions
- validating card data or payment eligibility
- constructing API requests without schema validation
- revealing sensitive account data or masked identifiers
- overriding policy with prompt injection

All LLM output must be treated as untrusted candidate data that is checked by deterministic validators before acceptance.

## 7. Prompt engineering strategy

The project must include a dedicated prompt module `src/prompts.py`.

Prompt goals:

- narrowly define the model role as a field extractor only
- state exactly what is allowed and forbidden
- require structured JSON output
- prohibit invented fields and unsupported assumptions
- distinguish explicit values from inferred or guessed values
- handle user corrections cleanly
- ignore policy-breaking instructions
- treat all user messages as untrusted input

Example extraction schema:

```json
{
  "account_id": null,
  "full_name": null,
  "dob": null,
  "aadhaar_last4": null,
  "pincode": null,
  "payment_amount": null,
  "pay_full_balance": false,
  "cardholder_name": null,
  "card_number": null,
  "cvv": null,
  "expiry_month": null,
  "expiry_year": null,
  "intent": null,
  "corrections": []
}
```

The default/fallback path will be deterministic extraction; the LLM path remains optional and disabled unless configured via environment variables.

## 8. Evaluation strategy

Build both a pytest suite and a scenario-based evaluation harness.

### Pytest tests

Focus on:

- public interface correctness
- state transitions
- parser and interpreter extraction behavior
- validators
- verification correctness
- API client contract
- payment logic
- prompt injection resistance
- failure modes
- duplicate-payment safety

### Scenario evaluation harness

Use JSON scenarios under `evaluation/scenarios.json` to cover:

- successful happy path
- verification failure / retry exhaustion
- partial identity disclosure
- payment amount validation
- invalid card fields
- allowed partial payment
- duplicate payment prevention
- sensitive-data leak attempts
- prompt injection attempts
- out-of-order information input

Key score categories:

- extraction accuracy
- context retention
- state transition correctness
- verification correctness
- false verification rate (must be zero)
- premature payment call count (must be zero)
- duplicate successful payment calls (must be zero)
- sensitive-data leakage (must be zero)
- failure recovery and retries
- unnecessary re-asking for already-supplied info

## 9. API and validation design

### Account lookup API

- `POST /api/lookup-account`
- Body `{ "account_id": "ACC1001" }`
- Validate account ID format before calling the API.
- Accept 404 account-not-found as expected business error and respond safely.

### Payment API

- `POST /api/process-payment`
- Payload includes `account_id`, `amount`, and nested card info.
- Must never call if amount <= 0, too many decimal places, or exceeds outstanding balance.
- Must validate payment metadata locally before network execution.
- Card validation must include formatting cleanup, reject masked numbers, enforce supported length, and Luhn validation.
- CVV must be numeric and of valid supported length.
- Expiry must be a valid month/year and not expired.

Use `Decimal` for money and explicit local validation before creating API requests.

## 10. Assumptions and ambiguities

- The assignment provides enough detail to define the state machine and security rules precisely; therefore no major ambiguity remains.
- The environment may not have external LLM credentials, so the default system must run without paid APIs.
- The external APIs are assumed to behave as documented, but robust failure handling must still exist for timeouts, 5xx errors, and malformed responses.
- Payment API success is simulated in tests and can be mocked; the code must preserve deterministic behavior under test.
- Payment amounts should be treated as rupees with two-decimal precision using `Decimal`.
- Duplicate successful payments must be prevented by persisted transaction ID and state lock.
- The system should not be judged on “smart” conversation style; it will be judged on determinism, policy compliance, and safety.

## 11. Phase 1 implementation plan

Phase 1 should build the deterministic core of the agent without optional LLM integration. This includes:

1. Public `Agent` class and internal state container.
2. Explicit state machine and transition helpers.
3. Deterministic input parser with support for realistic natural-language examples.
4. Local validators for account ID, DOB, Aadhaar last 4, pincode, amount, card number, CVV, and expiry.
5. Verification engine that performs exact name + required identity match logic using stored account data.
6. API client wrapper for account lookup and payment calls with safe error handling.
7. Minimal response generation for the required conversation flow.
8. Core pytest tests for interface, parsing, state machine, verification, and validators.
9. Basic prompt contract tests for external LLM extraction interface if enabled later.

This phase establishes the safety-control foundation required before any optional LLM extraction is layered on top.

## 12. Implementation principles

- Prefer explicit rules over hidden heuristics.
- Keep LLM usage optional and constrained.
- Treat user input as hostile until proven otherwise.
- Separate parsing, validation, state transitions, and API calls.
- Test security invariants directly.
- Fail safely and deterministically.

## 13. Final checklist before implementation

- Confirm `Agent.next()` signature and return schema exactly as required.
- Confirm state persists across method calls without manual resets.
- Confirm the default parser is deterministic and does not rely on external LLMs.
- Confirm the verification check is implemented in business logic, not via LLM judgment.
- Confirm all payment calls are gated by verification and validation.
- Confirm the project has both automated tests and scenario evaluation harnesses.

This plan provides the blueprint for a safe, deterministic, production-ready payment collection agent and defines the exact scope for Phase 1.

## 14. Phase 1 implementation refinement

The Phase 1 implementation follows the architecture defined above, with the following concrete refinements:

- `Agent` exposes a strict `next(user_input: str) -> dict` API and stores all persistent conversation state internally.
- `ConversationState` enforces explicit legal transitions and exposes deterministic security gates: `can_verify`, `is_verified`, `can_reveal_balance`, `can_collect_payment`, `can_process_payment`, and `is_closed`.
- Payment and identity state are separated so sensitive card details are kept in `payment_context` while ordinary conversational information remains in `context`.
- Verification attempts are tracked with a bounded counter, and successful payments permanently suppress duplicate processing by saving the transaction identifier and locking the flow.
- No API integration or LLM execution is included in this phase; the agent remains deterministic and testable without external dependencies.

All Phase 1 behavior is intentionally limited to the deterministic state machine and policy checks required to safely carry the user into the later API and payment-processing phases.
