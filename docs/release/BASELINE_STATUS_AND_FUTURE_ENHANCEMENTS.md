# Baseline Status And Future Enhancements (v1.3.0-ui)

## Current Baseline Status

- Version baseline: `v1.3.0-ui`
- Deployment pattern: dedicated ACA stack
- External UI domain: `diiacui.vendorlogic.io`
- Identity: Entra production auth
- Secrets: Key Vault only
- LLM provider mode: `copilot_only`
- Evidence posture: checkpoint artifacts captured under `docs/release/evidence/`

## Stable Today

- End-to-end UI -> bridge -> runtime governance flow
- Signed decision artifacts and trust verification surfaces
- Role-based access mapped from Entra claims
- Custom-domain UI access with TLS

## Planned Enhancements

1. Hardened automation around domain binding and certificate lifecycle checks.
2. Expanded policy/evidence quality metrics surfaced directly in UI.
3. Additional regression suites for auth and role-mapping edge cases.
4. Stronger environment promotion workflows (staging -> production).

## Guardrails To Keep

- What-if before every apply
- Non-destructive rollout posture
- Key Vault-only secrets handling
- Evidence capture at each significant checkpoint
