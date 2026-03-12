# Vendorlogic Local Staging Guide (v1.3.0-ui)

This guide provides a production-like local staging environment for smoke checks before Azure apply.

## Goals

- Validate UI, bridge, and runtime integration.
- Validate Entra-related wiring where needed.
- Validate deterministic governance outputs and signatures.

## 1. Build Validation

```powershell
python -m py_compile app.py
node --check backend-ui-bridge/server.js
Set-Location Frontend; npm run build; Set-Location ..
```

## 2. Start Local Staging Stack

```powershell
docker compose up --build
```

## 3. Optional Staging Auth Settings

Set `.env` values when testing Entra behavior:

- `AUTH_MODE=entra_jwt_hs256` for controlled integration tests
- `ENTRA_*` claims/audience/issuer settings
- `VITE_ENTRA_*` frontend settings

For day-to-day staging, legacy header mode can remain enabled.

## 4. Run Smoke Matrix

- Open UI at `http://localhost:5174`
- Confirm bridge health and auth status
- Execute a governance flow and verify artifact generation
- Export a decision pack and verify cryptographic metadata

## 5. Exit And Cleanup

```powershell
docker compose down --remove-orphans
```

If needed, clear local volumes for a clean rerun.
