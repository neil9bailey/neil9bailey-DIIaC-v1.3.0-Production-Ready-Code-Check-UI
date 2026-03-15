# VALIDATION_OUTPUTS

Generated_at_utc: 2026-03-15T12:44:00Z  
Commit: 28ca865  
Repository_root: F:/code/diiac/diiac_v1.3.0_ui

## Command Log

### CMD-01
- command: `git status --short`
- pass_fail: PASS
- output_snippet:
```text
M CONTRADICTION_REPORT.md
M Frontend/package-lock.json
... (modified/untracked working files listed)
```

### CMD-02
- command: `git rev-parse --abbrev-ref HEAD`
- pass_fail: PASS
- output_snippet:
```text
main
```

### CMD-03
- command: `Get-ChildItem IMPLEMENTATION_CLOSURE_MATRIX.md,VERIFICATION_MANIFEST.json,QUALITY_GATES_REPORT.json,UNRESOLVED_GAPS.md,CONTRADICTION_REPORT.md,VALIDATION_OUTPUTS.md | Select-Object Name,Length,LastWriteTime`
- pass_fail: PASS
- output_snippet:
```text
IMPLEMENTATION_CLOSURE_MATRIX.md 13149
VERIFICATION_MANIFEST.json 22020
QUALITY_GATES_REPORT.json 7190
UNRESOLVED_GAPS.md 1910
CONTRADICTION_REPORT.md 861
VALIDATION_OUTPUTS.md 4663
```

### CMD-04
- command: `rg -n "<Wave1 required test names>" tests`
- pass_fail: PASS
- output_snippet:
```text
tests/test_admin_console.py:977:def test_replay_does_not_inject_legacy_non_negotiables()
...
tests/test_admin_console.py:1546:def test_vendor_evidence_mismatch_hard_fails_selected_vendor()
```

### CMD-05
- command: `rg -n "<Wave2/Wave3 required test names>" tests`
- pass_fail: PASS
- output_snippet:
```text
tests/test_wave2_parity_contracts.py:89:def test_provider_metadata_does_not_leak_into_recommendation()
...
tests/test_wave3_accountability.py:162:def test_incomplete_selected_vendor_dossier_fails()
```

### CMD-06
- command: `Get-Content CONTRADICTION_REPORT.md`
- pass_fail: PASS
- output_snippet:
```text
In-Scope Contradictions (R1-R14): None detected.
```

### CMD-07
- command: `rg -n "assessment_mode|assurance_level|compliance_position|legal_confirmation_required|evidence_ids|residual_uncertainty" openapi.yaml Frontend/src/api.ts Frontend/src/components/PolicySemanticsPanel.tsx Frontend/src/MultiRoleGovernedCompilePanel.tsx`
- pass_fail: PASS
- output_snippet:
```text
openapi.yaml:338: - assessment_mode
Frontend/src/api.ts:131: assessment_mode: ...
Frontend/src/components/PolicySemanticsPanel.tsx:37: Assessment Mode: ...
```

### CMD-08
- command: `rg -n "PASS" Frontend/src -g"*.tsx" -g"*.ts"`
- pass_fail: PASS
- output_snippet:
```text
Frontend/src/components/PolicySemanticsPanel.tsx:32: Controls: ... PASS: ...
Frontend/src/api.ts:129: status: "PASS" | "FAIL";
```

### CMD-09
- command: `Get-Content e2e_assurance_validation_export.json`
- pass_fail: PASS
- output_snippet:
```text
overall_result: PASS
copilot_run.execution_id: 30c3ac1e-ae16-5c32-a19e-1fdac632aec0
```

### CMD-10
- command: `git rev-parse --short HEAD`
- pass_fail: PASS
- output_snippet:
```text
74a66ea
```

### CMD-11
- command: `python -m pytest -q --basetemp .pytest_tmp`
- pass_fail: PASS
- output_snippet:
```text
collected 89 items
89 passed in 16.68s
```

### CMD-12
- command: `node --check backend-ui-bridge/server.js`
- pass_fail: PASS
- output_snippet:
```text
(no output)
```

