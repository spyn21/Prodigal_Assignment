Design Overview — Payment Collection Agent
=========================================

Hybrid agent architecture
-------------------------
The agent uses a hybrid architecture that separates natural-language understanding (NLU) from deterministic business logic.
- DeterministicInterpreter / Parsers: extract structured candidate fields from user messages using regexes and deterministic normalizers. These are the default and the only required components for running the project.
- Optional LLMInterpreter: an optional constrained extractor for more complex conversational phrasing. Any LLM output must be validated against strict schemas before being used.
- State machine & Authorization: a deterministic ConversationState controls legal transitions and enforces security gates before any external action (account lookup, reveal balance, process payment).

State machine
-------------
Implemented in src/state.py, the state machine defines legal transitions and derived properties such as is_verified, can_collect_payment, and can_process_payment.
Key states:
- WAITING_FOR_ACCOUNT_ID
- WAITING_FOR_IDENTITY
- VERIFIED
- WAITING_FOR_AMOUNT
- WAITING_FOR_CARD_DETAILS
- READY_TO_PAY
- PROCESSING_PAYMENT
- SUCCESS
- VERIFICATION_LOCKED
- CLOSED

Context management
------------------
- The Agent maintains two primary context maps:
  - authoritative account_data (stored under state.context['account_data']) populated only after a successful lookup
  - state.candidate_info for user-supplied candidate identity data
- This separation ensures parser output can't be implicitly trusted as authoritative data.

Structured extraction
---------------------
- Parsers normalize account IDs, names, dates, amounts (including words -> Decimal), card numbers (format stripping), CVV (digits or spelled-out), and expiry dates.
- Normalization occurs prior to validation and comparison. For example, DOB strings like "14th May 1990" are normalized to ISO date "1990-05-14".

Prompt engineering strategy
---------------------------
- Prompts to any optional LLM are designed to request only structured fields and to return strict JSON or key/value pairs.
- The deterministic fallback always operates without an LLM, ensuring the system remains functional offline.
- Any LLM output is treated as untrusted and validated by schema validators before being used in decisions.

Deterministic verification
--------------------------
- Verification is a pure deterministic function in src/verification.py implementing the rule:
  verified = (full_name exact match) AND (dob OR aadhaar_last4 OR pincode exact match)
- Name matching is exact and case-sensitive; no fuzzy matching nor LLM-based semantic comparison is allowed.
- DOB normalization is allowed (format conversion only).

Validation boundary
-------------------
- Parsers and validators accept and normalize candidate data.
- Verification and payment authorization logic enforce security properties and decide whether actions may proceed.
- External APIs are invoked only after passing deterministic gates.

Tool / API layer
----------------
- src/api_client.py encapsulates HTTP behavior with explicit timeouts, error handling, and structured return types (LookupResult, PaymentResult).
- The evaluation harness replaces this client with ScenarioApiClient for deterministic testing.

Failure handling
----------------
- API connection/timeouts map to user-friendly messages and do not leak raw exception content.
- Local validation errors prompt re-entry of only the offending fields (amount vs card details) where it is safe to do so.
- After 3 failed verification attempts, conversation is locked for security.

Security architecture
---------------------
- Strict trust boundary between untrusted user input and trusted authoritative data.
- Deterministic business logic for verification and payment authorization; LLMs limited to extraction.
- Data minimization: clear CVV/PAN after successful payment, avoid logging raw sensitive values.

Why LLMs are used for language understanding but NOT as authority
----------------------------------------------------------------
- LLMs excel at interpreting diverse user phrasing, but their probabilistic outputs are unsuitable for security decisions that must be deterministic and auditable. Therefore, use LLMs only for candidate extraction with strict schema validation and deterministic post-processing.

Tradeoffs and improvements
-------------------------
- Tradeoffs: regex-based parsing is simple and auditable but may miss exotic phrasing; LLMs improve coverage but increase risk and require careful validation.
- With more time: introduce a constrained LLM extractor + schema validation, improve fallback heuristics, add event-level auditing and tamper-evident logs, and implement rate-limiting and secure secret storage for API credentials.
