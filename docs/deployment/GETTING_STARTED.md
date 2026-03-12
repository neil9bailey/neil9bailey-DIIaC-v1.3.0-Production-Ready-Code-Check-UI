# Getting Started (v1.3.0-ui)

This guide gets you from clone to a working local stack, then points to the production deployment path used for Vendorlogic.

## 1. Prerequisites

- Python 3.11+
- Node.js 20+
- Docker Desktop (for compose flow)
- Azure CLI (for cloud deployment)

## 2. Local Runtime Only (fast path)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python app.py
```

Runtime health endpoint:

```powershell
curl http://localhost:8000/health
```

## 3. Full Local Stack (UI + Bridge + Runtime)

```powershell
docker compose up --build
```

Default local endpoints:

- UI: `http://localhost:5174`
- Bridge: `http://localhost:3101`
- Runtime: `http://localhost:8100`

## 4. Optional Entra Local Wiring

For local UI auth flows, set `VITE_ENTRA_*` variables and bridge `AUTH_MODE` settings in `.env`.

Use production-style Entra only when validating token behavior.
For normal local dev, legacy header mode can remain enabled.

## 5. Production Deployment Path

For the current Vendorlogic production pattern, use:

- `infra/aca-dedicated-ui/main.sub.bicep`
- `infra/aca-dedicated-ui/main.rg.bicep`
- `infra/aca-dedicated-ui/vendorlogic-prod.sub.bicepparam`
- `scripts/deploy-azure-dedicated-ui.sh`
- `scripts/build-push-dedicated-ui-images.sh`

Start with plan/what-if:

```bash
bash scripts/deploy-azure-dedicated-ui.sh --plan --infra-only
```

Then follow the full deployment guide: `docs/deployment/VENDORLOGIC_DEPLOYMENT_GUIDE.md`.
