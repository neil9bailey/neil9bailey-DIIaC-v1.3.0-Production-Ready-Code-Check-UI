# DIIaC v1.2.0 — Comprehensive Product Briefing

**Decision Intelligence Infrastructure as Code**
*Version 1.2.0 — Production-Ready Release*

---

## 1. Executive Summary

DIIaC (Decision Intelligence Infrastructure as Code) is the first platform to treat **organisational decisions as deployable, immutably ledger-anchored, cryptographically attested infrastructure** — the same way Terraform treats cloud resources or Kubernetes treats workloads. It provides a deterministic governance runtime that ingests human intent, optionally incorporates LLM-assisted analysis, and compiles it into a cryptographically sealed, auditable decision package that can be independently verified, replayed, and exported.

Version 1.2.0 is the production-ready baseline: a fully operational three-tier stack (React frontend, Node.js bridge, Flask governance runtime) with 25,000+ lines of production code, 15 cryptographically bound artefact types per decision, Ed25519 digital signatures, SHA-256 Merkle tree verification, and a complete offline verification capability — all demonstrated end-to-end against a real-world UK Rail Network SD-WAN transformation scenario.

---

## 2. What DIIaC Actually Is

### The Core Insight

Every organisation makes high-stakes decisions — vendor selections, architecture choices, compliance assessments, investment approvals — yet these decisions live in slide decks, emails, and meeting notes. They are:

- **Not reproducible** — run the same decision process twice, get different results
- **Not verifiable** — no cryptographic proof that evidence was actually considered
- **Not auditable** — no tamper-evident chain linking intent to outcome
- **Not governed** — no enforcement that policy, role authority, or compliance requirements were met

DIIaC solves this by treating decisions the way modern infrastructure treats deployments: as **compiled, versioned, signed, and immutably ledger-anchored artefacts** produced by a deterministic pipeline.

### The "Infrastructure as Code" Analogy

| IaC Concept | DIIaC Equivalent |
|---|---|
| Terraform plan | Governed compile (deterministic decision compilation) |
| State file | Trust ledger (hash-chained, append-only) |
| Provider plugins | Business profile contracts (domain-specific governance rules) |
| Module registry | Schema contracts (GENERAL_SOLUTION_BOARD_REPORT_V1, etc.) |
| Plan/apply cycle | Human intent capture → LLM synthesis → deterministic compile → verify |
| Drift detection | Replay attestation (re-execute and compare hashes) |
| Signed artefacts | Ed25519 signed decision packs with Merkle proofs |

---

## 3. Architecture

### Three-Tier Production Stack

```
┌─────────────────────────────────────────────────────────┐
│                    FRONTEND (React/Vite)                 │
│  Decision Evidence Workspace · Trust Dashboard           │
│  Multi-Role Compile Panel · Governance Metadata Viewer   │
│  Admin Console · Impact/Policy/Compliance Viewers        │
│                    :5173                                 │
└──────────────────────┬──────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────┐
│              BACKEND UI BRIDGE (Node.js/Express)         │
│  LLM Orchestration · Intent Synthesis · Evidence Hashing │
│  Role Evidence Forwarding · Compile Orchestration        │
│                    :3001                                 │
└──────────────────────┬──────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────┐
│          GOVERNANCE RUNTIME (Python/Flask)                │
│  Deterministic Compile Engine · Trust Ledger              │
│  Cryptographic Verification Surfaces · Merkle Binding    │
│  Signed Export · Audit Trail · Admin APIs                 │
│                    :8000                                 │
└─────────────────────────────────────────────────────────┘
```

### Deployment Model

- **Docker Compose** — single-command full-stack deployment (`docker compose up --build`)
- **Three containers** + **four named volumes** (artefacts, exports, audit, trust ledger)
- Configurable host port mapping for conflict-free operation
- Development-safe defaults with production-mode hardening via environment variables

---

## 4. Complete Feature Inventory

### 4.1 Deterministic Governance Compilation

The core of DIIaC: a **deterministic compile pipeline** that transforms human intent + business profile + policy constraints into a sealed decision package.

