# DIIaC UI Workflow Guide (Production)

This guide explains exactly how to populate the UI, what each field means, what to enter, and how to execute a full governed workflow from intent to verifiable decision pack.

## Who this is for
- Product/strategy teams preparing board decisions.
- Architecture/security/governance leaders validating options under policy constraints.
- Operations/compliance teams who need reproducible, auditable outputs.

## Core idea in one line
DIIaC combines **LLM-assisted synthesis** with **deterministic governed compile** so decision outputs are both high-value and cryptographically verifiable.

---

## End-to-end workflow (mapped to the previous sequence image)

1. **Enter human intent + role evidence** in the UI.
2. **Submit role input** to create decision context records.
3. **Select profile + schema + governance levels (R/P)**.
4. **Run Governed Compile** (production path):
   - Bridge can synthesize LLM structure from intent.
   - Runtime executes deterministic governed compile as authoritative step.
5. **Review execution outputs** (execution ID, scoring, trace map, trust status).
6. **Run verification/attestation** (`verify execution`, `pack`, `replay`, `merkle`).
7. **Export package** for stakeholders + optional audit bundle.

---

## UI walkthrough: exactly what to populate

### 1) Decision Evidence Workspace (Production)
Use this as the primary workflow panel.

#### Human Intent (free text)
What it is:
- The business problem, desired outcome, constraints, and success criteria.

What to include:
- Decision objective (e.g., “select strategic SD-WAN vendor for 5-year rollout”).
- Scope and timeline.
- Key constraints (budget, compliance, architecture standards).
- Outcome expectations (cost, risk reduction, delivery speed, resilience).

Prompt template:
- “We need to decide between Vendor A and Vendor B for [scope].
  Constraints: [budget/compliance/legacy dependencies].
  Success in 12 months means [quantified outcomes].
  Non-negotiables are [items].”

#### Execution Context ID
What it is:
- A stable identifier that ties all role inputs to one governed compile context.

How to populate:
- Use a meaningful ID, for example:
  - `ctx-network-2026q1`
  - `ctx-uk-rail-sdwan-phase1`

Guidance:
- Reuse the same context ID while refining role inputs for the same decision cycle.

#### Role (dropdown)
What it is:
- The perspective that contributes evidence (CIO, enterprise architect, etc.).

How to use:
- Choose the role that owns the evidence you are about to submit.
- Repeat submission for multiple roles to build multi-role context.

#### Domain (free text)
What it is:
- A short label describing the evidence domain.

What to enter:
- Examples: `network-transformation`, `cyber-risk`, `service-operations`, `regulatory-compliance`.

Why it matters:
- Helps structure and interpret role assertions in governance context.

#### Assertion (free text)
What it is:
- The concrete claim/recommendation from that role.

What to enter:
- A clear, decision-relevant statement with implied or explicit evidence.
- Example: “Vendor B provides lower 5-year TCO with acceptable compliance risk under phased rollout.”

Good assertion checklist:
- Specific
- Testable/defensible
- Decision-relevant
- Not generic marketing language

#### Submit Role Input (button)
What it does:
- Stores this role evidence for the selected execution context.
- If Human Intent is populated, it is saved as the latest intent context.

---

### 2) Governance controls before compile

#### Business Profile
What it is:
- Sector/operating profile contract that defines allowed schemas and required sections.

How to choose:
- Pick the profile closest to your operating domain (e.g., transport, finance, healthcare).

#### Schema
What it is:
- The report contract/template allowed by the selected business profile.

How to choose:
- Use board-report schema for executive decisions.
- Ensure the schema aligns to review audience and governance needs.

#### Reasoning Level (R)
What it controls:
- Depth/complexity of analysis.

Typical use:
- `R2/R3` for rapid strategy cycles.
- `R4/R5` for board-level, multi-scenario, high-stakes decisions.

#### Policy Level (P)
What it controls:
- Governance strictness and required policy sections.

Typical use:
- `P1/P2` for lighter governance cycles.
- `P3+` for regulated/assurance-heavy contexts.

---

### 3) Run Governed Compile

#### Run Governed Compile (button)
Production behavior:
- Executes the production orchestration path where LLM-assisted synthesis is combined with deterministic governed compile.
- Returns authoritative execution ID from governed compile flow.

Expected output:
- Execution ID
- Pack hash / manifest-linked artifacts
- Deterministic governance outputs suitable for verification/export

---

## Real-world example use case (board decision)

## Scenario
A UK transport operator must choose SD-WAN strategy between two vendors for national rollout.

### Example inputs
- Human Intent:
  - “Select SD-WAN vendor for 3-year national rollout.
     Constraints: £2m capex cap, GDPR + NIS2 obligations, minimize service interruption.
     Success: 20% incident reduction, 15% lower run costs, improved branch uptime.”
- Role: `CIO`
- Domain: `network-transformation`
- Assertion:
  - “Vendor B is preferred due to lower TCO and faster phased migration with acceptable compliance controls.”
- Profile: `transport_profile_v1`
- Schema: `GENERAL_SOLUTION_BOARD_REPORT_V1`
- Reasoning: `R5`
- Policy: `P3`

### Expected outcome quality
- Board-ready structured report sections.
- Traceable evidence mapping and deterministic scoring artifacts.
- Verifiable package suitable for governance/compliance review.

---

## What to do after compile (must-do verification)

1. Verify execution integrity.
2. Verify pack/merkle/replay as needed.
3. Review trust status and admin logs.
4. Export signed package and optional audit bundle.

This is what makes the output operationally trustworthy, not just well-written.

---

## Why this is valuable vs normal AI reporting

- LLM adds synthesis speed and depth.
- Governance runtime enforces deterministic policy constraints.
- Cryptographic and replay surfaces provide verifiability.
- You can defend not only the recommendation, but the process used to generate it.

---

## Capability summary and key benefits

### 1) Deterministic governed compile
- Benefit: reproducibility and stable attestation under strict mode.
- Provides: deterministic execution artifacts, consistent policy enforcement.

### 2) LLM-orchestrated production compile
- Benefit: richer strategic content with governance-safe finalization.
- Provides: LLM-assisted context synthesis + deterministic authoritative compile.

### 3) Cryptographic verification surfaces
- Benefit: confidence and auditability in regulated contexts.
- Provides: pack verification, merkle proofs, replay checks, signed exports.

### 4) Admin and operational controls
- Benefit: production observability and operational readiness.
- Provides: health, metrics, logs, audit export, DB status/maintenance endpoints.

### 5) Multi-role evidence model
- Benefit: balanced decisions across business, architecture, risk, and security viewpoints.
- Provides: role-scoped assertions and evidence references bound to execution context.

---

## Practical operating policy recommendation

- **Production decisions**: use Decision Evidence Workspace + Run Governed Compile.
- **Exploration/drafts**: use exploratory panel only for ideation; do not treat as attested final output.
- **Always** retain execution IDs and verification artifacts in governance records.

