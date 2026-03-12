# CP2 - Dedicated UI Topology and No-Touch Guardrails

Date: 2026-03-11
Scope: Vendorlogic production UI migration to a dedicated Azure environment with zero overlap on headless runtime services.

## Requirement Lock
- Dedicated environment for this UI version.
- No overlap with currently running headless production resources.
- Shared components allowed: Entra ID + existing Key Vault (`kv-diiac-vendorlogic`) only.
- External access required at `diiacui.vendorlogic.io`.

## Frozen Dedicated Topology
- Tenant: `1384b1c5-2bae-45a1-a4b4-e94e3315eb41`
- Subscription: `3ed9fa77-6bf2-4ffc-bd67-f5a442d3e5e7`
- Region: `uksouth`
- New dedicated resource group: `RG_UI_VENDORLOGIC_PROD_V130`
- New dedicated Azure Container Apps environment: `acae-vendorlogic-ui-prod-v130`
- New dedicated resources:
  - ACR: `acrdiiacv130vlui`
  - User-assigned MI: `id-vendorlogic-ui-prod-v130`
  - Log Analytics: `law-vendorlogic-ui-prod-v130`
  - Runtime app: `rt-vendorlogic-ui-prod-v130` (internal ingress)
  - Bridge app: `br-vendorlogic-ui-prod-v130` (external ingress)
  - Frontend app: `ui-vendorlogic-ui-prod-v130` (external ingress + custom domain)

## Shared Components (Allowed)
- Entra tenant/app IDs/groups and RBAC claims mapping.
- Existing Key Vault: `kv-diiac-vendorlogic` in `RG_ROOT`.
- Secrets are consumed via Key Vault secret references only; no secret values in repo.

## Authoritative Admin Group
- Admin group ID to use: `81786818-de16-4115-b061-92fce74b00bd`.
- Rationale: this ID is already wired into the currently active production UI + bridge role mapping.

## Explicit No-Touch Guardrails
- Do not modify/delete/update resources in `RG_ROOT`:
  - `rt-vendorlogic-prod-v130`
  - `br-vendorlogic-prod-v130`
  - `ui-vendorlogic-prod-v130`
  - `acae-vendorlogic-prod-v130`
  - `acrdiiacv130vl`
  - `id-vendorlogic-prod-v130`
  - `law-vendorlogic-prod-v130`
- Allowed shared-resource action only:
  - Additive Key Vault RBAC assignment on `kv-diiac-vendorlogic` for the new dedicated managed identity.

## DNS Prerequisites (IONOS)
- TXT record:
  - Host: `asuid.diiacui`
  - Value: `B01B517DF534900404CD467B96A1A1B57E73B6E8EEDF856F26751B5C518EA101`
- CNAME record:
  - Host: `diiacui`
  - Target: dedicated UI app FQDN generated at deployment time.
  - Expected format after app creation: `ui-vendorlogic-ui-prod-v130.<aca-env-default-domain>`

## Gated Next Steps
- CP3: Implement dedicated deployment assets only (no apply).
- CP4: Run what-if/safety checks and present predicted diff.
- CP5: Apply dedicated deployment only after explicit approval.
- CP6: Domain binding + smoke/functional + non-regression checks.
- CP7: Final evidence pack + rollback instructions.