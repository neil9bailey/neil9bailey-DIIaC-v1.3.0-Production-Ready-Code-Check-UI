# DIIaC-v1.2.0-Production-Ready-Release

Runnable deterministic governance runtime with profile-driven compile, cryptographic verification surfaces, and audit operations.

## Run
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
STRICT_DETERMINISTIC_MODE=true python app.py
```

## Docker Compose (full stack)
```bash
docker compose up --build
```

Services (default host ports):
- Frontend: `http://localhost:5173`
- Backend UI bridge: `http://localhost:3001`
- Governance runtime API: `http://localhost:8000`

The compose stack defaults to development-safe local settings (`APP_ENV=development`, `ADMIN_AUTH_ENABLED=false`) for local validation.

### Compose behavior and port-conflict troubleshooting
- Expected resources for this stack are **3 containers** + **4 named volumes**.
- Compose project name is pinned to `diiac_v120` to avoid creating differently-prefixed stacks from different folder names.
- If port `3001` is already in use, override host ports:
  ```bash
  BRIDGE_HOST_PORT=3002 docker compose up -d
  ```
  You can also override frontend/runtime ports with `FRONTEND_HOST_PORT` and `RUNTIME_HOST_PORT`.
- To clear stale resources before restart:
  ```bash
  docker compose down --remove-orphans
  ```
- If Docker Desktop/BuildKit fails with `parent snapshot ... does not exist`, run the recovery script:
  - macOS/Linux:
    ```bash
    ./scripts_recover_docker_buildkit.sh
    ```
  - Windows PowerShell:
    ```powershell
    .\scripts_recover_docker_buildkit.ps1
    ```
  This performs compose down + build cache prune + no-cache rebuild.

### LLM key configuration (Bridge)
- Your local `.env` is **not committed to Git** by design.
- For Docker Compose, copy `.env.example` to `.env` at repo root and set:
  - `OPENAI_API_KEY=<your_key>`
  - `LLM_INGESTION_ENABLED=true`
  - Optional fallback: `LLM_STUB_ENABLED=true` (uses deterministic stub if key is unavailable)
- For non-Docker local bridge runs, copy `backend-ui-bridge/.env.example` to `backend-ui-bridge/.env`.

Example:
```bash
cp .env.example .env
# edit .env and set OPENAI_API_KEY
docker compose up --build
```


## Primary APIs
- Role ingestion: `POST /api/human-input/role`
- Profile listing: `GET /api/business-profiles`
- Production deterministic + LLM compile: `POST /api/llm-governed-compile` (bridge orchestrates LLM synthesis and then deterministic governed compile)
- Governed compile: `POST /api/governed-compile`
- Trace + scoring: `GET /executions/<id>/trace-map`, `GET /executions/<id>/scoring`
- Merkle: `GET /executions/<id>/merkle`, `GET /executions/<id>/merkle/proof/<artefact_name>`
- Verification: `GET /verify/execution/<id>`, `POST /verify/pack`, `POST /verify/merkle-proof`, `POST /verify/replay`, `GET /verify/public-keys`
- Signed export: `GET /decision-pack/<id>/export-signed`
- Trust + admin: `GET /trust/status`, `/admin/health`, `/admin/logs`, `/admin/audit-export`
- Auth: `GET /auth/status`, `GET /auth/callback`
- Copilot intercept: `POST /api/intercept/request`, `POST /api/intercept/response`, `POST /api/intercept/approval`

## Recommended production procedure (always LLM + deterministic)
1. Capture intent and role evidence in the **Decision Evidence Workspace (Production)** UI panel.
2. Submit role input (`POST /api/human-input/role`) with free-form `domain` and `assertions` content.
3. Run `POST /api/llm-governed-compile` to:
   - synthesize LLM output from latest human intent,
   - create/update role evidence,
   - execute deterministic `POST /api/governed-compile` as the final authoritative step.
4. Verify via `/verify/execution/<id>`, `/verify/pack`, `/verify/replay`.

`/govern/decision` remains available for exploratory non-deterministic drafts and demos.

## Entra ID Authentication

The bridge supports Microsoft Entra ID (Azure AD) JWT authentication for production deployments:

- **Production mode:** `AUTH_MODE=entra_jwt_rs256` — validates RS256 JWTs via Entra OIDC/JWKS
- **Integration test mode:** `AUTH_MODE=entra_jwt_hs256` — validates HS256 JWTs with shared secret
- **Legacy mode:** `AUTH_MODE=` (unset) — uses `x-role` header (development only)

