# Copilot + Entra Production Checklist (v1.3.0-ui)

Use this checklist before approving production rollout.

## Identity

- [ ] `AUTH_MODE=entra_jwt_rs256`
- [ ] Tenant ID matches target tenant
- [ ] Expected audience is correct (`api://<app-id>`)
- [ ] Issuer pinning includes required Entra issuer
- [ ] Group-to-role mapping loaded with admin and standard IDs
- [ ] Custom-domain redirect URI configured in Entra app registration

## Secrets And Keys

- [ ] `diiac-admin-api-token` present in Key Vault
- [ ] `diiac-signing-private-key-pem` present in Key Vault
- [ ] `diiac-github-token` present in Key Vault
- [ ] Container apps read secrets via managed identity references
- [ ] No plaintext secret values committed in repo

## Copilot Provider

- [ ] `LLM_PROVIDER_MODE=copilot_only`
- [ ] `LLM_INGESTION_ENABLED=true`
- [ ] `LLM_STUB_ENABLED=false` in production
- [ ] `COPILOT_MODEL` set to approved model

## Runtime Security

- [ ] Signing enabled and production key ID set
- [ ] Admin auth enabled
- [ ] CORS restricted to approved origins
- [ ] TLS enforced on external ingress

## Evidence

- [ ] What-if output captured before apply
- [ ] Apply output captured
- [ ] Auth status snapshot captured
- [ ] Post-deploy smoke evidence captured
- [ ] Quality summary captured for at least one decision pack
