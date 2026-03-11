# DIIaC v1.2.0 Capabilities Matrix

| Capability | Status | Operational Evidence |
|---|---|---|
| Context hash | Operational | compile response + execution state |
| Pack hash | Operational | compile response + verify endpoint |
| Manifest hash | Operational | verify execution + manifest artifact |
| Ledger chaining | Operational | `/trust/status`, `/admin/logs?source=ledger` |
| Merkle root binding | Operational | `/executions/<id>/merkle` |
| Merkle proof generation | Operational | `/executions/<id>/merkle/proof/<artefact_name>` |
| Signed export (Ed25519) | Operational | `/decision-pack/<id>/export-signed` + `signed_export.sigmeta.json` |
| Verify execution endpoint | Operational | `/verify/execution/<id>` |
| Verify pack endpoint | Operational | `/verify/pack` |
| Verify public keys endpoint | Operational | `/verify/public-keys` |
| Admin health/logs | Operational | `/admin/health`, `/admin/logs` |
| Audit export generation | Operational | `/admin/audit-export` |
| Multi-role compile | Operational | `/api/human-input/role`, `/api/governed-compile` |
| LLM-orchestrated deterministic compile | Operational | `/api/llm-governed-compile` (bridge) -> `/api/governed-compile` (runtime) |
| Tier enforcement R/P | Operational | board report + deterministic log |
| Evidence trace map | Operational | `evidence_trace_map.json`, `/executions/<id>/trace-map` |
| Deterministic strict mode | Operational | strict tests + stable execution/pack/score |
| Vendor scoring matrix | Operational | `/executions/<id>/scoring` + artifact |

| Replay attestation endpoint | Operational | `POST /verify/replay` + `replay_certificate.json` |
