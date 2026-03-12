# DIIAC Capabilities Matrix (v1.3.0-ui)

| Capability | UI | Bridge | Runtime | Status |
|---|---|---|---|---|
| Entra sign-in | Yes | Yes (token validation) | N/A | Active |
| RBAC by Entra groups | Yes (role UX) | Yes (enforcement) | Indirect | Active |
| Deterministic governance compile | Trigger | Orchestrate | Execute | Active |
| Evidence capture | View/export | Aggregate/proxy | Generate | Active |
| Signed decision packs | Download | Route export | Sign + emit | Active |
| Replay/verification endpoints | View | Proxy | Execute | Active |
| Copilot-only LLM ingestion | UX controls | Provider lock | Consumes outputs | Active |
| Offline verifier workflow | Initiate/export | Packaging | Integrity source | Active |
| Custom domain HTTPS UI | Yes | N/A | N/A | Active |

## Notes

- Production provider mode is `copilot_only`.
- Production auth mode is `entra_jwt_rs256`.
- Secret values remain in Key Vault.
