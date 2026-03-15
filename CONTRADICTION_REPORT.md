# CONTRADICTION_REPORT

Generated_at_utc: 2026-03-15T12:05:00Z  
Commit: 74a66ea

## In-Scope Contradictions (R1-R14)

- None detected.

## Checks Performed

- Verified all ticket claims against runtime-path code symbols and direct tests.
- Verified OpenAPI response contract and frontend rendering for policy semantics fields.
- Verified bridge/runtime trust and intent parity tests.
- Verified trust lifecycle + verifier negative tests.
- Verified golden fixture and negative fixture suites.
- Verified review/approval ledger event append and export/UI exposure.

## Historical Docs-vs-Runtime Drift

- Previous Wave 1 closure artifacts under this repo reported out-of-scope gaps for R7-R14.
- Current runtime and tests now implement and verify those previously-open items.

## Remaining Contradictions

- None found in targeted control posture for this run.

## Operational Contradiction Risk (Not Locally Proven)

- Azure live deployment/runtime state is not verified by local repository tests.
