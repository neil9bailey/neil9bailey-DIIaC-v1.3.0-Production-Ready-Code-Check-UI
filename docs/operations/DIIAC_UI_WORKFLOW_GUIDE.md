# DIIaC UI Report Compilation Guide (v1.3.0-ui)

This guide is the operator playbook for compiling a high-quality governance report from the UI.
It maps each UI field to what it controls, what to enter, and what "good" looks like before sending to the LLM pipeline.

## 1. UI Map (Decision Evidence Workspace)

The compile workspace is split into four functional sections:

1. Intent + Context
- `Human Intent`
- `Execution Context ID` + `Generate from role/domain`

2. Role Evidence Input
- `Role`
- `Domain`
- `Assertion`
- `Evidence References`
- `Submit Role Input`

3. Compile Controls
- `Business Profile`
- `Schema`
- `Reasoning`
- `Policy`
- `Governance Modes`

4. Compile Action + Status
- `Run Governed Compile`
- Status banner with success/failure detail and execution ID

## 2. Field-By-Field Guide

### Human Intent
- Purpose: Gives the LLM the decision objective, hard constraints, and expected outcomes.
- Required in practice: Yes. The bridge compile flow rejects runs without stored intent (`no_human_intent`).
- Write like this: objective + constraints + measurable success criteria + decision ask.
- Good example:
  - "Decide whether to standardize on a single AI coding assistant platform for 1,200 engineers across UK/EU operations. Must meet GDPR, ISO 27001 controls, and SOC2 evidenceability. Budget cap: GBP 1.8M/year. Success = >=15% cycle-time reduction, <=3 months rollout wave 1, no increase in critical security incidents."
- Avoid:
  - "Need AI tool recommendation quickly."

### Execution Context ID
- Purpose: Correlates role submissions and compile run into one governance context.
- Format: lowercase, hyphenated ID; use `ctx-<domain>-<role>` pattern.
- Best practice: Reuse the same context ID for multi-role evidence (CIO/CTO/CFO, etc.) before final compile.
- Good example:
  - `ctx-ai-coding-assistant-cio`

### Role
- Purpose: Defines perspective and accountability context in role evidence.
- Options in UI:
  - `CIO`, `CTO`, `CFO`, `PROCUREMENT`, `CSO`, `ENTERPRISE_ARCHITECT`, `PRINCIPAL_ENGINEER`, `IT_SECTOR_LEAD`
- Best practice: Submit one role at a time with role-specific assertion and evidence.

### Domain
- Purpose: Functional domain for the decision.
- Write like this: concise, scoped domain phrase.
- Good example:
  - `ai-engineering-governance`
- Avoid:
  - `it`

### Assertion
- Purpose: The role's core claim/recommendation to be tested by governance.
- Write like this: one clear claim with expected business/technical outcome.
- Good example:
  - "Approve phased enterprise rollout of a governed AI coding assistant with strict policy gates and quarterly value realization checks."
- Avoid:
  - "AI is good and we should do it."

### Evidence References
- Purpose: Traceable evidence used to support assertions.
- Required: Minimum `2` strong refs (UI and backend gate).
- Strong refs include: URLs, URNs, document paths, hashes (for example `sha256:...`).
- Entry format: one item per line.
- Good example set:
  - `https://learn.microsoft.com/en-us/copilot/`
  - `urn:finance:business-case:ai-coding-assistant:2026-q1`
  - `sha256:3f1d0b0c5e6e0a1b2c3d4e5f60718293a4b5c6d7e8f90123456789abcdef0123`
- Avoid:
  - `teams message from john`

### Business Profile
- Purpose: Applies organization-specific governance contract (risk appetite, jurisdiction, required sections).
- Required: Yes.
- Rule: Chosen profile constrains valid schema choices.
- Best practice: Confirm profile matches the customer/legal operating model before compile.

### Schema
- Purpose: Selects report contract template for the output artifact.
- Required: Yes.
- Rule: Must be approved globally and allowed by selected business profile.
- Best practice: Keep schema stable through a decision cycle unless governance board agrees to a change.

### Reasoning
- Purpose: Controls analysis depth (`R2` to `R5`).
- Typical usage:
  - `R2-R3` for quick triage
  - `R4-R5` for board-grade submissions
- Recommendation for production decision packs: `R5`.

### Policy
- Purpose: Sets strictness level (`P1` to `P5`) for compliance/control framing.
- Typical usage:
  - `P1-P2` low assurance
  - `P3-P4` production governance
  - `P5` maximum strictness
