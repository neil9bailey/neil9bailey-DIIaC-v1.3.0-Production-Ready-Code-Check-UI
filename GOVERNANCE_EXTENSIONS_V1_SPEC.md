# DIIaC Governance Extensions v1 Spec

Implemented scope in this baseline:
1. Merkle root binding + proof APIs
2. Signed pack exports + key registry
3. Public verification endpoints
4. Admin health/logs/audit export APIs

Key APIs:
- `GET /executions/<execution_id>/merkle`
- `GET /executions/<execution_id>/merkle/proof/<artefact_name>`
- `GET /decision-pack/<execution_id>/export-signed`
- `GET /verify/public-keys`
- `POST /verify/pack`
- `POST /verify/merkle-proof`
- `POST /verify/replay`
- `GET /verify/execution/<execution_id>`
- `GET /admin/health`
- `GET /admin/logs`
- `GET /admin/executions/<execution_id>/logs`
- `POST /admin/audit-export`
