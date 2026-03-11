# DIIaC v1.2.0 — Architecture Picture & Capability Blueprint

**Decision Intelligence Infrastructure as Code**
*A Deterministic Governance Runtime for Cryptographically Verifiable Strategic Decisions*

---

## 1. What Is DIIaC?

DIIaC is a **first-of-its-kind governance runtime** that solves a critical problem in enterprise decision-making: **how do you use AI/LLM assistance for strategic decisions while maintaining absolute auditability, reproducibility, and cryptographic proof of what was decided, why, and by whom?**

Traditional approaches force a choice — use AI and lose verifiability, or stay manual and lose speed. DIIaC eliminates that trade-off by placing a **deterministic governance layer** between human intent, LLM synthesis, and the final decision artifact. Every output is hash-locked, signature-bound, and independently verifiable.

### The Core Innovation

```
┌──────────────────────────────────────────────────────────────────────────┐
│                         THE DIIaC PRINCIPLE                              │
│                                                                          │
│   Human Intent  ──►  LLM Synthesis  ──►  DETERMINISTIC GOVERNANCE  ──►  │
│                                           COMPILE ENGINE                 │
│                                                │                         │
│                                                ▼                         │
│                                    Cryptographically Sealed              │
│                                    Decision Artifact                     │
│                                                                          │
│   "The LLM helps you think. The runtime proves what you decided."        │
└──────────────────────────────────────────────────────────────────────────┘
```

**Key distinction:** The LLM is a *synthesis assistant*, not the decision authority. The deterministic governance runtime is the **authoritative source of truth**. Identical inputs always produce identical, verifiable outputs.

---

## 2. High-Level Architecture

### 2.1 Three-Tier Runtime Topology

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          DIIaC v1.2.0 SYSTEM TOPOLOGY                       │
│                                                                             │
│  ┌──────────────────────┐                                                   │
│  │   FRONTEND (React)   │  Port 5173                                        │
│  │                      │  Human operator interface                         │
│  │  • Intent Capture    │  Role evidence workspace                          │
│  │  • Compile Controls  │  Profile/schema/R-P selection                     │
│  │  • Report Viewer     │  Decision pack display                            │
│  │  • Trust Dashboard   │  Ledger & verification status                     │
│  │  • Admin Console     │  Operational management                           │
│  └──────────┬───────────┘                                                   │
│             │ HTTP                                                           │
│             ▼                                                                │
│  ┌──────────────────────┐                                                   │
│  │  BACKEND UI BRIDGE   │  Port 3001                                        │
│  │  (Node.js/Express)   │  Orchestration & LLM integration                  │
│  │                      │                                                   │
│  │  • LLM Synthesis     │  OpenAI gpt-4o-mini (or stub)                     │
│  │  • RBAC Middleware    │  Role-based access control                        │
│  │  • API Orchestration  │  Multi-step compile coordination                 │
│  │  • Decision Pack ZIP  │  Archival & export packaging                     │
│  └──────────┬───────────┘                                                   │
│             │ HTTP                                                           │
│             ▼                                                                │
│  ┌──────────────────────┐     ┌────────────────────────────────┐            │
│  │  GOVERNANCE RUNTIME  │     │     PERSISTENT STORAGE          │            │
│  │  (Python/Flask)      │────►│                                 │            │
│  │  Port 8000           │     │  artifacts/     Decision packs  │            │
│  │                      │     │  exports/       Signed ZIPs     │            │
│  │  • Deterministic     │     │  audit_exports/ Audit bundles   │            │
│  │    Compile Engine    │     │  human_input/   Role evidence   │            │
│  │  • Crypto Subsystem  │     │  ledger.jsonl   Trust chain     │            │
│  │  • Merkle Tree       │     │  contracts/     Profiles & keys │            │
│  │  • Trust Ledger      │     └────────────────────────────────┘            │
│  │  • Verification APIs │                                                   │
│  │  • Admin Operations  │                                                   │
│  └──────────────────────┘                                                   │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2.2 Docker Compose Deployment

