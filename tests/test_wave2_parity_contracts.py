import json
import os
import shutil
import subprocess
import threading
import base64
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from app import create_app
from tests.test_admin_console import (
    _bridge_env,
    _compile_payload,
    _find_free_port,
    _generate_signing_material,
    _hard_gate_codes,
    _http_json,
    _wait_for_health,
    _write_public_keys,
    client,
    submit_role,
    test_bridge_and_runtime_fail_same_trust_misconfiguration_e2e,
)


def _copy_pack_dir(execution_id: str, destination: Path) -> Path:
    src = Path.cwd() / "artifacts" / execution_id
    assert src.exists()
    target = destination / execution_id
    shutil.copytree(src, target)
    return target


def _run_pack_verifier(pack_dir: Path, registry_path: Path) -> tuple[int, dict]:
    result = subprocess.run(
        ["node", "scripts/verify_decision_pack.js", str(pack_dir), str(registry_path)],
        capture_output=True,
        text=True,
        cwd=Path(__file__).resolve().parents[1],
        timeout=20,
    )
    payload = json.loads(result.stdout) if result.stdout.strip() else {}
    return result.returncode, payload


def _submit_complete_vendor_role(c, ctx: str) -> None:
    role_payload = {
        "execution_context_id": ctx,
        "role": "cto",
        "domain": "network",
        "assertions": ["Must use Fortinet for SD-WAN with <=1% Sev1 increase in 6 months."],
        "non_negotiables": ["Budget cap GBP 1.8M/year"],
        "risk_flags": ["vendor-lockin"],
        "evidence_refs": [
            "https://www.fortinet.com/security/advisory?captured_at=2026-02-01T00:00:00Z",
            "https://www.fortinet.com/pricing/enterprise?captured_at=2026-02-01T00:00:00Z",
            "https://www.fortinet.com/operational/sla?captured_at=2026-02-01T00:00:00Z",
            "https://www.fortinet.com/commercial/contract-terms?captured_at=2026-02-01T00:00:00Z",
            "https://www.fortinet.com/deployment/runbook?captured_at=2026-02-01T00:00:00Z",
            "https://www.fortinet.com/products/fortinet-sase?captured_at=2026-02-01T00:00:00Z",
            "urn:independent:analyst-report:2026q1",
        ],
    }
    response = c.post("/api/human-input/role", json=role_payload)
    assert response.status_code == 201


def test_api_schema_contract_for_policy_semantics_response():
    text = Path("openapi.yaml").read_text(encoding="utf-8")
    required_markers = [
        "assessment_mode",
        "assurance_level",
        "compliance_position",
        "legal_confirmation_required",
        "evidence_ids",
        "residual_uncertainty",
        "PolicyControlResult",
        "GovernedCompileResponse",
        "LlmGovernedCompileResponse",
        "/api/llm-governed-compile:",
    ]
    for marker in required_markers:
        assert marker in text


def test_provider_metadata_does_not_leak_into_recommendation():
    c = client(strict=True, app_env="development")
    ctx = "ctx-provider-leakage-check"
    _submit_complete_vendor_role(c, ctx)
    compile_res = c.post(
        "/api/governed-compile",
        json=_compile_payload(
            ctx,
            llm_provider="Copilot",
            llm_analysis={
                "executive_summary": {"summary": "Provider metadata isolation check."},
                "vendor_scoring": {"options": [{"vendor": "Fortinet", "focus": "security and operations"}]},
                "board_recommendation": {"recommendation": "Select Fortinet based on evidence."},
                "audit_trail": {"timestamp": "2026-03-10T00:00:00Z"},
            },
        ),
    )
    assert compile_res.status_code == 201
    payload = compile_res.get_json()
    decision_basis = str(payload["decision_summary"].get("decision_basis", "")).lower()
    assert "copilot" not in decision_basis
    recommendation_text = str(payload["recommendation"].get("major_recommendation", "")).lower()
    assert "copilot" not in recommendation_text


