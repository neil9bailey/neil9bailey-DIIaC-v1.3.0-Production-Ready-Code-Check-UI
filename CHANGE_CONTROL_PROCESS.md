# DIIaC — Change Control Process

**Applies to:** Platform repo (`neil9bailey/DIIaC-v1.2.0-Production-Ready-Code-Check`)
and all customer instance repos derived from it.
**Owner:** neil9bailey
**Effective from:** v1.2.0

---

## 1. Purpose

This document defines the mandatory process for proposing, reviewing, approving,
testing, releasing, and rolling back changes to the DIIaC platform and to
customer instances. It exists to:

- Protect production customer deployments from untested or unreviewed changes.
- Ensure every release can be reproduced, verified, and rolled back.
- Give customer instance maintainers a predictable, low-friction upgrade path.

---

## 2. Scope

| What | Covered by this process |
|------|------------------------|
| Changes to platform runtime (`app.py`) | Yes — full gate |
| Changes to bridge (`backend-ui-bridge/`) | Yes — full gate |
| Changes to frontend (`Frontend/`) | Yes — full gate |
| New or modified sector profiles (`contracts/business-profiles/`) | Yes — lightweight gate |
| Platform documentation changes only | Yes — doc gate |
| Customer instance `customer-config/` files | Yes — instance gate |
| Azure infrastructure changes (Key Vault, Entra, AKS) | Yes — infra gate |
| Secret rotation | Yes — rotation procedure (Section 9) |

---

## 3. Change classification

All changes are classified at the point of proposal. Classification determines
the approval level and testing requirements.

| Class | SemVer bump | Examples | Approval required |
|-------|------------|----------|-------------------|
| **Patch** | `x.x.N` | Bug fix, doc correction, dependency pin update | Maintainer self-merge after CI green |
| **Minor** | `x.N.0` | New API endpoint, new sector profile, new customer config tooling | Maintainer + 1 review |
| **Major** | `N.0.0` | Breaking API change, auth model change, schema migration | Maintainer + 2 reviews + customer notification |
| **Hotfix** | `x.x.N` (expedited) | Security vulnerability, production-down incident | Maintainer self-merge; post-merge review required within 24 h |
| **Customer-instance** | N/A | Vendorlogic config update, pull script change | Instance maintainer; no platform review needed |

---

## 4. Branch naming convention

All platform changes must be developed on a named branch. Never commit directly
to `main` or a release tag.

```
<type>/<short-description>-<session-or-ticket-id>

Examples:
  feat/rbac-group-claim-validation-1234
  fix/signed-export-timeout-5678
  hotfix/admin-token-bypass-9abc
  docs/change-control-process-c9Ns1
  chore/dependency-pin-update-def0
```

