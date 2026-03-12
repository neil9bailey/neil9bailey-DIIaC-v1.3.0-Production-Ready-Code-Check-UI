> Historical archive notice: This document is retained for audit traceability and is not the authoritative source for current v1.3.0-ui operations. Use docs/README.md and current deployment/security runbooks for active guidance.
# DIIaC Real-World E2E Assurance Report (HITL)

## Objective
Validate a full production-flow run where human intent is combined with LLM-assisted synthesis and deterministic governed compile to produce verifiable decision artefacts.

## Test scenario
**Use case:** UK rail network SD-WAN transformation decision.

**Human intent used:**
- Assess vendor strategy for national rail operations.
- Reduce incidents by 20%.
- Maintain GDPR/NIS2 compliance.
- Minimize migration disruption.

## Execution setup
- Runtime: `STRICT_DETERMINISTIC_MODE=true`
- Bridge: `LLM_INGESTION_ENABLED=true`, `LLM_STUB_ENABLED=true`, `PYTHON_BASE_URL=http://127.0.0.1:8000`
- Production endpoint exercised: `POST /api/llm-governed-compile`

## Input payload (bridge production endpoint)
```json
{
  "execution_context_id": "ctx-bridge-uk-rail-2026q1",
  "profile_id": "transport_profile_v1",
  "schema_id": "GENERAL_SOLUTION_BOARD_REPORT_V1",
  "reasoning_level": "R5",
  "policy_level": "P3",
  "role": "CIO",
  "domain": "network-transformation",
  "assertions": [
    "Select resilient SD-WAN strategy with auditable controls and lower 5-year TCO."
  ],
  "provider": "ChatGPT",
  "human_intent": "Assess SD-WAN vendors for UK rail operations. Must reduce incidents by 20%, maintain GDPR/NIS2 compliance, and minimize migration disruption."
}
```

## Key output evidence
- `mode`: `llm_plus_deterministic_governed_compile`
- `llm_output_hash`: `d25f585bad88e792f159561522566be97f830e5c6034164292548186efab442e`
- `execution_id`: `8e35778c-cb31-5a71-b629-1b238af42bce`
- `pack_hash`: `ea034a90af4de965bc30671f2cf8ea16dc943dee7223ff5e6e7c8935c5a949f9`
- `manifest_hash`: `c100c4394798ad5def7f091cfeb3e80e0366ff47a047a452c93d46f9a5450358`
- `merkle_root`: `84845e0718977d563afdba5390a65ca6d09f8a38af0f456bda45662c01e813ee`
- `verify_execution.status`: `VERIFIABLE`
- `verify_pack.overall_valid`: `true`
- `signed export bytes`: `894`

## Artefacts produced (reported by `/executions/<id>/reports`)
1. `board_report.json`
2. `business_profile_snapshot.json`
3. `deterministic_compilation_log.json`
4. `down_select_recommendation.json`
5. `evidence_trace_map.json`
6. `governance_manifest.json`
7. `profile_compliance_matrix.json`
8. `profile_override_log.json`
9. `role_input_bundle.json`
10. `schema_contract.json`
11. `scoring.json`
12. `signed_export.sig`
13. `signed_export.sigmeta.json`
14. `trace_map.json`
15. `vendor_scoring_matrix.json`

## Decision-readiness interpretation
This run demonstrates that DIIaC can produce:
- Human-led problem framing (HITL intent and role evidence).
- Machine-assisted synthesis (LLM stage with explicit hash traceability).
- Deterministic governance finalization (runtime authoritative compile).
- Cryptographically verifiable outputs (manifest, merkle root, signatures, verification endpoints).

## Assurance conclusion
The production path is operating as designed for governed decision-making: **human intent + LLM assistance + deterministic compilation + verifiable artefact chain**.

## Reproduction note
Raw machine output from this run was captured at:
- `/tmp/diiac_bridge_realworld_strict.json`