```
┌──────────────────── Docker Compose: diiac_v120 ────────────────────┐
│                                                                     │
│  ┌─────────────┐  ┌──────────────────┐  ┌──────────────────────┐   │
│  │  frontend    │  │ backend-ui-bridge │  │ governance-runtime   │   │
│  │  :5173       │──│ :3001             │──│ :8000                │   │
│  │  React+Vite  │  │ Node.js+Express   │  │ Python 3.11+Flask   │   │
│  └─────────────┘  └──────────────────┘  └──────────┬───────────┘   │
│                                                      │              │
│  Named Volumes:                                      │              │
│  ┌──────────────────┐  ┌──────────────────┐         │              │
│  │ diiac-artifacts   │  │ diiac-exports     │◄────────┤              │
│  └──────────────────┘  └──────────────────┘         │              │
│  ┌──────────────────┐  ┌──────────────────┐         │              │
│  │ diiac-audit-      │  │ diiac-human-      │◄────────┘              │
│  │ exports           │  │ input             │                        │
│  └──────────────────┘  └──────────────────┘                        │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 3. The Governed Decision Pipeline

This is the core workflow — from human thought to cryptographically sealed decision.

### 3.1 End-to-End Decision Flow

```
 PHASE 1: HUMAN INTENT           PHASE 2: LLM SYNTHESIS         PHASE 3: DETERMINISTIC COMPILE
 ═══════════════════             ═══════════════════════         ═══════════════════════════════

 ┌───────────────────┐           ┌───────────────────┐         ┌───────────────────────────┐
 │  Human Operator    │           │  LLM Provider      │         │  Governance Runtime        │
 │                    │           │  (OpenAI/Stub)      │         │                            │
 │  1. Enter intent   │           │                    │         │  8. Validate profile       │
 │  2. Select profile │           │  5. Synthesize     │         │  9. Enforce schema         │
 │  3. Submit role    │──────────►│     structured     │────────►│ 10. Deterministic build    │
 │     evidence       │           │     report draft   │         │ 11. Hash all artifacts     │
 │  4. Choose R/P     │           │  6. Hash LLM       │         │ 12. Build Merkle tree      │
 │     levels         │           │     output         │         │ 13. Sign with Ed25519      │
 └───────────────────┘           │  7. Forward to      │         │ 14. Append trust ledger    │
                                  │     runtime        │         │ 15. Persist decision pack  │
                                  └───────────────────┘         └─────────────┬─────────────┘
                                                                               │
                                                                               ▼
 PHASE 4: VERIFICATION & EXPORT                              ┌──────────────────────────────┐
 ══════════════════════════════                               │  SEALED DECISION ARTIFACTS    │
                                                              │                               │
 ┌───────────────────────────┐                               │  • Board Report (Markdown)    │
 │  Verification Surface      │                               │  • Governance Manifest        │
 │                            │                               │  • Evidence Trace Map         │
 │  • Execution verification  │◄──────────────────────────────│  • Vendor Scoring Matrix      │
 │  • Pack hash verification  │                               │  • Merkle Tree + Root         │
 │  • Merkle proof checks     │                               │  • Ed25519 Signature          │
 │  • Replay attestation      │                               │  • Trust Ledger Record        │
 │  • Signed export download  │                               │  • Replay Certificate         │
 └───────────────────────────┘                               └──────────────────────────────┘