- **Profile-driven compilation** — domain-specific business profiles (e.g., `transport_profile_v1`) define governance rules, compliance requirements, and scoring criteria
- **Schema contracts** — structural templates (e.g., `GENERAL_SOLUTION_BOARD_REPORT_V1`) ensure consistent decision output format
- **Reasoning and policy levels** — configurable R1-R5 reasoning depth and P1-P5 policy strictness
- **Role-based authority** — CIO, CTO, CISO, CFO role bindings with tier enforcement
- **Strict deterministic mode** — `STRICT_DETERMINISTIC_MODE=true` guarantees identical inputs produce identical outputs, pack hashes, and scores
- **Multi-role compilation** — multiple stakeholders contribute role evidence to a single governed decision

### 4.2 Human-in-the-Loop (HITL) + LLM Integration

DIIaC is explicitly designed so that **AI assists but does not decide**:

1. **Human intent capture** — operators enter problem framing, assertions, and domain context
2. **Role evidence submission** — structured role inputs with domain and assertion fields
3. **LLM synthesis** — the bridge layer optionally calls an LLM (OpenAI/ChatGPT) to synthesise analysis from human intent
4. **LLM output hashing** — every LLM response is SHA-256 hashed and bound into the evidence chain
5. **Deterministic finalization** — the governance runtime performs the authoritative compile, not the LLM
6. **LLM stub fallback** — `LLM_STUB_ENABLED=true` provides a deterministic stub when no API key is available, ensuring the pipeline works without external dependencies

**Key principle:** The LLM is a *contributor of evidence*, not the decision-maker. The deterministic compile is always the final authority.

### 4.3 Cryptographic Verification Layer

Every decision is cryptographically sealed with multiple independent verification surfaces:

| Capability | Implementation |
|---|---|
| **Context hash** | SHA-256 hash of the execution context binding all inputs |
| **Pack hash** | SHA-256 hash of the complete decision package |
| **Manifest hash** | SHA-256 hash of the governance manifest linking all artefacts |
| **Merkle root** | Binary Merkle tree over all artefacts (lexicographic leaf sort, odd-leaf duplication) |
| **Merkle proofs** | Per-artefact inclusion proofs verifiable offline |
| **Ledger chaining** | Append-only trust ledger with hash-chain linking successive executions |
| **Digital signatures** | Ed25519 signing of decision packs with key ID binding |
| **Public key registry** | Runtime-served key registry for independent verification |

### 4.4 Verification Endpoints

Five independent verification surfaces, each usable standalone:

| Endpoint | Purpose |
|---|---|
| `GET /verify/execution/<id>` | Full execution verification state |
| `POST /verify/pack` | Pack hash + manifest hash integrity check |
| `POST /verify/merkle-proof` | Merkle inclusion proof validation |
| `POST /verify/replay` | Replay execution and compare hashes (drift detection) |
| `GET /verify/public-keys` | Retrieve signing key registry |

### 4.5 Trust and Audit Operations

- **Trust ledger** — append-only, hash-chained record of all governance executions
- **Trust status API** — `GET /trust/status` exposes current ledger state, growth metrics, and chain integrity
- **Evidence trace mapping** — `evidence_trace_map.json` links every artefact to its originating evidence
- **Audit export** — `POST /admin/audit-export` generates timestamped, comprehensive audit packages
- **Structured logging** — all backend events carry stable `event_id` values for audit triage
- **Operational metrics** — `GET /admin/metrics` with alerts and threshold recommendations

### 4.6 Decision Artefacts (15 per execution)

Every governed compile produces a complete, self-contained decision package:

1. **board_report.json** — the final decision document, structured for board-level review
2. **governance_manifest.json** — links all artefacts with their hashes and governance metadata
3. **vendor_scoring_matrix.json** — quantitative scoring of evaluated options
4. **scoring.json** — detailed scoring breakdown with rationale
5. **down_select_recommendation.json** — ranked recommendation with evidence binding
6. **evidence_trace_map.json** — full evidence-to-artefact traceability
7. **trace_map.json** — execution path tracing
8. **role_input_bundle.json** — all role evidence inputs preserved
9. **business_profile_snapshot.json** — the profile contract used at compile time
10. **schema_contract.json** — the schema contract governing output structure
11. **profile_compliance_matrix.json** — compliance assessment against profile requirements
12. **profile_override_log.json** — any profile overrides applied during compilation
13. **deterministic_compilation_log.json** — step-by-step compilation audit trail
14. **signed_export.sig** — Ed25519 signature over the decision pack
15. **signed_export.sigmeta.json** — signature metadata (key ID, algorithm, timestamp)

### 4.7 Frontend Capabilities

A React/Vite/TypeScript production UI with purpose-built governance panels:

