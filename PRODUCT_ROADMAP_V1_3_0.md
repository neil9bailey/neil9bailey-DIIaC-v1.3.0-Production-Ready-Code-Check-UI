# DIIaC Product Roadmap v1.3.0

## Objective
Move DIIaC from UI-first baseline to a governance-plane product that can mediate LLM-native workflows while preserving deterministic assurance, replayability, and auditability.

## v1.2.2 — Verification Hardening (SHIPPED)

**Verification endpoints now support both Ed25519 and ES256 signatures.**

`/verify/pack` and `/verify/execution` now dispatch signature verification based on `signature_alg` in `signed_export.sigmeta.json`, rather than assuming a single algorithm. ES256 (ECDSA P-256, Azure Key Vault) packs verify correctly alongside existing Ed25519 packs. Responses are backward compatible (additive fields only: `signature_alg`, `signing_key_id`, `verification_provider`).

---

## v1.2.1 — Patch Release Backlog

These items are scoped for the first patch on top of the v1.2.0-ledger-anchored baseline. All are low-risk, additive, and require no schema or API breaking changes.

### 1. `ledger_root_at_export` in Audit Exports

**What:** Compute a Merkle root over the full ledger at the moment an audit export is generated and embed it in the `audit_manifest` block.

**Why:** Currently the audit export includes a `ledger_slice` (the subset of ledger records relevant to the selected executions) but there is no cryptographic proof of the ledger's total state at export time. A `ledger_root_at_export` allows an auditor to verify that the ledger had not grown (or been modified) between export and review — closing the chain of custody from execution to audit hand-off.

**Target field (in `audit_manifest`):**
```json
"ledger_root_at_export": "<sha256 of canonical ledger at export time>",
"ledger_record_count_at_export": 14
```

**Implementation note:** Compute `_sha256_text(_canonical_json(ledger_logs))` at the point `admin_audit_export()` assembles the bundle, before writing to disk.

---

### 2. Full `ledger_slice` with Merkle proof per record

**What:** Enhance the `ledger_slice` in audit exports to include a per-record Merkle inclusion proof against `ledger_root_at_export`.

**Why:** The current `ledger_slice` is a raw list of matching records. Adding inclusion proofs allows an auditor to verify each record's membership in the ledger without having access to the full ledger history — essential for partial disclosure to external auditors or regulators.

**Target shape:**
```json
"ledger_slice": [
  {
    "record": { ...existing ledger record... },
    "ledger_inclusion_proof": {
      "leaf_index": 3,
      "siblings": ["<hash>", "<hash>", "<hash>"],
      "root": "<ledger_root_at_export>"
    }
  }
]
```

---

### 3. `LEDGER_FREEZE` environment flag (SHIPPED in v1.2.0-ledger-anchored)

**Status: DONE** — `LEDGER_FREEZE=true` prevents new records from being appended to the in-memory ledger. The current state is preserved and all read/verify endpoints remain operational. The flag is reported in `/admin/config` as `"ledger_freeze": true`.

**Use case:** Demo and diligence environments — present a pre-populated, immutable ledger to prospects or auditors without risk of state mutation during the session.

---

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