```

### 3.2 Multi-Role Evidence Collection

DIIaC captures decision evidence from multiple enterprise perspectives to ensure balanced, well-governed strategic decisions:

```
┌────────────────────────────────────────────────────────────────────┐
│                    MULTI-ROLE EVIDENCE MODEL                       │
│                                                                    │
│   ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐            │
│   │   CTO   │  │   CSO   │  │   CIO   │  │   EA    │   + more   │
│   │ Tech    │  │Security │  │ Info    │  │ Arch.  │   custom   │
│   │ Strategy│  │ Posture │  │ Ops     │  │ Align  │   roles    │
│   └────┬────┘  └────┬────┘  └────┬────┘  └────┬────┘            │
│        │            │            │            │                    │
│        ▼            ▼            ▼            ▼                    │
│   ┌─────────────────────────────────────────────────┐             │
│   │          Role Evidence Bundle                    │             │
│   │  • role_id          (who)                        │             │
│   │  • domain           (what area)                  │             │
│   │  • assertions[]     (what they claim)            │             │
│   │  • timestamp        (when)                       │             │
│   │  • context_id       (which decision)             │             │
│   └─────────────────────────┬───────────────────────┘             │
│                             │                                      │
│                             ▼                                      │
│              ┌──────────────────────────────┐                      │
│              │  Evidence Trace Map           │                      │
│              │  (evidence_trace_map.json)    │                      │
│              │                               │                      │
│              │  Binds each claim in the      │                      │
│              │  board report back to the     │                      │
│              │  specific role evidence       │                      │
│              │  that supports it.            │                      │
│              └──────────────────────────────┘                      │
└────────────────────────────────────────────────────────────────────┘
```

---

## 4. Cryptographic Trust Architecture

### 4.1 Hash Chain & Signature Model

```
┌──────────────────────────────────────────────────────────────────────┐
│                    CRYPTOGRAPHIC TRUST LAYERS                         │
│                                                                      │
│  Layer 1: ARTIFACT HASHING (SHA-256 lowercase hex)                   │
│  ────────────────────────────────────────────                        │
│  Every artifact is individually hashed:                               │
│  board_report.md ──► sha256 ──► "a3f7c2..."                         │
│  manifest.json   ──► sha256 ──► "8b12d4..."                         │
│  scoring.json    ──► sha256 ──► "f1e9a0..."                         │
│  trace_map.json  ──► sha256 ──► "c4d8b3..."                         │
│                                                                      │
│  Layer 2: MERKLE TREE BINDING                                        │
│  ────────────────────────────                                        │
│                    [Merkle Root]                                      │
│                    /            \                                     │
│             [hash(A+B)]      [hash(C+D)]                             │
│              /      \          /      \                               │
│           leaf_A  leaf_B   leaf_C  leaf_D                            │
│            │        │        │        │                               │
│       report   manifest  scoring  trace_map                          │
│                                                                      │
│  Leaf hash = sha256("artifact_name:artifact_hash")                   │
│  Leaves sorted lexicographically by filename                         │
│  Odd layers: duplicate last node                                     │
│                                                                      │
│  Layer 3: EXECUTION SIGNING (Ed25519)                                │
│  ────────────────────────────────────                                │
│  Pack = canonical_json(execution_state) ──► sha256 ──► pack_hash    │
│  Signature = Ed25519.sign(private_key, pack_bytes)                   │
│  Metadata written to signed_export.sigmeta.json                      │
│                                                                      │
│  Layer 4: TRUST LEDGER (Hash-Chained JSONL)                         │
│  ───────────────────────────────────────────                         │
│  Record N:                                                           │
│    previous_record_hash = Record(N-1).record_hash                    │
│    record_hash = sha256(canonical_json(record_core))                 │
│                                                                      │
│  [Record 1] ──► [Record 2] ──► [Record 3] ──► [Record N]            │
│   genesis         prev=R1        prev=R2        prev=R(N-1)         │
│                                                                      │
│  Any tampering with any record breaks the entire chain.              │
└──────────────────────────────────────────────────────────────────────┘
```

### 4.2 Verification Surfaces

```
┌────────────────────────────────────────────────────────────────────┐
│                     VERIFICATION ENDPOINTS                          │
│                                                                    │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │ GET /verify/execution/<id>                                   │   │
│  │ Validates: execution_hash, pack_hash, manifest_hash,         │   │
│  │           merkle_root, signature integrity                   │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                    │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │ POST /verify/pack                                            │   │
│  │ Re-computes pack hash from submitted data and compares       │   │
│  │ against stored hash. Detects any post-compile tampering.     │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                    │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │ POST /verify/merkle-proof                                    │   │
│  │ Verifies a specific artifact's inclusion in the Merkle tree  │   │
│  │ using sibling hashes and root comparison.                    │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                    │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │ POST /verify/replay                                          │   │
│  │ Re-executes the compile with identical inputs. If outputs    │   │
│  │ match, issues a replay_certificate.json attestation.         │   │
│  │ This is the strongest proof of deterministic integrity.      │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                    │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │ GET /verify/public-keys                                      │   │
│  │ Exposes the public key registry for offline verification.    │   │
│  └─────────────────────────────────────────────────────────────┘   │
└────────────────────────────────────────────────────────────────────┘
```

---

## 5. Business Profile System

DIIaC is **sector-aware**. Business profiles define the governance constraints for different regulated industries:

```
┌────────────────────────────────────────────────────────────────────────────┐
│                        BUSINESS PROFILE ENGINE                              │
│                                                                            │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐         │
│  │    FINANCE        │  │   HEALTHCARE      │  │  IT ENTERPRISE   │         │
│  │  UK jurisdiction  │  │  UK jurisdiction  │  │  Global          │         │
│  │  Risk: LOW        │  │  Risk: LOW        │  │  Risk: MEDIUM    │         │
│  │  R4/P5 default    │  │  R4/P5 default    │  │  R3/P3 default   │         │
│  │  psirt_governance │  │  patient_safety   │  │  zero_trust      │         │
│  │  Sec: 30%         │  │  Sec: 25%         │  │  Sec: 25%        │         │
│  └──────────────────┘  └──────────────────┘  └──────────────────┘         │
│                                                                            │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐         │
│  │   TRANSPORT       │  │  NATIONAL RAIL    │  │     TfL           │         │
│  │  UK jurisdiction  │  │  UK jurisdiction  │  │  London           │         │
│  │  Risk: LOW        │  │  Risk: LOW        │  │  Risk: LOW        │         │
│  └──────────────────┘  └──────────────────┘  └──────────────────┘         │
│                                                                            │
│  ┌──────────────────┐  ┌──────────────────┐                               │
│  │ NAT. HIGHWAYS     │  │  IT SERVICE PROV  │   Each profile defines:      │
│  │  UK jurisdiction  │  │  Global           │   • Allowed schemas          │
│  │  Risk: LOW        │  │  Risk: MEDIUM     │   • Required controls        │
│  └──────────────────┘  └──────────────────┘   • Required sections          │
│                                                 • Scoring weights           │
│  Profile Structure:                             • Reasoning/Policy levels   │
│  {                                              • Risk appetite             │
│    profile_id, sector, jurisdiction,            • Jurisdiction              │
│    risk_appetite, default_reasoning_level,                                  │
│    default_policy_level, allowed_schemas[],                                │
│    required_controls[], required_sections[],                               │
│    scoring_weights: { security, resilience,                                │
│      interoperability, operations, commercial }                            │
│  }                                                                         │
└────────────────────────────────────────────────────────────────────────────┘
```

### Reasoning & Policy Level Matrix

```
┌─────────────────────────────────────────────────────────────┐
│              GOVERNANCE TIER CONTROLS                         │
│                                                              │
│  REASONING LEVELS (Complexity)     POLICY LEVELS (Rigor)     │
│  ─────────────────────────────     ──────────────────────    │
│  R2 — Moderate complexity          P1 — Standard policy      │
│  R3 — Significant complexity       P2 — Enhanced policy      │
│  R4 — High complexity              P3 — Strict policy        │
│  R5 — Maximum complexity           P3+/P5 — Maximum rigor   │
│                                                              │
│  Higher R = more sections, deeper analysis                   │
│  Higher P = stricter controls, more required evidence        │
│                                                              │
│  Example: Finance profile defaults to R4/P5                  │
│  (high complexity analysis + maximum governance rigor)       │
└─────────────────────────────────────────────────────────────┘
```

---

## 6. Decision Artifact Anatomy

Every governed compile produces a complete, self-contained decision pack:

```
┌────────────────────────────────────────────────────────────────────┐
│                    DECISION PACK CONTENTS                           │
│                                                                    │
│  artifacts/<execution_id>/                                         │
│  │                                                                 │
│  ├── board_report.md              Strategic decision document      │
│  │   ├── Executive Summary        with enforced section structure  │
│  │   ├── Context                  matching the profile's           │
│  │   ├── Risk Register            required_sections[].             │
│  │   ├── Success Metrics                                           │
│  │   └── Down-Select Recommendation                               │
│  │                                                                 │
│  ├── governance_manifest.json     Compile parameters, profile,     │
│  │                                schema, R/P levels, controls,    │
│  │                                timestamps, deterministic flag   │
│  │                                                                 │
│  ├── evidence_trace_map.json      Maps each report claim to the    │
│  │                                specific role evidence and       │
│  │                                assertions that support it       │
│  │                                                                 │
│  ├── scoring_matrix.json          Vendor/option scoring using      │
│  │                                profile-defined weights:         │
│  │                                security, resilience, interop,   │
│  │                                operations, commercial           │
│  │                                                                 │
│  ├── merkle_tree.json             Full Merkle tree with root,      │
│  │                                levels, and leaf details         │
│  │                                                                 │
│  └── replay_certificate.json      Attestation that re-execution    │
│                                   with identical inputs produces   │
│                                   identical outputs                │
│                                                                    │
│  exports/<execution_id>/                                           │
│  │                                                                 │
│  ├── decision_pack.zip            Complete signed export           │
│  └── signed_export.sigmeta.json   Ed25519 signature metadata       │
│                                                                    │
│  ledger.jsonl                     Hash-chained trust record        │
│       └── { record_id, timestamp, event_type,                      │
│             previous_record_hash, execution_id,                    │
│             pack_hash, merkle_root, record_hash }                  │
└────────────────────────────────────────────────────────────────────┘
```

---

## 7. Vendor Scoring Engine

```
┌────────────────────────────────────────────────────────────────────┐
│                   DETERMINISTIC SCORING MODEL                       │
│                                                                    │
│  Profile-defined weights:                                          │
│  ┌────────────────────────────────────────────────────┐            │
│  │  Finance Example:                                   │            │
│  │  Security:          30%  ████████████████████████    │            │
│  │  Resilience:        25%  ████████████████████        │            │
│  │  Commercial:        20%  ████████████████            │            │
│  │  Interoperability:  15%  ████████████                │            │
│  │  Operations:        10%  ████████                    │            │
│  └────────────────────────────────────────────────────┘            │
│                                                                    │
│  Score generation: Deterministic hash-derived scoring              │
│  score = 50 + (int(sha256(seed:label)[:8], 16) % 5000) / 100     │
│                                                                    │
│  Same inputs always produce same scores — fully reproducible.      │
└────────────────────────────────────────────────────────────────────┘
```

---

## 8. Frontend User Interface

```
┌────────────────────────────────────────────────────────────────────────┐
│                    DIIaC OPERATIONS CONSOLE                             │
│                                                                        │
│  ┌──── CUSTOMER MODE ─────────────────────────────────────────────┐    │
│  │                                                                 │    │
│  │  ┌─────────────────────┐  ┌──────────────────────────────┐     │    │
│  │  │  Human Input Panel   │  │  Governed CTO Strategy        │     │    │
│  │  │  • Enter free-form   │  │  • Select business profile    │     │    │
│  │  │    decision intent   │  │  • Choose schema/version      │     │    │
│  │  │  • Capture context   │  │  • Set R/P levels             │     │    │
│  │  └─────────────────────┘  │  • Execute compile             │     │    │
│  │                            └──────────────────────────────┘     │    │
│  │  ┌──────────────────────────────────────────────────────┐      │    │
│  │  │  Governed Report Viewer                               │      │    │
│  │  │  • Rendered board report (Markdown)                    │      │    │
│  │  │  • Governance metadata display                         │      │    │
│  │  │  • Compliance panel                                    │      │    │
│  │  │  • Policy diff viewer                                  │      │    │
│  │  └──────────────────────────────────────────────────────┘      │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│                                                                        │
│  ┌──── ADMIN MODE (additional panels) ────────────────────────────┐    │
│  │                                                                 │    │
│  │  ┌─────────────────────┐  ┌──────────────────────────────┐     │    │
│  │  │  Impact Viewer       │  │  Trust Dashboard              │     │    │
│  │  │  • Decision impact   │  │  • Ledger chain status        │     │    │
│  │  │    assessment        │  │  • Chain validation            │     │    │
│  │  └─────────────────────┘  │  • Growth metrics              │     │    │
│  │                            └──────────────────────────────┘     │    │
│  │  ┌─────────────────────┐  ┌──────────────────────────────┐     │    │
│  │  │  Multi-Role Compile  │  │  Admin Console                │     │    │
│  │  │  • Production HITL   │  │  • Health checks              │     │    │
│  │  │    compile workflow  │  │  • Execution logs              │     │    │
│  │  │  • Multi-role input  │  │  • Metrics & alerts            │     │    │
│  │  │  • LLM + deterministic│ │  • Audit exports              │     │    │
│  │  └─────────────────────┘  │  • DB maintenance              │     │    │
│  │                            └──────────────────────────────┘     │    │
│  └─────────────────────────────────────────────────────────────────┘    │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 9. Operational & Security Controls

