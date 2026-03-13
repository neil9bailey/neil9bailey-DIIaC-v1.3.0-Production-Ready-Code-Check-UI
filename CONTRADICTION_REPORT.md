# CONTRADICTION_REPORT

Generated_at_utc: 2026-03-13T01:13:00Z
Commit: bfe6ea2
Scope: R1-R6 only

## In-Scope Contradictions (R1-R6)

- None detected.

Verified checks performed:
- Replay path no longer synthesizes legacy defaults (`deterministic-governance`, `llm-hallucination-risk`, `auto-ref-*`) and now returns structured errors for missing required provenance/evidence.
- Bridge non-dev startup now fails on the same trust misconfigurations as runtime (missing active registered key, active key mismatch).
- Board required sections now hard-fail when missing and production outputs tested contain no placeholder sections.
- KPI schema strictness is enforced at request validation + compile gates and frontend emits strict KPI objects.
- Stale critical evidence (security/pricing) blocks high-assurance compile; stale noncritical evidence remains warning-only.
- Vendor mismatch and competitor-primary evidence are explicitly hard-failed.

## Out-of-Scope/Program-Level Contradictions (Not Claimed Resolved In This Run)

- Full policy semantics uplift (Epic 4) is still incomplete end-to-end in response contracts/UI rendering.
- Golden/negative fixture programs (Epic 7) are not fully implemented.
- Human review workflow ledger-chain accountability (Epic 8) remains incomplete.

These are not contradictions against R1-R6 completion claims; they remain explicit out-of-scope items for this run.
