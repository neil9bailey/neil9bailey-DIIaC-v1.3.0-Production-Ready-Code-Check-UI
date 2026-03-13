import os
import base64
import json
import shutil
import socket
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest
from app import create_app
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

TEST_SIGNING_PRIVATE_KEY_PEM = (
    "-----BEGIN PRIVATE KEY-----\n"
    "MC4CAQAwBQYDK2VwBCIEIBdMTAGU2mmT3F30y1oCkr4csd7XaiSU95TnmT87RDUH\n"
    "-----END PRIVATE KEY-----\n"
)


def client(strict: bool = False, app_env: str = 'development', admin_api_token: str = 'test-admin-token'):
    if strict:
        os.environ['STRICT_DETERMINISTIC_MODE'] = 'true'
    else:
        os.environ.pop('STRICT_DETERMINISTIC_MODE', None)

    os.environ['APP_ENV'] = app_env
    os.environ['ADMIN_API_TOKEN'] = admin_api_token
    os.environ['ADMIN_AUTH_ENABLED'] = 'true'
    os.environ['DIIAC_STATE_DB'] = ':memory:'
    if app_env.lower() in {'prod', 'production', 'stage', 'staging', 'uat'}:
        os.environ['SIGNING_ENABLED'] = 'false'
        os.environ.pop('SIGNING_PRIVATE_KEY_PEM', None)
    else:
        os.environ['SIGNING_ENABLED'] = 'true'
        os.environ['SIGNING_KEY_ID'] = 'ephemeral-local-ed25519'
        os.environ['SIGNING_PRIVATE_KEY_PEM'] = TEST_SIGNING_PRIVATE_KEY_PEM

    app = create_app()
    app.testing = True
    return app.test_client()


