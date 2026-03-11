import base64
import hashlib
import hmac
import json
import os
import time
from pathlib import Path

from app import create_app


def client(strict: bool = False):
    if strict:
        os.environ['STRICT_DETERMINISTIC_MODE'] = 'true'
    else:
        os.environ.pop('STRICT_DETERMINISTIC_MODE', None)
    app = create_app()
    app.testing = True
    return app.test_client()


def _jwt_admin_token(secret: str, role: str = 'admin') -> str:
    header = {'alg': 'HS256', 'typ': 'JWT'}
    payload = {
        'iss': 'diiac',
        'aud': 'diiac-admin',
        'exp': int(time.time()) + 300,
        'role': role,
    }

    def b64url(data: bytes) -> str:
        return base64.urlsafe_b64encode(data).decode('utf-8').rstrip('=')

    header_b64 = b64url(json.dumps(header, separators=(',', ':')).encode('utf-8'))
    payload_b64 = b64url(json.dumps(payload, separators=(',', ':')).encode('utf-8'))
    signing_input = f'{header_b64}.{payload_b64}'.encode('utf-8')
    signature = hmac.new(secret.encode('utf-8'), signing_input, hashlib.sha256).digest()
    return f'{header_b64}.{payload_b64}.{b64url(signature)}'


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


def test_verify_merkle_proof_validation_errors():
    c = client(strict=True)
    bad_siblings = c.post('/verify/merkle-proof', json={'leaf_hash': 'abc', 'siblings': 'not-a-list', 'index': 0, 'merkle_root': 'root'})
    assert bad_siblings.status_code == 400
    assert bad_siblings.get_json()['error'] == 'invalid_siblings'

    bad_index = c.post('/verify/merkle-proof', json={'leaf_hash': 'abc', 'siblings': [], 'index': 'NaN', 'merkle_root': 'root'})
    assert bad_index.status_code == 400
    assert bad_index.get_json()['error'] == 'invalid_index'


def test_blueprint_compat_endpoints_operational():
    c = client(strict=True)
    ctx = 'ctx-blueprint-compat'
    submit_role(c, ctx, 'cto')

    governed = c.post('/govern/decision', json={
        'execution_context_id': ctx,
        'profile_id': 'transport_profile_v1',
        'schema_id': 'GENERAL_SOLUTION_BOARD_REPORT_V1',
        'reasoning_level': 'R4',
        'policy_level': 'P4',
    })
    assert governed.status_code == 201
    execution_id = governed.get_json()['execution_id']

    impact = c.post('/api/impact/policy', json={'policy_text': 'critical outage and safety impact'})
    assert impact.status_code == 200
    assert impact.get_json()['severity'] == 'HIGH'

    export = c.get(f'/decision-pack/{execution_id}/export')
    assert export.status_code == 200
    assert export.mimetype == 'application/zip'
    assert export.data


def test_supporting_specs_crypto_and_extensions_alignment():
    c = client(strict=True)
    ctx = 'ctx-spec-alignment'
    submit_role(c, ctx, 'cto')

    compile_json = governed_compile(c, ctx).get_json()
    execution_id = compile_json['execution_id']

    # Cryptographic spec: sha256 hex chain surfaces
    assert len(compile_json['pack_hash']) == 64
    assert all(ch in '0123456789abcdef' for ch in compile_json['pack_hash'])
    assert len(compile_json['manifest_hash']) == 64
    assert len(compile_json['merkle_root']) == 64

    merkle = c.get(f'/executions/{execution_id}/merkle').get_json()
    leaf_names = [leaf['name'] for leaf in merkle['leaves']]
    assert leaf_names == sorted(leaf_names)

    proof = c.get(f'/executions/{execution_id}/merkle/proof/board_report.json').get_json()
    assert c.post('/verify/merkle-proof', json=proof).get_json()['proof_valid'] is True

    verify_exec = c.get(f'/verify/execution/{execution_id}').get_json()
    assert verify_exec['ledger_match'] is True

    verify_pack = c.post('/verify/pack', json={
        'execution_id': execution_id,
        'pack_hash': compile_json['pack_hash'],
        'manifest_hash': compile_json['manifest_hash'],
    }).get_json()
    assert verify_pack['overall_valid'] is True

    pub_keys = c.get('/verify/public-keys').get_json()
    assert pub_keys['keys']

    signed_export = c.get(f'/decision-pack/{execution_id}/export-signed').get_json()
    assert signed_export['sigmeta']['signature_alg'] == 'Ed25519'

    assert c.get('/admin/health').status_code == 200
    assert c.get('/admin/logs').status_code == 200

    audit = c.post('/admin/audit-export', json={'execution_ids': [execution_id]})
    assert audit.status_code == 201


def test_admin_db_status_and_table_access():
    c = client(strict=True)
    ctx = 'ctx-db-admin'
    submit_role(c, ctx, 'cto')
    execution_id = governed_compile(c, ctx).get_json()['execution_id']

    status = c.get('/admin/db/status')
    assert status.status_code == 200
    tables = status.get_json()['tables']
    assert tables['executions'] >= 1
    assert tables['role_inputs'] >= 1

    rows = c.get('/admin/db/table/executions?limit=5')
    assert rows.status_code == 200
    assert any(r['execution_id'] == execution_id for r in rows.get_json()['rows'])

    compact = c.post('/admin/db/maintenance/compact')
    assert compact.status_code == 200