def test_recommendation_invariant_under_provider_label_change():
    c = client(strict=True, app_env="development")
    base_analysis = {
        "executive_summary": {"summary": "Provider invariance check."},
        "vendor_scoring": {"options": [{"vendor": "Fortinet", "focus": "security and operations"}]},
        "board_recommendation": {"recommendation": "Select Fortinet based on evidence."},
        "audit_trail": {"timestamp": "2026-03-10T00:00:00Z"},
    }
    ctx = "ctx-provider-invariance"
    _submit_complete_vendor_role(c, ctx)

    res_a = c.post("/api/governed-compile", json=_compile_payload(ctx, llm_provider="Copilot", llm_analysis=base_analysis))
    res_b = c.post("/api/governed-compile", json=_compile_payload(ctx, llm_provider="ChatGPT", llm_analysis=base_analysis))
    assert res_a.status_code == 201
    assert res_b.status_code == 201
    rec_a = res_a.get_json()["recommendation"]
    rec_b = res_b.get_json()["recommendation"]
    assert rec_a["selected_vendor"] == rec_b["selected_vendor"]
    assert rec_a["decision_status"] == rec_b["decision_status"]
    assert rec_a["score"] == rec_b["score"]


def test_decision_basis_references_vendor_not_provider():
    c = client(strict=True, app_env="development")
    ctx = "ctx-decision-basis-vendor-not-provider"
    _submit_complete_vendor_role(c, ctx)
    compile_res = c.post(
        "/api/governed-compile",
        json=_compile_payload(
            ctx,
            llm_provider="Copilot",
            llm_analysis={
                "executive_summary": {"summary": "Decision basis vendor reference check."},
                "vendor_scoring": {"options": [{"vendor": "Fortinet", "focus": "secure SD-WAN"}]},
                "board_recommendation": {"recommendation": "Select Fortinet based on deterministic scoring."},
                "audit_trail": {"timestamp": "2026-03-10T00:00:00Z"},
            },
        ),
    )
    assert compile_res.status_code == 201
    decision_basis = str(compile_res.get_json()["decision_summary"].get("decision_basis", ""))
    assert "Fortinet" in decision_basis
    assert "Copilot" not in decision_basis
    assert "ChatGPT" not in decision_basis


def test_bridge_runtime_parity_for_non_dev_trust_blockers(monkeypatch, tmp_path):
    test_bridge_and_runtime_fail_same_trust_misconfiguration_e2e(monkeypatch, tmp_path)


def test_bridge_runtime_parity_for_intent_preservation(tmp_path):
    captured: dict[str, object] = {}

    class RuntimeMockHandler(BaseHTTPRequestHandler):
        def _json(self, status: int, payload: dict) -> None:
            body = json.dumps(payload).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):  # noqa: N802
            if self.path == "/health":
                self._json(200, {"status": "OK"})
                return
            self._json(404, {"error": "not_found"})

        def do_POST(self):  # noqa: N802
            if self.path != "/api/governed-compile":
                self._json(404, {"error": "not_found"})
                return
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length).decode("utf-8")) if length else {}
            captured["compile_payload"] = payload
            self._json(
                201,
                {
                    "execution_id": "mock-exec-1",
                    "decision_summary": {"decision_status": "recommended"},
                    "recommendation": {
                        "selected_vendor": "Fortinet",
                        "decision_status": "recommended",
                        "review_state": payload.get("review_state", {}),
                        "policy_pack_compliance": [],
                    },
                    "policy_pack_compliance": [],
                    "review_state": payload.get("review_state", {}),
                    "review_approval_events": [],
                    "execution_state": {"execution_id": "mock-exec-1"},
                },
            )

        def log_message(self, *_args, **_kwargs):  # noqa: ANN002, ANN003
            return

    runtime_port = _find_free_port()
    mock_server = ThreadingHTTPServer(("127.0.0.1", runtime_port), RuntimeMockHandler)
    server_thread = threading.Thread(target=mock_server.serve_forever, daemon=True)
    server_thread.start()

    private_pem, public_b64 = _generate_signing_material()
    key_id = "bridge-parity-key"
    workspace = tmp_path / "bridge-parity-workspace"
    _write_public_keys(
        workspace / "contracts" / "keys" / "public_keys.json",
        [{"key_id": key_id, "algorithm": "Ed25519", "public_key_b64": public_b64}],
    )
    human_input_dir = workspace / "artefacts" / "human-input"
    human_input_dir.mkdir(parents=True, exist_ok=True)
    (human_input_dir / "seed.json").write_text(json.dumps({"raw_text": "Preserve intent exactly."}), encoding="utf-8")

    bridge_port = _find_free_port()
    env = _bridge_env(workspace, bridge_port, key_id, private_pem, app_env="development")
    env["PYTHON_BASE_URL"] = f"http://127.0.0.1:{runtime_port}"
    env["PYTHON_AUTOSTART"] = "false"
    env["LLM_STUB_ENABLED"] = "true"
    env["LLM_INGESTION_ENABLED"] = "true"
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
        status, _health = _wait_for_health(f"http://127.0.0.1:{bridge_port}")
        assert status == 200
        request_payload = {
            "provider": "Copilot",
            "reasoning_level": "R4",
            "policy_level": "P4",
            "profile_id": "it_enterprise_profile_v1",
            "schema_id": "GENERAL_SOLUTION_BOARD_REPORT_V1",
            "role": "CIO",
            "domain": "network-transformation",
            "assertions": ["Primary assertion"],
            "non_negotiables": ["Budget cap GBP 1.8M/year"],
            "risk_flags": ["vendor-lockin"],
            "goals": ["Cycle-time reduction >=15%"],
            "regulatory_context": ["GDPR"],
            "success_targets": ["<=1% Sev1 increase"],
            "success_metrics": [
                {
                    "metric_name": "Cycle-time reduction",
                    "baseline": 20,
                    "target_value": 15,
                    "unit": "percent",
                    "measurement_window": "6 months",
                    "owner": "cio-owner",
                }
            ],
            "review_state": {"human_review_required": False},
        }
        status_code, response = _http_json(
            f"http://127.0.0.1:{bridge_port}/api/llm-governed-compile",
            method="POST",
            payload=request_payload,
            headers={"x-role": "admin"},
        )
        assert status_code == 200
        payload = captured.get("compile_payload")
        assert isinstance(payload, dict)
        assert payload.get("non_negotiables") == request_payload["non_negotiables"]
        assert payload.get("risk_flags") == request_payload["risk_flags"]
        assert payload.get("success_metrics") == request_payload["success_metrics"]
        assert "deterministic-governance" not in payload.get("non_negotiables", [])
        assert "llm-hallucination-risk" not in payload.get("risk_flags", [])
        assert "review_state" in payload
        assert response.get("compile", {}).get("recommendation", {}).get("selected_vendor") == "Fortinet"
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
        mock_server.shutdown()
        mock_server.server_close()


