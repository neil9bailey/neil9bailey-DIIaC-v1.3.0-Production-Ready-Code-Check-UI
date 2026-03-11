# DIIaC v1.2.0 — Production-Ready Governance Runtime

Deterministic governance runtime with profile-driven compile, cryptographic verification surfaces, and audit operations.

## Quick Start

### Local (Python)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
$env:STRICT_DETERMINISTIC_MODE = "true"
python app.py
```

### Docker Compose (full stack)

```powershell
docker compose up --build
```

Services (default host ports):

| Service | URL | Port Override |
|---------|-----|---------------|
| Frontend | `http://localhost:5174` | `FRONTEND_HOST_PORT` |
| Backend UI Bridge | `http://localhost:3101` | `BRIDGE_HOST_PORT` |
| Governance Runtime API | `http://localhost:8100` | `RUNTIME_HOST_PORT` |

The compose stack defaults to development-safe local settings (`APP_ENV=development`, `ADMIN_AUTH_ENABLED=false`).

### LLM Key Configuration

```powershell
Copy-Item .env.example .env
# Edit .env and set OPENAI_API_KEY
docker compose up --build
```

- `LLM_INGESTION_ENABLED=true` — enable LLM synthesis
- `LLM_STUB_ENABLED=true` — deterministic fallback when no API key is available

## Primary APIs

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/human-input/role` | POST | Role ingestion |
| `/api/business-profiles` | GET | Profile listing |
| `/api/llm-governed-compile` | POST | LLM + deterministic governed compile |
| `/api/governed-compile` | POST | Deterministic governed compile |
| `/executions/<id>/trace-map` | GET | Trace map |
| `/executions/<id>/scoring` | GET | Vendor scoring |
| `/executions/<id>/merkle` | GET | Merkle tree |
| `/verify/execution/<id>` | GET | Verification |
| `/verify/pack` | POST | Pack verification |
| `/verify/replay` | POST | Replay verification |
| `/decision-pack/<id>/export-signed` | GET | Signed decision pack export |
| `/trust/status` | GET | Trust ledger status |
| `/admin/health` | GET | Admin health (token required) |
| `/admin/metrics` | GET | Operational metrics (token required) |
| `/admin/audit-export` | POST | Audit export (token required) |
| `/api/intercept/request` | POST | Copilot governance intercept |
| `/api/intercept/response` | POST | Copilot response audit |
| `/api/intercept/approval` | POST | Human approval gate |

## Production Workflow

1. Capture intent and role evidence in the **Decision Evidence Workspace** UI panel.
2. Submit role input via `POST /api/human-input/role`.
3. Run `POST /api/llm-governed-compile` — synthesises LLM output, creates role evidence, then executes deterministic governed compile.
4. Verify via `/verify/execution/<id>`, `/verify/pack`, `/verify/replay`.

## Entra ID Authentication

| Mode | Setting | Use |
|------|---------|-----|
| Production | `AUTH_MODE=entra_jwt_rs256` | RS256 JWT via Entra OIDC/JWKS |
| Integration test | `AUTH_MODE=entra_jwt_hs256` | HS256 JWT with shared secret |
| Development | `AUTH_MODE=` (unset) | `x-role` header (local only) |

See [Entra ID Setup Guide](docs/security/ENTRA_ID_SETUP_GUIDE.md) and [Entra Production Checklist](docs/security/COPILOT_ENTRA_PRODUCTION_CHECKLIST.md).

## Admin Authentication

- Admin routes (`/admin/*`) require `Authorization: Bearer <ADMIN_API_TOKEN>` when `APP_ENV` is not `development`.
- `ADMIN_AUTH_ENABLED=false` disables enforcement (not recommended for production).

## Compose Troubleshooting

- Project name pinned to `diiac_v121_codex` to isolate this repo from other local DIIaC stacks.
- Override host ports: `$env:BRIDGE_HOST_PORT = "3102"; docker compose up -d`
- If frontend port changes outside compose defaults, set `ALLOWED_ORIGINS` in `.env` (comma-separated) for bridge CORS.
- Bridge operational dashboard state now persists on `diiac-bridge-state` volume (`BRIDGE_STATE_PATH`).
- Clear stale resources: `docker compose down --remove-orphans`
- BuildKit snapshot error: run `.\scripts_recover_docker_buildkit.ps1`

## Tests

```powershell
pytest -q
python scripts_e2e_runtime_smoke.py
python scripts_production_readiness_check.py
```

## Release Lock

```powershell
python -m py_compile app.py
node --check backend-ui-bridge/server.js
pytest -q
Set-Location Frontend; npm run build; Set-Location ..
python scripts_e2e_runtime_smoke.py
python scripts_production_readiness_check.py
git tag -a v1.2.0 -m "DIIaC v1.2.0 release lock"
```

## Documentation

All documentation is organised under [`docs/`](docs/README.md):

| Folder | Contents |
|--------|----------|
| [`docs/deployment/`](docs/deployment/) | Deployment guides, runbooks, validation procedures |
| [`docs/architecture/`](docs/architecture/) | Architecture blueprints, specs, capability matrices |
| [`docs/security/`](docs/security/) | Security policy, Entra ID guides, auth checklists |
| [`docs/operations/`](docs/operations/) | Admin console guide, UI workflow guide |
| [`docs/release/`](docs/release/) | Changelog, release notes, roadmap |
| [`docs/archive/`](docs/archive/) | Historical reports and snapshots (review for deletion) |

See the full [Documentation Index](docs/README.md) for a complete file listing.
