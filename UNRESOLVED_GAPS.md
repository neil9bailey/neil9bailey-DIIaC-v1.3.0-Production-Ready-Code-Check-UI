# UNRESOLVED_GAPS

Generated_at_utc: 2026-03-13T00:00:10Z
Commit: 612e654

## Verified Facts vs Inference

- Verified facts: sourced from direct code/test/command evidence in [IMPLEMENTATION_CLOSURE_MATRIX.md](/F:/code/diiac/diiac_v1.3.0_ui/IMPLEMENTATION_CLOSURE_MATRIX.md), [VERIFICATION_MANIFEST.json](/F:/code/diiac/diiac_v1.3.0_ui/VERIFICATION_MANIFEST.json), and [VALIDATION_OUTPUTS.md](/F:/code/diiac/diiac_v1.3.0_ui/VALIDATION_OUTPUTS.md).
- Inferred risk: used only where runtime behavior is heuristic or not directly test-proven.

## Unresolved Runtime Behaviors

- `app.py` `/verify/replay` still injects legacy fallback defaults:
  - `non_negotiables` fallback includes `deterministic-governance`.
  - `risk_flags` fallback includes `llm-hallucination-risk`.
  - `evidence_refs` fallback includes `auto-ref-*`.
- Startup trust failures are still process-level `RuntimeError` exits instead of structured startup failure payloads with deterministic error codes.
- Some recommendation fields still use fallback values when user input is absent, which can dilute intent fidelity.

## Partial Policy Semantics

- Runtime emits semantics fields, but full enum posture requested by spec is not fully represented in operational output states.
- No dedicated enum-level validation tests are present.
- Frontend does not render these semantics in policy views.

## Placeholder Logic Still Present Anywhere

- Placeholder detection logic exists in evidence/classification paths (`placeholder-*`, `auto-ref-*`).
- Section placeholder checks exist (expected), but replay fallback still introduces placeholder-style references.

## Fallback Logic Still Present Anywhere

- Replay endpoint fallback behavior (see above) contradicts strict no-overwrite intent.
- Runtime fallback values for guardrails/residual risks remain when upstream constraints are absent.
- Bridge has runtime/profile fallback branches for availability scenarios.

## Self-Healing Trust Logic Still Present Anywhere

- Dev-only trust registry self-update remains available via `TRUST_REGISTRY_DEV_AUTOREGISTER=true`.
- Non-dev self-healing is blocked, but dev path can still normalize drift and hide trust issues until later.

## Weak Evidence Binding Still Present Anywhere

- Hard gates exist, but not every gate has a direct negative test.
- Stale evidence is currently warning-only rather than hard-fail for critical evidence classes.
- Selected-vendor dossier checks are not class-complete (security/pricing/operational evidence classes).

## Incomplete UI/API Exposure of Runtime Semantics

- OpenAPI does not fully model response-side policy semantics and trust readiness details.
- Frontend type surface focuses on request payloads for review/assurance, not full runtime semantics rendering.
- No UI evidence of explicit signal vs evidence-backed vs external validation posture display.

## Tests That Do Not Truly Prove Claimed Behavior

- `tests/golden` is absent.
- `tests/negative` is absent.
- No bridge/runtime parity contract suite exists.
- No provider-metadata differential invariance test exists.
- No key-rotation trust-bundle verification regression test exists.
