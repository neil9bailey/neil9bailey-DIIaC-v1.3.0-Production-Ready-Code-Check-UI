# DIIaC v1.2.0 Architecture Blueprint

## Decision Intelligence Infrastructure as Code — Governance Layer Architecture

**Version:** 1.2.0
**Classification:** Architecture Reference — Internal / Customer-Facing
**Status:** Production-Ready (post production-readiness hardening)

---

## 1. Thesis: Turning Probabilistic AI into Deterministic Decision Evidence

Large Language Models (ChatGPT, GitHub Copilot, and any future provider) are
probabilistic by nature. Given the same prompt twice, they may return different
wording, different option rankings, and different risk assessments. This is
unacceptable for board-level decisions where auditability, repeatability, and
legal defensibility matter.

**DIIaC solves this.** It wraps every LLM interaction inside a deterministic
governance pipeline that produces:

- A **fixed, reproducible hash** for every decision pack regardless of LLM output variation
- **Cryptographic Ed25519 signatures** binding every artifact to a verifiable identity
- **Merkle tree proofs** allowing any single artifact to be independently verified against the whole
- **Append-only ledger records** creating an immutable audit trail
- **Deterministic weighted scoring** that replaces LLM opinion with mathematically reproducible numbers
- **Evidence trace maps** linking every recommendation back to human-supplied claims and role evidence

The result: **AI provides the thinking. DIIaC makes it defensible.**

The LLM's probabilistic content is captured, governed, scored, signed, hashed,
and sealed into a decision pack where every artifact is independently
verifiable. Even if the LLM produces different prose on a second run, the
governance layer produces the same deterministic scoring, the same
evidence chain, and a new signed pack with full traceability to the original.

---

## 2. System Architecture Overview

```
                    TIER 1                    TIER 2                      TIER 3
                ┌───────────┐          ┌──────────────────┐       ┌──────────────────┐
                │  React /  │          │  Express.js      │       │  Python / Flask   │
  Human ──────> │  Vite     │ ──────>  │  Backend-UI      │ ────> │  Governance       │
  Operator      │  Frontend │ <──────  │  Bridge           │ <──── │  Runtime          │
                │  :5173    │          │  :3001            │       │  :8000            │
                └───────────┘          └──────────────────┘       └──────────────────┘
                     │                        │                          │
                     │                   ┌────┴────┐              ┌──────┴──────┐
                     │                   │  LLM    │              │ Artifacts   │
                     │                   │  Layer  │              │ Merkle Tree │
                     │                   ├─────────┤              │ Signing     │
                     │                   │ OpenAI  │              │ Ledger      │
                     │                   │ Copilot │              │ Scoring     │
                     │                   │  Stub   │              │ Profiles    │
                     │                   └─────────┘              └─────────────┘
                     │
              Entra ID / MSAL
              Authentication
```

### Tier 1 — React/Vite Frontend (port 5173)
- **Decision Evidence Workspace** — primary operator interface
- **Entra ID (MSAL)** SSO with group-to-role resolution
- Human Intent input, role/evidence submission, R/P level selection
- Business profile and schema selection
- LLM provider toggle (ChatGPT / Copilot)
- Trust Dashboard — live ledger state, record counts, root hashes
- Governed Report Viewer — artifact listing, decision pack export
- Governance Metadata extraction from compiled reports

### Tier 2 — Express.js Backend-UI-Bridge (port 3001)
- **LLM orchestration** — calls OpenAI or GitHub Copilot, enforces R/P sections
- **Governance proxy** — forwards governed compile requests to Python runtime
- **Bridge-side signing, hashing, and ledger** — independent evidence chain
- **RBAC** — Entra JWT (RS256/HS256) or legacy x-role header auth
- **LLM ingestion subsystem** — dedicated provider modules with prompt/response hashing

### Tier 3 — Python/Flask Governance Runtime (port 8000)
- **Deterministic compilation engine** — the core governance pipeline
- **Cryptographic signing** (Ed25519), **Merkle tree** construction, **canonical JSON** serialization
- **Business profile enforcement** — sector-specific scoring weights and required controls
- **Verification endpoints** — pack, artifact, Merkle proof, and replay verification
- **Append-only ledger** with hash-chained records
- **Audit export** — bundled evidence packs for compliance review

---

## 3. The Governance Pipeline: End-to-End Flow

### Phase 1: Human Intent Capture

```
Human Operator
     │
     ▼
┌─────────────────────────────────────┐
│  MultiRoleGovernedCompilePanel      │
│  (Frontend/src/MultiRoleGovern...)  │
│                                     │
│  Inputs:                            │
│  - Human Intent (free text)         │
│  - Role (CIO, CSO, CTO, etc.)      │
│  - Domain (network, security, etc.) │
│  - Assertions (claims/evidence)     │
│  - Non-negotiables                  │
│  - Risk flags                       │
│  - Evidence references              │
│  - Business Profile selection       │
│  - Schema selection                 │
│  - R/P enforcement levels           │
│  - LLM Provider (ChatGPT/Copilot)  │
│  - Governance Modes                 │
└──────────────┬──────────────────────┘
               │
               ▼
     POST /api/human-input
     POST /api/human-input/role
```

