# DIIaC-v1.1.0-Production-Ready-Baseline

Runnable deterministic governance runtime with profile-driven compile, cryptographic verification surfaces, and audit operations.

## Run
```bash
cp .env.example .env
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
STRICT_DETERMINISTIC_MODE=true python app.py
```

## Primary APIs
- Role ingestion: `POST /api/human-input/role`
- Profile listing: `GET /api/business-profiles`
- Governed compile: `POST /api/governed-compile`, `POST /govern/decision`
- Trace + scoring: `GET /executions/<id>/trace-map`, `GET /executions/<id>/scoring`
- Merkle: `GET /executions/<id>/merkle`, `GET /executions/<id>/merkle/proof/<artefact_name>`
- Verification: `GET /verify/execution/<id>`, `POST /verify/pack`, `POST /verify/merkle-proof`, `POST /verify/replay`, `GET /verify/public-keys`
- Export: `GET /decision-pack/<id>/export`, signed metadata: `GET /decision-pack/<id>/export-signed`
- Impact + trust + admin: `POST /api/impact/policy`, `GET /trust/status`, `/admin/health`, `/admin/logs`, `/admin/audit-export`, `/admin/metrics`, `/admin/db/status`
- Governance review: `GET /executions/<id>/diff/<other_id>`

## Security/ops environment knobs
- `ENFORCE_ADMIN_AUTH=true`
- `ADMIN_API_KEY=<secret>` and/or JWT Bearer auth (`JWT_SECRET`, `JWT_ISSUER`, `JWT_AUDIENCE`)
- `MAX_REQUEST_BYTES=<bytes>` for request size limiting

## Supporting Specs
- `DIIAC_CAPABILITIES_MATRIX.md`
- `DIIAC_CRYPTOGRAPHIC_SPEC.md`
- `GOVERNANCE_EXTENSIONS_V1_SPEC.md`

## Test
```bash
pytest -q
```

## Production Readiness Validation
```bash
./scripts/production-readiness-check.sh
```

## Docker Compose topology
- `governance-runtime` (Flask/Python) serves governance APIs on internal port `8000`.
- `backend` (Node bridge) serves UI/API gateway on `3001` and proxies to `governance-runtime`.
- `frontend` (Vite/React) serves UI on `5173`.

## Continuation / no-drift handoff
- `CONTINUATION_PROMPT_AND_STATUS_PROTOCOL.md`
- `HANDOFF.md`

Use these two files to start any new chat with full context continuity, explicit no-drift guardrails, and mandatory repo status reporting.
