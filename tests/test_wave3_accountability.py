import json
from pathlib import Path

from tests.test_admin_console import _compile_payload, _hard_gate_codes, client


def _submit_vendor_complete_role(c, ctx: str) -> None:
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


def test_review_completion_appends_ledger_event():
    c = client(strict=True, app_env="development")
    ctx = "ctx-review-ledger-completion"
    _submit_vendor_complete_role(c, ctx)
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
    assert compile_res.status_code == 201
    execution_id = compile_res.get_json()["execution_id"]
    ledger = c.get("/admin/logs?source=ledger", headers={"Authorization": "Bearer test-admin-token"}).get_json()["logs"]
    assert any(item.get("event_type") == "HUMAN_REVIEW_COMPLETED" and item.get("execution_id") == execution_id for item in ledger)


def test_approval_appends_ledger_event():
    c = client(strict=True, app_env="development")
    ctx = "ctx-review-ledger-approval"
    _submit_vendor_complete_role(c, ctx)
    compile_res = c.post(
        "/api/governed-compile",
        json=_compile_payload(
            ctx,
            requested_assurance_level="externally_validated",
            review_state={
                "human_review_required": True,
                "human_review_completed": True,
                "reviewed_by": "reviewer-2",
                "approved_by": "approver-2",
                "review_timestamps": {"approved_at": "2026-03-12T10:00:00Z"},
            },
        ),
    )
    assert compile_res.status_code == 201
    execution_id = compile_res.get_json()["execution_id"]
    ledger = c.get("/admin/logs?source=ledger", headers={"Authorization": "Bearer test-admin-token"}).get_json()["logs"]
    assert any(item.get("event_type") == "HUMAN_APPROVAL_RECORDED" and item.get("execution_id") == execution_id for item in ledger)


def test_exceptions_and_waivers_surface_in_export_and_ui():
    c = client(strict=True, app_env="development")
    ctx = "ctx-review-exceptions-waivers"
    _submit_vendor_complete_role(c, ctx)
    compile_res = c.post(
        "/api/governed-compile",
        json=_compile_payload(
            ctx,
            requested_assurance_level="human_reviewed",
            review_state={
                "human_review_required": True,
                "human_review_completed": True,
                "reviewed_by": "reviewer-3",
                "approved_by": "approver-3",
                "review_timestamps": {"completed_at": "2026-03-12T11:00:00Z"},
                "open_exceptions": ["exception-a"],
                "waived_controls": ["control-waiver-a"],
            },
        ),
    )
    assert compile_res.status_code == 201
    payload = compile_res.get_json()
    execution_id = payload["execution_id"]
    assert payload["review_state"]["open_exceptions"] == ["exception-a"]
    assert payload["review_state"]["waived_controls"] == ["control-waiver-a"]
    assert len(payload["review_approval_events"]) >= 2
    events_artifact = json.loads((Path.cwd() / "artifacts" / execution_id / "review_approval_events.json").read_text(encoding="utf-8"))
    assert any(item.get("event_type") == "REVIEW_EXCEPTION_RECORDED" for item in events_artifact)
    assert any(item.get("event_type") == "CONTROL_WAIVER_RECORDED" for item in events_artifact)


def test_selected_vendor_requires_security_pricing_operational_support():
    c = client(strict=True, app_env="development")
    ctx = "ctx-missing-vendor-classes"
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
            "urn:independent:analyst-report:2026q1",
        ],
    }
    assert c.post("/api/human-input/role", json=role_payload).status_code == 201
    compile_res = c.post(
        "/api/governed-compile",
        json=_compile_payload(
            ctx,
            llm_provider="Copilot",
            llm_audit_timestamp="2026-03-10T00:00:00+00:00",
            llm_analysis={
                "executive_summary": {"summary": "Selected-vendor dossier completeness gate test."},
                "vendor_scoring": {"options": [{"vendor": "Fortinet", "focus": "secure SD-WAN"}]},
                "board_recommendation": {"recommendation": "Fortinet"},
                "audit_trail": {"timestamp": "2026-03-10T00:00:00Z"},
            },
        ),
    )
    assert compile_res.status_code == 422
    codes = _hard_gate_codes(compile_res)
    assert "SELECTED_VENDOR_DOSSIER_INCOMPLETE" in codes


def test_product_label_normalization_is_applied():
    c = client(strict=True, app_env="development")
    ctx = "ctx-product-normalization"
    _submit_vendor_complete_role(c, ctx)
    compile_res = c.post("/api/governed-compile", json=_compile_payload(ctx))
    assert compile_res.status_code == 201
    execution_id = compile_res.get_json()["execution_id"]
    executions = c.get("/admin/executions", headers={"Authorization": "Bearer test-admin-token"}).get_json()["executions"]
    execution = next(item for item in executions if item["execution_id"] == execution_id)
    evidence_objects = execution["down_select_recommendation"]["evidence_quality"]["evidence_objects"]
    normalized_labels = {
        item.get("product_label_normalized")
        for item in evidence_objects
        if isinstance(item, dict) and item.get("product_label_normalized")
    }
    assert "Fortinet Secure SD-WAN" in normalized_labels


def test_incomplete_selected_vendor_dossier_fails():
    c = client(strict=True, app_env="development")
    ctx = "ctx-incomplete-selected-vendor-dossier"
    role_payload = {
        "execution_context_id": ctx,
        "role": "cto",
        "domain": "network",
        "assertions": ["Must use Fortinet for SD-WAN with <=1% Sev1 increase in 6 months."],
        "non_negotiables": ["Budget cap GBP 1.8M/year"],
        "risk_flags": ["vendor-lockin"],
        "evidence_refs": [
            "https://www.fortinet.com/security/advisory?captured_at=2026-02-01T00:00:00Z",
            "https://www.fortinet.com/operational/sla?captured_at=2026-02-01T00:00:00Z",
            "https://www.fortinet.com/commercial/contract-terms?captured_at=2026-02-01T00:00:00Z",
            "urn:independent:analyst-report:2026q1",
        ],
    }
    assert c.post("/api/human-input/role", json=role_payload).status_code == 201
    compile_res = c.post(
        "/api/governed-compile",
        json=_compile_payload(
            ctx,
            llm_provider="Copilot",
            llm_audit_timestamp="2026-03-10T00:00:00+00:00",
            llm_analysis={
                "executive_summary": {"summary": "Selected-vendor class completeness enforcement."},
                "vendor_scoring": {"options": [{"vendor": "Fortinet", "focus": "secure SD-WAN"}]},
                "board_recommendation": {"recommendation": "Fortinet"},
                "audit_trail": {"timestamp": "2026-03-10T00:00:00Z"},
            },
        ),
    )
    assert compile_res.status_code == 422
    payload = compile_res.get_json()
    assert "SELECTED_VENDOR_DOSSIER_INCOMPLETE" in _hard_gate_codes(compile_res)
    failure = next(item for item in payload["hard_gate_failures"] if item.get("code") == "SELECTED_VENDOR_DOSSIER_INCOMPLETE")
    assert "missing_required_classes" in failure.get("details", {})
