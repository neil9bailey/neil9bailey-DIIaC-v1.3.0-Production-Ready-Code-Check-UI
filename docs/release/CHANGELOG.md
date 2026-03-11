# Changelog — DIIaC

All notable changes to DIIaC are documented in this file.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).
Versioning follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [1.2.1] - 2026-03-10  *(Staging Baseline Hardening)*

### Changed
- Business profiles narrowed to 5 sector-aligned contracts for staging baseline: `it_enterprise_profile_v1`, `it_service_provider_profile_v1`, `finance_profile_v1`, `healthcare_profile_v1`, `transport_profile_v1`.
- Removed transport sub-sector profile contracts from active set: `national_highways_profile_v1`, `national_rail_profile_v1`, `tfl_profile_v1`.
- UI role selector updated to use `CTO` (replacing `ACTING_CTO`) and extended with `CFO` and `PROCUREMENT`.
- Bridge fallback profile defaults aligned with runtime contract set so proxy fallback behavior matches the active 5-profile baseline.

### Fixed
- Replay verification deterministic hash parity: `/verify/replay` now normalizes role bundles and payload hashing in the same way as governed compile input snapshot generation.
- Admin console regression test expectation for profile count updated from `8` to `5`.
- Deployment validation guide checkpoints updated to reflect the 5-profile baseline.
- LLM freshness gate reliability: bridge now stamps a governance-captured UTC audit timestamp on every LLM compile and runtime freshness evaluation prefers explicit `llm_audit_timestamp` override when provided.
- Operational dashboard intercept panel clarified as optional Copilot intercept telemetry, with zero-event explanation and count+percentage display.
- Final production-baseline release evidence captured (gate logs, CFO validation decision pack, package SHA256 manifests, customer/evidence ZIP artifacts in `dist-release/`).

---

## [1.2.0] — 2026-03-04  *(Production Release)*

### Added

#### Core Governance Engine
- `POST /api/governed-compile` and `POST /api/compile` — Deterministic governed compile with structured `runtime_dependency_failure` taxonomy for artifact storage and timeout failures.
- `POST /api/llm-governed-compile` — Production LLM synthesis + deterministic governed compile orchestration in a single endpoint.
- `POST /verify/replay` — Replay verification endpoint emitting deterministic `replay_certificate.json` for attestation workflows.
- `GET /verify/pack` — Decision pack hash + Merkle root verification.
- `GET /executions/<id>/trace-map` — Evidence trace map linking recommendations to claim IDs.
- `GET /executions/<id>/scoring` — Vendor scoring matrix and down-select recommendation.
- `GET /executions/<id>/merkle` — Merkle tree for a compiled execution.
- `GET /executions/<id>/merkle-proof/<artefact>` — Per-artefact Merkle proof.

#### Authentication & Security
- Admin auth enforcement (`ADMIN_API_TOKEN` bearer token) enabled by default in all non-development environments.
- `ADMIN_AUTH_ENABLED` environment variable for explicit control.
- Payload schema bounds validation across all key write endpoints (role input, compile, verify, human input, audit export).

#### Observability & Operations
- Structured backend logs with stable event IDs (format: `EVT-<SHA256[:8]>`).
- `/admin/metrics` — Alerting guidance with threshold recommendations (`MTR-001`, `MTR-002`).
- `/health` and `/admin/health` — Explicit `storage`, `contracts`, and `database` readiness state.
- Extended runtime dependency taxonomy covering signed export, audit export, and verify-pack metadata read failures.

#### Audit & Cryptography
- Hash-chained trust ledger (`ledger.jsonl`) with append-only semantics.
- Ed25519 signed decision pack exports (`/decision-pack/<id>/export-signed`).
- Audit export bundles (`/admin/audit-export`) with signed ZIP artefacts.
- Public key registry loaded from `contracts/keys/public_keys.json`.

#### Infrastructure & Deployment
- Root `docker-compose.yml` for full-stack local bring-up (runtime + bridge + frontend).
- Multi-stage Dockerfiles with network retry/timeout tuning for apt/npm installs.
- Docker Compose project naming (`diiac_v120`) and host-port override controls.
- `RUNTIME_HOST_PORT`, `BRIDGE_HOST_PORT`, `FRONTEND_HOST_PORT` env vars for port collision avoidance.
- Backend UI bridge compatibility fallbacks for missing runtime DB admin endpoints and decision-pack export aliasing.
- OPENAI key wiring via `.env.example` and compose env passthrough; local bridge `.env` autoload support.

#### Tooling & Scripts
- `scripts_e2e_runtime_smoke.py` — HTTP E2E smoke test covering role input, compile, trust, verify, admin logs, and audit export.
- `scripts_production_readiness_check.py` — Production-mode validation script covering admin auth, compile/verify/export, and admin audit/metrics.
- `scripts_recover_docker_buildkit.sh` / `.ps1` — Docker BuildKit recovery scripts for Linux and Windows.
- `scripts/generate-test-token.mjs` — Test JWT generation for development.
- `scripts/entra-token-test.mjs` — Entra ID token testing script.

#### Business Profiles
- 8 sector-specific governance profiles: finance, healthcare, IT enterprise, IT service provider, national highways, national rail, TfL, transport.