The human operator provides **structured decision context**, not just a prompt.
Every input is validated against maximum lengths and type constraints
(`app.py:203-255`). Role inputs are accumulated under an `execution_context_id`
so multiple stakeholders can contribute evidence to the same decision.

### Phase 2: LLM Analysis (Bridge Layer)

```
POST /api/llm-governed-compile
         │
         ▼
┌─────────────────────────────────────────┐
│  generateAI()  (server.js:256-379)      │
│                                         │
│  System Prompt:                         │
│  "You are an enterprise strategy and    │
│   technology advisory AI. Your analysis │
│   will be governed by DIIaC..."         │
│                                         │
│  Required sections driven by R/P level: │
│  R0-R1: executive_summary              │
│  R2: + strategic_context               │
│  R3: + market_analysis                 │
│  R4: + risk_matrix                     │
│  R5: + financial_model, scenario,      │
│       implementation, governance,       │
│       vendor_scoring, board_rec        │
│                                         │
│  Policy additions:                      │
│  P2: risk_matrix                       │
│  P3: regulatory_position               │
│  P4: audit_trail                       │
│  P5: trace_manifest                    │
│                                         │
│  Provider routing:                      │
│  ┌──────────┐  ┌──────────────────┐    │
│  │ OpenAI   │  │ GitHub Copilot   │    │
│  │ (GPT-4o  │  │ (via Azure       │    │
│  │  mini)   │  │  Models API)     │    │
│  │          │  │  GPT-4o          │    │
│  └──────────┘  └──────────────────┘    │
│        │              │                 │
│        ▼              ▼                 │
│  temperature: 0, response: JSON only   │
│                                         │
│  Fallback: LLM Stub mode              │
│  (deterministic template when no key)   │
└──────────────┬──────────────────────────┘
               │
               │  LLM output is raw JSON
               │  (probabilistic content)
               ▼
```

**Key design decision:** The LLM is called with `temperature: 0` and forced
JSON output, but even this does not guarantee determinism across API versions or
model updates. DIIaC does not rely on LLM determinism — it wraps whatever the
LLM returns in a deterministic governance envelope.

**Provider architecture:**
- **OpenAI (ChatGPT):** Direct API via `openai` SDK, model `gpt-4o-mini` (configurable)
- **GitHub Copilot:** Azure Models Inference API (`models.inference.ai.azure.com`), model `gpt-4o` (configurable), authenticated via `GITHUB_TOKEN`
- **Stub mode:** Returns a deterministic template when no API keys are configured — ensures the governance pipeline always produces output

**LLM ingestion subsystem** (`/api/ingest/llm`): Independent capture of raw LLM
interactions with prompt hash, response hash, and untrusted-by-default storage
(`trusted: false`) in `/workspace/artefacts/llm-ingestion/`.

### Phase 3: R/P Section Enforcement

```
               │  Raw LLM JSON
               ▼
┌─────────────────────────────────────────┐
│  enforceSections()  (server.js:200-252) │
│                                         │
│  For each section required by R/P:      │
│  - If LLM provided it → keep it        │
│  - If LLM missed it → inject enforced  │
│    placeholder with policy reference    │
│                                         │
│  Returns:                               │
│  { report, enforced_sections }          │
└──────────────┬──────────────────────────┘
               │
               ▼  Enforcement metadata
                  tracked separately
```

This is the **first governance gate**: the R/P matrix ensures that regardless of
what the LLM decided to include, all policy-required sections exist in the
output. Missing sections are flagged with enforcement notes.

### Phase 4: Bridge-Side Signing & Ledger

```
┌─────────────────────────────────────────┐
│  /govern/decision handler               │
│  (server.js:421-598)                    │
│                                         │
│  1. Hash all artifacts: sha256(content) │
│  2. Compute pack_hash:                  │
│     sha256(hash1 + hash2 + ...)         │
│  3. Sign payload with Ed25519           │
│  4. Append to JSONL ledger:             │
│     stableJson() → sha256 → chain      │
│  5. Write artifacts to disk             │
└──────────────┬──────────────────────────┘
               │
               ▼
```

The bridge maintains its **own independent evidence chain** — signing key,
artifact hashing, and append-only ledger — providing defence-in-depth.

### Phase 5: Governed Compile (Python Runtime — The Core)

This is where probabilistic becomes deterministic.

