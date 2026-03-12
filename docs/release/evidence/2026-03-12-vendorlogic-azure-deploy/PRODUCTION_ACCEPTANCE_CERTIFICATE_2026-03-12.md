# DIIaC v1.3.0-ui Production Acceptance Certificate

## Certificate Metadata
- Date (UTC): 2026-03-12
- Environment: Vendorlogic Azure Production (Dedicated UI Environment)
- Tenant ID: 1384b1c5-2bae-45a1-a4b4-e94e3315eb41
- Subscription ID: 3ed9fa77-6bf2-4ffc-bd67-f5a442d3e5e7
- Resource Group: RG_UI_VENDORLOGIC_PROD_V130
- Public UI Domain: https://diiacui.vendorlogic.io

## Deployment Scope
This certificate confirms successful deployment and operational validation of DIIaC UI v1.3.0 in a dedicated Azure production environment, with Entra ID and shared Key Vault integration, and with no overlap requirement for headless runtime services.

## Deployment Result
- Infra deployment: diiac-ui-vendorlogic-infra-20260312-112304 (Succeeded)
- Apps deployment: diiac-ui-vendorlogic-apps-20260312-112530 (Succeeded)
- Key Vault preflight: Passed

## DNS Validation Values (IONOS)
- CNAME host: diiacui
- CNAME target: ui-vendorlogic-ui-prod-v130.blackpond-85ed120f.uksouth.azurecontainerapps.io
- TXT host: asuid.diiacui
- TXT value: B01B517DF534900404CD467B96A1A1B57E73B6E8EEDF856F26751B5C518EA101

## Authentication and Security Validation
- Bridge auth mode: entra_jwt_rs256
- Entra API token version: 2 (verified in app registration state)
- Authenticated API role resolution: admin (from Entra token)
- Key Vault secrets used in runtime/bridge: confirmed (no secret values stored in repository)

## Functional Governance Smoke (Production)
- Smoke timestamp (UTC): 2026-03-12T11:37:57.6558823Z
- Execution ID: bb4d6134-32db-574e-aa5d-aa8c4f09e05e
- Verify execution status: VERIFIABLE
- Pack verification: overall_valid=true
- Signed export algorithm: Ed25519
- Signing key id: diiac-vendorlogic-prod
- Audit export ID: audit-2ccd2e8bfb26
- ZIP SHA256: 939778A00DB4DACBE2AB11859E188F85BD8A597756A7F6B9D1F9492779F09F62

## Acceptance Criteria Checklist
- [x] Dedicated Azure UI environment deployed and operational
- [x] External access enabled on diiacui.vendorlogic.io
- [x] Entra ID authentication enforced (legacy auth not active)
- [x] Key Vault-only secret handling maintained
- [x] Safe deployment path followed (validate and what-if before apply)
- [x] Governance runtime functional end-to-end in production
- [x] Signed decision-pack export and verification successful
- [x] Audit export generation successful

## Authoritative Evidence References
- Account context: cp0_account_context.json
- Validate/What-if: cp2_validate_*.json, cp2_whatif_*.json
- Apply outputs: cp3_apply_*.json, cp3_outputs_*.json
- DNS evidence: cp4_dns_records_diiac-ui-vendorlogic-apps-20260312-112530.txt
- Smoke bundle: cp5-smoke-20260312-113751/
  - 00_entra_api_app_state.json
  - 03_bridge_public_checks.json
  - 04_auth_me.json
  - 05_governance_flow.json
  - 06_smoke_summary.json
  - 07_smoke_report.md
  - decision-pack_bb4d6134-32db-574e-aa5d-aa8c4f09e05e.zip

## Final Statement
DIIaC v1.3.0-ui is accepted as production-operational in Azure for Vendorlogic based on successful gated deployment, security/authentication validation, and end-to-end governance smoke execution evidenced in this release bundle.

---
Prepared by: Codex deployment agent