- **Decision Evidence Workspace** — production-mode human intent and role evidence capture
- **Multi-Role Governed Compile Panel** — profile selection, compile initiation, status tracking
- **Governed Report Viewer** — structured display of board reports and recommendations
- **Trust Dashboard** — real-time trust ledger visualisation and chain integrity
- **Governance Metadata Panel** — execution hashes, verification status, Merkle roots
- **Admin Console** — health, logs, metrics, audit export management
- **Policy Diff Viewer** — compare policy configurations
- **Derived Compliance Panel** — compliance matrix display
- **Impact Viewer** — decision impact assessment display

### 4.8 Production Hardening

- **Admin authentication** — bearer token auth on all `/admin/*` routes (enforced in non-dev environments)
- **Payload validation bounds** — schema-enforced size/type constraints on all write endpoints
- **Runtime readiness checks** — `/health` and `/admin/health` verify storage, contracts, keys, and DB presence
- **Structured error taxonomy** — `ARTIFACT_STORAGE_UNAVAILABLE`, `RUNTIME_DEPENDENCY_TIMEOUT`, `EXPORT_STORAGE_UNAVAILABLE`, `AUDIT_STORAGE_UNAVAILABLE`, `SIGNATURE_METADATA_UNAVAILABLE`
- **Deterministic replay** — tamper detection via hash comparison on replay
- **Offline verification** — signed exports can be verified without runtime access

---

## 5. Real-World Validation

### UK Rail Network SD-WAN Transformation

DIIaC v1.2.0 has been validated end-to-end against a real-world enterprise decision scenario:

**Scenario:** A UK national rail operator evaluating SD-WAN transformation strategy across their network, requiring vendor assessment, incident reduction targets (20%), GDPR/NIS2 compliance, and migration risk minimisation.

**Execution:**
- Role: CIO, domain: network-transformation
- Profile: `transport_profile_v1`
- Schema: `GENERAL_SOLUTION_BOARD_REPORT_V1`
- Reasoning: R5 (maximum depth), Policy: P3
- LLM synthesis + deterministic governed compile

**Results:**
- Mode: `llm_plus_deterministic_governed_compile`
- 15 artefacts produced with full cryptographic binding
- Pack hash, manifest hash, and Merkle root all independently verifiable
- Verification status: **VERIFIABLE**
- Pack integrity: **overall_valid = true**
- Signed export: 894 bytes, independently verifiable offline
- Replay attestation: deterministic hash match confirmed

This demonstrates the complete production loop: **human intent → LLM-assisted analysis → deterministic compilation → cryptographic verification → offline-verifiable export**.

---

## 6. Market Positioning and Competitive Analysis

### 6.1 Market Category: Decision Intelligence Infrastructure

DIIaC operates at the intersection of three converging markets:

1. **Decision Intelligence** (Gartner Top Strategic Technology Trend) — tools that improve decision-making through data, analytics, and AI
2. **GRC / Governance Automation** — platforms for compliance, risk, and audit
3. **AI Governance / Responsible AI** — frameworks for governing AI-assisted outputs

### 6.2 Why Nothing Like This Exists

| Capability | Traditional BI/Analytics | Decision Intelligence Platforms | GRC Tools | DIIaC v1.2.0 |
|---|---|---|---|---|
| Deterministic decision compilation | No | No | No | **Yes** |
| Cryptographic decision verification | No | No | Partial (logs) | **Yes (5 surfaces)** |
| Merkle tree artefact binding | No | No | No | **Yes** |
| Ed25519 signed decision packs | No | No | No | **Yes** |
| Offline verification capability | No | No | No | **Yes** |
| LLM synthesis with hash traceability | No | Partial | No | **Yes** |
| Replay attestation (drift detection) | No | No | No | **Yes** |
| Human-in-the-loop + deterministic finalization | No | Partial | No | **Yes** |
| Profile-driven governance contracts | No | No | Partial | **Yes** |
| Hash-chained trust ledger | No | No | No | **Yes** |

**Closest competitors and how DIIaC differs:**

