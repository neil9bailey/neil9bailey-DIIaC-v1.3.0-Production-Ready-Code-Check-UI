# DIIaC Customer Value and Assurance Overview (2026-03-10)

## What This Solution Is

DIIaC is a **governance layer for LLM-assisted decisions**, not a replacement LLM. It wraps customer-selected models (currently staging is locked to Copilot) with deterministic policy controls, cryptographic traceability, and human accountability.

## What DIIaC Proves

When configured and operating correctly, DIIaC can prove:

- Who submitted what, under which role and execution context
- Which governance controls and policy packs were active
- Which evidence and claims were used
- Why a recommendation was accepted, deferred, or rejected
- That the exported decision pack is signed and tamper-evident
- That output can be replayed against deterministic inputs

This is the difference between "AI generated an answer" and "an auditable governance process accepted a decision outcome."

## Native LLM Use vs DIIaC Governance Wrap

| Dimension | Native LLM Use (No Governance Layer) | DIIaC Governance Layer |
|---|---|---|
| Identity and access | Often prompt-level identity only, weak role separation | Entra auth + RBAC enforced before privileged compile paths |
| Determinism | Non-deterministic session behavior, hard to replay | Deterministic compile policy (R/P), governed modes, frozen input model |
| Evidence quality | Optional and inconsistent citations | Structured evidence model, quality/freshness gates, claim mapping |
| Auditability | Prompt history may be incomplete/non-portable | Signed decision packs, manifests, ledger chain, replay checks |
| Regulatory mapping | Manual interpretation per team | Policy packs encode regulatory controls as machine-checkable gates |
| Board defensibility | Difficult to show governance intent-to-output lineage | End-to-end evidence trail from human intent to signed recommendation |

## Risk, Impact, and Potential Penalty Exposure Without Governance

Potential exposures for unmanaged native LLM decisioning include:

- Inability to evidence lawful and controlled processing decisions
- Weak accountability for high-impact recommendations
- Poor traceability of data provenance and stale/hallucinated evidence
- Greater enforcement exposure where legal obligations apply

### EU and UK Regulatory Context (as of 2026-03-10)

- **EU AI Act (Regulation (EU) 2024/1689):** official text includes administrative fine tiers up to:
  - EUR 35,000,000 or 7% global annual turnover (higher tier)
  - EUR 15,000,000 or 3%
  - EUR 7,500,000 or 1%
- **EU GDPR (Regulation (EU) 2016/679, Article 83):** up to EUR 20,000,000 or 4% (higher tier), and EUR 10,000,000 or 2% for lower-tier infringements.
- **UK GDPR / DPA 2018 (ICO guidance):** fines can be up to GBP 17.5 million or 4% annual worldwide turnover (higher tier), and GBP 8.7 million or 2% for lower tier.
- **UK AI regulation model:** UK government position remains principles-based/non-statutory through existing regulators; no single enacted UK-wide AI Act was identified in the reviewed government and Parliament sources.

See evidence source list in:

- `docs/release/evidence/2026-03-10-copilot-governance/external_regulatory_sources.md`

## What DIIaC Mitigates and Assures

DIIaC reduces risk by:

- Enforcing controlled compile pathways (not free-form unchecked generation)
- Capturing explicit human intent, role assertions, and governance modes
- Binding outputs to signed, hash-verifiable artifacts
- Preserving provenance for auditor replay and challenge
- Creating a repeatable governance envelope across LLM providers

## Strategic Customer Benefit

For customers, DIIaC turns LLM usage from an experimentation risk into an operationally governable decision system. That improves:

- executive confidence,
- regulatory defensibility,
- procurement and assurance readiness,
- and speed of safe AI adoption.

## Strategic Ecosystem Value

Because DIIaC is provider-agnostic by design, enterprises and LLM providers can converge on a common governance contract. That creates a practical path for DIIaC to become a "default assurance layer" where regulated AI decisions must withstand external audit scrutiny.

---

This overview is operational and governance analysis, not legal advice.
