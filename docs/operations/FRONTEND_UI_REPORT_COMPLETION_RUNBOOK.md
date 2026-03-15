# DIIaC Frontend Report Completion Runbook

This guide explains how to complete every field in the frontend UI to produce an accurate governed report.
It includes two complete worked examples and a precise summary of what happens when you submit.

## 1. Quick Operator Flow

1. Open **Decision Evidence Workspace (Production)** in the admin UI.
2. Enter **Human Intent**.
3. Set or generate **Execution Context ID**.
4. Complete role evidence fields and click **Submit Role Input**.
5. Select compile controls (Business Profile, Schema, Reasoning, Policy, Governance Modes).
6. Click **Run Governed Compile**.
7. Capture the returned `execution_id`.
8. Review policy semantics and report artifacts.

## 2. Field-by-Field Completion Guide

| UI field | What to put | Accuracy note (what makes output reliable) |
|---|---|---|
| `LLM Provider` (header badge) | Read-only in current UI (`Copilot`). | Provider label is passed to bridge/runtime, but recommendation logic is tested for provider-label invariance when evidence/scoring is unchanged. |
| `Human Intent` | 4 parts in one short paragraph: objective, constraints, measurable outcomes, decision ask. | If intent is vague, downstream assertions/evidence mapping becomes weak. Be concrete and measurable. |
| `Execution Context ID` | Stable ID for one decision cycle, for example `ctx-national-highways-hybrid-wan-2026q2`. | Reuse the same context for multi-role inputs. Changing context creates a separate evidence bundle. |
| `Role` | The accountable decision perspective (`CIO`, `CTO`, `CFO`, etc.). | Role drives framing and idempotency key generation for role submission. |
| `Domain` | Specific decision domain, for example `public-sector-network-modernisation`. | Keep domain narrow. Broad domains dilute assertions and evidence quality. |
| `Assertion` | One high-value claim to test, for example “approve phased migration...”. | Use one clear claim, not multiple mixed claims. |
| `Non-Negotiables` | Hard constraints separated by commas/new lines, for example budget, residency, uptime. | These are explicit constraints; do not leave key hard limits only in free text intent. |
| `Risk Flags` | Top risks to test explicitly, for example `migration-outage-risk`, `vendor-lockin`. | Include operational and compliance risks that could disqualify options. |
| `Goals` | Outcome goals, short and measurable where possible. | Goals help preserve business intent into deterministic compile checks. |
| `Regulatory Context` | Named obligations relevant to the decision. | If regulation is mentioned in intent but empty here, compile can hard-fail under quality gates. |
| `Success Targets` | Concrete target statements, for example `<=1% Sev1 increase`, `>=15% cycle-time reduction`. | If goals/targets are present in intent but omitted here, compile can hard-fail. |
| `Success Metrics` (`name\|baseline\|target\|unit\|window\|owner`) | One row per KPI. Baseline/target must be numeric. | Principle-only entries are rejected. Every row needs all 6 fields. |
| `Evidence References` | Strong refs only: URLs, URNs, hashes, or durable file references. At least 2 strong refs required. | Weak refs reduce evidence strength and may fail gates. Prefer first-party + independent evidence where possible. |
| `Business Profile` | Profile matching operating context and governance contract. | Profile constrains schema and policy interpretation. Use correct one for sector/use case. |
| `Schema` | Board/report schema allowed by selected profile. | Must be profile-allowed. Use stable schema for a decision cycle. |
| `Reasoning` (`R2`-`R5`) | `R4` or `R5` for board-level decisions. | Higher reasoning levels are better for complex, high-stakes decisions. |
| `Policy` (`P1`-`P5`) | `P4` or `P5` for high-assurance environments. | Higher policy levels tighten control posture and evidence expectations. |
| `Governance Modes` | Keep mandatory modes enabled: `FIRST-PRINCIPLES`, `DEVIL'S ADVOCATE`, `CONSTRAINTS-FIRST`. | Bridge enforces these required modes even if omitted. |
| `Submit Role Input` | Click after role fields are complete. | Stores role evidence bundle for the context. Submit before compile. |
| `Run Governed Compile` | Click after role submission and compile controls are set. | Triggers LLM + governed deterministic compile pipeline. |
| `Status` banner | Read and capture execution result and `execution_id`. | Use `execution_id` for downstream report retrieval, verification, and audit. |

## 2A. Exact Input Rules (Formatting, Spaces, Delimiters)

These rules reflect current frontend parsing and runtime gates.

### General list fields

Fields:
- `Non-Negotiables`
- `Risk Flags`
- `Goals`
- `Regulatory Context`
- `Success Targets`
- `Evidence References`

Accepted separators:
- newline
- comma `,`
- semicolon `;`

Normalization behavior:
- surrounding spaces are trimmed
- empty values are dropped
- duplicates are removed

Important:
- spaces are allowed inside values
- if you use commas inside one value, it will split into multiple values
- safest format for multi-word content is **one item per line**

### Success Metrics field

Expected row format:
- `metric_name|baseline|target_value|unit|measurement_window|owner`