- **Palantir Foundry / Decisions** — powerful data integration and analytics, but decisions are not compiled, signed, or independently verifiable. No deterministic replay.
- **IBM Watson / Decision Optimization** — optimisation engine, not a governance infrastructure. No cryptographic attestation.
- **Salesforce Einstein / Tableau** — analytics and prediction, not decision governance. No artefact verification.
- **ServiceNow GRC** — compliance workflow tooling, but decisions are ticket-state, not cryptographically sealed artefacts.
- **Archer / RSA** — traditional GRC with audit trails, but no deterministic compilation, no Merkle binding, no signed exports.
- **Dataiku / H2O.ai** — ML/AI platforms with some governance features, but focused on model governance, not decision governance.
- **LangChain / LlamaIndex** — LLM orchestration frameworks with no governance, verification, or decision compilation capability.

### 6.3 Market Ranking

DIIaC is **category-defining**. It does not compete within existing categories — it creates a new one:

**Decision Intelligence Infrastructure as Code (DIIaC)**

This positions alongside:
- IaC (Terraform, Pulumi) — infrastructure as code
- GitOps (ArgoCD, Flux) — operations as code
- Policy as Code (OPA, Sentinel) — policy as code
- **DIIaC** — decisions as code

In terms of maturity and capability completeness for its category, DIIaC v1.2.0 is analogous to **Terraform v0.12** — the version where Terraform became genuinely production-usable with a rich expression language, state management, and provider ecosystem. DIIaC v1.2.0 has the deterministic engine, cryptographic layer, verification surfaces, and production hardening to serve as the foundation for enterprise adoption.

---

## 7. Alignment to "Decision Intelligence Infrastructure as Code"

### 7.1 Decision Intelligence

DIIaC implements Decision Intelligence not as a dashboard or analytics layer, but as **executable infrastructure**:

- **Structured decision capture** — human intent, role evidence, domain context, and assertions are formalised inputs, not free-form notes
- **Evidence-based compilation** — decisions are compiled from evidence, not opinions; every input is traced to its output impact
- **Quantitative scoring** — vendor scoring matrices and confidence assessments provide measurable decision quality
- **LLM augmentation with governance guardrails** — AI contributes evidence but the deterministic engine governs the outcome
- **Board-ready outputs** — structured reports designed for executive and board-level consumption

### 7.2 Infrastructure

DIIaC treats decisions as infrastructure with the same rigour as cloud resources:

- **Deterministic** — same inputs always produce the same outputs (strict deterministic mode)
- **Versioned** — execution IDs, pack hashes, and ledger positions provide full version history
- **Deployable** — Docker Compose single-command deployment with environment-based configuration
- **Observable** — health checks, metrics, structured logging, and trust dashboards
- **Recoverable** — replay attestation can re-execute any decision and verify hash consistency

### 7.3 As Code

The "as Code" dimension means decisions are:

- **Profile contracts** — JSON-based governance rules that define domain-specific compilation behaviour
- **Schema contracts** — structural templates that enforce output format consistency
- **Programmable verification** — five API endpoints for automated verification pipeline integration
- **CI/CD compatible** — deterministic outputs and API-first design enable pipeline integration
- **Git-friendly** — contracts, profiles, and schemas are version-controlled artefacts

---

## 8. Technical Specifications

| Dimension | Detail |
|---|---|
| **Codebase** | ~25,000 lines across Python, TypeScript/React, Node.js |
| **Source files** | 28 source files + 1 test file + 311 spec/documentation files |
| **Runtime** | Flask (Python) — governance engine |
| **Bridge** | Express (Node.js) — LLM orchestration and UI integration |
| **Frontend** | React + Vite + TypeScript |
| **Hash algorithm** | SHA-256, lowercase hex |
| **Signature algorithm** | Ed25519 |
| **Merkle tree** | Binary, lexicographic leaf sort, odd-leaf duplication |
| **Deployment** | Docker Compose (3 containers, 4 volumes) |
| **Environments** | Development (auth bypassed) / Production (auth enforced) |
| **LLM integration** | OpenAI API (configurable), deterministic stub fallback |
| **Artefact types** | 15 per execution |
| **Verification surfaces** | 5 independent endpoints |
| **API endpoints** | 20+ governance, verification, trust, and admin endpoints |

---

## 9. Current Status

### v1.2.0 — Production-Ready Baseline (Current)

**Status: Scope-frozen, validation-gated, release-locked.**

All core capabilities are implemented and operational:

