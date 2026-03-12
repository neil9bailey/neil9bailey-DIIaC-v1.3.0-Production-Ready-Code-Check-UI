import os
import base64
import json
import shutil
from pathlib import Path

from app import create_app
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey


def client(strict: bool = False, app_env: str = 'development', admin_api_token: str = 'test-admin-token'):
    if strict:
        os.environ['STRICT_DETERMINISTIC_MODE'] = 'true'
    else:
        os.environ.pop('STRICT_DETERMINISTIC_MODE', None)

    os.environ['APP_ENV'] = app_env
    os.environ['ADMIN_API_TOKEN'] = admin_api_token
    os.environ['ADMIN_AUTH_ENABLED'] = 'true'
    os.environ['DIIAC_STATE_DB'] = ':memory:'

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
    assert c.get('/api/business-profiles').get_json()['profiles_count'] == 5
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


def test_replay_verification_certificate_for_deterministic_execution():
    c = client(strict=True)
    ctx = 'ctx-replay'
    submit_role(c, ctx, 'cto')
    compile_json = governed_compile(c, ctx).get_json()

    replay = c.post('/verify/replay', json={
        'execution_context_id': ctx,
        'profile_id': 'transport_profile_v1',
        'schema_id': 'GENERAL_SOLUTION_BOARD_REPORT_V1',
        'reasoning_level': 'R4',
        'policy_level': 'P4',
    })
    assert replay.status_code == 200
    replay_json = replay.get_json()
    assert replay_json['replay_valid'] is True
    assert replay_json['expected_execution_id'] == compile_json['execution_id']
    assert replay_json['pack_hash'] == compile_json['pack_hash']
    assert replay_json['certificate_path'].endswith('replay_certificate.json')


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
    audit_json = audit.get_json()
    audit_id = audit_json['audit_export_id']
    assert audit_json.get('storage_path', '').endswith(f"{audit_id}.json")
    assert audit_json.get('storage_path_relative', '').endswith(f"{audit_id}.json")
    dl = c.get(f'/admin/audit/exports/{audit_id}/download')
    assert dl.status_code == 200
    assert dl.data

    listing = c.get('/admin/audit/exports')
    assert listing.status_code == 200
    listing_json = listing.get_json()
    assert listing_json['count'] >= 1
    match = next((item for item in listing_json['exports'] if item['audit_export_id'] == audit_id), None)
    assert match is not None
    assert match['exists'] is True
    assert match['size_bytes'] > 0
    assert match.get('storage_path_relative', '').endswith(f"{audit_id}.json")

    verify_exec = c.get(f'/verify/execution/{execution_id}').get_json()
    verify_pack = c.post('/verify/pack', json={
        'execution_id': execution_id,
        'pack_hash': verify_exec['pack_hash'],
        'manifest_hash': verify_exec['manifest_hash'],
    }).get_json()
    assert verify_pack['overall_valid'] is True


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


def test_vendor_names_from_intent_are_preserved_in_scoring_and_report():
    c = client(strict=True)
    ctx = 'ctx-vendor-names'
    c.post('/api/human-input/role', json={
        'execution_context_id': ctx,
        'role': 'enterprise_architect',
        'domain': 'network-transformation, Secure-Edge, ZTNA',
        'assertions': ['Assess two leading vendors, Palo-Alto Networks and Fortinet, for SD-WAN and hybrid WAN.'],
        'non_negotiables': ['security', 'regulatory'],
        'risk_flags': ['vendor-lockin'],
        'evidence_refs': ['ea-evidence-1'],
    })

    compile_res = c.post('/api/governed-compile', json={
        'execution_context_id': ctx,
        'profile_id': 'it_enterprise_profile_v1',
        'schema_id': 'GENERAL_SOLUTION_BOARD_REPORT_V1',
        'reasoning_level': 'R4',
        'policy_level': 'P3',
        'governance_modes': ["CONSTRAINTS-FIRST MODE"],
    })
    assert compile_res.status_code == 201
    compile_json = compile_res.get_json()
    assert compile_json['decision_summary']['decision_status'] in {
        'recommended',
        'needs_more_evidence',
        'not_recommended',
    }

    all_execs = c.get('/admin/executions').get_json()['executions']
    execution = [
        e for e in all_execs
        if e['execution_id'] == compile_json['execution_id']
    ][0]
    ranked = execution['board_report']['ranked_options']
    ranked_names = {r['vendor'] for r in ranked}
    assert 'Palo Alto Networks' in ranked_names
    assert 'Fortinet' in ranked_names