def test_bridge_runtime_parity_for_review_state_and_policy_semantics():
    c = client(strict=True, app_env="development")
    ctx = "ctx-parity-review-policy-semantics"
    assert submit_role(c, ctx, "cto").status_code == 201
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
                "open_exceptions": ["exception-a"],
                "waived_controls": ["control-waiver-a"],
            },
        ),
    )
    assert compile_res.status_code == 201
    payload = compile_res.get_json()
    recommendation = payload["recommendation"]
    controls = (recommendation.get("policy_pack_compliance") or [{}])[0].get("controls", [])
    assert controls
    required_fields = {
        "assessment_mode",
        "assurance_level",
        "compliance_position",
        "legal_confirmation_required",
        "evidence_ids",
        "residual_uncertainty",
    }
    for control in controls:
        assert required_fields.issubset(set(control.keys()))
    assert payload.get("review_state", {}).get("human_review_completed") is True
    assert isinstance(payload.get("review_approval_events", []), list)


def test_trust_bundle_contains_validity_window():
    c = client(strict=True, app_env="development")
    ctx = "ctx-trust-bundle-validity-window"
    assert submit_role(c, ctx, "cto").status_code == 201
    compile_res = c.post("/api/governed-compile", json=_compile_payload(ctx))
    assert compile_res.status_code == 201
    execution_id = compile_res.get_json()["execution_id"]
    trust_bundle = json.loads((Path.cwd() / "artifacts" / execution_id / "trust_bundle.json").read_text(encoding="utf-8"))
    assert trust_bundle["validity_reference_time"] == "signature_payload.signed_at"
    active_key = trust_bundle.get("active_key") or {}
    assert "valid_from" in active_key
    assert "valid_to" in active_key
    historical_keys = trust_bundle.get("historical_keys") or []
    assert isinstance(historical_keys, list)
    assert all("valid_from" in key and "valid_to" in key for key in historical_keys if isinstance(key, dict))


