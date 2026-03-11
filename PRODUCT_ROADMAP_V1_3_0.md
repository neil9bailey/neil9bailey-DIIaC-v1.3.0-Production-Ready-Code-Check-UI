# DIIaC Product Roadmap v1.3.0

## Objective
Move DIIaC from UI-first baseline to a governance-plane product that can mediate LLM-native workflows while preserving deterministic assurance, replayability, and auditability.

## Phase A — Decision Quality & Confidence Layer (v1.2.x hardening)
1. Structured `governance_modes[]` controls (prompt-mode policy packs).
2. Confidence scoring model in outputs (score, level, rationale).
3. Recommendation contract fields enforced:
   - evidence IDs
   - assumptions
   - risk treatment
   - confidence rationale
4. Deterministic "decision not recommended" path when controls fail.
5. Board-ready markdown + JSON artifacts with ranked options and implementation plan.

## Phase B — Headless Governance Plane (v1.3.0 core)
1. API-first/headless operation (UI optional).
2. External intent ingestion from LLM-native channels.
3. Policy pack versioning and signed policy manifests.
4. Deterministic compile + replay verification as mandatory close-out stage.
5. Confidence and trust scoring exposed as first-class API fields.

## Phase C — Copilot/Enterprise Integration Overlay
1. Request intercept via enterprise extension/agent boundary.
2. Response governance layer before user-visible output.
3. Evidence binding + unsupported-claim checks + confidence bounds.
4. Human approval gates for high-risk decisions.
5. Immutable audit lineage exportable for regulator/auditor review.

## Non-Goals (for v1.3.0)
- Replacing tenant-native security boundaries.
- Bypassing enterprise identity/permission models.
- Removing deterministic governance attestation in production mode.