def submit_role(c, ctx, role='cto'):
    return c.post('/api/human-input/role', json={
        'execution_context_id': ctx,
        'role': role,
        'domain': 'network',
        'assertions': [
            'Deliver >=15% cycle-time reduction within 6 months with <=1% Sev1 increase.'
        ],
        'non_negotiables': ['Budget cap GBP 1.8M/year'],
        'risk_flags': ['r1'],
        'evidence_refs': [
            'https://www.fortinet.com/products/secure-sd-wan',
            'urn:independent:analyst-report:2026q1',
        ],
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
    expected_profile_count = len(list((Path(__file__).resolve().parents[1] / "contracts" / "business-profiles").glob("*_profile_v1.json")))
    assert c.get('/api/business-profiles').get_json()['profiles_count'] == expected_profile_count
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
    assert sections == [
        'Executive Summary',
        'Context',
        'Objectives',
        'Recommendation',
        'Assumptions',
        'Disqualifiers',
        'Residual Risks',
        'Measurable KPIs',
        'Regulatory Constraints',
        'Implementation Guardrails',
        'What Would Change The Recommendation',
        'Risk Register',
    ]


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
        'replay_provenance': {
            'source': 'test-suite',
            'captured_at': '2026-03-01T00:00:00Z',
            'evidence_ids': ['evidence-manual-1'],
        },
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
        'assertions': [
            'Must use Fortinet for primary SD-WAN recommendation with >=15% cycle-time reduction in <=6 months.',
            'Assess Palo-Alto Networks as a controlled alternative option.',
        ],
        'non_negotiables': ['Budget cap GBP 1.8M/year'],
        'risk_flags': ['vendor-lockin'],
        'evidence_refs': [
            'urn:independent:analyst-report:2026q1',
            'https://www.fortinet.com/products/secure-sd-wan',
        ],
    })

    compile_res = c.post('/api/governed-compile', json={
        'execution_context_id': ctx,
        'profile_id': 'it_enterprise_profile_v1',
        'schema_id': 'GENERAL_SOLUTION_BOARD_REPORT_V1',
        'reasoning_level': 'R4',
        'policy_level': 'P3',
        'success_metrics': _valid_success_metrics(),
        'governance_modes': ["CONSTRAINTS-FIRST MODE"],
    })
    if compile_res.status_code == 201:
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
    else:
        assert compile_res.status_code == 422
        payload = compile_res.get_json()
        codes = {item.get('code') for item in payload.get('hard_gate_failures', []) if isinstance(item, dict)}
        assert 'VENDOR_EVIDENCE_MISMATCH' in codes
        selected_vendor_values = {
            item.get('details', {}).get('selected_vendor')
            for item in payload.get('hard_gate_failures', [])
            if isinstance(item, dict) and isinstance(item.get('details'), dict)
        }
        assert selected_vendor_values.intersection({'Palo Alto Networks', 'Fortinet'})


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
    monkeypatch.setenv("TRUST_REGISTRY_DEV_AUTOREGISTER", "true")

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
        'assertions': ['Evaluate Fortinet and Palo Alto Networks for SD-WAN with >=12% cycle-time reduction in 6 months.'],
        'non_negotiables': ['Budget cap GBP 1.8M/year'],
        'risk_flags': ['vendor-lockin'],
        'evidence_refs': [
            'https://www.fortinet.com/products/secure-sd-wan',
            'https://www.paloaltonetworks.com/sase/prisma-sd-wan',
            'urn:independent:analyst-report:2026q1',
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


def test_admin_config_contract_exposes_dynamic_contract_hashes():
    c = client(strict=True)
    response = c.get('/admin/config/contract')
    assert response.status_code == 200
    payload = response.get_json()
    assert payload['profiles']['count'] == len(
        list((Path(__file__).resolve().parents[1] / "contracts" / "business-profiles").glob("*_profile_v1.json"))
    )
    assert payload['policy_packs']['count'] == len(
        list((Path(__file__).resolve().parents[1] / "contracts" / "policy-packs").glob("*_v1.json"))
    )
    assert isinstance(payload['contract_hash'], str) and len(payload['contract_hash']) == 64


def test_governed_compile_runtime_dependency_failure_taxonomy(monkeypatch):
    c = client(strict=True)

    import app as app_module

    def raise_os_error(*_args, **_kwargs):
        raise OSError('disk unavailable')

    monkeypatch.setattr(app_module.Path, 'write_bytes', raise_os_error)

    payload = {
        'execution_context_id': 'ctx-runtime-failure',
        'profile_id': 'transport_profile_v1',
        'schema_id': 'GENERAL_SOLUTION_BOARD_REPORT_V1',
        'reasoning_level': 'R4',
        'policy_level': 'P4',
        'role': 'cto',
        'domain': 'network',
        'assertions': ['Deliver >=15% cycle-time reduction within 6 months.'],
        'non_negotiables': ['Budget cap GBP 1.8M/year'],
        'risk_flags': ['vendor-lockin'],
        'evidence_refs': [
            'https://www.fortinet.com/products/secure-sd-wan',
            'urn:independent:analyst-report:2026q1',
        ],
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


def test_compile_hard_gate_rejects_unresolved_evidence_and_non_measurable_metrics():
    c = client(strict=True, app_env='development')
    ctx = 'ctx-hard-gate-unresolved'
    role_input = c.post('/api/human-input/role', json={
        'execution_context_id': ctx,
        'role': 'cto',
        'domain': 'network',
        'assertions': ['Improve governance outcomes.'],
        'non_negotiables': ['privacy-by-design'],
        'risk_flags': ['vendor-lockin'],
        'evidence_refs': ['token-evidence-1'],
    })
    assert role_input.status_code == 201

    compile_res = c.post('/api/governed-compile', json={
        'execution_context_id': ctx,
        'profile_id': 'it_enterprise_profile_v1',
        'schema_id': 'GENERAL_SOLUTION_BOARD_REPORT_V1',
        'reasoning_level': 'R4',
        'policy_level': 'P4',
    })
    assert compile_res.status_code == 422
    payload = compile_res.get_json()
    codes = {item['code'] for item in payload.get('hard_gate_failures', [])}
    assert 'UNRESOLVED_EVIDENCE' in codes
    assert 'INVALID_SUCCESS_METRICS' in codes


def test_inline_payload_preserves_intent_without_default_overwrite():
    c = client(strict=True, app_env='development')
    compile_res = c.post('/api/governed-compile', json={
        'execution_context_id': 'ctx-inline-intent',
        'profile_id': 'it_enterprise_profile_v1',
        'schema_id': 'GENERAL_SOLUTION_BOARD_REPORT_V1',
        'reasoning_level': 'R4',
        'policy_level': 'P4',
        'role': 'cto',
        'domain': 'network',
        'assertions': ['Deliver >=12% cycle-time reduction in <=6 months.'],
        'non_negotiables': ['budget-cap-1'],
        'risk_flags': ['vendor-lockin'],
        'evidence_refs': [
            'https://www.fortinet.com/products/secure-sd-wan',
            'urn:independent:analyst-report:2026q1',
        ],
    })
    assert compile_res.status_code == 201
    execution_id = compile_res.get_json()['execution_id']
    execution = [
        e for e in c.get('/admin/executions').get_json()['executions']
        if e['execution_id'] == execution_id
    ][0]
    role_bundle = execution['down_select_recommendation'].get('review_state')
    assert role_bundle is not None
    role_inputs = execution['board_report']['bridge_metadata']
    assert isinstance(role_inputs, dict) or role_inputs is None

    role_artifact = c.get(f'/executions/{execution_id}/reports/role_input_bundle.json')
    assert role_artifact.status_code == 200
    role_payload = role_artifact.get_json()
    assert role_payload['roles'][0]['non_negotiables'] == ['budget-cap-1']
    assert role_payload['roles'][0]['risk_flags'] == ['vendor-lockin']


def test_high_assurance_requires_completed_review_state():
    c = client(strict=True, app_env='development')
    ctx = 'ctx-high-assurance'
    submit_role(c, ctx, 'cto')
    blocked = c.post('/api/governed-compile', json={
        'execution_context_id': ctx,
        'profile_id': 'it_enterprise_profile_v1',
        'schema_id': 'GENERAL_SOLUTION_BOARD_REPORT_V1',
        'reasoning_level': 'R4',
        'policy_level': 'P4',
        'requested_assurance_level': 'human_reviewed',
        'review_state': {
            'human_review_required': True,
            'human_review_completed': False,
        },
    })
    assert blocked.status_code == 422
    blocked_codes = {item['code'] for item in blocked.get_json().get('hard_gate_failures', [])}
    assert 'REVIEW_STATE_INCOMPLETE' in blocked_codes

    allowed = c.post('/api/governed-compile', json={
        'execution_context_id': ctx,
        'profile_id': 'it_enterprise_profile_v1',
        'schema_id': 'GENERAL_SOLUTION_BOARD_REPORT_V1',
        'reasoning_level': 'R4',
        'policy_level': 'P4',
        'requested_assurance_level': 'human_reviewed',
        'review_state': {
            'human_review_required': True,
            'human_review_completed': True,
            'reviewed_by': 'reviewer-1',
            'approved_by': 'approver-1',
            'review_timestamps': {'completed_at': '2026-03-12T09:00:00Z'},
        },
    })
    assert allowed.status_code == 201


def test_non_dev_runtime_blocks_ephemeral_signing(monkeypatch, tmp_path):
    source_contracts = Path(__file__).resolve().parents[1] / "contracts"
    target_contracts = tmp_path / "contracts"
    shutil.copytree(source_contracts, target_contracts)

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("ADMIN_AUTH_ENABLED", "false")
    monkeypatch.setenv("DIIAC_STATE_DB", ":memory:")
    monkeypatch.setenv("SIGNING_ENABLED", "true")
    monkeypatch.delenv("SIGNING_PRIVATE_KEY_PEM", raising=False)

    with pytest.raises(RuntimeError, match="SIGNING_PRIVATE_KEY_PEM"):
        create_app()


def test_non_dev_runtime_requires_registered_active_signing_key(monkeypatch, tmp_path):
    source_contracts = Path(__file__).resolve().parents[1] / "contracts"
    target_contracts = tmp_path / "contracts"
    shutil.copytree(source_contracts, target_contracts)

    active_private = Ed25519PrivateKey.generate()
    active_private_pem = active_private.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("ADMIN_AUTH_ENABLED", "false")
    monkeypatch.setenv("DIIAC_STATE_DB", ":memory:")
    monkeypatch.setenv("SIGNING_ENABLED", "true")
    monkeypatch.setenv("SIGNING_KEY_ID", "missing-prod-key")
    monkeypatch.setenv("SIGNING_PRIVATE_KEY_PEM", active_private_pem)

    with pytest.raises(RuntimeError, match="not present in contracts/keys/public_keys.json"):
        create_app()


def test_signed_export_includes_verification_metadata_and_schema_version():
    c = client(strict=True, app_env='development')
    ctx = 'ctx-signed-export-metadata'
    submit_role(c, ctx, 'cto')
    execution_id = governed_compile(c, ctx).get_json()['execution_id']

    export_meta = c.get(f'/decision-pack/{execution_id}/export-signed')
    assert export_meta.status_code == 200
    payload = export_meta.get_json()
    sigmeta = payload['sigmeta']
    assert sigmeta['signature_payload_schema_version']
    assert sigmeta['signature_scope'] == 'execution_manifest'
    assert sigmeta['export_verification']['verified'] is True
    assert sigmeta['export_bundle']['zip_sha256']


def _valid_success_metrics() -> list[dict[str, object]]:
    return [
        {
            "metric_name": "Cycle-time reduction percent",
            "baseline": 20,
            "target_value": 15,
            "unit": "percent",
            "measurement_window": "6 months",
            "owner": "cio-owner",
        }
    ]


def _hard_gate_codes(response) -> set[str]:
    payload = response.get_json() or {}
    return {
        str(item.get("code"))
        for item in payload.get("hard_gate_failures", [])
        if isinstance(item, dict) and item.get("code")
    }


def _compile_payload(ctx: str, **overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "execution_context_id": ctx,
        "profile_id": "it_enterprise_profile_v1",
        "schema_id": "GENERAL_SOLUTION_BOARD_REPORT_V1",
        "reasoning_level": "R4",
        "policy_level": "P4",
        "success_metrics": _valid_success_metrics(),
    }
    payload.update(overrides)
    return payload


def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _http_json(url: str, method: str = "GET", payload: dict | None = None, headers: dict[str, str] | None = None) -> tuple[int, dict]:
    body = None
    req_headers = {"Content-Type": "application/json"}
    if headers:
        req_headers.update(headers)
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=body, method=method, headers=req_headers)
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            text = resp.read().decode("utf-8")
            return resp.status, json.loads(text) if text else {}
    except urllib.error.HTTPError as exc:
        text = exc.read().decode("utf-8")
        return exc.code, json.loads(text) if text else {}


def _wait_for_health(base_url: str, timeout_seconds: float = 10.0) -> tuple[int, dict]:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        try:
            status, payload = _http_json(f"{base_url}/health")
            if status in {200, 503}:
                return status, payload
        except Exception:
            pass
        time.sleep(0.15)
    raise RuntimeError("bridge health endpoint did not become reachable")


def _generate_signing_material() -> tuple[str, str]:
    private_key = Ed25519PrivateKey.generate()
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")
    public_b64 = base64.b64encode(
        private_key.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
    ).decode("utf-8")
    return private_pem, public_b64


def _write_public_keys(target_path: Path, entries: list[dict[str, str]]) -> None:
    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_text(json.dumps({"keys": entries}, indent=2), encoding="utf-8")


def _bridge_env(workspace: Path, port: int, key_id: str, private_pem: str, app_env: str = "production") -> dict[str, str]:
    env = os.environ.copy()
    env.update(
        {
            "APP_ENV": app_env,
            "SIGNING_ENABLED": "true",
            "SIGNING_KEY_ID": key_id,
            "SIGNING_PRIVATE_KEY_PEM": private_pem,
            "DIIAC_WORKSPACE": str(workspace),
            "PORT": str(port),
            "LLM_INGESTION_ENABLED": "false",
        }
    )
    return env


def test_replay_does_not_inject_legacy_non_negotiables():
    c = client(strict=True, app_env="development")
    base_payload = {
        "execution_context_id": "ctx-replay-no-legacy-non-negotiables",
        "profile_id": "transport_profile_v1",
        "schema_id": "GENERAL_SOLUTION_BOARD_REPORT_V1",
        "reasoning_level": "R4",
        "policy_level": "P4",
        "assertions": ["Deliver >=15% cycle-time reduction in <=6 months."],
        "evidence_refs": ["https://www.fortinet.com/products/secure-sd-wan"],
        "replay_provenance": {
            "source": "test-suite",
            "captured_at": "2026-03-01T00:00:00Z",
            "evidence_ids": ["evidence-manual-1"],
        },
    }
    replay_without_legacy = c.post("/verify/replay", json=base_payload)
    replay_with_legacy = c.post(
        "/verify/replay",
        json={**base_payload, "non_negotiables": ["deterministic-governance"]},
    )
    assert replay_without_legacy.status_code == 200
    assert replay_with_legacy.status_code == 200
    assert replay_without_legacy.get_json()["expected_execution_id"] != replay_with_legacy.get_json()["expected_execution_id"]


def test_replay_does_not_inject_legacy_risk_flags():
    c = client(strict=True, app_env="development")
    base_payload = {
        "execution_context_id": "ctx-replay-no-legacy-risk-flags",
        "profile_id": "transport_profile_v1",
        "schema_id": "GENERAL_SOLUTION_BOARD_REPORT_V1",
        "reasoning_level": "R4",
        "policy_level": "P4",
        "assertions": ["Deliver >=15% cycle-time reduction in <=6 months."],
        "evidence_refs": ["https://www.fortinet.com/products/secure-sd-wan"],
        "replay_provenance": {
            "source": "test-suite",
            "captured_at": "2026-03-01T00:00:00Z",
            "evidence_ids": ["evidence-manual-2"],
        },
    }
    replay_without_legacy = c.post("/verify/replay", json=base_payload)
    replay_with_legacy = c.post(
        "/verify/replay",
        json={**base_payload, "risk_flags": ["llm-hallucination-risk"]},
    )
    assert replay_without_legacy.status_code == 200
    assert replay_with_legacy.status_code == 200
    assert replay_without_legacy.get_json()["expected_execution_id"] != replay_with_legacy.get_json()["expected_execution_id"]


def test_replay_rejects_missing_evidence_ids_without_auto_refs():
    c = client(strict=True, app_env="development")
    ctx = "ctx-replay-missing-evidence-no-auto-ref"
    role_response = c.post(
        "/api/human-input/role",
        json={
            "execution_context_id": ctx,
            "role": "cto",
            "domain": "network",
            "assertions": ["Deliver >=15% cycle-time reduction in <=6 months."],
            "non_negotiables": ["Budget cap GBP 1.8M/year"],
            "risk_flags": ["vendor-lockin"],
            "evidence_refs": [],
        },
    )
    assert role_response.status_code == 201

    replay = c.post(
        "/verify/replay",
        json={
            "execution_context_id": ctx,
            "profile_id": "transport_profile_v1",
            "schema_id": "GENERAL_SOLUTION_BOARD_REPORT_V1",
            "reasoning_level": "R4",
            "policy_level": "P4",
            "replay_provenance": {
                "source": "test-suite",
                "captured_at": "2026-03-01T00:00:00Z",
                "evidence_ids": ["evidence-manual-3"],
            },
        },
    )
    assert replay.status_code == 422
    payload = replay.get_json()
    assert payload["error"] == "replay_input_invalid"
    assert payload["error_code"] == "MISSING_EVIDENCE_IDS"


def test_replay_fails_with_structured_error_on_missing_required_provenance():
    c = client(strict=True, app_env="development")
    replay = c.post(
        "/verify/replay",
        json={
            "execution_context_id": "ctx-replay-missing-provenance",
            "profile_id": "transport_profile_v1",
            "schema_id": "GENERAL_SOLUTION_BOARD_REPORT_V1",
            "reasoning_level": "R4",
            "policy_level": "P4",
            "assertions": ["Deliver >=15% cycle-time reduction in <=6 months."],
            "evidence_refs": ["https://www.fortinet.com/products/secure-sd-wan"],
        },
    )
    assert replay.status_code == 422
    payload = replay.get_json()
    assert payload["error"] == "replay_input_invalid"
    assert payload["error_code"] == "MISSING_REQUIRED_PROVENANCE"


def test_bridge_non_dev_requires_registered_active_key(tmp_path):
    workspace = tmp_path / "bridge-workspace-missing-key"
    private_pem, _public_b64 = _generate_signing_material()
    _write_public_keys(
        workspace / "contracts" / "keys" / "public_keys.json",
        [{"key_id": "different-key", "algorithm": "Ed25519", "public_key_b64": "AAAA"}],
    )
    env = _bridge_env(workspace, _find_free_port(), "bridge-prod-key", private_pem)

    bridge_cwd = Path(__file__).resolve().parents[1] / "backend-ui-bridge"
    result = subprocess.run(
        ["node", "server.js"],
        cwd=bridge_cwd,
        env=env,
        capture_output=True,
        text=True,
        timeout=12,
    )
    output = f"{result.stdout}\n{result.stderr}"
    assert result.returncode != 0
    assert "BRIDGE_TRUST_BLOCKED:MISSING_REGISTERED_ACTIVE_KEY" in output


def test_bridge_non_dev_rejects_mismatched_registered_key(tmp_path):
    workspace = tmp_path / "bridge-workspace-mismatch"
    private_pem, _public_b64 = _generate_signing_material()
    _other_private_pem, other_public_b64 = _generate_signing_material()
    _write_public_keys(
        workspace / "contracts" / "keys" / "public_keys.json",
        [{"key_id": "bridge-prod-key", "algorithm": "Ed25519", "public_key_b64": other_public_b64}],
    )
    env = _bridge_env(workspace, _find_free_port(), "bridge-prod-key", private_pem)

    bridge_cwd = Path(__file__).resolve().parents[1] / "backend-ui-bridge"
    result = subprocess.run(
        ["node", "server.js"],
        cwd=bridge_cwd,
        env=env,
        capture_output=True,
        text=True,
        timeout=12,
    )
    output = f"{result.stdout}\n{result.stderr}"
    assert result.returncode != 0
    assert "BRIDGE_TRUST_BLOCKED:ACTIVE_KEY_MISMATCH" in output


def test_bridge_runtime_trust_parity_contract(monkeypatch, tmp_path):
    private_pem, public_b64 = _generate_signing_material()
    key_id = "prod-parity-key"

    runtime_root = tmp_path / "runtime-root"
    shutil.copytree(Path(__file__).resolve().parents[1] / "contracts", runtime_root / "contracts")
    _write_public_keys(
        runtime_root / "contracts" / "keys" / "public_keys.json",
        [{"key_id": key_id, "algorithm": "Ed25519", "public_key_b64": public_b64}],
    )
    monkeypatch.chdir(runtime_root)
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("ADMIN_AUTH_ENABLED", "false")
    monkeypatch.setenv("DIIAC_STATE_DB", ":memory:")
    monkeypatch.setenv("SIGNING_ENABLED", "true")
    monkeypatch.setenv("SIGNING_KEY_ID", key_id)
    monkeypatch.setenv("SIGNING_PRIVATE_KEY_PEM", private_pem)
    runtime_app = create_app()
    runtime_app.testing = True
    runtime_client = runtime_app.test_client()
    runtime_health = runtime_client.get("/admin/health").get_json()
    assert runtime_health["production_trust_ready"] is True
    assert runtime_health["signing_trust_blockers"] == []

    bridge_workspace = tmp_path / "bridge-workspace-parity"
    _write_public_keys(
        bridge_workspace / "contracts" / "keys" / "public_keys.json",
        [{"key_id": key_id, "algorithm": "Ed25519", "public_key_b64": public_b64}],
    )
    bridge_port = _find_free_port()
    env = _bridge_env(bridge_workspace, bridge_port, key_id, private_pem, app_env="development")
    bridge_cwd = Path(__file__).resolve().parents[1] / "backend-ui-bridge"
    proc = subprocess.Popen(
        ["node", "server.js"],
        cwd=bridge_cwd,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        status, bridge_health = _wait_for_health(f"http://127.0.0.1:{bridge_port}")
        assert status == 200
        assert bridge_health["signing"]["production_trust_ready"] is True
        assert bridge_health["trust"]["signing_trust_blockers"] == []

        config_status, bridge_config = _http_json(
            f"http://127.0.0.1:{bridge_port}/admin/config/effective",
            headers={"x-role": "admin"},
        )
        assert config_status == 200
        assert bridge_config["signing"]["production_trust_ready"] is True
        assert bridge_config["signing"]["signing_trust_blockers"] == []
        assert bridge_config["signing"]["trust_source"] == runtime_health["trust_source"]
        assert bridge_config["signing"]["trust_registry_mode"] == runtime_health["trust_registry_mode"]
        assert bridge_config["signing"]["trust_registry_source"] == runtime_health["trust_registry_source"]
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()


def test_bridge_and_runtime_fail_same_trust_misconfiguration_e2e(monkeypatch, tmp_path):
    private_pem, _public_b64 = _generate_signing_material()
    key_id = "prod-misconfigured-key"

    runtime_root = tmp_path / "runtime-misconfig-root"
    shutil.copytree(Path(__file__).resolve().parents[1] / "contracts", runtime_root / "contracts")
    _write_public_keys(
        runtime_root / "contracts" / "keys" / "public_keys.json",
        [{"key_id": "different-key", "algorithm": "Ed25519", "public_key_b64": "AAAA"}],
    )
    monkeypatch.chdir(runtime_root)
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("ADMIN_AUTH_ENABLED", "false")
    monkeypatch.setenv("DIIAC_STATE_DB", ":memory:")
    monkeypatch.setenv("SIGNING_ENABLED", "true")
    monkeypatch.setenv("SIGNING_KEY_ID", key_id)
    monkeypatch.setenv("SIGNING_PRIVATE_KEY_PEM", private_pem)
    with pytest.raises(RuntimeError, match="not present in contracts/keys/public_keys.json"):
        create_app()

    bridge_workspace = tmp_path / "bridge-workspace-misconfig"
    _write_public_keys(
        bridge_workspace / "contracts" / "keys" / "public_keys.json",
        [{"key_id": "different-key", "algorithm": "Ed25519", "public_key_b64": "AAAA"}],
    )
    env = _bridge_env(bridge_workspace, _find_free_port(), key_id, private_pem)
    bridge_cwd = Path(__file__).resolve().parents[1] / "backend-ui-bridge"
    result = subprocess.run(
        ["node", "server.js"],
        cwd=bridge_cwd,
        env=env,
        capture_output=True,
        text=True,
        timeout=12,
    )
    output = f"{result.stdout}\n{result.stderr}"
    assert result.returncode != 0
    assert "BRIDGE_TRUST_BLOCKED:MISSING_REGISTERED_ACTIVE_KEY" in output


def test_missing_risk_register_fails_board_section_incomplete():
    c = client(strict=True, app_env="development")
    ctx = "ctx-missing-risk-register"
    role_input = c.post(
        "/api/human-input/role",
        json={
            "execution_context_id": ctx,
            "role": "cto",
            "domain": "network",
            "assertions": ["Deliver >=15% cycle-time reduction in <=6 months."],
            "non_negotiables": ["Budget cap GBP 1.8M/year"],
            "risk_flags": [],
            "evidence_refs": [
                "https://www.fortinet.com/products/secure-sd-wan",
                "urn:independent:analyst-report:2026q1",
            ],
        },
    )
    assert role_input.status_code == 201

    compile_res = c.post("/api/governed-compile", json=_compile_payload(ctx))
    assert compile_res.status_code == 422
    assert "BOARD_SECTION_INCOMPLETE" in _hard_gate_codes(compile_res)


def test_missing_executive_summary_fails_board_section_incomplete():
    c = client(strict=True, app_env="development")
    ctx = "ctx-missing-executive-summary"
    role_input = c.post(
        "/api/human-input/role",
        json={
            "execution_context_id": ctx,
            "role": "cto",
            "domain": "network",
            "assertions": [],
            "non_negotiables": ["Budget cap GBP 1.8M/year"],
            "risk_flags": ["vendor-lockin"],
            "evidence_refs": [
                "https://www.fortinet.com/products/secure-sd-wan",
                "urn:independent:analyst-report:2026q1",
            ],
        },
    )
    assert role_input.status_code == 201

    compile_res = c.post("/api/governed-compile", json=_compile_payload(ctx))
    assert compile_res.status_code == 422
    assert "BOARD_SECTION_INCOMPLETE" in _hard_gate_codes(compile_res)


def test_production_output_contains_no_placeholder_sections():
    c = client(strict=True, app_env="production")
    ctx = "ctx-production-no-placeholders"
    role_input = c.post(
        "/api/human-input/role",
        json={
            "execution_context_id": ctx,
            "role": "cto",
            "domain": "network",
            "assertions": ["Deliver >=15% cycle-time reduction in <=6 months."],
            "non_negotiables": ["Budget cap GBP 1.8M/year"],
            "risk_flags": ["vendor-lockin"],
            "evidence_refs": [
                "https://www.fortinet.com/products/secure-sd-wan",
                "urn:independent:analyst-report:2026q1",
            ],
        },
    )
    assert role_input.status_code == 201
    compile_res = c.post("/api/governed-compile", json=_compile_payload(ctx))
    assert compile_res.status_code == 201
    execution_id = compile_res.get_json()["execution_id"]
    execution = [
        e for e in c.get("/admin/executions", headers={"Authorization": "Bearer test-admin-token"}).get_json()["executions"]
        if e["execution_id"] == execution_id
    ][0]
    for section in execution["board_report"]["sections"]:
        content = str(section.get("content", ""))
        assert "PLACEHOLDER" not in content.upper()
        assert "No explicit role risk flags provided" not in content
        assert "No explicit objectives supplied." not in content


def test_success_metrics_require_baseline_target_unit_window_owner():
    c = client(strict=True, app_env="development")
    ctx = "ctx-kpi-missing-fields"
    assert submit_role(c, ctx, "cto").status_code == 201
    compile_res = c.post(
        "/api/governed-compile",
        json=_compile_payload(
            ctx,
            success_metrics=[{"metric_name": "Cycle-time reduction"}],
        ),
    )
    assert compile_res.status_code == 400
    payload = compile_res.get_json()
    assert payload["error"] == "missing_fields"
    assert payload["field"] == "success_metrics"


def test_principle_only_metric_fails_invalid_success_metrics():
    c = client(strict=True, app_env="development")
    ctx = "ctx-kpi-principle-only"
    assert submit_role(c, ctx, "cto").status_code == 201
    compile_res = c.post(
        "/api/governed-compile",
        json=_compile_payload(
            ctx,
            success_metrics=[
                {
                    "metric_name": "privacy-by-design",
                    "baseline": 0,
                    "target_value": 1,
                    "unit": "count",
                    "measurement_window": "6 months",
                    "owner": "cio-owner",
                }
            ],
        ),
    )
    assert compile_res.status_code == 422
    assert "INVALID_SUCCESS_METRICS" in _hard_gate_codes(compile_res)


def test_kpi_schema_round_trip_contract():
    c = client(strict=True, app_env="development")
    ctx = "ctx-kpi-round-trip"
    assert submit_role(c, ctx, "cto").status_code == 201
    success_metrics = [
        {
            "metric_name": "Cycle-time reduction percent",
            "baseline": 20,
            "target_value": 15,
            "unit": "percent",
            "measurement_window": "6 months",
            "owner": "cio-owner",
        },
        {
            "metric_name": "Sev1 incidents per month",
            "baseline": 3,
            "target_value": 1,
            "unit": "incidents",
            "measurement_window": "3 months",
            "owner": "sre-owner",
        },
    ]
    compile_res = c.post("/api/governed-compile", json=_compile_payload(ctx, success_metrics=success_metrics))
    assert compile_res.status_code == 201
    execution_id = compile_res.get_json()["execution_id"]
    scoring = c.get(f"/executions/{execution_id}/scoring").get_json()
    kpis = scoring["recommendation"]["success_metrics"]
    assert len(kpis) == 2
    for kpi in kpis:
        assert set(["metric_name", "baseline", "target_value", "unit", "measurement_window", "owner"]).issubset(set(kpi.keys()))


def test_stale_security_evidence_blocks_high_assurance():
    c = client(strict=True, app_env="development")
    ctx = "ctx-stale-security-high-assurance"
    role_input = c.post(
        "/api/human-input/role",
        json={
            "execution_context_id": ctx,
            "role": "cto",
            "domain": "network",
            "assertions": ["Must use Fortinet for SD-WAN with <=1% Sev1 increase in 6 months."],
            "non_negotiables": ["Budget cap GBP 1.8M/year"],
            "risk_flags": ["vendor-lockin"],
            "evidence_refs": [
                "https://www.fortinet.com/security/advisory?captured_at=2020-01-01T00:00:00Z",
                "urn:independent:analyst-report:2026q1",
            ],
        },
    )
    assert role_input.status_code == 201
    compile_res = c.post(
        "/api/governed-compile",
        json=_compile_payload(
            ctx,
            requested_assurance_level="human_reviewed",
            review_state={
                "human_review_required": True,
                "human_review_completed": True,
                "reviewed_by": "reviewer-1",
                "approved_by": "approver-1",
                "review_timestamps": {"completed_at": "2026-03-12T09:00:00Z"},
            },
        ),
    )
    assert compile_res.status_code == 422
    assert "STALE_CRITICAL_EVIDENCE" in _hard_gate_codes(compile_res)


def test_stale_pricing_evidence_blocks_high_assurance():
    c = client(strict=True, app_env="development")
    ctx = "ctx-stale-pricing-high-assurance"
    role_input = c.post(
        "/api/human-input/role",
        json={
            "execution_context_id": ctx,
            "role": "cto",
            "domain": "network",
            "assertions": ["Must use Fortinet for SD-WAN with <=1% Sev1 increase in 6 months."],
            "non_negotiables": ["Budget cap GBP 1.8M/year"],
            "risk_flags": ["vendor-lockin"],
            "evidence_refs": [
                "https://www.fortinet.com/pricing/enterprise?captured_at=2020-01-01T00:00:00Z",
                "urn:independent:analyst-report:2026q1",
            ],
        },
    )
    assert role_input.status_code == 201
    compile_res = c.post(
        "/api/governed-compile",
        json=_compile_payload(
            ctx,
            requested_assurance_level="externally_validated",
            review_state={
                "human_review_required": True,
                "human_review_completed": True,
                "reviewed_by": "reviewer-1",
                "approved_by": "approver-1",
                "review_timestamps": {"completed_at": "2026-03-12T09:00:00Z"},
            },
        ),
    )
    assert compile_res.status_code == 422
    assert "STALE_CRITICAL_EVIDENCE" in _hard_gate_codes(compile_res)


def test_noncritical_stale_evidence_warns_without_false_pass():
    c = client(strict=True, app_env="development")
    ctx = "ctx-stale-operational-noncritical"
    role_input = c.post(
        "/api/human-input/role",
        json={
            "execution_context_id": ctx,
            "role": "cto",
            "domain": "network",
            "assertions": ["Must use Fortinet for SD-WAN with <=1% Sev1 increase in 6 months."],
            "non_negotiables": ["Budget cap GBP 1.8M/year"],
            "risk_flags": ["vendor-lockin"],
            "evidence_refs": [
                "https://www.fortinet.com/operational/sla?captured_at=2020-01-01T00:00:00Z",
                "https://www.fortinet.com/security/advisory?captured_at=2026-02-01T00:00:00Z",
                "urn:independent:analyst-report:2026q1",
            ],
        },
    )
    assert role_input.status_code == 201
    compile_res = c.post(
        "/api/governed-compile",
        json=_compile_payload(ctx, requested_assurance_level="evidence_backed"),
    )
    assert compile_res.status_code == 201
    decision_summary = compile_res.get_json()["decision_summary"]
    warnings = decision_summary.get("quality_gate_failures", [])
    assert any("stale noncritical evidence present" in str(item).lower() for item in warnings)


def test_selected_vendor_rejects_competitor_primary_evidence():
    c = client(strict=True, app_env="development")
    ctx = "ctx-competitor-primary-evidence"
    role_input = c.post(
        "/api/human-input/role",
        json={
            "execution_context_id": ctx,
            "role": "cto",
            "domain": "network",
            "assertions": ["Must use Fortinet for SD-WAN with <=1% Sev1 increase in 6 months."],
            "non_negotiables": ["Budget cap GBP 1.8M/year"],
            "risk_flags": ["vendor-lockin"],
            "evidence_refs": [
                "https://www.paloaltonetworks.com/sase/prisma-sd-wan?captured_at=2026-02-01T00:00:00Z",
                "urn:independent:analyst-report:2026q1",
            ],
        },
    )
    assert role_input.status_code == 201
    compile_res = c.post("/api/governed-compile", json=_compile_payload(ctx))
    assert compile_res.status_code == 422
    assert "COMPETITOR_PRIMARY_EVIDENCE" in _hard_gate_codes(compile_res)


def test_vendor_scope_general_does_not_satisfy_first_party_requirement():
    c = client(strict=True, app_env="development")
    ctx = "ctx-vendor-scope-general"
    role_input = c.post(
        "/api/human-input/role",
        json={
            "execution_context_id": ctx,
            "role": "cto",
            "domain": "network",
            "assertions": ["Must use Fortinet for SD-WAN with <=1% Sev1 increase in 6 months."],
            "non_negotiables": ["Budget cap GBP 1.8M/year"],
            "risk_flags": ["vendor-lockin"],
            "evidence_refs": [
                "urn:independent:analyst-report:2026q1",
                "https://example.org/industry-report?captured_at=2026-02-01T00:00:00Z",
            ],
        },
    )
    assert role_input.status_code == 201
    compile_res = c.post("/api/governed-compile", json=_compile_payload(ctx))
    assert compile_res.status_code == 422
    assert "VENDOR_EVIDENCE_MISMATCH" in _hard_gate_codes(compile_res)


def test_vendor_evidence_mismatch_hard_fails_selected_vendor():
    c = client(strict=True, app_env="development")
    ctx = "ctx-vendor-evidence-mismatch"
    role_input = c.post(
        "/api/human-input/role",
        json={
            "execution_context_id": ctx,
            "role": "cto",
            "domain": "network",
            "assertions": ["Must use Fortinet for SD-WAN with <=1% Sev1 increase in 6 months."],
            "non_negotiables": ["Budget cap GBP 1.8M/year"],
            "risk_flags": ["vendor-lockin"],
            "evidence_refs": [
                "https://www.cisco.com/c/en/us/solutions/enterprise-networks/sd-wan.html?captured_at=2026-02-01T00:00:00Z",
                "urn:independent:analyst-report:2026q1",
            ],
        },
    )
    assert role_input.status_code == 201
    compile_res = c.post("/api/governed-compile", json=_compile_payload(ctx))
    assert compile_res.status_code == 422
    assert "VENDOR_EVIDENCE_MISMATCH" in _hard_gate_codes(compile_res)
