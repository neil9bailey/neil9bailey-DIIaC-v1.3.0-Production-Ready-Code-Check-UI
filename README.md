# DIIaC-v1.1.0-Production-Ready-Baseline

Runnable deterministic governance runtime with profile-driven compile, cryptographic verification surfaces, and audit operations.

## Run
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
STRICT_DETERMINISTIC_MODE=true python app.py
```

## Primary APIs
- Role ingestion: `POST /api/human-input/role`
- Profile listing: `GET /api/business-profiles`
- Governed compile: `POST /api/governed-compile`
- Trace + scoring: `GET /executions/<id>/trace-map`, `GET /executions/<id>/scoring`
- Merkle: `GET /executions/<id>/merkle`, `GET /executions/<id>/merkle/proof/<artefact_name>`
- Verification: `GET /verify/execution/<id>`, `POST /verify/pack`, `POST /verify/merkle-proof`, `GET /verify/public-keys`
- Signed export: `GET /decision-pack/<id>/export-signed`
- Trust + admin: `GET /trust/status`, `/admin/health`, `/admin/logs`, `/admin/audit-export`

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
