# Baseline Drift Assessment

## Compared repositories
- **Current repo**: `/workspace/DIIaC-v1.1.0-Production-Ready-Baseline`
- **Reference baseline**: `https://github.com/neil9bailey/DIIaC-v1.1.0-Governance-Engine-Production-Ready-Core`
- **Reference baseline commit**: `152dd89`

## Executive summary
This repository has **substantially drifted** from the referenced baseline and appears to be a **different implementation line** rather than an incremental continuation.

Key drift signals:
- Runtime stack changed from **Node/Express + Vite React** baseline to **Python Flask + minimal Node stub** in this repo.
- Repository footprint collapsed from a large baseline (including `.github`, `openapi.json`, Docker composition, and richer frontend/backend bridge assets) into a compact governance runtime and documentation set.
- Shared path overlap is extremely low (3 shared file paths after excluding common virtualenv/cache folders).

## Quantitative drift
- Current files (excluding `.git`, venv/cache folders): **118**
- Baseline files (excluding `.git`, venv/cache folders): **3692**
- Shared relative file paths: **3**
- Files only in current repo: **115**
- Files only in baseline repo: **3689**

## Structural drift
### Present in baseline but missing in current
- `.github/` workflows (determinism/golden prompts/library validation)
- `openapi.json`
- `docker-compose.yml`
- `anchor-store/`
- Full frontend scaffold and source tree
- Full backend UI bridge service implementation

### Present in current but not baseline
- Governance/docs package:
  - `DIIAC_CAPABILITIES_MATRIX.md`
  - `DIIAC_CRYPTOGRAPHIC_SPEC.md`
  - `GOVERNANCE_EXTENSIONS_V1_SPEC.md`
  - `DIIAC_ARCHITECTURE_ALIGNMENT_REPORT.md`
  - `ADMIN_CONSOLE_USER_GUIDE.md`
  - `HANDOFF.md`
- Flask runtime implementation in `app.py`
- Deterministic governance contracts and test suite in `contracts/` and `tests/`

## Code-level drift highlights
### Frontend package simplification
`Frontend/package.json` changed from full Vite/TypeScript/React tooling and dependencies to a minimal placeholder package with echo-based `lint`/`build` scripts.

### Backend bridge rewrite
`backend-ui-bridge/server.js` changed from a feature-rich Express service (authz, governed execution routes, policy impact route, decision pack export route, OpenAI integration) to an 11-line Node HTTP health stub.

### API surface migration
- Baseline backend bridge exposed a small Express route set (e.g., `/trust`, `/api/human-input`, `/api/impact/policy`, `/govern/decision`, `/decision-pack/:execution_id/export`).
- Current runtime exposes a broader Flask governance API set (compile, verification, Merkle proofs, audit exports, trust/status, and aliases) via `app.py`.

## Interpretation
The current repository is not merely “drifted” in small ways; it is likely a **re-baselined or replatformed implementation** with new governance artifacts and tests, while losing much of the original baseline’s frontend/backend bridge and repository scaffolding.

## Reconciliation options
1. **Restore-and-merge strategy**: recover missing baseline components (`.github`, `openapi.json`, `docker-compose.yml`, frontend source, bridge service), then integrate the current Flask governance runtime deliberately.
2. **Declare hard fork strategy**: treat current repo as the new authoritative baseline, then back-port only the baseline components still required (CI workflows, API spec, deployment assets).
3. **Hybrid strategy**: keep current Flask governance engine while reviving baseline operational assets (OpenAPI, CI, deployment), with an explicit architecture decision record.

## Commands used
- `git clone --depth 1 https://github.com/neil9bailey/DIIaC-v1.1.0-Governance-Engine-Production-Ready-Core /workspace/baseline_ref`
- `python` scripts for top-level/file-count comparison
- `diff -u` on overlapping files
- `rg -n "app\.(get|post|put|delete)\(" /workspace/baseline_ref/backend-ui-bridge/server.js`
- `rg -n "@app\.(get|post|put|delete)\(" app.py`
