# DIIaC v1.2.0 — Documentation Index

## Deployment

Guides for standing up and validating DIIaC in any environment.

| # | Document | Description |
|---|----------|-------------|
| D-1 | [Getting Started](deployment/GETTING_STARTED.md) | First-run setup for local development |
| D-2 | [Vendorlogic Deployment Guide](deployment/VENDORLOGIC_DEPLOYMENT_GUIDE.md) | Full production deployment (Azure VM / AKS / ACI) |
| D-3 | [Vendorlogic Local Staging Guide](deployment/VENDORLOGIC_LOCAL_STAGING_GUIDE.md) | Local staging environment setup |
| D-4 | [Deployment Validation Runbook](deployment/DEPLOYMENT_VALIDATION_RUNBOOK.md) | Post-deployment validation checklist |
| D-5 | [Clean Build & Test Validation](deployment/DIIAC_CLEAN_BUILD_TEST_VALIDATION_GUIDE.md) | Clean-build test procedures |
| D-6 | [Offline Verifier Runbook](deployment/OFFLINE_VERIFIER_RUNBOOK.md) | Air-gapped signature verification |
| D-7 | [Customer Fork Model](deployment/CUSTOMER_FORK_MODEL.md) | Multi-customer fork/deploy model |

## Architecture

Technical blueprints, specifications, and capability documentation.

| # | Document | Description |
|---|----------|-------------|
| A-1 | [Architecture Blueprint v1.2.0](architecture/ARCHITECTURE_BLUEPRINT_v1.2.0.md) | Core architecture blueprint |
| A-2 | [Current Architecture Blueprint](architecture/DIIAC_CURRENT_ARCHITECTURE_BLUEPRINT.md) | Living architecture reference |
| A-3 | [Architecture & Capabilities Picture](architecture/DIIAC_ARCHITECTURE_AND_CAPABILITIES_PICTURE.md) | High-level architecture diagram |
| A-4 | [Capabilities Matrix](architecture/DIIAC_CAPABILITIES_MATRIX.md) | Feature capability matrix |
| A-5 | [Cryptographic Spec](architecture/DIIAC_CRYPTOGRAPHIC_SPEC.md) | Ed25519 signing, Merkle trees, hash chains |
| A-6 | [Visual Workflow Diagram](architecture/DIIAC_VISUAL_WORKFLOW_DIAGRAM.md) | End-to-end workflow visualisation |
| A-7 | [Governance Extensions Spec](architecture/GOVERNANCE_EXTENSIONS_V1_SPEC.md) | v1 extension point specification |
| A-8 | [v1.2.0 Comprehensive Briefing](architecture/DIIAC_V1_2_0_COMPREHENSIVE_BRIEFING.md) | Full product/architecture briefing |
| A-9 | [v1.2.0 Feature Documentation](architecture/DIIaC_v1.2.0_Feature_Documentation.md) | Detailed feature documentation |
| A-10 | [Governance Layer Blueprint v1.2.1](architecture/DIIAC_GOVERNANCE_LAYER_BLUEPRINT_v1.2.1.md) | Deterministic governance layer model with policy packs and evidence gates |

## Security

Authentication, authorisation, and security policies.

| # | Document | Description |
|---|----------|-------------|
| S-1 | [Security Policy](security/SECURITY.md) | Vulnerability reporting and security policy |
| S-2 | [Entra ID Setup Guide](security/ENTRA_ID_SETUP_GUIDE.md) | Microsoft Entra ID configuration |
| S-3 | [Entra Production Checklist](security/COPILOT_ENTRA_PRODUCTION_CHECKLIST.md) | 84-point Entra ID production checklist |
| S-4 | [Local Auth Testing](security/LOCAL_AUTH_TESTING.md) | HS256 local authentication testing |

## Operations

Day-to-day operational guides for administrators and users.

| # | Document | Description |
|---|----------|-------------|
| O-1 | [Admin Console User Guide](operations/ADMIN_CONSOLE_USER_GUIDE.md) | Admin dashboard and metrics |
| O-2 | [UI Workflow Guide](operations/DIIAC_UI_WORKFLOW_GUIDE.md) | Frontend workflow walkthrough |

## Release

Version history, release notes, and roadmap.

| # | Document | Description |
|---|----------|-------------|
| R-1 | [Changelog](release/CHANGELOG.md) | Version changelog |
| R-2 | [v1.2.0 Release Notes](release/RELEASE_NOTES_V1_2_0.md) | v1.2.0 release notes |
| R-3 | [v1.2.0 Release Lock](release/RELEASE_LOCK_V1_2_0.md) | Release lock checklist and criteria |
| R-4 | [v1.3.0 Product Roadmap](release/PRODUCT_ROADMAP_V1_3_0.md) | Future roadmap |
| R-5 | [Baseline Status & Enhancements](release/BASELINE_STATUS_AND_FUTURE_ENHANCEMENTS.md) | Shipped vs. planned feature tracker |

## Archive

Historical reports and point-in-time snapshots. These are retained for reference but are not required for ongoing operations. **Review for deletion.**

| # | Document | Description |
|---|----------|-------------|
| X-1 | [Architecture Alignment Report](archive/DIIAC_ARCHITECTURE_ALIGNMENT_REPORT.md) | One-time code-vs-architecture audit |
| X-2 | [Production Readiness Report](archive/DIIAC_PRODUCTION_READINESS_REPORT.md) | Point-in-time readiness verdict |
| X-3 | [E2E Assurance Report](archive/DIIAC_REAL_WORLD_E2E_ASSURANCE_REPORT.md) | One-time UK Rail E2E test run |
| X-4 | [Debug & Test Report](archive/DIIAC_V1_2_0_DEBUG_AND_TEST_REPORT.md) | Dated debug session issue register |
| X-5 | [Production Certification Report](archive/DIIAC_V1_2_0_PRODUCTION_CERTIFICATION_AND_AUDIT_REPORT.md) | One-time certification snapshot |
| X-6 | [Vendorlogic Staging Test Report](archive/VENDORLOGIC_DOCKER_STAGING_TEST_REPORT.md) | Staging validation test results |
| X-7 | [Handoff Notes](archive/HANDOFF.md) | Session handoff context |