See `ENTRA_ID_SETUP_GUIDE.md` for full configuration and `COPILOT_ENTRA_PRODUCTION_CHECKLIST.md` for production validation.

### Copilot Governance Intercept

The `/api/intercept/*` endpoints provide a governance layer for Copilot-style LLM interactions:
- `POST /api/intercept/request` — intercept and record a Copilot request with actor lineage
- `POST /api/intercept/response` — record a Copilot response for audit
- `POST /api/intercept/approval` — human approval gate (approve/reject/escalate)

All events are recorded in the hash-chained trust ledger with full actor identity from Entra JWT claims.

## Supporting Specs
- `DIIAC_CURRENT_ARCHITECTURE_BLUEPRINT.md`
- `BASELINE_STATUS_AND_FUTURE_ENHANCEMENTS.md`
- `DIIAC_CAPABILITIES_MATRIX.md`
- `DIIAC_CRYPTOGRAPHIC_SPEC.md`
- `GOVERNANCE_EXTENSIONS_V1_SPEC.md`
- `OFFLINE_VERIFIER_RUNBOOK.md`
- `DEPLOYMENT_VALIDATION_RUNBOOK.md`
- `DIIAC_UI_WORKFLOW_GUIDE.md`
- `DIIAC_REAL_WORLD_E2E_ASSURANCE_REPORT.md`
- `DIIAC_VISUAL_WORKFLOW_DIAGRAM.md`
- `PRODUCT_ROADMAP_V1_3_0.md`
- `RELEASE_LOCK_V1_2_0.md`
- `ENTRA_ID_SETUP_GUIDE.md`
- `COPILOT_ENTRA_PRODUCTION_CHECKLIST.md`
- `DIIAC_V1_2_0_COMPREHENSIVE_BRIEFING.md`

## v1.2.0 release lock and tagging workflow
Run the explicit release-lock checklist before tagging:

```bash
python3 -m py_compile app.py
node --check backend-ui-bridge/server.js
pytest -q
cd Frontend && npm run build
python3 scripts_e2e_runtime_smoke.py
python3 scripts_production_readiness_check.py
```

Create and validate release tag:

```bash
git tag -a v1.2.0 -m "DIIaC v1.2.0 release lock"
git show v1.2.0 --no-patch
```



## Admin authentication
- Admin routes (`/admin/*`) require `Authorization: Bearer <ADMIN_API_TOKEN>` by default when `APP_ENV` is not `development`/`dev`.
- In development (`APP_ENV=development`), admin auth is bypassed for local operation.
- `ADMIN_AUTH_ENABLED=false` can disable admin auth enforcement (not recommended for production).


## Payload validation bounds
- Write endpoints now enforce schema bounds for critical string/list fields to reduce malformed or oversized writes.
- Guarded endpoints include `/api/human-input/role`, `/api/human-input`, `/api/governed-compile`, `/api/compile`, `/verify/pack`, `/verify/merkle-proof`, `/verify/replay`, and `/admin/audit-export`.

## Runtime readiness
- `GET /health` and `GET /admin/health` now include a `readiness` object with explicit checks for artifact/export/audit storage, contracts, keys, and DB configuration presence.
- Governed compile endpoints (`/api/governed-compile` and `/api/compile`) emit structured dependency failures when runtime dependencies fail:
  - `error=runtime_dependency_failure`
  - `error_code=ARTIFACT_STORAGE_UNAVAILABLE` for storage failures
  - `error_code=RUNTIME_DEPENDENCY_TIMEOUT` for runtime timeouts
  - `error_code=EXPORT_STORAGE_UNAVAILABLE` for signed export storage failures
  - `error_code=AUDIT_STORAGE_UNAVAILABLE` for audit export storage failures
  - `error_code=SIGNATURE_METADATA_UNAVAILABLE` for verify-pack signature metadata read failures


## Operational metrics and logging
- Backend logs include stable `event_id` values to support audit triage and event-based filtering.
- `GET /admin/metrics` includes `alerts` and `threshold_recommendations` for baseline operational monitoring.

## End-to-end smoke
```bash
python scripts_e2e_runtime_smoke.py
python scripts_production_readiness_check.py
```

## Test
```bash
pytest -q
```
