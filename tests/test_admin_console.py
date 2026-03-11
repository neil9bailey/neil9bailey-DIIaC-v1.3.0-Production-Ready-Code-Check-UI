import os

from app import create_app


def client(strict: bool = False):
    if strict:
        os.environ['STRICT_DETERMINISTIC_MODE'] = 'true'
    else:
        os.environ.pop('STRICT_DETERMINISTIC_MODE', None)
    app = create_app()
    app.testing = True
    return app.test_client()


def submit_role(c, ctx, role='cto'):
    return c.post('/api/human-input/role', json={
        'execution_context_id': ctx,
        'role': role,
        'domain': 'network',
        'assertions': ['a1'],
        'non_negotiables': ['n1'],
        'risk_flags': ['r1'],
        'evidence_refs': [f'{role}-evidence-1'],
    })


def governed_compile(c, ctx):
    return c.post('/api/governed-compile', json={
        'execution_context_id': ctx,
        'profile_id': 'transport_profile_v1',
        'schema_id': 'GENERAL_SOLUTION_BOARD_REPORT_V1',
        'reasoning_level': 'R4',
        'policy_level': 'P4',
    })


def test_core_capabilities_matrix_endpoints_operational():
    c = client(strict=True)
    assert c.get('/api/business-profiles').get_json()['profiles_count'] == 8
    ctx = 'ctx-cap-matrix'
    assert submit_role(c, ctx, 'cto').status_code == 201
    compile_res = governed_compile(c, ctx)
    assert compile_res.status_code == 201
    execution_id = compile_res.get_json()['execution_id']

    verify_exec = c.get(f'/verify/execution/{execution_id}').get_json()
    assert verify_exec['status'] == 'VERIFIABLE'
    assert verify_exec['signature_present'] is True
    assert verify_exec['pack_hash']
    assert verify_exec['manifest_hash']

    assert c.get('/verify/public-keys').status_code == 200


def test_deterministic_same_inputs_same_scores_and_structured_sections():
    c = client(strict=True)
    ctx = 'ctx-deterministic'
    submit_role(c, ctx, 'cto')
    submit_role(c, ctx, 'cso')

    first = governed_compile(c, ctx).get_json()
    second = governed_compile(c, ctx).get_json()
    assert first['execution_id'] == second['execution_id']
    assert first['pack_hash'] == second['pack_hash']

    scoring_a = c.get(f"/executions/{first['execution_id']}/scoring").get_json()
    scoring_b = c.get(f"/executions/{second['execution_id']}/scoring").get_json()
    assert scoring_a['scoring']['rows'] == scoring_b['scoring']['rows']

    execution = c.get('/admin/executions').get_json()['executions'][0]
    sections = [s['title'] for s in execution['board_report']['sections']]
    assert sections == ['Executive Summary', 'Context', 'Risk Register', 'Success Metrics', 'Down-Select Recommendation']


def test_evidence_trace_linking_and_required_artifacts_present():
    c = client(strict=True)
    ctx = 'ctx-evidence'
    submit_role(c, ctx, 'ea')
    compile_json = governed_compile(c, ctx).get_json()
    execution_id = compile_json['execution_id']

    trace = c.get(f'/executions/{execution_id}/trace-map').get_json()
    claim_ids = {e['claim_id'] for e in trace['entries']}
    scoring = c.get(f'/executions/{execution_id}/scoring').get_json()
    assert set(scoring['recommendation']['claim_ids']).issubset(claim_ids)

    execution = [e for e in c.get('/admin/executions').get_json()['executions'] if e['execution_id'] == execution_id][0]
    required = {
        'board_report.json', 'deterministic_compilation_log.json', 'evidence_trace_map.json',
        'governance_manifest.json', 'role_input_bundle.json', 'schema_contract.json',
        'vendor_scoring_matrix.json', 'business_profile_snapshot.json',
        'profile_compliance_matrix.json', 'profile_override_log.json',
        'down_select_recommendation.json', 'signed_export.sigmeta.json', 'signed_export.sig',
    }
    assert required.issubset(set(execution['artifacts']))


def test_merkle_binding_and_proof_verification_and_signed_export():
    c = client(strict=True)
    ctx = 'ctx-merkle'
    submit_role(c, ctx, 'principal_engineer')
    compile_json = governed_compile(c, ctx).get_json()
    execution_id = compile_json['execution_id']

    merkle = c.get(f'/executions/{execution_id}/merkle').get_json()
    assert merkle['algorithm'] == 'sha256'
    assert merkle['merkle_root'] == compile_json['merkle_root']

    proof = c.get(f'/executions/{execution_id}/merkle/proof/board_report.json').get_json()
    verify = c.post('/verify/merkle-proof', json=proof).get_json()
    assert verify['proof_valid'] is True

    exported = c.get(f'/decision-pack/{execution_id}/export-signed').get_json()
    assert exported['sigmeta']['signature_alg'] == 'Ed25519'
    assert exported['sigmeta']['execution_id'] == execution_id


def test_trust_ledger_growth_admin_logs_and_audit_export_operational():
    c = client(strict=True)
    before = c.get('/trust/status').get_json()['ledger_records']
    ctx = 'ctx-ledger'
    submit_role(c, ctx, 'cio')
    execution_id = governed_compile(c, ctx).get_json()['execution_id']
    after = c.get('/trust/status').get_json()['ledger_records']
    assert after > before

    assert c.get('/admin/logs?source=backend').status_code == 200
    assert c.get(f'/admin/executions/{execution_id}/logs').status_code == 200

    audit = c.post('/admin/audit-export', json={'execution_ids': [execution_id]})
    assert audit.status_code == 201
    audit_id = audit.get_json()['audit_export_id']
    dl = c.get(f'/admin/audit/exports/{audit_id}/download')
    assert dl.status_code == 200
    assert dl.data

    verify_exec = c.get(f'/verify/execution/{execution_id}').get_json()
    verify_pack = c.post('/verify/pack', json={'execution_id': execution_id, 'pack_hash': verify_exec['pack_hash'], 'manifest_hash': verify_exec['manifest_hash']}).get_json()
    assert verify_pack['overall_valid'] is True

    verify_pack_default = c.post('/verify/pack', json={'execution_id': execution_id}).get_json()
    assert verify_pack_default['overall_valid'] is True


def test_report_alias_endpoints_and_compile_state_fields():
    c = client(strict=True)
    assert c.get('/trust').status_code == 200
    human = c.post('/api/human-input', json={'text': 'hello world'})
    assert human.status_code == 201

    ctx = 'ctx-aliases'
    submit_role(c, ctx, 'cto')
    comp = governed_compile(c, ctx)
    assert comp.status_code == 201
    payload = comp.get_json()
    assert payload['execution_state']['signature_present'] is True
    assert payload['execution_state']['signing_enabled'] is True

    execution_id = payload['execution_id']
    reports = c.get(f'/executions/{execution_id}/reports')
    assert reports.status_code == 200
    assert reports.get_json()['reports']

    audit = c.post('/admin/audit-export', json={'execution_ids': [execution_id]}).get_json()
    dl = c.get(f"/admin/audit-export/{audit['audit_export_id']}/download")
    assert dl.status_code == 200
