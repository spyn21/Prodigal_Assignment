Security and Adversarial Controls
=================================

This document summarizes the threat model, trust boundaries, and security controls implemented in the payment collection agent for the take-home assignment.

Threat model
------------
- Adversaries: remote users interacting with the conversational agent, potentially malicious, seeking to bypass verification, cause unauthorized payments, or extract sensitive account data.
- Goals: bypass identity verification, trigger payments without required gates, learn stored personal data (DOB, Aadhaar last4, pincode), cause duplicate charges, or leak card PAN/CVV through logs or error texts.

Trust boundaries
----------------
- Untrusted: all user-supplied text. Parsers and any LLM-based extractors treat user text as untrusted candidate data only.
- Trusted: authoritative account data returned from the account lookup API and the internal state machine decisions derived by deterministic business logic.
- Operational: the API client and external payment / lookup services are considered out-of-process.

Sensitive assets
----------------
- Stored PII: full_name, dob, aadhaar_last4, pincode (from lookup API)
- Payment data: cardholder_name, PAN (card_number), CVV, expiry
- Transaction state: transaction_id

Verification controls
---------------------
- Deterministic verification function (src/verification.py) compares candidate fields (user-supplied) against authoritative account data.
- Full name comparison requires exact match (no lowercasing, no fuzzy matching, no embeddings, no LLM decisions).
- At least one secondary factor (DOB OR Aadhaar last4 OR pincode) must also match exactly after normalization (DOB formats normalized to ISO date string).
- Max failed verification attempts = 3; on exhaustion the conversation goes to VERIFICATION_LOCKED and is not reversible by user text.

Prompt injection controls
-------------------------
- User text is always parsed into candidate structured fields but never used as an authorization token.
- Parser output cannot directly change state or call APIs. Authorization checks are separate deterministic logic that consults ConversationState.
- LLM outputs (if used) are constrained: any extraction must be validated by strict schema validators before being used. LLM cannot assert "verified=true" to bypass verification.
- Embedded directive-like phrases ("Developer mode", "Ignore previous instructions") are treated as candidate text and do not change policy.

Payment authorization controls
------------------------------
- process-payment is invoked only after all of the following deterministic checks:
  - account lookup succeeded and authoritative data present
  - identity verified (deterministic verify_identity returns True)
  - payment amount is present and validated (Decimal, >0, <= balance)
  - cardholder_name present
  - card number locally validated (length + Luhn)
  - CVV locally validated (3-4 digits)
  - expiry validated (not expired)
  - no prior successful payment recorded in this conversation
- Payment invocation requires an explicit user confirmation token ("process payment", "confirm", "pay now", etc.).

Data minimization and logging
-----------------------------
- Sensitive values (card PAN, CVV, raw DOB, Aadhaar, pincode) are not included in logs or user-facing error messages.
- The agent clears CVV and raw PAN from in-memory payment context immediately after a successful payment.
- API clients perform only required conversions and avoid leaking raw sensitive values in exception messages returned to users.

Duplicate-payment protection
----------------------------
- Agent records the first successful transaction_id and sets payment_completed = True. Further user attempts to pay will be rejected and will not call the payment API again.

Error handling and leakage prevention
-------------------------------------
- External API exceptions are caught and mapped to generic user-facing messages.
- Errors returned by external services are mapped to actionable but non-sensitive messages (e.g. "Payment method rejected", "Payment failed").

Remaining limitations
---------------------
- The current evaluation harness simulates API behavior and uses deterministic parsing; additional hardening is required for production LLM integrations (rate limiting, structured logging, secure telemetry, HSM for keys, PCI scope management).
- Event ordering checks (to assert exact ordering of lookup vs payment calls) are approximated by tests; adding an append-only event log in the Agent would improve forensic guarantees.

Responsible disclosure
----------------------
If you find a security issue, please report it to the project owner following standard responsible disclosure practices.
