# Security Policy — DIIaC v1.2.0

## Supported Versions

| Version | Status              | Security Fixes |
|---------|---------------------|----------------|
| 1.2.x   | Active / Supported  | Yes            |
| < 1.2.0 | End of Life         | No             |

---

## Reporting a Vulnerability

**Do not report security vulnerabilities through public GitHub issues.**

If you discover a security vulnerability in DIIaC, please report it responsibly
via the repository's **Security → Advisories → Report a vulnerability** feature
(GitHub Private Security Reporting), or contact the maintainers directly through
your enterprise account representative.

### What to include in your report

1. **Description** — A clear description of the vulnerability.
2. **Affected component** — Which layer is affected (governance runtime, bridge, frontend, cryptographic module, admin auth, etc.).
3. **Reproduction steps** — Minimal steps to reproduce the issue.
4. **Impact assessment** — Potential impact if exploited (data exposure, auth bypass, integrity breach, etc.).
5. **Suggested fix** (optional) — Any recommendations you have.

### Response timeline

| Stage                     | Target            |
|---------------------------|-------------------|
| Acknowledgement           | Within 2 business days  |
| Initial triage & severity | Within 5 business days  |
| Patch / mitigation plan   | Within 14 business days |
| Public disclosure         | Coordinated with reporter |

---

## Security Architecture

### Cryptographic controls

- **Ed25519 signing** — All decision packs and audit exports are cryptographically signed using Ed25519 private keys injected via `SIGNING_PRIVATE_KEY_PEM`.
- **Merkle tree verification** — SHA-256 Merkle trees provide tamper-evident audit trails for all compiled artefacts.
- **Hash-chained ledger** — The trust ledger (`ledger.jsonl`) is hash-chained; any tampering is detectable by replaying the chain.
- **Deterministic execution IDs** — Execution IDs are derived from input hashes; identical inputs always produce identical IDs in strict mode.

### Authentication & authorisation

- **Admin endpoints** (`/admin/*`) are protected by a bearer token (`ADMIN_API_TOKEN`) enforced in all non-development environments.
- **Entra ID RS256 JWT** validation is available for full enterprise SSO integration via the backend-ui-bridge.
- **RBAC** — Three roles are enforced at the bridge layer: `admin`, `standard`, and `customer`.
- Development mode (`APP_ENV=development`) relaxes admin auth and must **never** be used in production.

### Network security

- The governance runtime (port 8000) should **not** be exposed directly to the public internet; route all external traffic through the backend-ui-bridge or a WAF.
- TLS termination must occur at the load balancer / reverse proxy layer.
- CORS origins should be explicitly restricted in production (configure `CORS_ALLOWED_ORIGINS` in the bridge).

### Payload security

- Input payloads are validated against schema bounds on all key write endpoints to prevent oversized injection attacks.
- SQL injection is not a risk (no raw SQL is used); persistence uses JSON/JSONL file storage and SQLite with ORM-safe access.
- All user-supplied strings are validated for length before processing.

---

## Known Security Considerations

### Ephemeral signing key (default development behaviour)

When `SIGNING_PRIVATE_KEY_PEM` is not set, the runtime generates an ephemeral Ed25519 key at startup. This key is lost on restart, making signature verification impossible across sessions.

**Production requirement:** Always inject a stable `SIGNING_PRIVATE_KEY_PEM` via a secrets manager (Azure Key Vault, AWS Secrets Manager, HashiCorp Vault, or Kubernetes Secrets).

### SQLite single-node storage

The default storage backend is SQLite on the local filesystem. It is not replicated. For high-availability or multi-instance deployments, consider a shared NFS volume or migration to PostgreSQL.

### OPENAI_API_KEY exposure

The OpenAI API key is passed via environment variable. Ensure it is:
- Stored in a secrets manager, not hardcoded.
- Scoped to the minimum required API permissions.
- Rotated on a regular schedule (recommended: 90 days).

### Admin token strength

`ADMIN_API_TOKEN` should be a cryptographically random string of at least 32 characters. Use `openssl rand -hex 32` or equivalent to generate.

---

## Security Hardening Checklist (Production Deployment)

- [ ] `SIGNING_PRIVATE_KEY_PEM` injected from secrets manager (not `.env` file).
- [ ] `ADMIN_API_TOKEN` is a 32+ character random string, stored in secrets manager.
- [ ] `OPENAI_API_KEY` stored in secrets manager with rotation policy.
- [ ] `APP_ENV` is **not** set to `development` or `dev`.
- [ ] `ADMIN_AUTH_ENABLED=true` confirmed in `/admin/health` response.
- [ ] Runtime port 8000 is **not** publicly reachable (firewall / NSG rules in place).
- [ ] TLS 1.2+ enforced at load balancer / ingress layer.
- [ ] CORS restricted to known frontend origin(s).
- [ ] Log output reviewed for accidental secret leakage before enabling external log shipping.
- [ ] Container images scanned for CVEs before deployment (Trivy, Grype, or equivalent).
- [ ] Entra ID group-to-role mappings reviewed and least-privilege-applied.
- [ ] Admin bearer token rotated after any personnel change.

---

## Dependency Security

### Python runtime
Dependencies are declared in `requirements.txt` and `pyproject.toml`. Monitor for CVEs using:
```bash
pip install pip-audit
pip-audit -r requirements.txt
```

### Node.js bridge and frontend
```bash
cd backend-ui-bridge && npm audit
cd Frontend && npm audit
```

### Container images
```bash
docker run --rm aquasec/trivy image diiac-runtime:v1.2.0
docker run --rm aquasec/trivy image diiac-bridge:v1.2.0
docker run --rm aquasec/trivy image diiac-frontend:v1.2.0
```

---

## Incident Response

If a security incident is detected:

1. **Isolate** — Remove the affected instance from the load balancer / network immediately.
2. **Preserve** — Take snapshots of `ledger.jsonl`, `diiac.sqlite3`, and container logs before any remediation.
3. **Notify** — Alert your security team and account representative.
4. **Assess** — Determine whether decision packs or audit exports have been tampered with by replaying Merkle proofs (see `OFFLINE_VERIFIER_RUNBOOK.md`).
5. **Recover** — Redeploy from a known-good container image with rotated secrets.
6. **Review** — Analyse admin logs (`/admin/logs`) and the ledger for the timeline of events.
7. **Disclose** — Follow coordinated disclosure procedures with affected customers.