- Deterministic governed compile: **Operational**
- Cryptographic verification (all 5 surfaces): **Operational**
- Trust ledger with hash chaining: **Operational**
- Merkle binding and proofs: **Operational**
- Signed exports (Ed25519): **Operational**
- LLM-governed compile (bridge orchestration): **Operational**
- Multi-role evidence compilation: **Operational**
- Admin authentication and payload bounds: **Operational**
- Runtime readiness and health checks: **Operational**
- Audit export: **Operational**
- Frontend (all panels): **Operational**
- E2E real-world validation: **Passed** (UK Rail SD-WAN scenario)

**Validation gates passed:**
- `python3 -m py_compile app.py` — syntax verified
- `node --check backend-ui-bridge/server.js` — syntax verified
- `pytest -q` — all tests passing
- `npm run build` (frontend) — production build successful
- `scripts_e2e_runtime_smoke.py` — end-to-end smoke passed
- `scripts_production_readiness_check.py` — production readiness confirmed

**Remaining hardening (non-blocking):**
- Browser-level UI E2E tests and baseline screenshots
- Expanded operational threshold/alert recommendations
- Incident triage guidance documentation

### v1.3.0 — Headless Governance Plane (Next)

The roadmap for v1.3.0 transforms DIIaC from a UI-first platform to a **headless governance plane** that can mediate any LLM-native workflow:

**Phase A — Decision Quality and Confidence Layer:**
- Structured governance mode controls (prompt-mode policy packs)
- Confidence scoring model (score, level, rationale) in all outputs
- Recommendation contracts with evidence IDs, assumptions, risk treatment
- Deterministic "decision not recommended" path for control failures
- Board-ready markdown + JSON artefacts with ranked options

**Phase B — Headless Governance Plane:**
- API-first/headless operation (UI becomes optional)
- External intent ingestion from LLM-native channels
- Policy pack versioning with signed policy manifests
- Confidence and trust scoring as first-class API fields

**Phase C — Copilot/Enterprise Integration Overlay:**
- Request intercept via enterprise extension/agent boundary
- Response governance layer before user-visible output
- Evidence binding + unsupported-claim detection + confidence bounds
- Human approval gates for high-risk decisions
- Immutable audit lineage for regulator/auditor review

---

## 10. Impact and Value Proposition

### For Enterprises

- **Audit readiness** — every decision is cryptographically sealed and independently verifiable, satisfying SOX, NIS2, GDPR audit requirements
- **AI governance** — LLM outputs are explicitly hashed, traced, and subordinated to deterministic governance, addressing the "black box AI" regulatory concern
- **Decision quality** — structured compilation with profile-driven governance catches gaps, enforces compliance, and produces consistent outputs
- **Institutional memory** — hash-chained trust ledger creates a permanent, tamper-evident record of all organisational decisions
- **Board confidence** — structured, evidence-traced decision packages replace slide decks and ad-hoc justifications

### For Regulators and Auditors

- **Independent verification** — offline-verifiable signed exports mean auditors don't need runtime access
- **Tamper evidence** — any modification to any artefact invalidates the Merkle root, pack hash, and signature
- **Replay attestation** — re-execute any historical decision and cryptographically prove consistency
- **Evidence lineage** — trace any output back to its originating human intent and evidence inputs

### For the AI/LLM Industry

- **Governance layer for LLM-assisted decisions** — solves the "who decided this and why" problem for AI-augmented workflows
- **Deterministic finalization** — proves that a human-governed process, not an LLM alone, produced the final decision
- **Hash-bound LLM traceability** — every LLM contribution is explicitly captured, hashed, and linked into the evidence chain
- **Foundation for responsible AI** — provides the missing infrastructure layer between "AI generated this" and "this decision is governed, immutably ledger-anchored, and auditable"

---

## 11. Summary: Why DIIaC Matters

DIIaC v1.2.0 represents the emergence of a new infrastructure category. Just as:

- **Git** made code version-controlled and collaborative
- **Terraform** made infrastructure declarative and reproducible
- **Kubernetes** made workloads deployable and observable

**DIIaC makes organisational decisions deterministic, immutably ledger-anchored, and auditable.**

In a world where AI is increasingly involved in high-stakes decisions, the ability to prove — cryptographically — that a governed process was followed, that evidence was considered, that human authority was exercised, and that the output has not been tampered with, is not a nice-to-have. It is becoming a regulatory and operational necessity.

DIIaC v1.2.0 is the production-ready foundation for that future.

---

*DIIaC v1.2.0 — Decision Intelligence Infrastructure as Code*
*Production-Ready Release — Scope Frozen — Validation Passed*
