# VALIDATION_OUTPUTS

Generated_at_utc: 2026-03-13T01:15:00Z
Commit: bfe6ea2
Repository_root: F:/code/diiac/diiac_v1.3.0_ui

## Command Log

### CMD-01
- command: `git rev-parse --short HEAD`
- pass_fail: PASS
- output:
```text
bfe6ea2
```

### CMD-02
- command: `python -m pytest -q --basetemp .pytest_tmp`
- pass_fail: PASS
- output:
```text
collected 53 items
53 passed in 8.53s
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
> tsc --noEmit && vite build
vite v7.3.1 building client environment for production...
? built in 4.40s
(!) Some chunks are larger than 500 kB after minification.
```

### CMD-05
- command: `python scripts_e2e_runtime_smoke.py`
- pass_fail: PASS
- output:
```text
E2E runtime smoke PASSED
```

### CMD-06 (first run)
- command: `python scripts_e2e_assurance_validation.py`
- pass_fail: FAIL
- output:
```text
[FAIL] Governed compile (201) — execution_id=MISSING
error: compile_quality_gate_failed
code: INVALID_SUCCESS_METRICS
OVERALL: FAIL
```
- action_taken: Script updated to send strict `success_metrics` in compile payload.

### CMD-07 (rerun after fix)
- command: `python scripts_e2e_assurance_validation.py`
- pass_fail: PASS
- output:
```text
chatgpt_run: PASS (19/19)
copilot_run: PASS (19/19)
dashboard_validation: PASS (6/6)
OVERALL: PASS
```

### CMD-08
- command: `python scripts_production_readiness_check.py`
- pass_fail: PASS
- output:
```text
Production readiness check PASSED
```

### CMD-09
- command: `node scripts/verify_decision_pack.js artifacts/3cb94e0d-2455-5a20-8dd8-0cef52523142 contracts/keys/public_keys.json`
- pass_fail: PASS
- output:
```text
"overall": "PASS"
"signature_ok": true
"trust_bundle": { "present": true, "source": "pack" }
```

### CMD-10
- command: `python -m pytest -q --basetemp .pytest_tmp tests/test_admin_console.py -k "bridge_non_dev_requires_registered_active_key or bridge_non_dev_rejects_mismatched_registered_key or bridge_runtime_trust_parity_contract or bridge_and_runtime_fail_same_trust_misconfiguration_e2e"`
- pass_fail: PASS
- output:
```text
4 passed, 46 deselected
```

### CMD-11
- command: `python -m pytest -q --basetemp .pytest_tmp tests/test_admin_console.py -k "missing_risk_register_fails_board_section_incomplete or missing_executive_summary_fails_board_section_incomplete or production_output_contains_no_placeholder_sections or success_metrics_require_baseline_target_unit_window_owner or principle_only_metric_fails_invalid_success_metrics or kpi_schema_round_trip_contract or stale_security_evidence_blocks_high_assurance or stale_pricing_evidence_blocks_high_assurance or noncritical_stale_evidence_warns_without_false_pass or selected_vendor_rejects_competitor_primary_evidence or vendor_scope_general_does_not_satisfy_first_party_requirement or vendor_evidence_mismatch_hard_fails_selected_vendor"`
- pass_fail: PASS
- output:
```text
12 passed, 38 deselected
```

### CMD-12
- command: `python -m py_compile app.py tests/test_admin_console.py`
- pass_fail: PASS
- output:
```text
(no output)
```

### CMD-13
- command: `npm --prefix backend-ui-bridge install`
- pass_fail: PASS
- output:
```text
added 130 packages, and audited 131 packages in 11s
1 high severity vulnerability (reported by npm audit)
```

## Commands That Could Not Be Run

- `Remove-Item -Recurse -Force .pytest_tmp,tmp_bridge_ws -ErrorAction SilentlyContinue`
- reason: blocked by command policy in this environment.

## Files That Could Not Be Found

- none relevant to mandatory verification command list.

## Branch/Scope/Path Ambiguity

- none observed.
