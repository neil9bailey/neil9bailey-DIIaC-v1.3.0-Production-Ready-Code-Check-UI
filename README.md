# DIIaC v1.3.0-ui

DIIaC is a deterministic governance platform with a React UI, a Node.js bridge, and a Python runtime.  
This repository contains the Vendorlogic UI-focused build aligned to the Azure production deployment completed on 2026-03-11.

## Current Production Baseline

- Topology: dedicated Azure Container Apps environment for UI stack isolation.
- External UI URL: `https://diiacui.vendorlogic.io`
- Auth: Microsoft Entra ID (`AUTH_MODE=entra_jwt_rs256` in bridge/runtime path).
- Secrets: Azure Key Vault only (`kv-diiac-vendorlogic`), referenced from managed identity.
- LLM mode: `copilot_only` via GitHub Models token from Key Vault.

Dedicated IaC and scripts:

- `infra/aca-dedicated-ui/main.sub.bicep`
- `infra/aca-dedicated-ui/main.rg.bicep`
- `infra/aca-dedicated-ui/vendorlogic-prod.sub.bicepparam`
- `scripts/deploy-azure-dedicated-ui.sh`
- `scripts/build-push-dedicated-ui-images.sh`

Legacy ACI IaC remains in `infra/main.bicep` for compatibility/reference, but the authoritative production pattern for this build is the dedicated ACA path above.

## Local Development

### Python + Node local

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python app.py
```

### Full local stack (Docker Compose)

```powershell
docker compose up --build
```

Default local ports:

- Frontend: `http://localhost:5174`
- Bridge API: `http://localhost:3101`
- Runtime API: `http://localhost:8100`

## Quality Gates

```powershell
python -m py_compile app.py
node --check backend-ui-bridge/server.js
pytest -q
Set-Location Frontend; npm run build; Set-Location ..
python scripts_e2e_runtime_smoke.py
python scripts_production_readiness_check.py
```

## Documentation

Use [`docs/README.md`](docs/README.md) as the documentation index.  
Release evidence and deployment checkpoints are under `docs/release/evidence/`.
Primary low-level architecture reference: `docs/architecture/DIIAC_CURRENT_ARCHITECTURE_BLUEPRINT.md`.

## Security Notes

- Never store secret values in the repository.
- Keep Entra IDs, group object IDs, and app IDs in config as non-secret identifiers only.
- Keep production signing keys and API tokens in Key Vault.