```
POST /api/governed-compile
         │
         ▼
┌──────────────────────────────────────────────────────────────┐
│  _build_execution()  (app.py:769-1205)                      │
│                                                              │
│  STEP 1: Profile & Schema Validation                        │
│  ─────────────────────────────────                          │
│  - Load business profile by profile_id                      │
│  - Verify schema is in approved_schemas set                 │
│  - Verify schema is allowed for this profile                │
│  - Retrieve accumulated role_bundle for context_id          │
│                                                              │
│  STEP 2: Context Hash (Deterministic Seed)                  │
│  ─────────────────────────────────────────                  │
│  seed_payload = {                                            │
│    context_id, profile_id, profile_hash,                    │
│    schema_id, schema_version, rp_levels,                    │
│    role_bundle, request_payload, governance_modes            │
│  }                                                           │
│  context_hash = SHA256(canonical_json(seed_payload))         │
│                                                              │
│  In STRICT_DETERMINISTIC_MODE:                              │
│    execution_id = UUID5(NAMESPACE_URL, "diiac:" + hash)     │
│  Otherwise:                                                  │
│    execution_id = UUID4()                                    │
│                                                              │
│  STEP 3: LLM Content Extraction                            │
│  ──────────────────────────────                             │
│  IF llm_analysis provided:                                  │
│    llm_options = _extract_options_from_llm(llm_analysis)    │
│    llm_sections = _extract_sections_from_llm(llm_analysis)  │
│    option_profiles = llm_options || fallback_templates       │
│  ELSE:                                                       │
│    option_profiles = keyword-matched templates               │
│                                                              │
│  STEP 4: Deterministic Scoring                              │
│  ────────────────────────────                               │
│  For each option:                                            │
│    For each weight dimension (from business profile):       │
│      score = deterministic_score(context_hash, vendor:dim)  │
│              ┌──────────────────────────────────────┐       │
│              │ val = int(SHA256(seed:label)[:8], 16) │       │
│              │ score = 50 + (val % 5000) / 100       │       │
│              │ Range: 50.00 — 99.99                  │       │
│              └──────────────────────────────────────┘       │
│    total = sum(score[k] * weight[k])                        │
│                                                              │
│  Sort by total descending → ranked_options                  │
│                                                              │
│  STEP 5: Compliance Matrix                                  │
│  ────────────────────────                                   │
│  required_controls (from profile) vs provided_controls      │
│  → all_required_satisfied: boolean                          │
│  → decision_allowed: true only if all controls met          │
│                                                              │
│  STEP 6: Confidence & Recommendation                        │
│  ──────────────────────────────────                         │
│  confidence = top_score - (8 * control_failures)            │
│             + min(6, role_count * 2)                         │
│  Levels: HIGH (>=80), MEDIUM (>=60), LOW (<60)              │
│                                                              │
│  STEP 7: Report Assembly                                    │
│  ──────────────────────                                     │
│  IF LLM analysis present:                                   │
│    deterministic_sections = _build_human_readable_sections() │
│    Merge: LLM sections override, deterministic fill gaps    │
│  ELSE:                                                       │
│    sections = _build_human_readable_sections()              │
│                                                              │
│  _enforce_sections(required_sections, draft_sections)       │
│  → Guarantees all profile-required sections exist           │
│                                                              │
│  STEP 8: Evidence Trace Map                                 │
│  ────────────────────────                                   │
│  For each section:                                           │
│    claim_id, report_section, source_role,                   │
│    source_ref, policy_ref, confidence_reason                │
│  → Links every report section to a human role and evidence  │
│                                                              │
│  STEP 9: Artifact Assembly (13+ artifacts)                  │
│  ────────────────────────────────────────                   │
│  → See Section 4 for full artifact manifest                 │
│                                                              │
│  STEP 10: Cryptographic Sealing                             │
│  ─────────────────────────────                              │
│  → See Section 5 for full crypto chain                      │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

---

## 4. Artifact Manifest — The Decision Pack

Every governed compile produces a **sealed decision pack** containing 13+
individually verifiable artifacts:

| # | Artifact | Format | Purpose |
|---|----------|--------|---------|
| 1 | `board_report.json` | JSON | Structured board report with sections, recommendations, rankings |
| 2 | `board_report.md` | Markdown | Human-readable board report for direct consumption |
| 3 | `deterministic_compilation_log.json` | JSON | 6-stage pipeline hash trace proving compilation path |
| 4 | `evidence_trace_map.json` | JSON | Links every section to source role, evidence ref, policy ref |
| 5 | `role_input_bundle.json` | JSON | Complete snapshot of all role inputs for this context |
| 6 | `schema_contract.json` | JSON | Schema ID, version, and schema hash |
| 7 | `vendor_scoring_matrix.json` | JSON | Full scoring breakdown per option per dimension |
| 8 | `business_profile_snapshot.json` | JSON | Profile state at compile time (profile hash included) |
| 9 | `profile_compliance_matrix.json` | JSON | Required vs provided controls and satisfaction state |
| 10 | `profile_override_log.json` | JSON | Any profile overrides applied |
| 11 | `down_select_recommendation.json` | JSON | Full recommendation with evidence IDs, assumptions, risk treatment |
| 12 | `governance_manifest.json` | JSON | Pack hash, Merkle tree, leaf hashes, manifest hash |
| 13 | `signed_export.sigmeta.json` | JSON | Ed25519 signature metadata, signing key ID, timestamp |
| 14 | `signed_export.sig` | Text | Raw Ed25519 signature (base64) |
| 15 | `llm_analysis_raw.json` | JSON | Raw LLM output with provider, timestamp, and output hash (when LLM used) |
| 16 | `trace_map.json` | JSON | Evidence trace (alias for regulatory cross-reference) |
| 17 | `scoring.json` | JSON | Scoring matrix (alias for external tooling) |

**LLM Provenance** — When LLM analysis is used, the board report includes an
`llm_provenance` block recording:
- Provider name (ChatGPT / Copilot)
- Content source (`llm_analysis`)
- Governance layer description
- Count of LLM sections and options used

---

## 5. Cryptographic Evidence Chain

### 5.1 Canonical Serialization

All hashing uses **canonical JSON** — deterministic key ordering with no
whitespace:

```python
def _canonical_json(data):
    return json.dumps(data, sort_keys=True, separators=(",", ":"))