### CMD-13
- command: `npm --prefix Frontend run build`
- pass_fail: PASS
- output_snippet:
```text
tsc --noEmit && vite build
✓ built in 4.44s
```

### CMD-14
- command: `python scripts_e2e_runtime_smoke.py`
- pass_fail: PASS
- output_snippet:
```text
E2E runtime smoke PASSED
```

### CMD-15
- command: `python scripts_e2e_assurance_validation.py`
- pass_fail: PASS
- output_snippet:
```text
chatgpt_run: PASS (19/19)
copilot_run: PASS (19/19)
dashboard_validation: PASS (6/6)
OVERALL: PASS
```

### CMD-16
- command: `python scripts_production_readiness_check.py`
- pass_fail: PASS
- output_snippet:
```text
Production readiness check PASSED
```

### CMD-17
- command: `$id=(Get-Content e2e_assurance_validation_export.json | ConvertFrom-Json).copilot_run.execution_id; node scripts/verify_decision_pack.js artifacts/$id contracts/keys/public_keys.json`
- pass_fail: PASS
- output_snippet:
```text
USING_EXECUTION_ID=5fea0f49-9911-5a83-8f29-e68230a01a0b
"overall": "PASS"
"signature_ok": true
```

### CMD-18
- command: `python -m pytest -q tests/test_golden_exports.py --basetemp .pytest_tmp`
- pass_fail: PASS
- output_snippet:
```text
3 passed in 1.09s
```

### CMD-19
- command: `python -m pytest -q tests/test_negative_fixtures.py --basetemp .pytest_tmp`
- pass_fail: PASS
- output_snippet:
```text
15 passed in 2.68s
```

### CMD-20
- command: `npm --prefix Frontend run test -- --run`
- pass_fail: PASS
- output_snippet:
```text
1 passed test file, 2 passed tests
```

### CMD-21
- command: `python -m pytest -q tests/test_wave2_parity_contracts.py --basetemp .pytest_tmp`
- pass_fail: PASS
- output_snippet:
```text
12 passed in 6.36s
```

### CMD-22
- command: `python -m pytest -q tests/test_wave3_accountability.py --basetemp .pytest_tmp`
- pass_fail: PASS
- output_snippet:
```text
6 passed in 1.29s
```

### CMD-23
- command: `python -m pytest -q tests/test_wave2_parity_contracts.py -k "provider_metadata or recommendation_invariant or decision_basis_references_vendor_not_provider or trust_bundle_contains_validity_window or historical_pack_verifies_under_rotated_key_registry or unknown_key_export_fails or tampered_signature_fails_verification" --basetemp .pytest_tmp`
- pass_fail: FAIL
- output_snippet:
```text
PermissionError: [WinError 32] ... .pytest_tmp ... file is being used by another process
```
- action_taken: reran with dedicated base temp path.

### CMD-24
- command: `python -m pytest -q tests/test_wave2_parity_contracts.py -k "provider_metadata or recommendation_invariant or decision_basis_references_vendor_not_provider or trust_bundle_contains_validity_window or historical_pack_verifies_under_rotated_key_registry or unknown_key_export_fails or tampered_signature_fails_verification" --basetemp .pytest_tmp_wave2_target`
- pass_fail: PASS
- output_snippet:
```text
7 passed, 5 deselected in 2.13s
```

### CMD-25
- command: `python -m pytest -q tests/test_wave2_parity_contracts.py -k "api_schema_contract_for_policy_semantics_response or bridge_runtime_parity" --basetemp .pytest_tmp_parity`
- pass_fail: PASS
- output_snippet:
```text
4 passed, 8 deselected in 3.10s
```

### CMD-26
- command: `rg -n "test_api_schema_contract_for_policy_semantics_response" tests/test_wave2_parity_contracts.py tests/test_admin_console.py`
- pass_fail: PASS
- output_snippet:
```text
tests/test_wave2_parity_contracts.py:71:def test_api_schema_contract_for_policy_semantics_response()
```

### CMD-27
- command: `Get-Content IMPLEMENTATION_CLOSURE_MATRIX.md; Get-Content VERIFICATION_MANIFEST.json; Get-Content QUALITY_GATES_REPORT.json`
- pass_fail: PASS
- output_snippet:
```text
Closure artifacts loaded for strict verification.
```

