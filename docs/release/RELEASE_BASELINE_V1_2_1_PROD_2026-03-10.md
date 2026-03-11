# DIIaC v1.2.1 Production Baseline Release Record (2026-03-10)

Repository: `F:\code\diiac\diiac_v1.2.1_codex`
Branch: `main`

## Release Gates (Hard Pass/Fail)

All gate logs are stored under:
- `docs/release/evidence/2026-03-10-prod-baseline/`

Executed commands:
1. `python -m pytest` -> PASS (`22 passed`)
2. `npm --prefix Frontend run build` -> PASS
3. `$env:DIIAC_STATE_DB=':memory:'; python scripts_e2e_runtime_smoke.py` -> PASS
4. `$env:DIIAC_STATE_DB=':memory:'; python scripts_production_readiness_check.py` -> PASS

## Final CFO Compile Validation

Source file:
- `docs/release/evidence/2026-03-10-prod-baseline/cfo_compile_validation.json`

Result summary:
- `execution_id`: `e118509c-3ae1-5989-b6da-7fc208eaaa76`
- `decision_status`: `recommended`
- `selected_vendor`: `Palo Alto Networks`
- `llm_freshness`: `CURRENT`
- `quality_gate_failures`: none
- `control_failure_reasons`: none
- `signed_export_sigmeta.signing_key_id`: `diiac-vendorlogic-prod`
- `verify_pack.overall_valid`: `true`
- Decision-pack artifact:
  - `docs/release/evidence/2026-03-10-prod-baseline/decision-pack_e118509c-3ae1-5989-b6da-7fc208eaaa76.zip`

## Release Artifacts

Generated locally in `dist-release/`:
- `diiac-v1.2.1-customer-release.zip`
- `diiac-v1.2.1-evidence-pack.zip`
- `SHA256SUMS.txt`
- `release_artifacts_manifest.json`

SHA256:
- `4e7c6d6ee6ccc1df7d564a09331e119ee2f2a7e9d52280fdd811522223f464ee  diiac-v1.2.1-customer-release.zip`
- `adf3c5706312c208bc9f3f5b567f8e4998b52a659ff3524eba2b1d871a552561  diiac-v1.2.1-evidence-pack.zip`

## Packaging Scope

Customer release package includes source, contracts, compose files, docs, runbooks, scripts, deploy and monitoring assets.
Excluded from package: `.git`, `.secrets`, runtime state/artifacts/exports, local caches, and non-example `.env*` files.
