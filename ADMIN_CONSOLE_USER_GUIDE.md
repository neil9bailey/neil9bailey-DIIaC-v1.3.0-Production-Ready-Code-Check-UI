# DIIaC™ v1.1.0 Admin Console User Guide

## Main Actions
- Submit role inputs: `POST /api/human-input/role`
- Run governed compile: `POST /api/governed-compile`
- Verify execution/pack/merkle: `/verify/*`
- Inspect trust status: `GET /trust/status`
- Fetch logs: `GET /admin/logs`, `GET /admin/executions/<id>/logs`
- Generate auditor package: `POST /admin/audit-export`
- Run DB checks/maintenance: `GET /admin/db/status`, `POST /admin/db/maintenance/compact`

## Dashboard views
The admin dashboard is separated into operational views:

1. **Overview**
   - runtime health
   - trust/metrics snapshot
   - container visibility snapshot
   - DB integrity snapshot
2. **Exports**
   - execution verification status
   - audit export generation and retrieval
3. **Logs**
   - backend logs
   - ledger logs
   - execution-scoped logs
4. **DB Maintenance**
   - table counts and integrity checks
   - compact operation

Raw JSON is intentionally optional and hidden behind a toggle for export/troubleshooting use.

## Deterministic validation flow
1. submit same role inputs to same context id
2. compile twice with same profile/schema/RP
3. confirm identical execution id, pack hash, scoring rows

## Stakeholder-ready validation run
1. In admin mode, run compile for target infrastructure requirement.
2. Capture execution ID and generated artifacts.
3. Validate execution via verification endpoints.
4. Export decision pack + audit bundle.
5. Capture metrics/health/log snapshots from dashboard.
6. Produce report sections:
   - context/objective
   - governance controls
   - scoring + recommendation
   - cryptographic verification evidence
   - operational status evidence
   - next actions