```

This ensures that `{"b":2,"a":1}` and `{"a":1,"b":2}` produce **identical
hashes**. Both Python (`_canonical_json`) and Node.js (`stableJson`) implement
the same algorithm.

### 5.2 Hash Chain

```
                    ┌──────────────────┐
                    │  Each Artifact   │
                    │  content         │
                    └────────┬─────────┘
                             │
                    SHA256(content)  ← string artifacts hashed as-is
                             │         JSON artifacts hashed via canonical_json
                             ▼
                    ┌──────────────────┐
                    │  artifact_hash   │  (per artifact)
                    └────────┬─────────┘
                             │
              SHA256(name + ":" + artifact_hash)
                             │
                             ▼
                    ┌──────────────────┐
                    │  leaf_hash       │  (per artifact — Merkle leaf)
                    └────────┬─────────┘
                             │
                    ┌────────┴─────────┐
                    │  Merkle Tree     │
                    │  (binary, paired │
                    │   SHA256 concat) │
                    └────────┬─────────┘
                             │
                             ▼
                    ┌──────────────────┐
                    │  merkle_root     │
                    └────────┬─────────┘
                             │
    ┌────────────────────────┼────────────────────────┐
    │                        │                        │
    ▼                        ▼                        ▼
┌───────────┐      ┌──────────────────┐      ┌───────────────┐
│ pack_hash │      │ manifest_hash    │      │ signing       │
│ SHA256(   │      │ SHA256(          │      │ payload       │
│  concat   │      │  canonical_json( │      │               │
│  sorted   │      │   manifest))     │      │ execution_id  │
│  artifact │      │                  │      │ pack_hash     │
│  hashes)  │      │                  │      │ merkle_root   │
└─────┬─────┘      └────────┬─────────┘      │ manifest_hash │
      │                     │                 │ signed_at     │
      └─────────────────────┼─────────────────┘
                            │
                            ▼
                   ┌──────────────────┐
                   │  Ed25519 Sign    │
                   │  (private key)   │
                   └────────┬─────────┘
                            │
                            ▼
                   ┌──────────────────┐
                   │  signature       │
                   │  (base64)        │
                   └────────┬─────────┘
                            │
                            ▼
                   ┌──────────────────┐
                   │  Append-Only     │
                   │  Ledger Record   │
                   │                  │
                   │  record_id       │
                   │  event_type      │
                   │  execution_id    │
                   │  pack_hash       │
                   │  manifest_hash   │
                   │  merkle_root     │
                   │  previous_hash   │
                   │  record_hash ────┤──> next record's
                   │                  │    previous_hash
                   └──────────────────┘
```

### 5.3 Merkle Tree Construction

```python
def _build_merkle(leaves):
    nodes = [leaf["leaf_hash"] for leaf in leaves]
    levels = [nodes]
    while len(current) > 1:
        # Odd leaves: duplicate last
        if len(current) % 2 == 1:
            current = current + [current[-1]]
        # Pair and hash
        next_level = [SHA256(current[i] + current[i+1])
                      for i in range(0, len(current), 2)]
        levels.append(next_level)
        current = next_level
    return {"root": current[0], "levels": levels}
```

**Merkle proofs** allow verification of any single artifact against the root
without needing the entire pack:

```
GET /executions/{id}/merkle/proof/{artifact_name}
→ { leaf_hash, index, siblings, merkle_root }

