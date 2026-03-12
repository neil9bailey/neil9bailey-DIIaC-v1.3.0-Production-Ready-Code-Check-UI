# Release Lock (Maintained Reference, v1.3.0-ui)

Note: filename is legacy for continuity. Use this as the current release lock checklist.

## Build Lock Criteria

- [ ] `python -m py_compile app.py` passes
- [ ] `node --check backend-ui-bridge/server.js` passes
- [ ] `pytest -q` passes
- [ ] `npm run build` (Frontend) passes
- [ ] smoke and readiness scripts pass

## Security Lock Criteria

- [ ] Production auth mode is Entra RS256
- [ ] Redirect URIs include production custom-domain callback
- [ ] Key Vault secrets present and referenced via managed identity
- [ ] No plaintext secrets in repository changes

## Deployment Lock Criteria

- [ ] `--plan` validate and what-if complete
- [ ] Evidence captured before apply
- [ ] Apply succeeds with expected outputs
- [ ] Post-deploy runbook checks pass

## Governance Lock Criteria

- [ ] At least one decision pack quality check passes
- [ ] Signed artifact path verified
- [ ] Trust endpoints healthy
