# DIIaC v1.2.0 — Release Notes

**Release date:** 2026-03-04
**Status:** Production release — locked

---

## What is DIIaC?

DIIaC (Deterministic Infrastructure Intelligence as Code) is a governed decision
intelligence platform that produces cryptographically verifiable, deterministic
assurance outputs for infrastructure procurement and governance decisions.

Every compile is deterministic, every output is signed, every decision is
Merkle-proofed, and every audit event is hash-chained.

---

## Highlights of v1.2.0

### Deterministic governance you can prove

- **Same inputs → same outputs, always.** In strict deterministic mode, identical
  role inputs + profile + schema + reasoning/policy level produce the same
  execution ID, pack hash, and scoring — every time.
- **Ed25519 signed decision packs.** Every compiled governance output is signed
  with a stable Ed25519 private key and verifiable offline with the public key
  registry.
- **SHA-256 Merkle trees.** All compiled artefacts are bound into a Merkle tree;
  any single-byte tamper is detectable by re-running the proof.

### LLM + deterministic compile in one call

New `POST /api/llm-governed-compile` endpoint orchestrates:
1. OpenAI LLM synthesis of the governance narrative.
2. Deterministic governed compile of the structured output.
3. Returns a fully signed, Merkle-proofed decision pack.

### Replay attestation

`POST /verify/replay` issues a deterministic `replay_certificate.json` — a
cryptographically anchored attestation that a specific set of inputs has been
independently verified to reproduce the recorded execution.

### Production-hardened operations

- Admin endpoints protected by bearer token in all non-development environments.
- Payload schema bounds enforced on all write endpoints.
- Structured backend logs with stable event IDs (`EVT-<SHA256[:8]>`).
- `/admin/metrics` exposes alerting guidance (MTR-001, MTR-002 alert codes).
- `/health` and `/admin/health` expose explicit `storage`, `contracts`, and
  `database` readiness checks.

### Full-stack Docker Compose bring-up

One command to run the complete stack (runtime + bridge + frontend):

```bash
cp .env.example .env
# Edit .env with your OPENAI_API_KEY
docker compose up
```

Open: http://localhost:5173

---

## Production deployment

### Docker Compose (single-node / staging)

See [README.md](README.md) for full Docker Compose instructions.

### Kubernetes (production cluster)

See [deploy/kubernetes/README.md](deploy/kubernetes/README.md) for
step-by-step Kubernetes deployment instructions.

### Pre-deployment validation

Run the full validation gate before promoting to production:

```bash
python3 -m py_compile app.py
node --check backend-ui-bridge/server.js
pytest -q
cd Frontend && npm run build
python3 scripts_e2e_runtime_smoke.py
python3 scripts_production_readiness_check.py
```

See [DEPLOYMENT_VALIDATION_RUNBOOK.md](DEPLOYMENT_VALIDATION_RUNBOOK.md) for
the full promotion checklist with acceptance criteria and rollback guidance.

---

## Security

### Admin authentication

In all non-development environments (`APP_ENV` is not `development` or `dev`),
the `/admin/*` endpoints require a bearer token:

```bash
curl -H "Authorization: Bearer $ADMIN_API_TOKEN" http://localhost:8000/admin/health
```

**Generate a strong token:**
```bash
openssl rand -hex 32
```

### Signing key

Set `SIGNING_PRIVATE_KEY_PEM` from a secrets manager for stable signatures.
Without it, an ephemeral key is generated at startup — signatures will not
be verifiable across restarts.

### Full security hardening checklist

See [SECURITY.md](SECURITY.md).

---

## API reference

Full OpenAPI 3.0 specification: [openapi.yaml](openapi.yaml)

### Key endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/human-input/role` | Ingest stakeholder role input |
| POST | `/api/governed-compile` | Deterministic governed compile |
| POST | `/api/llm-governed-compile` | LLM synthesis + governed compile |
| GET | `/verify/execution/<id>` | Verify execution against ledger |
| POST | `/verify/pack` | Verify pack hash + Ed25519 signature |
| POST | `/verify/replay` | Replay attestation certificate |
| GET | `/decision-pack/<id>/export-signed` | Signed export metadata |
| POST | `/admin/audit-export` | Generate audit bundle |
| GET | `/health` | Runtime readiness |
| GET | `/admin/metrics` | Operational metrics |