POST /verify/merkle-proof
→ { proof_valid: true/false }
```

### 5.4 Ed25519 Signing

- **Key management:** Environment variable `SIGNING_PRIVATE_KEY_PEM` (production)
  or auto-generated ephemeral key (development)
- **Key ID:** Configurable via `SIGNING_KEY_ID`
- **Public key registry:** `contracts/keys/public_keys.json`
- **Signing payload:** `canonical_json({execution_id, pack_hash, merkle_root, manifest_hash, signed_at})`
- **Export signing:** Decision pack ZIP files are also independently signed (`_generate_signed_export_artifacts`)

### 5.5 Append-Only Ledger

```python
def _append_ledger(event_type, payload):
    prev = ledger_logs[-1]["record_hash"] if ledger_logs else "0" * 64
    record_core = {
        "record_id": sequential,
        "timestamp": utc_now,
        "event_type": event_type,      # e.g. "GOVERNED_MULTI_ROLE_COMPILE"
        "previous_record_hash": prev,
        **payload,                      # execution_id, pack_hash, etc.
    }
    record_hash = SHA256(canonical_json(record_core))
    return {**record_core, "record_hash": record_hash}
```

Each record chains to the previous via `previous_record_hash`, forming a
blockchain-like immutable sequence. Tampering with any record breaks the chain.

The bridge maintains a **parallel JSONL ledger** on disk
(`/workspace/ledger/ledger.jsonl`) using the same canonical hashing scheme,
providing dual-tier auditability.

---

## 6. Deterministic Scoring Engine

### 6.1 The Core Algorithm

```python
def _deterministic_score(seed, label):
    val = int(SHA256(f"{seed}:{label}")[:8], 16)
    return round(50 + (val % 5000) / 100, 2)
