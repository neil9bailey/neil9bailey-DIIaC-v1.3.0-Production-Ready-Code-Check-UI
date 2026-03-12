# Admin Console User Guide (v1.3.0-ui)

This guide covers day-to-day admin use in the DIIaC UI.

## Access

- URL: `https://diiacui.vendorlogic.io`
- Auth: Entra sign-in
- Admin role source: mapped Entra group membership

## Key Admin Areas

## 1. Health And Status

Use health views to confirm:

- Runtime availability
- Bridge auth mode and identity state
- Signing/trust readiness
- Integration health

## 2. Executions And Evidence

Admin users can:

- Review recent governance executions
- Inspect trace/scoring outputs
- Export decision packs and audit artifacts
- Verify deterministic and signed outputs

## 3. Approvals And Controls

Where enabled, approvals support:

- Governance intercept review
- Request-level decisioning
- Auditable approval history

## 4. Config And Diagnostics

Admin views expose effective config snapshots and operational metrics.
Use this for drift detection and incident triage.

## Operational Practice

- Validate auth status after each deployment.
- Confirm key governance controls before approving production use.
- Capture evidence artifacts for significant changes.