def test_data_root_override_controls_profile_loading(tmp_path, monkeypatch):
    profile_dir = tmp_path / 'contracts' / 'business-profiles'
    profile_dir.mkdir(parents=True)
    profile_dir.joinpath('custom_profile_v1.json').write_text((
        '{"profile_id":"custom_profile_v1","sector":"TEST","jurisdiction":"UK","risk_appetite":"LOW",'
        '"default_reasoning_level":"R4","default_policy_level":"P4",'
        '"allowed_schemas":["GENERAL_SOLUTION_BOARD_REPORT_V1"],'
        '"required_controls":["audit_trail"],'
        '"required_sections":["Executive Summary","Context","Risk Register","Success Metrics","Down-Select Recommendation"],'
        '"scoring_weights":{"security":0.4,"resilience":0.2,"interoperability":0.1,"operations":0.1,"commercial":0.2}}'
    ), encoding='utf-8')

    monkeypatch.setenv('DIIAC_DATA_ROOT', str(tmp_path))
    app = create_app()
    app.testing = True
    c = app.test_client()

    profiles = c.get('/api/business-profiles').get_json()
    assert profiles['profiles_count'] == 1
    assert profiles['profiles'][0]['profile_id'] == 'custom_profile_v1'


def test_governed_compile_accepts_ui_alias_payload_and_defaults_rp_levels():
    c = client(strict=True)
    ctx = 'ctx-ui-alias'
    submit_role(c, ctx, 'cto')

    res = c.post('/api/governed-compile', json={
        'execution_context_id': ctx,
        'schema': 'GENERAL_SOLUTION_BOARD_REPORT_V1',
        'business_profile': 'transport_profile_v1',
    })
    assert res.status_code == 201
    body = res.get_json()
    assert body['profile_id'] == 'transport_profile_v1'
    assert body['schema_id'] == 'GENERAL_SOLUTION_BOARD_REPORT_V1'

def test_compile_validation_and_execution_pagination():
    c = client(strict=True)
    invalid = c.post('/api/governed-compile', json={'execution_context_id': '', 'profile_id': 'transport_profile_v1', 'schema_id': 'GENERAL_SOLUTION_BOARD_REPORT_V1', 'reasoning_level': 'R4', 'policy_level': 'P4'})
    assert invalid.status_code == 400
    assert invalid.get_json()['error'] == 'invalid_field'
    assert invalid.get_json()['field'] == 'execution_context_id'

    ctx = 'ctx-page'
    submit_role(c, ctx, 'cto')
    governed_compile(c, ctx)

    page = c.get('/admin/executions?page=1&page_size=1&profile_id=transport_profile_v1')
    assert page.status_code == 200
    payload = page.get_json()
    assert payload['page_size'] == 1
    assert payload['total'] >= 1
    assert len(payload['executions']) == 1


def test_verify_replay_and_execution_diff_endpoint():
    c = client(strict=True)
    ctx = 'ctx-replay'
    submit_role(c, ctx, 'cto')
    run = governed_compile(c, ctx).get_json()

    replay = c.post('/verify/replay', json={
        'execution_context_id': ctx,
        'profile_id': 'transport_profile_v1',
        'schema_id': 'GENERAL_SOLUTION_BOARD_REPORT_V1',
        'reasoning_level': 'R4',
        'policy_level': 'P4',
    })
    assert replay.status_code == 200
    assert replay.get_json()['replay_valid'] is True
    assert replay.get_json()['expected_execution_id'] == run['execution_id']

    other_ctx = 'ctx-replay-other'
    submit_role(c, other_ctx, 'cto')
    other_run = c.post('/api/governed-compile', json={
        'execution_context_id': other_ctx,
        'profile_id': 'transport_profile_v1',
        'schema_id': 'GENERAL_SOLUTION_BOARD_REPORT_V1',
        'reasoning_level': 'R5',
        'policy_level': 'P4',
    }).get_json()

    diff = c.get(f"/executions/{run['execution_id']}/diff/{other_run['execution_id']}")
    assert diff.status_code == 200
    assert diff.get_json()['pack_hash_changed'] is True


def test_admin_auth_jwt_and_request_metrics_headers():
    os.environ['ENFORCE_ADMIN_AUTH'] = 'true'
    os.environ['ADMIN_API_KEY'] = 'fallback-key'
    os.environ['JWT_SECRET'] = 'super-secret'
    c = client(strict=True)

    denied = c.get('/admin/health')
    assert denied.status_code == 403

    token = _jwt_admin_token('super-secret')
    authorized = c.get('/admin/health', headers={'x-role': 'admin', 'Authorization': f'Bearer {token}'})
    assert authorized.status_code == 200
    assert authorized.headers.get('X-Request-ID')
    assert authorized.headers.get('X-Response-Time-Ms')

    metrics = c.get('/admin/metrics', headers={'x-role': 'admin', 'Authorization': f'Bearer {token}'})
    assert metrics.status_code == 200
    assert '/admin/health' in metrics.get_json()['routes']

    status = c.get('/admin/db/status', headers={'x-role': 'admin', 'Authorization': f'Bearer {token}'})
    assert status.status_code == 200
    assert 'integrity' in status.get_json()

    os.environ.pop('ENFORCE_ADMIN_AUTH', None)
    os.environ.pop('ADMIN_API_KEY', None)
    os.environ.pop('JWT_SECRET', None)
