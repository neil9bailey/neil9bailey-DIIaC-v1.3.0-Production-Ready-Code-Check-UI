# Deployment Validation Runbook

## Purpose
Operational checklist for staging/production promotion validation of the DIIaC baseline.

## Preconditions
- `APP_ENV=production`
- `ADMIN_AUTH_ENABLED=true`
- `ADMIN_API_TOKEN` configured
- `STRICT_DETERMINISTIC_MODE=true`

## Validation sequence
1. Unit and integration checks
   - `pytest -q`
2. Runtime API smoke checks
   - `python scripts_e2e_runtime_smoke.py`
3. Production-mode security/readiness checks
   - `python scripts_production_readiness_check.py`

## Acceptance criteria
- All commands above return success.
- Admin endpoints deny without token and allow with token.
- Governed compile returns verifiable execution status.
- Signed export and audit export flows succeed in production-mode checks.
- Metrics endpoint returns threshold recommendations payload.

## Rollback guidance
- If any step fails, rollback to previous known-good commit and rerun full validation sequence before re-promoting.


## Docker BuildKit snapshot corruption recovery
If `docker compose up --build` fails with an error similar to:
- `failed to prepare extraction snapshot ... parent snapshot ... does not exist`

Run:
- macOS/Linux:
```bash
./scripts_recover_docker_buildkit.sh
```
- Windows PowerShell:
```powershell
.\scripts_recover_docker_buildkit.ps1
```

What this does:
1. Stops compose services and removes orphans.
2. Prunes BuildKit cache and stale Docker resources.
3. Rebuilds `backend-ui-bridge` without cache.
4. Rebuilds and starts the full stack.