#### Documentation
- `DEPLOYMENT_VALIDATION_RUNBOOK.md` — Staging/production promotion checklist with rollback guidance.
- `OFFLINE_VERIFIER_RUNBOOK.md` — Offline pack and Merkle verification with tamper-check expectations.
- `DIIAC_UI_WORKFLOW_GUIDE.md` — Step-by-step UI population guidance.
- `DIIAC_VISUAL_WORKFLOW_DIAGRAM.md` — Full HITL + LLM + deterministic compile production sequence.
- `DIIAC_REAL_WORLD_E2E_ASSURANCE_REPORT.md` — Full real-world production-path run with artefact hashes.
- `DIIAC_CURRENT_ARCHITECTURE_BLUEPRINT.md` — Architecture blueprint for no-drift continuation.
- `BASELINE_STATUS_AND_FUTURE_ENHANCEMENTS.md` — Enhancement tracker.
- `ADMIN_CONSOLE_USER_GUIDE.md` — Comprehensive admin operations guide.
- `COPILOT_ENTRA_PRODUCTION_CHECKLIST.md` — 84-point production checklist for Entra ID + Copilot integration.
- `ENTRA_ID_SETUP_GUIDE.md` — Entra AD application registration and configuration guide.
- `LOCAL_AUTH_TESTING.md` — Local development authentication testing guide.
- `DIIAC_ARCHITECTURE_ALIGNMENT_REPORT.md`, `DIIAC_CAPABILITIES_MATRIX.md`, `DIIAC_CRYPTOGRAPHIC_SPEC.md`, `DIIAC_V1_2_0_COMPREHENSIVE_BRIEFING.md`, `DIIAC_V1_2_0_DEBUG_AND_TEST_REPORT.md`.

#### Production Packaging (v1.2.0 release)
- `LICENSE` — Proprietary software licence.
- `SECURITY.md` — Vulnerability disclosure process, security architecture, hardening checklist.
- `CHANGELOG.md` — This file.
- `pyproject.toml` — Python packaging metadata with full dependency specification.
- `requirements.txt` — Full pinned Python dependency manifest.
- `.github/workflows/ci.yml` — Automated CI: lint, test, smoke test on push/PR.
- `.github/workflows/docker-build.yml` — Docker image build and push pipeline.
- `.github/workflows/security.yml` — Dependency audit and container image scanning.
- `openapi.yaml` — OpenAPI 3.0 specification for all governance API endpoints.
- `deploy/kubernetes/` — Kubernetes manifests for production cluster deployment.
- `monitoring/prometheus/` — Prometheus scrape config and alert rules.
- `RELEASE_NOTES_V1_2_0.md` — Customer-facing release notes.

### Changed
- `requirements.txt` updated from 2 bare entries to a full pinned manifest with transitive dependencies.
- README.md expanded with Docker Compose bring-up, LLM key configuration, and full endpoint reference.

### Fixed
- Port collision on bridge port 3001 resolved via `BRIDGE_HOST_PORT` override.
- Signed export and audit export error taxonomy now returns structured `runtime_dependency_failure` responses instead of unhandled 500s.

---

## [1.2.1] - 2026-03-10  *(Staging Baseline Hardening)*

### Changed
- Business profiles narrowed to 5 sector-aligned contracts for staging baseline: it_enterprise_profile_v1, it_service_provider_profile_v1, inance_profile_v1, healthcare_profile_v1, 	ransport_profile_v1.
- Removed transport sub-sector profile contracts from active set: 
ational_highways_profile_v1, 
ational_rail_profile_v1, 	fl_profile_v1.
- UI role selector updated to use CTO (replacing ACTING_CTO) and extended with CFO and PROCUREMENT.
- Bridge fallback profile defaults aligned with runtime contract set so proxy fallback behavior matches the active 5-profile baseline.

### Fixed
- Replay verification deterministic hash parity: /verify/replay now normalizes role bundles and payload hashing in the same way as governed compile input snapshot generation.
- Admin console regression test expectation for profile count updated from 8 to 5.
- Deployment validation guide checkpoints updated to reflect the 5-profile baseline.

---
## [1.1.0] — 2025-12-15

### Added
- Initial deterministic governed compile with Merkle proofing.
- Ed25519 signing for decision packs.
- Hash-chained trust ledger.
- React frontend with Vite + TypeScript.
- Node.js Express backend-ui-bridge.
- 5 initial sector profiles (finance, healthcare, IT enterprise, transport, TfL).

---

## [1.2.1] - 2026-03-10  *(Staging Baseline Hardening)*

### Changed
- Business profiles narrowed to 5 sector-aligned contracts for staging baseline: it_enterprise_profile_v1, it_service_provider_profile_v1, inance_profile_v1, healthcare_profile_v1, 	ransport_profile_v1.
- Removed transport sub-sector profile contracts from active set: 
ational_highways_profile_v1, 
ational_rail_profile_v1, 	fl_profile_v1.
- UI role selector updated to use CTO (replacing ACTING_CTO) and extended with CFO and PROCUREMENT.
- Bridge fallback profile defaults aligned with runtime contract set so proxy fallback behavior matches the active 5-profile baseline.

### Fixed
- Replay verification deterministic hash parity: /verify/replay now normalizes role bundles and payload hashing in the same way as governed compile input snapshot generation.
- Admin console regression test expectation for profile count updated from 8 to 5.
- Deployment validation guide checkpoints updated to reflect the 5-profile baseline.

---
## [1.0.0] — 2025-09-01

### Added
- Initial prototype governance runtime.
- Role ingestion endpoint.
- Basic compile and verify endpoints.
- SQLite persistence layer.


