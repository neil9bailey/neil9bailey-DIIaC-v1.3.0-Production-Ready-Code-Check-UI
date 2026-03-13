# UNRESOLVED_GAPS

Generated_at_utc: 2026-03-13T01:12:00Z
Commit: bfe6ea2
Scope_note: R1-R6 blockers were the only implementation scope for this run.

## Verified Facts vs Inference

- Verified facts: derived from current code, direct tests, and command outputs in [VALIDATION_OUTPUTS.md](/F:/code/diiac/diiac_v1.3.0_ui/VALIDATION_OUTPUTS.md).
- Inference: used only where behavior is not directly asserted by tests.

## Unresolved Runtime Behaviors

- No unresolved runtime behavior remains for R1-R6 target controls (replay legacy injection, bridge/runtime non-dev trust parity, board hard-fails, KPI strictness, stale critical evidence blocking, vendor mismatch hard-fails).
- Remaining out-of-scope behavior gaps (not implemented in this run):
  - Full policy semantics exposure/rendering (Epic 4).
  - Human review workflow/ledger event chain (Epic 8).

## Partial Policy Semantics

- Backend semantics fields exist, but full end-to-end response schema + UI rendering coverage remains out of scope in this run.
- No dedicated frontend tests currently prove operator-visible semantics differentiation across all assurance/compliance states.

## Placeholder Logic Still Present Anywhere

- Placeholder classification logic still exists in `app.py` (`placeholder-*`, `auto-ref-*`) for detection/rejection semantics.
- This is not fallback synthesis on production/replay output paths; it is classification logic.

## Fallback Logic Still Present Anywhere

- Dev-mode trust registry auto-registration remains available when explicitly enabled (`TRUST_REGISTRY_DEV_AUTOREGISTER=true`).
- Some non-target narrative/recommendation fields still use conservative defaults when upstream content is absent (outside R1-R6 scope).

## Self-Healing Trust Logic Still Present Anywhere

- Dev-only self-healing trust behavior exists by design (`allow_registry_autoregister` path).
- Non-dev self-healing remains blocked and startup fails on trust misconfiguration.

## Weak Evidence Binding Still Present Anywhere

- R6 hard-fail controls are implemented and directly tested.
- Additional non-target evidence-model work remains (for example broader fixture coverage across all gate permutations).

## Incomplete UI/API Exposure of Runtime Semantics

- KPI request contract is now strict and wired through frontend/backend.
- Remaining semantics exposure gaps are non-wave items (full policy semantics rendering and expanded response contracts).

## Tests That Do Not Truly Prove Claimed Behavior

- Required R1-R6 tests are present and passing.
- Remaining test depth gaps (out of scope for this run):
  - No golden snapshot fixture suite (`tests/golden`).
  - No comprehensive negative fixture matrix (`tests/negative`) covering every gate permutation.
  - No dedicated UI semantic rendering tests for full policy semantics uplift.
