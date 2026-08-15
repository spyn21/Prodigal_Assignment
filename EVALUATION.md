Evaluation framework for the Payment Collection Agent

Overview
--------
This evaluation harness runs curated conversational scenarios against the Agent class using deterministic fake API clients. It measures functional and security-oriented properties and produces both a human-readable summary and a JSON results file.

Design principles
-----------------
- Deterministic: All scenarios use mock/fake API clients to avoid external network dependencies.
- Security-first: The harness checks for forbidden leaks of sensitive stored values (DOB, Aadhaar last4, pincode) and flags premature or duplicate payment calls.
- Scenario-driven: Each scenario defines a user message sequence, expected API behaviors, and expected outcomes.

Files
-----
- evaluation/scenarios.json: Scenario definitions (messages, API behavior, expectations).
- evaluation/evaluate.py: Script to run the scenarios and compute results.json.
- evaluation/results.json: Generated after running evaluate.py.

How to run
----------
From the repository root:

python evaluation/evaluate.py

Outputs
-------
- A console report summarizing pass/fail per scenario.
- evaluation/results.json: full per-scenario details and summary metrics.

Metrics (implemented)
---------------------
- total_scenarios
- passed
- overall_success_rate

Security invariants (HARD FAIL)
--------------------------------
- false verification: zero allowed
- premature payment API calls: zero allowed
- sensitive stored verification data leaked: zero allowed
- duplicate successful payment calls: zero allowed

Automated harness
-----------------
The harness executes each scenario by instantiating the Agent with a ScenarioApiClient mock. It records responses, counts API calls, and searches agent messages for sensitive substrings. Results are consolidated into evaluation/results.json for further inspection.

Observed weaknesses (current)
-----------------------------
- The evaluator's sensitive-leak detectors are substring-based and may miss redactions that slightly transform stored values. For production, enhance with more robust redaction/NLP checks.
- Precise event ordering (did a payment call occur before verification?) is approximated. Adding an append-only event log to Agent would enable exact ordering checks.

Re-running the harness
----------------------
Run the harness with:

python evaluation/evaluate.py

Review evaluation/results.json for per-scenario traces.

Contributing additional scenarios
--------------------------------
Add JSON scenario definitions to evaluation/scenarios.json following the existing schema. Each scenario may define:
- id
- messages: user message list
- lookup: {type: "ok"|"404"|...}
- payment: {type: "ok"|"insufficient_balance"|...}
- expected: expected final_state, lookup_calls, payment_calls

Contact
-------
Refer to the repository's tests and docs for interpretation of results and next steps.

- duplicate successful payment calls: zero allowed

Limitations and next steps
--------------------------
- Current harness covers many extraction, verification, and happy-path scenarios. Additional API-failure and edge-case scenarios may be added.
- The evaluator currently flags sensitive leaks by searching for exact stored substrings (DOB, Aadhaar last4, pincode) in agent responses. For production evaluation, add NLP-based redaction checks and audit trails.
- Timing and ordering-based checks (e.g., strict detection of whether a payment call happened before verification was established) use approximations; future improvements could instrument the Agent to expose an event log for precise ordering checks.

Security statement
------------------
This harness intentionally avoids using any external network calls and uses only mocked/fake clients. The harness preserves the agent's security model and verifies the absence of critical failure modes listed above.
