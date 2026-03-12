# Clean Build And Test Validation Guide (v1.3.0-ui)

Use this checklist before release or deployment.

## 1. Clean Python Compile

```powershell
python -m py_compile app.py
```

## 2. Bridge Syntax Check

```powershell
node --check backend-ui-bridge/server.js
```

## 3. Automated Tests

```powershell
pytest -q
python scripts_e2e_runtime_smoke.py
python scripts_production_readiness_check.py
```

## 4. Frontend Build

```powershell
Set-Location Frontend
npm ci
npm run build
Set-Location ..
```

## 5. Optional Container Build Checks

```powershell
docker build -f Dockerfile.runtime -t diiac/runtime:test .
docker build -f backend-ui-bridge/Dockerfile -t diiac/bridge:test backend-ui-bridge
docker build -f Frontend/Dockerfile -t diiac/frontend:test Frontend
```

## 6. Exit Criteria

- All commands pass.
- No critical test failures.
- No unresolved security regressions.
- Release docs updated to current version baseline.