```

This is the **critical determinism guarantee**. Given:
- `seed` = the `context_hash` (derived from all inputs)
- `label` = `"{vendor}:{dimension}"` (e.g. `"Palo Alto Networks:security"`)

The score is a pure function of these two values. **No randomness. No LLM
involvement. No model weights.** The same inputs will always produce the same
score, on any machine, at any time.

Score range: **50.00 to 99.99** (ensures all options are meaningfully scored).

### 6.2 Business Profile Weights

Each business profile defines sector-specific scoring weights:

| Profile | Sector | Security | Resilience | Interoperability | Operations | Commercial |
|---------|--------|----------|------------|-----------------|------------|------------|
| `transport_profile_v1` | TRANSPORT | 0.25 | 0.20 | 0.20 | 0.15 | 0.20 |
| `finance_profile_v1` | FINANCE | 0.30 | 0.25 | 0.15 | 0.10 | 0.20 |
| `it_service_provider_profile_v1` | IT_SERVICE_PROVIDER | 0.20 | 0.20 | 0.15 | 0.20 | 0.25 |
| `national_highways_profile_v1` | TRANSPORT (Highways) | Sector-specific weights |
| `national_rail_profile_v1` | TRANSPORT (Rail) | Sector-specific weights |
| `tfl_profile_v1` | TRANSPORT (TfL) | Sector-specific weights |
| `healthcare_profile_v1` | HEALTHCARE | Sector-specific weights |
| `it_enterprise_profile_v1` | IT_ENTERPRISE | Sector-specific weights |

The weighted total: `total = sum(score[dimension] * weight[dimension])`

This means a **FINANCE** profile inherently values security (0.30) over
commercial (0.20), while an **IT_SERVICE_PROVIDER** profile weights commercial
(0.25) highest. The governance layer enforces sector-appropriate decision
criteria automatically.

### 6.3 What the LLM Contributes vs. What is Deterministic

| Aspect | Source | Deterministic? |
|--------|--------|---------------|
| Solution option names | LLM analysis or keyword templates | No (LLM) / Yes (templates) |
| Option descriptions/rationale | LLM analysis or keyword templates | No (LLM) / Yes (templates) |
| Board report section content | LLM sections merged with templates | No (LLM) / Yes (templates) |
| **Scoring per option per dimension** | **SHA256-based deterministic function** | **Yes — always** |
| **Weighted total and ranking** | **Profile weights * deterministic scores** | **Yes — always** |
| **Compliance matrix** | **Profile required_controls vs provided** | **Yes — always** |
| **Confidence score** | **Formula: top_score - penalties + role bonus** | **Yes — always** |
| **Recommendation (go/no-go)** | **compliance_matrix.all_required_satisfied** | **Yes — always** |
| **Evidence trace map** | **Structural linkage from role inputs** | **Yes — always** |
| **All hashes, signatures, Merkle** | **SHA256 + Ed25519** | **Yes — always** |
| **Ledger record** | **Hash-chained append** | **Yes — always** |

**The key insight:** The LLM enriches the *content* of the report (better prose,
domain-specific analysis). But the *decision* — which option ranks first, whether
the decision is recommended, what the confidence level is, and whether controls
are satisfied — is **entirely deterministic** and derived from the context hash,
business profile weights, and compliance rules.

---

## 7. LLM Integration Architecture

### 7.1 Dual-Provider Support

```
┌─────────────────────────────────────────────────────┐
│                                                     │
│  ┌─────────────┐          ┌──────────────────┐     │
│  │  OpenAI     │          │  GitHub Copilot  │     │
│  │  ChatGPT    │          │  (Azure Models   │     │
│  │             │          │   Inference API) │     │
│  │  SDK:       │          │                  │     │
│  │  openai npm │          │  SDK: openai npm │     │
│  │             │          │  baseURL:        │     │
│  │  Model:     │          │  models.inference│     │
│  │  gpt-4o-    │          │  .ai.azure.com   │     │
│  │  mini       │          │                  │     │
│  │             │          │  Model: gpt-4o   │     │
│  │  Auth:      │          │                  │     │
│  │  OPENAI_    │          │  Auth:           │     │
│  │  API_KEY    │          │  GITHUB_TOKEN    │     │
│  └──────┬──────┘          └────────┬─────────┘     │
│         │                          │                │
│         └──────────┬───────────────┘                │
│                    │                                │
│                    ▼                                │
│         ┌──────────────────┐                       │
│         │  Common Contract │                       │
│         │  temperature: 0  │                       │
│         │  format: JSON    │                       │
│         │  system prompt:  │                       │
│         │  governed by     │                       │
│         │  DIIaC           │                       │
│         └──────────────────┘                       │
│                    │                                │
│         ┌──────────┴──────────┐                    │
│         │  No key? Stub mode  │                    │
│         │  Returns template   │                    │
│         │  JSON output        │                    │
│         └─────────────────────┘                    │
│                                                     │
│  LLM Ingestion Subsystem (/api/ingest/llm)         │
│  ─────────────────────────────────────────         │
│  Dedicated capture with:                            │
│  - prompt_hash: SHA256(prompt)                     │
│  - response_hash: SHA256(response)                 │
│  - trusted: false (default)                        │
│  - Stored to /workspace/artefacts/llm-ingestion/   │
│                                                     │
└─────────────────────────────────────────────────────┘
```

### 7.2 LLM Output Extraction

The Python runtime normalizes LLM output through two extractors:

**`_extract_options_from_llm()`** (`app.py:333-376`):
- Searches LLM output for options under multiple possible keys: `vendor_scoring`,
  `options`, `solution_options`, `recommendations`, `board_recommendation`,
  `market_analysis`
- Normalizes into `[{vendor, focus}]` format
- Handles nested structures, lists of strings, and single recommendations
- Truncates to safe lengths (vendor: 200, focus: 500 chars)

**`_extract_sections_from_llm()`** (`app.py:378-417`):
- Maps LLM keys to board report titles (e.g. `executive_summary` → "Executive Summary")
- Flattens dicts and lists into readable text
- 14 section mappings cover the full R5/P5 matrix

### 7.3 The Governance Guarantee

When an LLM call completes:

1. **Raw output captured** → `llm_analysis_raw.json` artifact with provider, timestamp, and `SHA256(canonical_json(llm_output))`
2. **Options extracted** → fed into deterministic scoring (scores are hash-derived, not LLM-derived)
3. **Sections extracted** → merged with deterministic sections (deterministic sections fill any gaps)
4. **R/P enforcement** → all profile-required sections guaranteed present
5. **Full governance envelope** → signing, Merkle, ledger all applied identically
6. **Provenance tracked** → `llm_provenance` in board report records exactly what came from the LLM

If the LLM fails, times out, or is unavailable:
- **Stub mode** returns a template response
- **Template fallback** provides keyword-matched solution options
- The governance pipeline **always completes** — LLM enhancement is additive, never blocking

---

## 8. Verification Architecture

DIIaC provides five independent verification capabilities:

### 8.1 Pack Verification
```
POST /verify/pack
{ execution_id, pack_hash, manifest_hash? }
→ { signature_valid, hash_valid, manifest_consistent, overall_valid }
```
Reconstructs the signing payload, verifies the Ed25519 signature against the
public key, and confirms pack_hash and manifest_hash consistency.

### 8.2 Merkle Proof Verification
```
POST /verify/merkle-proof
{ leaf_hash, siblings, index, merkle_root }
→ { proof_valid }
```
Verifies that a single artifact belongs to the decision pack without needing
any other artifacts — mathematical proof of inclusion.

### 8.3 Execution Verification
```
GET /verify/execution/{execution_id}
→ { pack_hash, manifest_hash, merkle_root, ledger_match, status }
```
Cross-references the execution against the ledger to confirm the pack was
properly recorded.

### 8.4 Replay Verification
```
POST /verify/replay
{ execution_context_id, profile_id, schema_id, reasoning_level, policy_level }
→ { replay_valid, expected_execution_id, context_hash, pack_hash }
```
In `STRICT_DETERMINISTIC_MODE`, re-derives the execution ID from inputs and
confirms it matches the original — proving the compile is perfectly reproducible.

### 8.5 Public Key Registry
```
GET /verify/public-keys
→ { keys: [{ key_id, algorithm, public_key_b64 }] }
```
Allows any party to retrieve the public key for independent signature
verification without access to the runtime.

---

## 9. Authentication & Authorization

```
┌────────────────────────────────────────────┐
│  Entra ID (Azure AD)                       │
│                                            │
│  App Registration → RS256 JWT tokens       │
│  Group memberships → role mapping          │
│                                            │
│  ┌────────────────────────────────┐       │
│  │ Frontend: MSAL.js (popup)      │       │
│  │ → ID token → Bearer header     │       │
│  │ → Group OIDs → role resolution │       │
│  └────────────────────────────────┘       │
│                                            │
│  ┌────────────────────────────────┐       │
│  │ Bridge: entra.js middleware    │       │
│  │ → JWKS validation (RS256)     │       │
│  │ → HS256 fallback              │       │
│  │ → Group-to-role mapping       │       │
│  │ → Principal-to-role mapping   │       │
│  └────────────────────────────────┘       │
│                                            │
│  ┌────────────────────────────────┐       │
│  │ Legacy: x-role header (dev)   │       │
│  │ → rbac.js validates against   │       │
│  │   allowed roles per endpoint  │       │
│  └────────────────────────────────┘       │
│                                            │
│  ┌────────────────────────────────┐       │
│  │ Runtime: Bearer admin token   │       │
│  │ → /admin/* endpoints only     │       │
│  │ → Disabled in dev mode        │       │
│  └────────────────────────────────┘       │
└────────────────────────────────────────────┘
```

Roles: `admin`, `standard`, `customer`, `viewer`

---

## 10. Deployment Architecture

```
┌─────────────────── docker-compose.yml ───────────────────┐
│                                                          │
│  governance-runtime (Python 3.11)                        │
│  ├── Source: ./:/app:ro (read-only mount)                │
│  ├── Volumes: artifacts, exports, audit_exports          │
│  ├── Health: /health endpoint                            │
│  ├── STRICT_DETERMINISTIC_MODE=true                      │
│  └── SIGNING_ENABLED=true                                │
│           │                                              │
│           ▼ service_healthy                              │
│  backend-ui-bridge (Node.js 24)                          │
│  ├── Built from Dockerfile (non-root user: diiac)        │
│  ├── LLM keys: OPENAI_API_KEY, GITHUB_TOKEN             │
│  ├── Entra config: full OIDC/JWKS chain                 │
│  ├── Health: /auth/status endpoint                       │
│  └── PYTHON_BASE_URL=http://governance-runtime:8000      │
│           │                                              │
│           ▼ service_healthy                              │
│  frontend (Node.js 24, multi-stage build)                │
│  ├── Build stage: npm ci + vite build                    │
│  ├── Runtime: vite preview (non-root user: diiac)        │
│  └── VITE_API_BASE configurable                          │
│                                                          │
│  Named Volumes:                                          │
│  ├── diiac-artifacts                                     │
│  ├── diiac-exports                                       │
│  ├── diiac-audit-exports                                 │
│  └── diiac-human-input                                   │
│                                                          │
│  Secrets via Azure Key Vault:                            │
│  ├── scripts/pull-keyvault-secrets.sh --customer <name>  │
│  ├── .env (generated, gitignored)                        │
│  └── .secrets/signing_key.pem (Ed25519, mode 600)        │
│                                                          │
└──────────────────────────────────────────────────────────┘
```

---

## 11. Complete Data Flow — From Human Intent to Signed Decision Pack

```
Human Intent: "We need to evaluate GitHub Copilot for enterprise
               code generation with ISO27001 and EU AI Act compliance"
     │
     ▼
[1] Frontend captures: intent text, role=CIO, domain=enterprise-strategy,
    assertions=["Adopt governed AI code assistant with IP protection"],
    non_negotiables=["privacy-by-design"], risk_flags=["vendor-lockin"],
    profile=finance_profile_v1, schema=GENERAL_SOLUTION_BOARD_REPORT_V1,
    R=R5, P=P4, provider=Copilot
     │
     ▼
[2] Bridge: POST /api/llm-governed-compile
    → Saves human intent to /workspace/artefacts/human-input/
    → Calls generateAI() with Copilot provider
    → Copilot returns JSON: {executive_summary, strategic_context,
       market_analysis, risk_matrix, financial_model, vendor_scoring,
       board_recommendation, ...}
    → LLM output hash: SHA256(stableJson(aiReport))
    → Constructs role payload with llm-output evidence ref
    → POST /api/human-input/role → Python runtime stores role
     │
     ▼
[3] Bridge: POST /api/governed-compile
    → Passes llm_analysis + llm_provider to Python runtime
     │
     ▼
[4] Python runtime: _build_execution()
    → Validates finance_profile_v1 (security=0.30 weight)
    → Computes context_hash from ALL inputs
    → Extracts LLM options: ["Governed AI Copilot Framework",
       "Enterprise LLM Gateway", "Adaptive AI Integration Platform"]
    → Extracts LLM sections: Executive Summary, Market Analysis, etc.
    → Deterministic scoring:
       - "Governed AI Copilot Framework:security" → SHA256 → 78.43
       - "Governed AI Copilot Framework:resilience" → SHA256 → 65.12
       ... (all dimensions, all options)
    → Weighted totals computed per finance profile weights
    → Ranked: Option A (82.15) > Option B (79.44) > Option C (76.89)
     │
     ▼
[5] Compliance check:
    → Profile requires: zero_trust, audit_trail, psirt_governance
    → All provided → decision_allowed = true
    → Confidence: 82.15 - 0 + 2.0 = 84.15 → HIGH
     │
     ▼
[6] Report assembly:
    → LLM sections merged with deterministic templates
    → R5 requires all 10 sections → enforced
    → P4 requires audit_trail → enforced
    → Evidence trace: each section → source role → evidence ref
     │
     ▼
[7] Artifact generation: 15 artifacts written
    → Including llm_analysis_raw.json with Copilot provenance
     │
     ▼
[8] Cryptographic sealing:
    → Artifact hashes computed (string vs JSON handled correctly)
    → Merkle tree built from leaf hashes
    → Pack hash = SHA256(sorted concatenated artifact hashes)
    → Manifest built with Merkle root
    → Manifest hash = SHA256(canonical_json(manifest))
    → Signing payload = {execution_id, pack_hash, merkle_root,
       manifest_hash, signed_at}
    → Ed25519 signature = sign(canonical_json(signing_payload))
     │
     ▼
[9] Ledger entry:
    → event_type: GOVERNED_MULTI_ROLE_COMPILE
    → execution_id, pack_hash, manifest_hash, merkle_root
    → previous_record_hash → record_hash (chained)
     │
     ▼
[10] Response to frontend:
     → execution_id, context_hash, pack_hash, merkle_root
     → decision_summary: {selected_vendor, confidence: HIGH,
        decision_basis: "LLM-analysed content (Copilot)
        governed by deterministic scoring + profile/policy controls"}
     │
     ▼
[11] Frontend displays:
     → Trust Dashboard: ledger valid, record count, root hash
     → Governed Report Viewer: 15 artifacts, export button
     → Decision status: "recommended" / "not_recommended"
     │
     ▼
[12] Export:
     → GET /decision-pack/{id}/export → ZIP of all artifacts
     → GET /decision-pack/{id}/export-signed → ZIP + .sig + .sigmeta
     → POST /admin/audit-export → bundled audit package
```

---

## 12. What DIIaC v1.2.0 Delivers

### The Problem
LLM queries are probabilistic. Ask ChatGPT or Copilot the same question twice
and you may get different answers. This is unacceptable for enterprise decisions
that require audit trails, regulatory compliance, and board-level defensibility.

### The Solution
DIIaC wraps LLM interactions in a **deterministic governance infrastructure**:

1. **Human intent is structured** — not just a prompt, but role-based evidence
   with assertions, non-negotiables, risk flags, and evidence references
2. **LLM output is captured and hashed** — the raw probabilistic content
   becomes a governed artifact with full provenance
3. **Scoring is deterministic** — SHA256-derived scores replace LLM opinion;
   same inputs always produce same rankings
4. **Business profiles enforce sector rules** — finance weights security higher;
   transport weights resilience; each sector's required controls must be satisfied
5. **R/P levels enforce completeness** — R5/P5 requires all sections;
   missing sections are flagged, not silently omitted
6. **Every artifact is independently verifiable** — Merkle proofs allow
   verification of any single document against the whole
7. **Cryptographic signatures bind identity** — Ed25519 signatures prove who
   signed and that nothing was altered
8. **Append-only ledgers create immutable history** — dual-tier (runtime +
   bridge) hash-chained records
9. **Replay verification proves reproducibility** — in strict deterministic
   mode, re-running with identical inputs produces an identical execution ID
10. **Audit exports package everything** — one-click export of ledger slices,
    verification snapshots, and logs for compliance review

### The Result
**A true Decision Intelligence Infrastructure as Code solution that transforms
AI LLM queries from natively probabilistic to fully deterministic with complete
evidence chains and reproducible outcomes.**

Every decision that passes through DIIaC carries:
- A unique execution ID traceable to its exact inputs
- A context hash proving what went in
- A pack hash proving what came out
- A Merkle root proving every artifact is intact
- An Ed25519 signature proving who authorized it
- A ledger record proving when it happened
- An evidence trace proving why the recommendation was made
- A compliance matrix proving which controls were satisfied
- LLM provenance proving which AI contributed and exactly what it said

The AI provides the thinking. DIIaC makes it defensible.

---

*DIIaC v1.2.0 — Decision Intelligence Infrastructure as Code*
*Architecture Blueprint — Generated from production codebase analysis*
