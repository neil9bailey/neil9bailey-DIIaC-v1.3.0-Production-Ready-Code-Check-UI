# DIIaC v1.2.0 Admin Console User Guide

## Main Actions
- Submit role inputs: `POST /api/human-input/role`
- Run governed compile: `POST /api/governed-compile`
- Verify execution/pack/merkle: `/verify/*`
- Inspect trust status: `GET /trust/status`
- Fetch logs: `GET /admin/logs`, `GET /admin/executions/<id>/logs`
- Generate auditor package: `POST /admin/audit-export`

## Deterministic validation flow
1. submit same role inputs to same context id
2. compile twice with same profile/schema/RP
3. confirm identical execution id, pack hash, scoring rows