Prefixes follow [Conventional Commits](https://www.conventionalcommits.org/):
`feat`, `fix`, `docs`, `chore`, `refactor`, `test`, `hotfix`.

---

## 5. Platform change gate

Every platform change (Patch, Minor, Major, Hotfix) must clear this gate before
merging to `main`.

### 5.1 Automated CI gate (mandatory)

All three workflows must pass on the PR branch:

| Workflow | File | What it checks |
|----------|------|---------------|
| CI | `.github/workflows/ci.yml` | Lint, unit tests, smoke tests |
| Docker build | `.github/workflows/docker-build.yml` | Image builds successfully |
| Security | `.github/workflows/security.yml` | Dependency audit, container scan |

A PR with any failing workflow **must not** be merged.

### 5.2 Local validation gate (mandatory for Patch and above)

Before opening a PR, the author must run the validation sequence from
`RELEASE_LOCK_V1_2_0.md` locally:

```bash
python3 -m py_compile app.py
node --check backend-ui-bridge/server.js
pytest -q
cd Frontend && npm run build && cd ..
python3 scripts_e2e_runtime_smoke.py
python3 scripts_production_readiness_check.py
```

All commands must return success. Include the console output as a PR comment
or as a collapsible section in the PR description.

### 5.3 Review gate

| Change class | Reviews required | Who can review |
|-------------|-----------------|----------------|
| Patch | 0 (self-merge after CI) | — |
| Minor | 1 | Any contributor with repo access |
| Major | 2 | Maintainer + 1 external reviewer |
| Hotfix | 0 (self-merge); post-merge review within 24 h | Maintainer assigns reviewer after merge |

### 5.4 Documentation gate

Every change that affects:
- API behaviour → update `openapi.yaml`
- Auth or security model → update `SECURITY.md` and relevant setup guide
- Customer instance workflow → update `CUSTOMER_FORK_MODEL.md`
- Environment variables → update `customer-config/_template/config.env`
- Changelog → add entry to `CHANGELOG.md`

PRs that affect any of the above without updating the corresponding doc
**will be rejected**.

---

## 6. Release process

### 6.1 Prepare the release branch

```bash
git checkout main
git pull origin main
git checkout -b release/vX.Y.Z
```

### 6.2 Update version artefacts

- `CHANGELOG.md` — add `## [X.Y.Z] — YYYY-MM-DD` section.
- `RELEASE_NOTES_vX_Y_Z.md` — create customer-facing release notes.
- `pyproject.toml` — bump `version`.

### 6.3 Run the full validation gate

```bash
python3 -m py_compile app.py
node --check backend-ui-bridge/server.js
pytest -q
cd Frontend && npm run build && cd ..
python3 scripts_e2e_runtime_smoke.py
python3 scripts_production_readiness_check.py
```

### 6.4 Merge and tag

```bash
# After PR approval and merge to main:
git checkout main
git pull origin main
git tag -a vX.Y.Z -m "DIIaC vX.Y.Z release"
git push origin main
git push origin vX.Y.Z
```

### 6.5 Post-tag integrity check

```bash
git checkout vX.Y.Z
python3 -m py_compile app.py
pytest -q
python3 scripts_e2e_runtime_smoke.py
```

If any check fails, the tag must be deleted (`git tag -d vX.Y.Z && git push --delete origin vX.Y.Z`),
the issue fixed, and the full release process restarted from 6.1.

---

## 7. Customer instance update process

When a new platform version is released, customer instance maintainers are
responsible for adopting it. The platform maintainer must:

1. Create a GitHub release on the platform repo with the tag and attach
   `RELEASE_NOTES_vX_Y_Z.md`.
2. For **Major** changes: open an issue on the affected customer instance repos
   describing the breaking change and the required config changes.
3. For **Minor/Patch** changes: the release notes are sufficient notification.

Customer instance maintainers follow the merge process in `CUSTOMER_FORK_MODEL.md`
(Section: *Receiving platform updates*):

```bash
git remote add platform https://github.com/neil9bailey/DIIaC-v1.2.0-Production-Ready-Code-Check.git
git fetch platform --tags
git checkout -b upgrade/vX.Y.Z
git merge platform/vX.Y.Z
# Resolve conflicts, test, then merge to main
```

Customer instances must **not** be updated by modifying platform files directly.
All customer-specific differences live in `customer-config/<customer>/`,
pull scripts, and the staging compose override only.

---

## 8. Rollback procedure

### 8.1 Platform rollback

If a release is found to be defective after tagging:

```bash
# On the platform repo — revert to previous known-good tag
git checkout vX.Y.(Z-1)
python3 scripts_e2e_runtime_smoke.py   # confirm good
# Communicate the issue via GitHub release notes (mark bad release as pre-release or delete)
```

Do not force-push or delete a tag that has already been adopted by customer instances
without coordinating with those instance maintainers first.

### 8.2 Customer instance rollback

```bash
# In the customer instance repo
git log --oneline -10    # find the pre-upgrade commit
git checkout -b rollback/vX.Y.Z-revert
git revert <merge-commit-sha>
git push origin rollback/vX.Y.Z-revert
# Open PR, merge, then redeploy
```

Refer to `DEPLOYMENT_VALIDATION_RUNBOOK.md` for the validation sequence to run
after any rollback before returning traffic to the rolled-back deployment.

---

## 9. Secret rotation

Secret rotation in Key Vault is **not** a platform code change and does not
require a PR or version bump. It follows the rotation procedures in
`customer-config/<customer>/keyvault-secrets-manifest.md`.

Rotation events must be logged in the customer instance's operational log
(out of band — not committed to the repo).

Rotation triggers:
- `diiac-admin-api-token` — every 90 days, or on suspected compromise.
- `diiac-openai-api-key` — every 90 days, or on suspected exposure.
- `diiac-entra-client-secret` — every 12 months via Entra portal.
- `diiac-signing-private-key-pem` — on compromise only; rotation breaks
  existing signature verification and requires a coordinated customer notification.

---

## 10. Emergency / hotfix process

For security vulnerabilities or production-down incidents:

1. **Identify and scope** — open a private security advisory on GitHub
   (do not disclose details in a public issue) per `SECURITY.md`.
2. **Branch** — create `hotfix/<description>-<id>` from the affected release tag,
   not from `main` (which may contain unreleased work).
3. **Fix and validate** — run the local validation gate (Section 5.2).
4. **Merge** — self-merge without waiting for review. CI must still be green.
5. **Tag** — bump the patch version and tag immediately.
6. **Post-merge review** — assign a reviewer within 24 hours.
7. **Notify customers** — open issues on affected customer instance repos
   with the CVE reference, affected versions, and upgrade steps.

---

## 11. Change freeze periods

The platform is in a **release freeze** from the point a release branch is
opened (Section 6.1) until the tag is published and the post-tag integrity
check passes. During a freeze:

- No new features may be merged to `main`.
- Bug fixes for the release may be cherry-picked onto the release branch.
- Hotfixes for production incidents bypass the freeze.

---

## 12. Related documents

| Document | Purpose |
|----------|---------|
| `CHANGELOG.md` | Versioned record of all platform changes |
| `RELEASE_LOCK_V1_2_0.md` | Validation gate reference for v1.2.0 |
| `DEPLOYMENT_VALIDATION_RUNBOOK.md` | Post-deploy acceptance criteria and rollback steps |
| `CUSTOMER_FORK_MODEL.md` | Customer instance creation and update workflow |
| `SECURITY.md` | Vulnerability disclosure and security hardening |
| `customer-config/_template/` | Template for new customer instance config |
