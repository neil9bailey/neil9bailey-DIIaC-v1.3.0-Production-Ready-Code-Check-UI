> Handoff snapshot notice: This handoff file captures point-in-time context from 2026-03-11 and may not reflect current repository documentation updates.
# Vendorlogic UI Azure Deployment Thread Handoff (2026-03-11)

## Goal

Start a new thread that deploys the already-built UI version to Azure production in the Vendorlogic tenant, alongside the existing headless deployment, without impacting the running headless services.

## Workspace Confirmed

- Root reviewed: `F:\code\diiac\diiac_v1.3.0_ui`
- Note: this folder currently has no `.git` directory at root, even though `.gitignore` exists.

## What Was Reviewed

Core deployment/auth/Copilot wiring:

1. `infra/main.bicep`
2. `infra/main.bicepparam`
3. `scripts/deploy-azure.sh`
4. `scripts/pull-keyvault-secrets.ps1`
5. `customer-config/vendorlogic/config.env`
6. `backend-ui-bridge/auth/entra.js`
7. `backend-ui-bridge/server.js`
8. `backend-ui-bridge/llm-ingestion/providers/copilot.js`
9. `Frontend/src/auth/authConfig.ts`
10. `Frontend/src/auth/roleMapping.ts`
11. `Frontend/src/api.ts`

## Build Health Snapshot (Local)

Executed in `F:\code\diiac\diiac_v1.3.0_ui`:

1. `python -m py_compile app.py` -> PASS
2. `node --check backend-ui-bridge/server.js` -> PASS
3. `python -m pytest -q` -> PASS (`22 passed`)
4. `npm run build` in `Frontend` -> PASS (chunk-size warning only)

## Azure And Identity Context (From UI Config)

- Tenant: `1384b1c5-2bae-45a1-a4b4-e94e3315eb41`
- UI config RG default: `rg-diiac-prod`
- UI config location: `uksouth`
- Key Vault name: `kv-diiac-vendorlogic`
- API app ID: `b726558d-f1c6-48f7-8a3d-72d5db818d0f`
- UI app ID: `b726558d-f1c6-48f7-8a3d-72d5db818d0f`
- Standard group: `9c7dd0d4-5b44-4811-b167-e52df21092d8`
- Admin group in UI config: `81786818-de16-4115-b061-92fce74b00bd`
- Copilot mode: locked to `copilot_only` with `GITHUB_TOKEN`

## Coexistence Constraint With Headless

The existing headless production baseline in your prior thread is in:

- subscription `3ed9fa77-6bf2-4ffc-bd67-f5a442d3e5e7`
- resource group `RG_ROOT`
- shared tenant `1384b1c5-2bae-45a1-a4b4-e94e3315eb41`

The new UI deployment thread must preserve current headless resources and endpoints.

## Critical Decisions Required In New Thread

1. Deployment target model:
   - keep UI on ACI path (`infra/main.bicep`) or align to ACA pattern used by headless.
2. Resource group strategy:
   - keep `rg-diiac-prod` isolated, or co-locate in `RG_ROOT`.
3. Key Vault strategy:
   - reuse `kv-diiac-vendorlogic` (already used by headless) or create UI-specific vault.
4. Admin group authority:
   - resolve `81786818-de16-4115-b061-92fce74b00bd` vs `4ef7c128-a3f2-4c7d-a51d-c893e5944c88`.
5. Public endpoint strategy for frontend -> bridge traffic in Azure.

## Known Deployment Risks To Address Early

1. `infra/main.bicep` creates a Key Vault named `kv-diiac-vendorlogic`; this can collide if it already exists.
2. `scripts/deploy-azure.sh` warns that ACI secret injection is not fully automated in-place after deploy.
3. `infra/main.bicep` sets frontend `VITE_API_BASE` to the same public FQDN used by frontend hosting; confirm backend routing path before production apply.
4. UI docs are mostly marked v1.2.x while this folder is named v1.3.0 UI; confirm release/version label for customer handoff artifacts.

## Required Inputs For New Thread

1. Final repo path for the UI git worktree (if different from `F:\code\diiac\diiac_v1.3.0_ui`).
2. Final Azure target scope:
   - subscription ID
   - resource group
   - DNS/certificate ownership for UI domain.
3. Authoritative Entra groups for admin/standard/viewer.
4. Decision on whether UI uses existing headless bridge/runtime or its own full stack in Azure.

## Suggested Checkpoint Flow For New Thread

1. CP1: Confirm workspace + Azure context + no-impact guardrails.
2. CP2: Finalize topology and naming (isolation first).
3. CP3: Parameterize IaC with customer-safe values and secret references only.
4. CP4: Run what-if and collision checks.
5. CP5: Apply deployment (gated approval).
6. CP6: Run smoke/RBAC/UI-monitoring validation matrix.
7. CP7: Capture evidence + sign-off pack.

## Fast Start

```powershell
Set-Location F:\code\diiac\diiac_v1.3.0_ui
python -m py_compile app.py
python -m pytest -q
Get-Content -Raw docs\release\handoffs\vendorlogic_ui_azure_context_2026-03-11.json
Get-Content -Raw docs\release\handoffs\NEW_THREAD_START_PROMPT_UI_AZURE_VENDORLOGIC_2026-03-11.md
```