### 9.1 Admin Authentication Model

```
┌────────────────────────────────────────────────────────────────────┐
│                    SECURITY BOUNDARY MODEL                          │
│                                                                    │
│  Production Mode (APP_ENV=production):                             │
│  ─────────────────────────────────────                             │
│  All /admin/* routes require:                                      │
│    Authorization: Bearer <ADMIN_API_TOKEN>                         │
│                                                                    │
│  Development Mode (APP_ENV=development):                           │
│  ────────────────────────────────────────                          │
│  Admin auth bypassed for local development.                        │
│                                                                    │
│  Payload Validation:                                               │
│  ──────────────────                                                │
│  All write endpoints enforce schema bounds:                        │
│  • String fields: max length (64–8000 chars by type)               │
│  • List fields: max items (50) + max item length (512)             │
│  • Required fields: validated on compile/replay endpoints          │
│  • Guarded endpoints: role input, compile, verify, audit           │
│                                                                    │
│  Runtime Readiness:                                                │
│  ─────────────────                                                 │
│  GET /health and GET /admin/health expose:                         │
│  • artifact_storage: writable?                                     │
│  • export_storage: writable?                                       │
│  • audit_storage: writable?                                        │
│  • contracts_profiles: loaded?                                     │
│  • contracts_keys: present?                                        │
│  • database: configured?                                           │
│  • overall_ready: all checks pass?                                 │
│                                                                    │
│  Error Taxonomy:                                                   │
│  ───────────────                                                   │
│  Structured runtime_dependency_failure responses:                  │
│  • ARTIFACT_STORAGE_UNAVAILABLE                                    │
│  • EXPORT_STORAGE_UNAVAILABLE                                      │
│  • AUDIT_STORAGE_UNAVAILABLE                                       │
│  • RUNTIME_DEPENDENCY_TIMEOUT                                      │
│  • SIGNATURE_METADATA_UNAVAILABLE                                  │
└────────────────────────────────────────────────────────────────────┘
```

