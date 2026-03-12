# VALIDATION_OUTPUTS

Generated_at_utc: 2026-03-13T00:00:40Z
Commit: 612e654

## Command Log

### CMD-01
- command: `git rev-parse --short HEAD`
- pass_fail: PASS
- output:
```text
612e654
```

### CMD-02
- command: `python -m pytest -q --basetemp .pytest_tmp`
- pass_fail: PASS
- output:
```text
collected 33 items
tests\test_admin_console.py ..............................
tests\test_persistence.py ...
33 passed
```

### CMD-03
- command: `node --check backend-ui-bridge/server.js`
- pass_fail: PASS
- output:
```text
(no output)
```

### CMD-04
- command: `npm --prefix Frontend run build`
- pass_fail: PASS
- output:
```text
vite v7.3.1 building client environment for production...
✓ built in 4.04s
(!) Some chunks are larger than 500 kB after minification.
```

### CMD-05
- command: `python scripts_e2e_runtime_smoke.py`
- pass_fail: PASS
- output:
```text
E2E runtime smoke PASSED
```

### CMD-06
- command: `python scripts_e2e_assurance_validation.py`
- pass_fail: PASS
- output:
```text
chatgpt_run: PASS (19/19)
copilot_run: PASS (19/19)
dashboard_validation: PASS (6/6)
OVERALL: PASS
```

### CMD-07
- command: `python scripts_production_readiness_check.py`
- pass_fail: PASS
- output:
```text
Production readiness check PASSED
```

### CMD-08
- command: `node scripts/verify_decision_pack.js artifacts/bc5ea544-7c75-5943-a840-3562fd7fa4a5 contracts/keys/public_keys.json`
- pass_fail: PASS
- output:
```text
"overall": "PASS"
"signature_ok": true
"trust_bundle": { "present": true, "source": "pack" }
```

### CMD-09
- command: `rg -n "hard_gate_failures|compile_quality_gate_failed|PLACEHOLDER_CLAIM_ID_PRESENT|UNRESOLVED_EVIDENCE|VENDOR_EVIDENCE_MISMATCH|COMPETITOR_PRIMARY_EVIDENCE|INVALID_SUCCESS_METRICS|MISSING_REGULATORY_CONSTRAINTS|MISSING_SUCCESS_TARGETS|DECISION_PROVENANCE_INCONSISTENT|POLICY_EVIDENCE_BASIS_MISSING|BOARD_SECTION_INCOMPLETE|REVIEW_STATE_INCOMPLETE|STALE_VENDOR_ALIAS_PRESENT" app.py`
- pass_fail: PASS
- output:
```text
... PLACEHOLDER_CLAIM_ID_PRESENT
... UNRESOLVED_EVIDENCE
... VENDOR_EVIDENCE_MISMATCH
... COMPETITOR_PRIMARY_EVIDENCE
... INVALID_SUCCESS_METRICS
... MISSING_REGULATORY_CONSTRAINTS
... MISSING_SUCCESS_TARGETS
... DECISION_PROVENANCE_INCONSISTENT
... POLICY_EVIDENCE_BASIS_MISSING
... BOARD_SECTION_INCOMPLETE
... REVIEW_STATE_INCOMPLETE
```

### CMD-10
- command: `rg -n "TRUST_REGISTRY_DEV_AUTOREGISTER|allow_registry_autoregister|Non-development runtime requires SIGNING_PRIVATE_KEY_PEM|not present in contracts/keys/public_keys.json|does not match registered public key material" app.py`
- pass_fail: PASS
- output:
```text
allow_registry_autoregister ...
Non-development runtime requires SIGNING_PRIVATE_KEY_PEM ...
... not present in contracts/keys/public_keys.json
... does not match registered public key material
```

### CMD-11
- command: `rg -n "ephemeral_dev_only|Non-development bridge runtime requires SIGNING_PRIVATE_KEY_PEM|key_registry_ok|trust_registry_source" backend-ui-bridge/server.js`
- pass_fail: PASS
- output:
```text
Non-development bridge runtime requires SIGNING_PRIVATE_KEY_PEM; ephemeral signing is blocked.
keyMode: "ephemeral_dev_only"
key_registry_ok: SIGNING_ENABLED ? signingKeyMode === "configured" || IS_DEV_RUNTIME : true
trust_registry_source: fs.existsSync(PUBLIC_KEYS_PATH) ? "local_registry_file" : "external_or_missing"
```

### CMD-12
- command: `rg -n "deterministic-governance|llm-hallucination-risk|auto-ref-|INLINE_ROLE_PAYLOAD_USED|fallback_evidence_ids|unresolved-evidence|intent_coverage|review_state|bridge_metadata" app.py backend-ui-bridge/server.js`
- pass_fail: PASS
- output:
```text
app.py:3859: evidence_refs ... auto-ref-{idx}
app.py:3872: ... or ["deterministic-governance"]
app.py:3873: ... or ["llm-hallucination-risk"]
app.py:2657: "intent_coverage": intent_signals
```

### CMD-13
- command: `rg -n "assessment_mode|assurance_level|compliance_position|legal_confirmation_required|residual_uncertainty" app.py Frontend/src openapi.yaml`
- pass_fail: PASS
- output:
```text
app.py: emits semantics fields
Frontend/src: no component rendering references
openapi.yaml: no full response schema for these fields
```

### CMD-14
- command: `if (Test-Path tests/golden) ...; if (Test-Path tests/negative) ...; workflows listing`
- pass_fail: PASS
- output:
```text
tests/golden:absent
tests/negative:absent
ci.yml
docker-build.yml
security.yml
```

### CMD-15
- command: `rg -n "requested_assurance_level|review_state|bridge_metadata|assessment_mode|assurance_level|compliance_position" openapi.yaml Frontend/src/api.ts`
- pass_fail: PASS
- output:
```text
openapi.yaml: requested_assurance_level/review_state/bridge_metadata present on request schema
Frontend/src/api.ts: requested_assurance_level/review_state present in payload typing
```

### CMD-16
- command: `rg -n "^def test_" tests/test_admin_console.py`
- pass_fail: PASS
- output:
```text
33 tests listed
(no golden fixture/parity/provider differential tests)
```

## Commands That Could Not Be Run

- none in this closure pass.

## Files That Could Not Be Found

- `tests/golden`
- `tests/negative`

## Branch/Scope/Path Ambiguity

- none observed.