Rules:
- rows are split by newline
- columns are split by pipe `|`
- at least 6 pipe-delimited columns required per row
- spaces are allowed around each column (they are trimmed)
- `baseline` and `target_value` must be numeric
- `metric_name`, `unit`, `measurement_window`, `owner` must be non-empty
- principle-only metric names (for example `privacy-by-design`, `deterministic-governance`, `security-first`) do not satisfy KPI requirements

Examples:
```text
WAN incident MTTR minutes|180|144|minutes|12 months|nh-noc-owner
Branch failover recovery minutes|40|34|minutes|9 months|nh-network-owner
```

Do not do this:
```text
UK data residency for log/telemetry stores| | |count|12 months|CTO
```

### Evidence references

Minimum:
- at least 2 strong refs are required before submit/compile

Strong refs include:
- `http://` / `https://`
- `urn:...`
- `sha256:...`
- durable file-style refs (path/document suffixes)

Best practice:
- one ref per line
- include first-party vendor refs and independent refs

### Execution Context ID

UI normalization behavior:
- lowercased
- only `a-z`, `0-9`, `-`
- max 64 chars
- repeated hyphens collapsed

Recommended pattern:
- `ctx-<customer>-<decision>-<period>`

## 3. Worked Example A: National Highways (Technical Solution)

Use case: public-sector National Highways secure ZTNA/SASE Hybrid WAN with SD-WAN overlay over existing MPLS core.

`Human Intent`
- Decide whether to implement a secure ZTNA SASE Hybrid WAN for National Highways using SD-WAN overlay on existing core MPLS backbone, preserving safety-critical network resilience and operational continuity. Must maintain UK data residency controls, no unplanned outage during phased migration, and measurable improvement in branch/edge performance. Decision required: approve phased national rollout and governance guardrails.

`Execution Context ID`
- `ctx-national-highways-hybrid-wan-2026q2`

`Role`
- `CTO`

`Domain`
- `public-sector-network-modernisation`

`Assertion`
- Approve phased deployment of secure ZTNA SASE hybrid WAN using SD-WAN overlay on MPLS core with no increase in Sev1 incidents and measurable reduction in incident resolution time.

`Non-Negotiables`
- UK data residency for log/telemetry stores
- no unplanned outage during migration windows
- retain MPLS core for critical fallback paths
- annual budget cap GBP 12m

`Risk Flags`
- migration-outage-risk
- vendor-lockin
- control-plane-security-risk
- service-assurance-risk

`Goals`
- improve edge security posture
- reduce branch failover latency
- improve incident triage speed

`Regulatory Context`
- UK GDPR
- Data Protection Act 2018
- NIS Regulations 2018

`Success Targets`
- <=1% Sev1 incident increase during migration
- >=20% reduction in MTTR for WAN/security incidents
- >=15% reduction in branch failover time

`Success Metrics`
```text
Sev1 incidents per quarter|22|22|incidents|12 months|nh-operations-owner
WAN incident MTTR minutes|180|144|minutes|12 months|nh-noc-owner
Branch failover time seconds|40|34|count|9 months|nh-network-owner
```

`Evidence References`
```text
https://www.fortinet.com/products/secure-sd-wan
https://www.fortinet.com/products/zero-trust-network-access
https://www.ncsc.gov.uk/collection/network-security
urn:national-highways:network-modernisation-board-paper:2026-q2
sha256:3f1d0b0c5e6e0a1b2c3d4e5f60718293a4b5c6d7e8f90123456789abcdef0123
```

`Business Profile`
- `it_enterprise_profile_v1` (or sector-specific profile if available in your deployment)

`Schema`
- `GENERAL_SOLUTION_BOARD_REPORT_V1`

`Reasoning`
- `R5`

`Policy`
- `P4`

`Governance Modes`
- `FIRST-PRINCIPLES MODE`
- `DEVIL'S ADVOCATE MODE`
- `CONSTRAINTS-FIRST MODE`
- optional: `/deepresearch`

## 4. Worked Example B: Financial Report (CFO Decision)

Use case: finance-led operating cost and control improvement report for treasury and reconciliation modernisation.

`Human Intent`
- Decide whether to fund a treasury and reconciliation modernisation programme to reduce manual reconciliation workload, improve control evidence quality, and reduce month-end close risk. Must stay within FY budget envelope, preserve auditability, and avoid increased financial control exceptions. Decision required: approve phased investment with KPI and control gates.

`Execution Context ID`
- `ctx-finance-reconciliation-modernisation-2026q2`

`Role`
- `CFO`

`Domain`
- `finance-controls-modernisation`

`Assertion`
- Approve phased finance reconciliation modernisation with deterministic governance controls to reduce close-cycle effort and exception rates within budget.

`Non-Negotiables`
- total programme budget <= GBP 3.2m
- no increase in high-severity financial control exceptions
- complete audit trail for all decision outputs

`Risk Flags`
- implementation-overrun-risk
- data-quality-risk
- control-exception-risk
- vendor-lockin

`Goals`
- reduce reconciliation manual effort
- reduce month-end close cycle time
- improve control evidence readiness

`Regulatory Context`
- SOX
- IFRS reporting controls
- UK GDPR