---

## Sector profiles included

| Profile | File |
|---------|------|
| Finance | `finance_profile_v1.json` |
| Healthcare | `healthcare_profile_v1.json` |
| IT Enterprise | `it_enterprise_profile_v1.json` |
| IT Service Provider | `it_service_provider_profile_v1.json` |
| National Highways | `national_highways_profile_v1.json` |
| National Rail | `national_rail_profile_v1.json` |
| Transport for London | `tfl_profile_v1.json` |
| Transport | `transport_profile_v1.json` |

---

## Documentation index

| Document | Purpose |
|----------|---------|
| [README.md](README.md) | Quick start, Docker Compose, API reference |
| [DEPLOYMENT_VALIDATION_RUNBOOK.md](DEPLOYMENT_VALIDATION_RUNBOOK.md) | Production promotion checklist |
| [SECURITY.md](SECURITY.md) | Security policy, hardening checklist |
| [OFFLINE_VERIFIER_RUNBOOK.md](OFFLINE_VERIFIER_RUNBOOK.md) | Offline pack + Merkle verification |
| [DIIAC_UI_WORKFLOW_GUIDE.md](DIIAC_UI_WORKFLOW_GUIDE.md) | Step-by-step UI workflow |
| [DIIAC_VISUAL_WORKFLOW_DIAGRAM.md](DIIAC_VISUAL_WORKFLOW_DIAGRAM.md) | Production sequence diagrams |
| [DIIAC_REAL_WORLD_E2E_ASSURANCE_REPORT.md](DIIAC_REAL_WORLD_E2E_ASSURANCE_REPORT.md) | Real-world production-path example |
| [ENTRA_ID_SETUP_GUIDE.md](ENTRA_ID_SETUP_GUIDE.md) | Entra ID SSO configuration |
| [COPILOT_ENTRA_PRODUCTION_CHECKLIST.md](COPILOT_ENTRA_PRODUCTION_CHECKLIST.md) | 84-point Copilot + Entra checklist |
| [ADMIN_CONSOLE_USER_GUIDE.md](ADMIN_CONSOLE_USER_GUIDE.md) | Admin console guide |
| [DIIAC_CRYPTOGRAPHIC_SPEC.md](DIIAC_CRYPTOGRAPHIC_SPEC.md) | Ed25519 + Merkle cryptographic spec |
| [openapi.yaml](openapi.yaml) | OpenAPI 3.0 API specification |
| [deploy/kubernetes/](deploy/kubernetes/) | Kubernetes deployment manifests |
| [monitoring/prometheus/](monitoring/prometheus/) | Prometheus scrape config + alerts |
| [CHANGELOG.md](CHANGELOG.md) | Full version history |
| [HANDOFF.md](HANDOFF.md) | v1.2.0 verified capability record |
| [RELEASE_LOCK_V1_2_0.md](RELEASE_LOCK_V1_2_0.md) | Release-lock record + tag workflow |

---

## Known limitations

- **Single-replica SQLite storage.** The governance runtime uses SQLite and is
  designed for single-instance deployment. For HA, use a shared NFS volume or
  migrate to a PostgreSQL backend (v1.3.0 roadmap).
- **In-memory execution state.** Execution records are held in-memory and
  persisted to the SQLite database. A runtime restart will reload state from
  disk; any in-flight executions at restart time may be incomplete.
- **LLM non-determinism.** The `llm-governed-compile` endpoint calls OpenAI;
  the LLM output is non-deterministic. The subsequent deterministic compile
  step is deterministic given the LLM output.

---

## What's next — v1.3.0

Development is underway on the v1.3.0 Headless Governance Plane:

- API-first / headless operation (UI as optional overlay).
- External intent ingestion from agent pipelines, Copilot, and CLI.
- Policy pack versioning with signed policy manifests.
- Confidence and trust scoring as first-class API response fields.

See [PRODUCT_ROADMAP_V1_3_0.md](PRODUCT_ROADMAP_V1_3_0.md) for the full
development roadmap.