### 9.2 Observability

```
┌────────────────────────────────────────────────────────────────────┐
│                    OBSERVABILITY STACK                               │
│                                                                    │
│  Structured Logging:                                               │
│  GET /admin/logs?source=backend|ledger|execution                   │
│  • Stable event_id per log type (EVT-<hash12>)                     │
│  • Timestamps in UTC ISO-8601                                      │
│  • Execution-linked log correlation                                │
│                                                                    │
│  Metrics:                                                          │
│  GET /admin/metrics                                                │
│  • Execution count, success/failure rates                          │
│  • Ledger growth tracking                                          │
│  • Alerts with threshold recommendations                           │
│  • Operational baseline monitoring                                 │
│                                                                    │
│  Audit Exports:                                                    │
│  POST /admin/audit-export                                          │
│  • Full execution context bundle (ZIP)                             │
│  • All artifacts + manifest + trace + scoring                      │
│  • Ledger records + role inputs                                    │
│  • Suitable for regulator/auditor handoff                          │
└────────────────────────────────────────────────────────────────────┘
```

---

## 10. Complete API Surface Map

```
┌────────────────────────────────────────────────────────────────────────────┐
│                         DIIaC v1.2.0 API MAP                               │
│                                                                            │
│  ═══ HUMAN INPUT ═══════════════════════════════════════════════            │
│  POST /api/human-input/role        Submit role evidence (CTO, CSO, etc.)   │
│  POST /api/human-input             Submit generic human intent             │
│  GET  /api/business-profiles       List available governance profiles      │
│                                                                            │
│  ═══ COMPILATION ═══════════════════════════════════════════════            │
│  POST /api/governed-compile        Deterministic governance compile        │
│  POST /api/compile                 Legacy compile alias                    │
│  POST /api/llm-governed-compile    LLM synthesis + deterministic compile   │
│                                    (via bridge orchestration)              │
│                                                                            │
│  ═══ EXECUTION DATA ════════════════════════════════════════════            │
│  GET  /executions/<id>/trace-map   Evidence-to-claim trace mapping         │
│  GET  /executions/<id>/scoring     Vendor scoring matrix                   │
│  GET  /executions/<id>/merkle      Merkle root + full tree                 │
│  GET  /executions/<id>/merkle/proof/<name>  Specific artifact proof        │
│                                                                            │
│  ═══ VERIFICATION ══════════════════════════════════════════════            │
│  GET  /verify/execution/<id>       Full execution verification             │
│  POST /verify/pack                 Pack hash re-computation check          │
│  POST /verify/merkle-proof         Merkle inclusion proof verification     │
│  POST /verify/replay               Replay attestation (re-execute+compare) │
│  GET  /verify/public-keys          Public key registry for offline verify  │
│                                                                            │
│  ═══ EXPORT ════════════════════════════════════════════════════            │
│  GET  /decision-pack/<id>/export-signed    Signed ZIP download             │
│  GET  /decision-pack/<id>/export           Unsigned ZIP download           │
│                                                                            │
│  ═══ TRUST ═════════════════════════════════════════════════════            │
│  GET  /trust/status                Ledger chain health + validation        │
│                                                                            │
│  ═══ ADMIN (auth required in production) ═══════════════════════           │
│  GET  /health                      Basic health check                      │
│  GET  /admin/health                Detailed health + readiness checks      │
│  GET  /admin/logs                  Structured event logs                   │
│  GET  /admin/metrics               Operational metrics + alerts            │
│  GET  /admin/executions            All execution records                   │
│  POST /admin/audit-export          Generate audit bundle                   │
│  GET  /admin/db/status             Database integrity check                │
│  POST /admin/db/compact            Database compaction                     │
└────────────────────────────────────────────────────────────────────────────┘
```