- Recommendation for production decision packs: `P4` or `P5`.

### Governance Modes
- Available:
  - `FIRST-PRINCIPLES MODE`
  - `DEVIL'S ADVOCATE MODE`
  - `CONSTRAINTS-FIRST MODE`
  - `/deepresearch` (optional)
- Important behavior:
  - The first three modes are mandatory and are auto-enforced even if unchecked.
  - `/deepresearch` is optional and additive.

## 3. What Is Auto-Populated Behind The UI

When you click `Submit Role Input`, the UI sends:

- `non_negotiables`: `["privacy-by-design"]`
- `risk_flags`: `["vendor-lockin"]`

When you click `Run Governed Compile`, the bridge pipeline also enforces/sets:

- Mandatory governance modes (if missing)
- LLM audit timestamp
- LLM output hash reference added to evidence set
- Compile payload defaults for missing role content when needed

## 4. Operator Workflow (Best Practice)

1. Set `Business Profile` and verify allowed `Schema` first.
2. Fill `Human Intent` with objective, constraints, and success metrics.
3. Set `Execution Context ID` (or use `Generate from role/domain`).
4. Complete role input: `Role`, `Domain`, `Assertion`, `Evidence References`.
5. Check `Strong refs detected` is at least `2 / 2`.
6. Click `Submit Role Input`.
7. Repeat step 4-6 for additional roles using the same context ID.
8. Set final `Reasoning`, `Policy`, and optional `/deepresearch` mode.
9. Click `Run Governed Compile`.
10. Record returned execution ID and review generated reports.

## 5. Copy-Ready Example (High-Quality Submission)

Use this as a starter and adapt customer specifics.

- Human Intent:
  - "Decide whether to adopt a single enterprise AI coding assistant across engineering teams in UK/EU operations. Decision must preserve data protection obligations, maintain auditability, and avoid vendor lock-in. Budget ceiling is GBP 1.8M annualized. Required outcomes: >=15% software delivery cycle-time improvement by Q4, no increase in Sev1 incidents, and full evidence traceability for board oversight."
- Execution Context ID:
  - `ctx-ai-coding-assistant-cio`
- Role:
  - `CIO`
- Domain:
  - `ai-engineering-governance`
- Assertion:
  - "Approve phased enterprise rollout of a governed AI coding assistant platform with policy controls, human approval gates, and measurable value tracking."
- Evidence References:
  - `https://learn.microsoft.com/en-us/copilot/`
  - `https://www.iso.org/isoiec-27001-information-security.html`
  - `urn:strategy:board-paper:ai-coding-assistant:2026-q1`
  - `sha256:3f1d0b0c5e6e0a1b2c3d4e5f60718293a4b5c6d7e8f90123456789abcdef0123`
- Business Profile:
  - `it_enterprise_profile_v1` (or customer-specific equivalent)
- Schema:
  - `GENERAL_SOLUTION_BOARD_REPORT_V1`
- Reasoning:
  - `R5`
- Policy:
  - `P4`
- Governance Modes:
  - `FIRST-PRINCIPLES MODE`, `DEVIL'S ADVOCATE MODE`, `CONSTRAINTS-FIRST MODE`, optional `/deepresearch`

## 6. Quality Gate Before Clicking Compile

Confirm all are true:

- Human Intent is specific and measurable.
- Assertion is one clear claim (not a paragraph of mixed claims).
- At least 2 strong evidence refs are present; 3-5 is better.
- Evidence contains at least one internal reference (`urn:`/document) and one external authoritative source.
- Selected schema is valid for selected business profile.
- Reasoning/Policy levels match decision criticality.
- Context ID is reused for all role contributions in the same decision cycle.

## 7. Common Errors And Fast Fixes

- Error: `no_human_intent`
  - Fix: Populate `Human Intent` and submit role input before compile.

- Error: `At least 2 strong evidence refs are required`
  - Fix: Replace weak evidence with URL, URN, file path, or hash refs.

- Error: `schema_not_allowed_for_profile`
  - Fix: Switch to a schema listed for the chosen business profile.

- Error: `profile_not_found`
  - Fix: Select a valid `Business Profile` from the dropdown and retry.

- Error: `governed_compile_failed`
  - Fix: Check role input exists for context ID, then confirm policy/profile/schema combination.

## 8. Output Expectation

A successful run returns an execution ID and generates board-grade governance artifacts (reports, traceability outputs, signed decision pack export) bound to that execution context.