### CMD-28
- command: `Get-Content UNRESOLVED_GAPS.md; Get-Content VALIDATION_OUTPUTS.md; Get-Content tests/test_wave2_parity_contracts.py`
- pass_fail: PASS
- output_snippet:
```text
Artifact + test files loaded.
```

### CMD-29
- command: `Get-Content Frontend/src/components/PolicySemanticsPanel.test.tsx`
- pass_fail: PASS
- output_snippet:
```text
it("frontend rendering test for assessment_mode / assurance_level / compliance_position", ...)
it("test_ui_displays_legal_confirmation_required_and_residual_uncertainty", ...)
```

### CMD-30
- command: `Get-ChildItem tests/negative | Select-Object Name`
- pass_fail: PASS
- output_snippet:
```text
15 negative fixtures present, including review_state_incomplete and signature_verification_failure.
```

### CMD-31
- command: `python - <<'PY' ...` (hash command with Unix heredoc in PowerShell)
- pass_fail: FAIL
- output_snippet:
```text
ParserError: Missing file specification after redirection operator.
```
- action_taken: reran with PowerShell here-string piped to python.

### CMD-32
- command: `@' ... '@ | python -` (file hash computation)
- pass_fail: PASS
- output_snippet:
```text
app.py 2EC72EA2...
backend-ui-bridge/server.js 59A25A3F...
Frontend/src/api.ts EC611BDA...
...
```

### CMD-33
- command: `git rev-parse --short HEAD`
- pass_fail: PASS
- output_snippet:
```text
28ca865
```

### CMD-34
- command: `python -m pytest -q --basetemp .pytest_tmp`
- pass_fail: PASS
- output_snippet:
```text
collected 89 items
89 passed in 15.99s
```

### CMD-35
- command: `node --check backend-ui-bridge/server.js`
- pass_fail: PASS
- output_snippet:
```text
(no output)
```

### CMD-36
- command: `npm --prefix Frontend run test -- --run`
- pass_fail: PASS
- output_snippet:
```text
1 passed test file, 2 passed tests
```

### CMD-37
- command: `npm --prefix Frontend run build`
- pass_fail: PASS
- output_snippet:
```text
tsc --noEmit && vite build
✓ built in 4.20s
```

### CMD-38
- command: `python scripts_e2e_runtime_smoke.py`
- pass_fail: PASS
- output_snippet:
```text
E2E runtime smoke PASSED
```

### CMD-39
- command: `python scripts_e2e_assurance_validation.py`
- pass_fail: PASS
- output_snippet:
```text
chatgpt_run: PASS (19/19)
copilot_run: PASS (19/19)
dashboard_validation: PASS (6/6)
OVERALL: PASS
```

### CMD-40
- command: `python scripts_production_readiness_check.py`
- pass_fail: PASS
- output_snippet:
```text
Production readiness check PASSED
```

### CMD-41
- command: `$id=(Get-Content e2e_assurance_validation_export.json | ConvertFrom-Json).copilot_run.execution_id; node scripts/verify_decision_pack.js artifacts/$id contracts/keys/public_keys.json`
- pass_fail: PASS
- output_snippet:
```text
USING_EXECUTION_ID=11ee6d88-a473-5dc8-acd6-cb817ef4742d
"overall": "PASS"
"signature_ok": true
```

## Commands Not Run / Could Not Run

- none for mandatory verification list.

## Files Not Found

- none for required files/paths in this run.

## Branch / Scope / Path Ambiguity

- none in local repository context.


### CMD-42
- command: `git rev-parse --short HEAD`
- pass_fail: PASS
- output_snippet:
```text
28ca865
```

### CMD-43
- command: `rg -n "Commit:|\\"commit\\"" IMPLEMENTATION_CLOSURE_MATRIX.md CONTRADICTION_REPORT.md QUALITY_GATES_REPORT.json VERIFICATION_MANIFEST.json VALIDATION_OUTPUTS.md`
- pass_fail: PASS
- output_snippet:
```text
(no matches)
```