def test_runtime_reconciles_public_key_registry_entry(monkeypatch, tmp_path):
    source_contracts = Path(__file__).resolve().parents[1] / "contracts"
    target_contracts = tmp_path / "contracts"
    shutil.copytree(source_contracts, target_contracts)

    # Seed the key registry with a stale key for the active key_id.
    stale_private = Ed25519PrivateKey.generate()
    stale_public_b64 = base64.b64encode(
        stale_private.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
    ).decode("utf-8")
    key_registry_path = target_contracts / "keys" / "public_keys.json"
    key_registry_path.write_text(
        json.dumps(
            {
                "keys": [
                    {
                        "key_id": "diiac-vendorlogic-prod",
                        "algorithm": "Ed25519",
                        "public_key_b64": stale_public_b64,
                    }
                ]
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    # Configure runtime with a different active private key.
    active_private = Ed25519PrivateKey.generate()
    active_private_pem = active_private.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")
    expected_public_b64 = base64.b64encode(
        active_private.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
    ).decode("utf-8")

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("ADMIN_AUTH_ENABLED", "false")
    monkeypatch.setenv("DIIAC_STATE_DB", ":memory:")
    monkeypatch.setenv("SIGNING_KEY_ID", "diiac-vendorlogic-prod")
    monkeypatch.setenv("SIGNING_PRIVATE_KEY_PEM", active_private_pem)

    app = create_app()
    app.testing = True

    reconciled = json.loads(key_registry_path.read_text(encoding="utf-8"))
    active_entry = next((k for k in reconciled.get("keys", []) if k.get("key_id") == "diiac-vendorlogic-prod"), None)
    assert active_entry is not None
    assert active_entry.get("algorithm") == "Ed25519"
    assert active_entry.get("public_key_b64") == expected_public_b64


def test_llm_audit_timestamp_override_prevents_stale_freshness_failure():
    c = client(strict=True)
    ctx = 'ctx-llm-freshness-override'
    role_input = c.post('/api/human-input/role', json={
        'execution_context_id': ctx,
        'role': 'cto',
        'domain': 'network-transformation',
        'assertions': ['Evaluate Fortinet and Palo Alto Networks for SD-WAN.'],
        'non_negotiables': ['privacy-by-design'],
        'risk_flags': ['vendor-lockin'],
        'evidence_refs': [
            'https://example.com/reference-1.pdf',
            'https://example.com/reference-2.pdf',
        ],
    })
    assert role_input.status_code == 201

    compile_res = c.post('/api/governed-compile', json={
        'execution_context_id': ctx,
        'profile_id': 'it_enterprise_profile_v1',
        'schema_id': 'GENERAL_SOLUTION_BOARD_REPORT_V1',
        'reasoning_level': 'R4',
        'policy_level': 'P4',
        'llm_provider': 'Copilot',
        'llm_audit_timestamp': '2026-03-10T00:00:00+00:00',
        'llm_analysis': {
            'executive_summary': {'summary': 'Deterministic freshness override test.'},
            'vendor_scoring': {
                'options': [
                    {'vendor': 'Fortinet', 'focus': 'Cost and resilience'},
                    {'vendor': 'Palo Alto Networks', 'focus': 'Security and operations'},
                ],
            },
            'board_recommendation': {'recommendation': 'Evaluate Fortinet and Palo Alto Networks.'},
            'audit_trail': {'timestamp': '2023-10-01T00:00:00Z'},
        },
    })
    assert compile_res.status_code == 201
    compile_json = compile_res.get_json()
    summary = compile_json['decision_summary']
    failures = summary.get('quality_gate_failures') or []
    assert all('llm evidence freshness requirement failed' not in issue for issue in failures)
    assert 'policy_pack_control_failed:EU-AIA-ART15-ACCURACY-ROBUSTNESS' not in (summary.get('control_failure_reasons') or [])

    executions = c.get('/admin/executions').get_json()['executions']
    execution = [e for e in executions if e['execution_id'] == compile_json['execution_id']][0]
    recommendation = execution['board_report']['major_recommendations'][0]
    evidence_quality = recommendation['evidence_quality']
    assert evidence_quality['llm_freshness'] == 'CURRENT'
    assert evidence_quality['llm_audit_timestamp_source'] == 'payload.llm_audit_timestamp'
    assert evidence_quality['llm_provider_reported_timestamp'] == '2023-10-01T00:00:00Z'


def test_health_and_admin_health_include_readiness_checks():
    c = client(strict=True)
    health = c.get('/health')
    assert health.status_code == 200
    health_json = health.get_json()
    assert health_json['status'] in {'OK', 'DEGRADED'}
    assert 'readiness' in health_json
    assert 'checks' in health_json['readiness']

    admin_health = c.get('/admin/health')
    assert admin_health.status_code == 200
    admin_json = admin_health.get_json()
    assert admin_json['status'] in {'OK', 'DEGRADED'}
    assert 'readiness' in admin_json
    checks = admin_json['readiness']['checks']
    assert checks['contracts_profiles'] is True
    assert checks['contracts_keys'] is True


def test_governed_compile_runtime_dependency_failure_taxonomy(monkeypatch):
    c = client(strict=True)

    import app as app_module

    def raise_os_error(*_args, **_kwargs):
        raise OSError('disk unavailable')

    monkeypatch.setattr(app_module.Path, 'write_text', raise_os_error)

    payload = {
        'execution_context_id': 'ctx-runtime-failure',
        'profile_id': 'transport_profile_v1',
        'schema_id': 'GENERAL_SOLUTION_BOARD_REPORT_V1',
        'reasoning_level': 'R4',
        'policy_level': 'P4',
    }

    response = c.post('/api/governed-compile', json=payload)

    assert response.status_code == 503
    result = response.get_json()
    assert result['error'] == 'runtime_dependency_failure'
    assert result['error_code'] == 'ARTIFACT_STORAGE_UNAVAILABLE'
    assert result['dependency'] == 'artifact_storage'

    alias_response = c.post('/api/compile', json=payload)
    assert alias_response.status_code == 503
    alias_result = alias_response.get_json()
    assert alias_result['error'] == 'runtime_dependency_failure'
    assert alias_result['error_code'] == 'ARTIFACT_STORAGE_UNAVAILABLE'


def test_admin_auth_enforced_in_production_deny_allow_matrix():
    token = 'prod-admin-secret'
    c = client(strict=True, app_env='production', admin_api_token=token)

    denied = c.get('/admin/health')
    assert denied.status_code == 401
    assert denied.get_json()['error'] == 'admin_auth_required'

    allowed = c.get('/admin/health', headers={'Authorization': f'Bearer {token}'})
    assert allowed.status_code == 200

    # non-admin endpoint remains available
    public_health = c.get('/health')
    assert public_health.status_code == 200


def test_admin_auth_not_required_in_development():
    c = client(strict=True, app_env='development', admin_api_token='dev-token')
    response = c.get('/admin/health')
    assert response.status_code == 200


def test_role_input_rejects_oversized_and_invalid_list_items():
    c = client(strict=True, app_env='development')
    payload = {
        'execution_context_id': 'ctx-bounds',
        'role': 'cto',
        'domain': 'network',
        'assertions': ['ok', ''],
        'non_negotiables': ['n1'],
        'risk_flags': ['r1'],
        'evidence_refs': ['e1'],
    }
    res = c.post('/api/human-input/role', json=payload)
    assert res.status_code == 400


def test_write_endpoints_enforce_payload_bounds():
    c = client(strict=True, app_env='development')

    text_res = c.post('/api/human-input', json={'text': 'x' * 9001})
    assert text_res.status_code == 400
    assert text_res.get_json()['error'] == 'field_too_long'

    verify_res = c.post('/verify/pack', json={'execution_id': 'x', 'pack_hash': ''})
    assert verify_res.status_code == 400

    proof_res = c.post('/verify/merkle-proof', json={'leaf_hash': 'a'*64, 'siblings': 'bad', 'index': 0, 'merkle_root': 'b'*64})
    assert proof_res.status_code == 400

    replay_res = c.post('/verify/replay', json={'execution_context_id': 'ctx-only'})
    assert replay_res.status_code == 400

    audit_res = c.post('/admin/audit-export', json={'execution_ids': 'not-a-list'})
    assert audit_res.status_code == 400


def test_signed_export_runtime_dependency_error_taxonomy(monkeypatch):
    c = client(strict=True, app_env='development')
    ctx = 'ctx-export-failure'
    submit_role(c, ctx, 'cto')
    execution_id = governed_compile(c, ctx).get_json()['execution_id']

    import app as app_module

    def raise_os_error(*_args, **_kwargs):
        raise OSError('export path unavailable')

    monkeypatch.setattr(app_module.Path, 'write_text', raise_os_error)

    response = c.get(f'/decision-pack/{execution_id}/export-signed')
    assert response.status_code == 503
    payload = response.get_json()
    assert payload['error'] == 'runtime_dependency_failure'
    assert payload['error_code'] == 'EXPORT_STORAGE_UNAVAILABLE'


def test_verify_pack_signature_metadata_unavailable_returns_runtime_error(monkeypatch):
    c = client(strict=True, app_env='development')
    ctx = 'ctx-verify-failure'
    submit_role(c, ctx, 'cto')
    execution_id = governed_compile(c, ctx).get_json()['execution_id']

    import app as app_module

    def raise_os_error(*_args, **_kwargs):
        raise OSError('cannot read signature metadata')

    monkeypatch.setattr(app_module.Path, 'read_text', raise_os_error)

    response = c.post('/verify/pack', json={'execution_id': execution_id, 'pack_hash': 'deadbeef'})
    assert response.status_code == 503
    payload = response.get_json()
    assert payload['error'] == 'runtime_dependency_failure'
    assert payload['error_code'] == 'SIGNATURE_METADATA_UNAVAILABLE'


def test_audit_export_runtime_dependency_error_taxonomy(monkeypatch):
    c = client(strict=True, app_env='development')
    ctx = 'ctx-audit-failure'
    submit_role(c, ctx, 'cto')
    execution_id = governed_compile(c, ctx).get_json()['execution_id']

    import app as app_module

    def raise_os_error(*_args, **_kwargs):
        raise OSError('audit path unavailable')

    monkeypatch.setattr(app_module.Path, 'write_text', raise_os_error)

    response = c.post('/admin/audit-export', json={'execution_ids': [execution_id]})
    assert response.status_code == 503
    payload = response.get_json()
    assert payload['error'] == 'runtime_dependency_failure'
    assert payload['error_code'] == 'AUDIT_STORAGE_UNAVAILABLE'


def test_verify_pack_detects_hash_and_manifest_tampering():
    c = client(strict=True, app_env='development')
    ctx = 'ctx-pack-tamper'
    submit_role(c, ctx, 'cto')
    execution_id = governed_compile(c, ctx).get_json()['execution_id']

    verify_exec = c.get(f'/verify/execution/{execution_id}').get_json()

    wrong_pack = c.post('/verify/pack', json={
        'execution_id': execution_id,
        'pack_hash': '0' * 64,
        'manifest_hash': verify_exec['manifest_hash'],
    }).get_json()
    assert wrong_pack['hash_valid'] is False
    assert wrong_pack['overall_valid'] is False

    wrong_manifest = c.post('/verify/pack', json={
        'execution_id': execution_id,
        'pack_hash': verify_exec['pack_hash'],
        'manifest_hash': 'f' * 64,
    }).get_json()
    assert wrong_manifest['manifest_consistent'] is False
    assert wrong_manifest['overall_valid'] is False


def test_verify_merkle_proof_detects_tampered_payload():
    c = client(strict=True, app_env='development')
    ctx = 'ctx-merkle-tamper'
    submit_role(c, ctx, 'cto')
    execution_id = governed_compile(c, ctx).get_json()['execution_id']

    proof = c.get(f'/executions/{execution_id}/merkle/proof/board_report.json').get_json()
    assert c.post('/verify/merkle-proof', json=proof).get_json()['proof_valid'] is True

    tampered = dict(proof)
    tampered['siblings'] = list(proof['siblings'])
    if tampered['siblings']:
        tampered['siblings'][0] = '0' * 64
    else:
        tampered['siblings'] = ['0' * 64]
    assert c.post('/verify/merkle-proof', json=tampered).get_json()['proof_valid'] is False


def test_admin_route_auth_matrix_for_sensitive_endpoints():
    token = 'prod-admin-token-matrix'
    c = client(strict=True, app_env='production', admin_api_token=token)

    ctx = 'ctx-admin-matrix'
    assert submit_role(c, ctx, 'cto').status_code == 201
    execution_id = governed_compile(c, ctx).get_json()['execution_id']

    protected = [
        '/admin/health',
        '/admin/config',
        '/admin/executions',
        '/admin/logs',
        '/admin/logs/backend',
        '/admin/logs/ledger',
        '/admin/metrics',
        f'/admin/executions/{execution_id}/logs',
    ]

    for path in protected:
        denied = c.get(path)
        assert denied.status_code == 401

        allowed = c.get(path, headers={'Authorization': f'Bearer {token}'})
        assert allowed.status_code == 200


def test_structured_logs_include_stable_event_ids_and_metrics_thresholds():
    c = client(strict=True, app_env='development')

    c.post('/api/human-input', json={'text': 'hello metrics and logs'})
    logs = c.get('/admin/logs/backend').get_json()['logs']
    assert logs
    assert 'event_id' in logs[-1]
    assert logs[-1]['event_id'].startswith('EVT-')

    metrics = c.get('/admin/metrics').get_json()
    assert 'threshold_recommendations' in metrics
    assert 'signed_recent_executions_min' in metrics['threshold_recommendations']
    assert isinstance(metrics['alerts'], list)