---

## 11. Technology Stack Summary

```
┌────────────────────────────────────────────────────────────────────┐
│                    TECHNOLOGY STACK                                  │
│                                                                    │
│  GOVERNANCE RUNTIME              BRIDGE                            │
│  ─────────────────               ──────                            │
│  Python 3.11                     Node.js + Express 4.18            │
│  Flask 3.1.0                     OpenAI SDK (gpt-4o-mini)          │
│  cryptography 44.0.1             Archiver (ZIP generation)         │
│    └─ Ed25519 + SHA-256          RBAC middleware                   │
│  SQLite (execution store)        CORS cross-origin support         │
│  JSONL (ledger format)                                             │
│                                  FRONTEND                          │
│  INFRASTRUCTURE                  ────────                          │
│  ──────────────                  React 19.2 + TypeScript 5.9       │
│  Docker + Docker Compose         Vite 7.2 (build tool)             │
│  Named volumes (4x)             React Markdown (report render)     │
│  Environment-driven config       ESLint (code quality)             │
│  Multi-platform (Linux/macOS/Win)                                  │
│                                                                    │
│  TESTING & VALIDATION                                              │
│  ────────────────────                                              │
│  pytest (unit + integration)                                       │
│  E2E smoke script (runtime)                                        │
│  Production readiness validator                                    │
│  Release lock checklist                                            │
└────────────────────────────────────────────────────────────────────┘
```

