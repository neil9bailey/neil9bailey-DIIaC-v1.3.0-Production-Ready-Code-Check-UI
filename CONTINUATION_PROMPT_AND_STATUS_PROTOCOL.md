# DIIaC Continuation Prompt + Status Protocol (No-Drift)

## Purpose
This file is the canonical bootstrap prompt and operating protocol for starting a **new chat** without losing context, scope, or delivery continuity.

---

## 1) Copy/Paste Prompt for a New Chat

Use the full block below at the start of a new chat:

```md
You are continuing development for DIIaC v1.1.0 on branch `work`.

Non-negotiables:
1. No drift: only implement changes aligned to the current blueprint/spec/docs unless I explicitly approve a scope change.
2. Always begin with a codebase status report:
   - current branch and head commit
   - whether local workspace is dirty/clean
   - whether commits are ahead/behind remote
   - list of any pending/uncommitted changes
3. Before coding, map requested work to these repo documents and cite exact files:
   - `DIIAC_CURRENT_ARCHITECTURE_BLUEPRINT.md`
   - `DIIAC_CAPABILITIES_MATRIX.md`
   - `DIIAC_CRYPTOGRAPHIC_SPEC.md`
   - `GOVERNANCE_EXTENSIONS_V1_SPEC.md`
   - `BASELINE_STATUS_AND_FUTURE_ENHANCEMENTS.md`
   - `DIIAC_ARCHITECTURE_ALIGNMENT_REPORT.md`
   - `README.md`
   - `HANDOFF.md`
4. For each requested change:
   - state aligned vs gap items
   - implement minimally and safely
   - run tests/checks
   - provide a status report with pass/fail evidence
5. End every response with:
   - `Repo status` (branch, commit, clean/dirty, ahead/behind)
   - `Pending git updates` (yes/no + what)
   - `Drift check` (explicitly confirm aligned or list deviations)
6. If docs and implementation disagree, prioritize implemented behavior and propose doc fixes immediately.

Current operating goal:
Maintain and harden the production-ready governance baseline (deterministic compile, cryptographic verification, admin and DB operations, and UI-to-runtime reliability), then progress remaining hardening items in controlled increments.
```

---

## 2) Required Reference Order (Always)

When continuing in a new chat, review in this order:

1. `HANDOFF.md` (latest quick state)
2. `DIIAC_CURRENT_ARCHITECTURE_BLUEPRINT.md` (target operating model)
3. `DIIAC_CAPABILITIES_MATRIX.md` (implemented capability inventory)
4. `BASELINE_STATUS_AND_FUTURE_ENHANCEMENTS.md` (what’s done vs pending)
5. `DIIAC_CRYPTOGRAPHIC_SPEC.md` + `GOVERNANCE_EXTENSIONS_V1_SPEC.md` (crypto/control constraints)
6. `README.md` (runtime and operational usage)
7. `DIIAC_ARCHITECTURE_ALIGNMENT_REPORT.md` (alignment statement)

---

## 3) Mandatory Status Report Format

Use this exact structure at start and end of implementation turns:

- **Repo status**
  - Branch:
  - HEAD:
  - Working tree: clean/dirty
  - Remote sync: ahead/behind/diverged
- **Pending git updates**
  - None / List of files + reason
- **Drift check**
  - `No drift detected` OR
  - `Potential drift:` with file/behavior details

Suggested commands:

```bash
git branch --show-current
git rev-parse --short HEAD
git status --short
git fetch origin
git rev-list --left-right --count HEAD...origin/$(git branch --show-current)
```

---

## 4) Definition of “No Drift” for DIIaC

A change is drift if it does any of the following without approval:
- renames/removes governance endpoints relied on by frontend/admin flows
- weakens deterministic compile behavior or governance controls
- alters cryptographic verification semantics without spec update
- changes role/access expectations without explicit policy decision
- updates docs to claim capabilities not implemented in code/tests

---

## 5) Next Development Priorities (Production Hardening)

Prioritized continuation roadmap:

1. **Security hardening**
   - enforce admin auth by default in non-dev
   - add route-level auth tests for deny/allow matrices
   - tighten payload schema bounds across all write endpoints
2. **Runtime resilience**
   - startup checks with explicit readiness for DB/contracts/keys
   - improve error taxonomy for proxy/runtime dependency failures
3. **Verification strength**
   - add offline verifier workflow documentation + sample runbook
   - expand tamper tests for signature/merkle mismatch cases
4. **Operational maturity**
   - structured logging with stable event IDs for audit triage
   - richer metrics documentation and threshold recommendations
5. **UI end-to-end confidence**
   - scripted e2e flows covering role input, compile, trust/admin/logs/db pages
   - capture baseline screenshots and expected results

---

## 6) Release Discipline Going Forward

For each development pass:
- implement scoped changes only
- run tests/checks and report command outputs
- commit with clear message
- publish PR summary with risk/rollback notes
- update `HANDOFF.md` + relevant docs if behavior changes