`Success Targets`
- >=25% reduction in manual reconciliation effort
- >=20% reduction in close cycle duration
- <=0.5% increase in high-severity control exceptions

`Success Metrics`
```text
Manual reconciliation hours per month|2400|1800|count|6 months|finance-ops-owner
Month-end close duration days|8|6|days|6 months|group-finance-owner
High-severity control exceptions per quarter|4|4|incidents|12 months|financial-controls-owner
```

`Evidence References`
```text
https://www.ifrs.org/issued-standards/list-of-standards/
https://www.sec.gov/spotlight/sarbanes-oxley.htm
urn:finance:board-paper:reconciliation-modernisation:2026-q2
urn:finance:baseline-kpi-pack:2026-q1
sha256:9b4d4a0f7cd9816ccaf38c5f87b8b4b8f4ce96eb264fba4f6ad9a012d90f4a31
```

`Business Profile`
- `it_enterprise_profile_v1` (or finance-specific profile in your environment)

`Schema`
- `GENERAL_SOLUTION_BOARD_REPORT_V1`

`Reasoning`
- `R5`

`Policy`
- `P4`

`Governance Modes`
- `FIRST-PRINCIPLES MODE`
- `DEVIL'S ADVOCATE MODE`
- `CONSTRAINTS-FIRST MODE`

## 5. What Happens After Submit (LLM + Governance Pipeline)

When you click **Submit Role Input**:

1. UI posts role payload to `/api/human-input/role`.
2. Runtime stores role assertions, constraints, risks, and evidence refs under the context ID.
3. Duplicate role submissions can be idempotently ignored.

When you click **Run Governed Compile**:

1. UI posts compile request to `/api/llm-governed-compile`.
2. Bridge validates/enforces required governance modes.
3. Bridge verifies that human intent exists.
4. Bridge sends intent/context to LLM generation (`generateAI`) with selected reasoning/policy/provider.
5. Bridge hashes LLM output (`llm_output_hash`) and builds compile payload with:
   - user constraints and evidence refs
   - LLM analysis sections
   - bridge metadata and audit timestamp
6. Bridge calls runtime `/api/governed-compile`.
7. Runtime executes deterministic governance/scoring/transformation and quality gates.
8. Runtime returns compile result, execution state, policy semantics, review state, and report metadata.
9. UI displays status and policy semantics in `PolicySemanticsPanel`.

## 6. What to Expect Back From the LLM Response

The LLM response is not treated as final truth. It is treated as structured input to governance compilation.

You receive:

- `execution_id` for traceability
- decision summary and recommendation
- per-control policy semantics including:
  - `assessment_mode`
  - `assurance_level`
  - `compliance_position`
  - `legal_confirmation_required`
  - `evidence_ids`
  - `residual_uncertainty`
- review/accountability state where applicable

## 7. Key Customer Benefits (Current Hardened State)

1. Stronger trust posture: non-dev trust and signing paths are gated; verification artifacts are explicit.
2. Better evidence integrity: claim/evidence binding and vendor-evidence mismatch controls reduce false confidence.
3. Board-grade output quality: required sections and measurable KPI enforcement reduce decision-useless reports.
4. Honest policy semantics: controls expose proof level and residual uncertainty, not just PASS labels.
5. Deterministic auditability: replay, signature verification, and decision-pack artifacts support due diligence and audit.
6. Human accountability: review state, approval events, exceptions, and waivers are visible for high-assurance outputs.

## 7A. If Customer Does Not Preselect a Vendor (Top-Vendor Down-Select Mode)

You can run vendor-neutral.

How:
1. Keep `Assertion` vendor-agnostic (do not name one vendor as mandatory).
2. Provide first-party evidence for each candidate vendor likely to rank in top positions.
3. Include independent evidence refs applicable across options.
4. Keep KPIs and constraints vendor-neutral and measurable.

Why this matters:
- runtime requires selected-vendor claims to be supported by selected-vendor evidence
- if winner is Vendor B but most primary evidence is Vendor A, you will hit:
  - `VENDOR_EVIDENCE_MISMATCH`
  - `COMPETITOR_PRIMARY_EVIDENCE`

Vendor-neutral assertion example:
- Approve the highest-scoring secure hybrid WAN option that meets regulatory constraints, no-unplanned-outage migration posture, and defined MTTR/failover KPI targets.

Vendor-neutral evidence pattern:
```text
https://www.paloaltonetworks.com/sase/prisma-sd-wan
https://www.fortinet.com/products/secure-sd-wan
https://www.cisco.com/site/us/en/products/networking/sd-wan/index.html
https://www.ncsc.gov.uk/collection/network-security
urn:national-highways:network-modernisation-board-paper:2026-q2
```

## 8. Final Accuracy Checklist Before Compile

1. Context ID is stable and reused for the decision cycle.
2. Human intent is specific and measurable.
3. At least 2 strong evidence refs are present.
4. Regulatory context is explicitly populated when regulation is relevant.
5. Success targets and KPI rows are fully populated and numeric where required.
6. Business profile/schema/reasoning/policy match decision criticality.
7. Required governance modes are enabled.