---

## 12. What Makes DIIaC Unique

```
┌────────────────────────────────────────────────────────────────────────────┐
│                     DIIaC DIFFERENTIATORS                                   │
│                                                                            │
│  1. DETERMINISTIC GOVERNANCE-AS-CODE                                       │
│     Unlike traditional document-based governance, DIIaC encodes            │
│     governance rules as executable profiles. The runtime enforces           │
│     them programmatically — no human can skip a required section,           │
│     bypass a control, or alter scoring weights after the fact.             │
│                                                                            │
│  2. LLM-SAFE ARCHITECTURE                                                  │
│     LLMs assist with synthesis, but the deterministic compile engine       │
│     is the final authority. This means LLM hallucinations or drift         │
│     cannot corrupt the governance artifact. The LLM is a tool,             │
│     not the decider.                                                       │
│                                                                            │
│  3. CRYPTOGRAPHIC PROOF CHAIN                                              │
│     SHA-256 hashing + Ed25519 signatures + Merkle trees + hash-chained     │
│     ledger = multi-layered tamper evidence. Any modification to any        │
│     artifact at any point in the chain is mathematically detectable.       │
│                                                                            │
│  4. REPLAY ATTESTATION                                                     │
│     The strongest verification: re-execute the entire compile with         │
│     identical inputs and prove the outputs match bit-for-bit.              │
│     This is determinism verification, not just integrity checking.         │
│                                                                            │
│  5. SECTOR-AWARE PROFILES                                                  │
│     Pre-built governance profiles for Finance, Healthcare, Transport,      │
│     Rail, IT Enterprise, and more. Each encodes the specific controls,     │
│     scoring weights, and section requirements for that industry.           │
│                                                                            │
│  6. FULL AUDIT TRAIL FOR REGULATORS                                        │
│     Every decision is exportable as a self-contained, signed,              │
│     verifiable bundle suitable for regulatory submission, audit            │
│     review, or legal discovery.                                            │
│                                                                            │
│  7. HUMAN-IN-THE-LOOP BY DESIGN                                           │
│     Multi-role evidence capture ensures decisions reflect input from       │
│     CTO, CSO, CIO, EA, and other stakeholders — not just one voice.       │
└────────────────────────────────────────────────────────────────────────────┘
```

