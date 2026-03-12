# DIIaC Documentation Index (v1.3.0-ui)

This index is the source of truth for the current UI build and Azure production model.

## Authoritative Baseline

- Build/version: `v1.3.0-ui`
- Production model: dedicated Azure Container Apps stack for Vendorlogic UI services
- Shared dependencies only: Microsoft Entra ID and Key Vault `kv-diiac-vendorlogic`
- Public UI domain: `diiacui.vendorlogic.io`

## Deployment

- [Getting Started](deployment/GETTING_STARTED.md)
- [Vendorlogic Deployment Guide](deployment/VENDORLOGIC_DEPLOYMENT_GUIDE.md)
- [Vendorlogic Local Staging Guide](deployment/VENDORLOGIC_LOCAL_STAGING_GUIDE.md)
- [Deployment Validation Runbook](deployment/DEPLOYMENT_VALIDATION_RUNBOOK.md)
- [Clean Build & Test Validation](deployment/DIIAC_CLEAN_BUILD_TEST_VALIDATION_GUIDE.md)
- [Offline Verifier Runbook](deployment/OFFLINE_VERIFIER_RUNBOOK.md)
- [Customer Fork Model](deployment/CUSTOMER_FORK_MODEL.md)

## Architecture

- [Current Architecture Blueprint (Low-Level Design)](architecture/DIIAC_CURRENT_ARCHITECTURE_BLUEPRINT.md)
- [Architecture Blueprint](architecture/ARCHITECTURE_BLUEPRINT_v1.2.0.md)
- [Architecture & Capabilities Picture](architecture/DIIAC_ARCHITECTURE_AND_CAPABILITIES_PICTURE.md)
- [Capabilities Matrix](architecture/DIIAC_CAPABILITIES_MATRIX.md)
- [Cryptographic Spec](architecture/DIIAC_CRYPTOGRAPHIC_SPEC.md)
- [Visual Workflow Diagram](architecture/DIIAC_VISUAL_WORKFLOW_DIAGRAM.md)
- [Governance Extensions Spec](architecture/GOVERNANCE_EXTENSIONS_V1_SPEC.md)
- [Governance Layer Blueprint](architecture/DIIAC_GOVERNANCE_LAYER_BLUEPRINT_v1.2.1.md)
- [Feature Documentation](architecture/DIIaC_v1.2.0_Feature_Documentation.md)
- [Comprehensive Briefing](architecture/DIIAC_V1_2_0_COMPREHENSIVE_BRIEFING.md)

## Security

- [Security Policy](security/SECURITY.md)
- [Entra ID Setup Guide](security/ENTRA_ID_SETUP_GUIDE.md)
- [Entra Production Checklist](security/COPILOT_ENTRA_PRODUCTION_CHECKLIST.md)
- [Local Auth Testing](security/LOCAL_AUTH_TESTING.md)

## Operations

- [Admin Console User Guide](operations/ADMIN_CONSOLE_USER_GUIDE.md)
- [UI Report Compilation Guide (Field Map)](operations/DIIAC_UI_WORKFLOW_GUIDE.md)

## Release

- [Changelog](release/CHANGELOG.md)
- [Release Notes](release/RELEASE_NOTES_V1_2_0.md)
- [Release Lock](release/RELEASE_LOCK_V1_2_0.md)
- [Release Baseline](release/RELEASE_BASELINE_V1_2_1_PROD_2026-03-10.md)
- [Production Baseline Validation](release/DIIAC_V1_2_1_PRODUCTION_BASELINE_VALIDATION_2026-03-10.md)
- [Baseline Status & Future Enhancements](release/BASELINE_STATUS_AND_FUTURE_ENHANCEMENTS.md)
- [Product Roadmap](release/PRODUCT_ROADMAP_V1_3_0.md)
- [Customer Value Overview](release/DIIAC_CUSTOMER_VALUE_OVERVIEW_2026-03-10.md)

## Release Reviews

- [Production Readiness Closure Note (2026-03-12)](release/reviews/PRODUCTION_READINESS_CLOSURE_NOTE_2026-03-12.md)
- [ChatGPT Issue Response (Resolved, 2026-03-12)](release/reviews/CHATGPT_ISSUE_RESPONSE_RESOLVED_2026-03-12.md)

## Deployment Evidence And Handoffs

- `docs/release/evidence/` contains immutable checkpoint evidence and quality artifacts.
- `docs/release/handoffs/` contains operator handoff packs and context snapshots.

## Archive

`docs/archive/` is historical reference only.  
Treat archive content as non-authoritative when it conflicts with current `v1.3.0-ui` docs.