def test_historical_pack_verifies_under_rotated_key_registry(tmp_path):
    c = client(strict=True, app_env="development")
    ctx = "ctx-trust-rotation-history"
    assert submit_role(c, ctx, "cto").status_code == 201
    compile_res = c.post("/api/governed-compile", json=_compile_payload(ctx))
    assert compile_res.status_code == 201
    execution_id = compile_res.get_json()["execution_id"]

    pack_dir = _copy_pack_dir(execution_id, tmp_path)
    sigmeta_path = pack_dir / "signed_export.sigmeta.json"
    sigmeta = json.loads(sigmeta_path.read_text(encoding="utf-8"))
    old_key_id = sigmeta["signing_key_id"]
    old_public = sigmeta["public_key_b64"]

    rotated_private = Ed25519PrivateKey.generate()
    rotated_public = (
        rotated_private.public_key()
        .public_bytes(encoding=serialization.Encoding.Raw, format=serialization.PublicFormat.Raw)
    )
    rotated_public_b64 = base64.b64encode(rotated_public).decode("utf-8")

    rotated_registry = tmp_path / "rotated_public_keys.json"
    rotated_registry.write_text(
        json.dumps(
            {
                "keys": [
                    {
                        "key_id": old_key_id,
                        "algorithm": "Ed25519",
                        "public_key_b64": old_public,
                        "valid_from": "2024-01-01T00:00:00+00:00",
                        "valid_to": "2027-01-01T00:00:00+00:00",
                    },
                    {
                        "key_id": "rotated-key-2026",
                        "algorithm": "Ed25519",
                        "public_key_b64": rotated_public_b64,
                        "valid_from": "2026-04-01T00:00:00+00:00",
                        "valid_to": None,
                    },
                ]
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    code, payload = _run_pack_verifier(pack_dir, rotated_registry)
    assert code == 0
    assert payload["overall"] == "PASS"


def test_unknown_key_export_fails(tmp_path):
    c = client(strict=True, app_env="development")
    ctx = "ctx-unknown-key-fail"
    assert submit_role(c, ctx, "cto").status_code == 201
    compile_res = c.post("/api/governed-compile", json=_compile_payload(ctx))
    assert compile_res.status_code == 201
    execution_id = compile_res.get_json()["execution_id"]

    pack_dir = _copy_pack_dir(execution_id, tmp_path)
    sigmeta_path = pack_dir / "signed_export.sigmeta.json"
    trust_bundle_path = pack_dir / "trust_bundle.json"
    sigmeta = json.loads(sigmeta_path.read_text(encoding="utf-8"))
    trust_bundle = json.loads(trust_bundle_path.read_text(encoding="utf-8"))
    sigmeta["signing_key_id"] = "unknown-key-id"
    sigmeta["public_key_b64"] = ""
    sigmeta_path.write_text(json.dumps(sigmeta, indent=2), encoding="utf-8")
    trust_bundle["active_key"] = None
    trust_bundle["historical_keys"] = []
    trust_bundle_path.write_text(json.dumps(trust_bundle, indent=2), encoding="utf-8")

    code, payload = _run_pack_verifier(pack_dir, Path("contracts/keys/public_keys.json"))
    assert code != 0
    assert payload["overall"] == "FAIL"
    assert payload["signature"]["error"] == "public_key_not_available"


def test_tampered_signature_fails_verification(tmp_path):
    c = client(strict=True, app_env="development")
    ctx = "ctx-tampered-signature-fail"
    assert submit_role(c, ctx, "cto").status_code == 201
    compile_res = c.post("/api/governed-compile", json=_compile_payload(ctx))
    assert compile_res.status_code == 201
    execution_id = compile_res.get_json()["execution_id"]

    pack_dir = _copy_pack_dir(execution_id, tmp_path)
    sigmeta_path = pack_dir / "signed_export.sigmeta.json"
    sigmeta = json.loads(sigmeta_path.read_text(encoding="utf-8"))
    sig_text = str(sigmeta.get("signature", "")).strip()
    assert sig_text
    tampered = ("A" if sig_text[0] != "A" else "B") + sig_text[1:]
    sigmeta["signature"] = tampered
    sigmeta_path.write_text(json.dumps(sigmeta, indent=2), encoding="utf-8")

    code, payload = _run_pack_verifier(pack_dir, Path("contracts/keys/public_keys.json"))
    assert code != 0
    assert payload["overall"] == "FAIL"
    assert payload["signature"]["error"] in {"invalid_signature", "signature_verify_exception:Invalid character in string"}