---

## 13. Target Use Cases

| Use Case | How DIIaC Serves It |
|---|---|
| **Regulated procurement decisions** | Profile-enforced governance + signed export for audit |
| **Board-level strategic decisions** | Multi-role evidence + structured board report output |
| **Vendor down-selection** | Deterministic scoring matrix with sector-weighted criteria |
| **Compliance-driven IT decisions** | Required controls enforcement + evidence trace mapping |
| **LLM-assisted decision workflows** | LLM synthesis with deterministic governance guardrails |
| **Audit/regulatory submissions** | Self-contained signed decision packs with Merkle proofs |
| **Cross-stakeholder decision governance** | CTO/CSO/CIO/EA multi-role evidence collection |
| **Decision reproducibility** | Replay attestation proves identical-input = identical-output |

---

## 14. Roadmap Vision (v1.3.0+)

```
┌────────────────────────────────────────────────────────────────────┐
│                    EVOLUTION TRAJECTORY                              │
│                                                                    │
│  v1.2.0 (Current)                                                  │
│  ─────────────────                                                 │
│  Production-ready runtime with full compile/verify/export/audit    │
│                                                                    │
│       │                                                            │
│       ▼                                                            │
│  v1.2.x (Hardening)                                                │
│  ───────────────────                                               │
│  • Confidence scoring model in outputs                             │
│  • Governance modes[] policy packs                                 │
│  • "Decision not recommended" path when controls fail              │
│  • Board-ready markdown with ranked options                        │
│                                                                    │
│       │                                                            │
│       ▼                                                            │
│  v1.3.0 (Headless Governance Plane)                                │
│  ──────────────────────────────────                                │
│  • API-first/headless operation (UI becomes optional)              │
│  • External intent ingestion from LLM-native channels              │
│  • Policy pack versioning + signed policy manifests                │
│  • Confidence/trust scoring as first-class API fields              │
│                                                                    │
│       │                                                            │
│       ▼                                                            │
│  v1.3.0+ (Enterprise Integration)                                  │
│  ────────────────────────────────                                  │
│  • Copilot/enterprise extension boundary intercept                 │
│  • Response governance layer before user-visible output            │
│  • Hallucination/drift scoring                                     │
│  • Human approval gates for high-risk decisions                    │
│  • Immutable audit lineage for regulator export                    │
└────────────────────────────────────────────────────────────────────┘
```

---

## 15. Summary Statement

**DIIaC v1.2.0 is a production-ready deterministic governance runtime** that bridges the gap between AI-assisted strategic thinking and the cryptographic verifiability demanded by regulated industries. It captures multi-stakeholder decision evidence, enforces sector-specific governance profiles, produces deterministic and reproducible decision artifacts, seals them with SHA-256 hashes, Ed25519 signatures, and Merkle proofs, chains them into a tamper-evident trust ledger, and packages everything into a signed, auditable decision pack ready for board review or regulatory submission.

**The core promise:** *Use AI to help you think. Use DIIaC to prove what you decided.*
