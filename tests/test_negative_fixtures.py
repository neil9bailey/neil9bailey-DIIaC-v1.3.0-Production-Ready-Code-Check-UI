import base64
import json
import shutil
import subprocess
from pathlib import Path

import pytest

import app as app_module
from app import create_app
from tests.test_admin_console import _compile_payload, _generate_signing_material, _hard_gate_codes, client


NEGATIVE_DIR = Path(__file__).resolve().parents[1] / "tests" / "negative"
REPO_ROOT = Path(__file__).resolve().parents[1]

FORTINET_COMPLETE_REFS = [
    "https://www.fortinet.com/security/advisory?captured_at=2026-02-01T00:00:00Z",
    "https://www.fortinet.com/pricing/enterprise?captured_at=2026-02-01T00:00:00Z",
    "https://www.fortinet.com/operational/sla?captured_at=2026-02-01T00:00:00Z",
    "https://www.fortinet.com/commercial/contract-terms?captured_at=2026-02-01T00:00:00Z",
    "https://www.fortinet.com/deployment/runbook?captured_at=2026-02-01T00:00:00Z",
    "https://www.fortinet.com/products/fortinet-sase?captured_at=2026-02-01T00:00:00Z",
    "urn:independent:analyst-report:2026q1",
]

PALO_ALTO_COMPLETE_REFS = [
    "https://www.paloaltonetworks.com/security/advisories?captured_at=2026-02-01T00:00:00Z",
    "https://www.paloaltonetworks.com/pricing/sase?captured_at=2026-02-01T00:00:00Z",
    "https://www.paloaltonetworks.com/operational/sla?captured_at=2026-02-01T00:00:00Z",
    "https://www.paloaltonetworks.com/commercial/contract-terms?captured_at=2026-02-01T00:00:00Z",
    "https://www.paloaltonetworks.com/deployment/runbook?captured_at=2026-02-01T00:00:00Z",
    "https://www.paloaltonetworks.com/products/prisma-sase?captured_at=2026-02-01T00:00:00Z",
    "urn:independent:analyst-report:2026q1",
]

DEFAULT_LLM_ANALYSIS = {
    "executive_summary": {"summary": "Negative fixture compile."},
    "vendor_scoring": {"options": [{"vendor": "Fortinet", "focus": "secure SD-WAN"}]},
    "audit_trail": {"timestamp": "2026-03-10T00:00:00Z"},
}


def _load_fixture(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _submit_role(
    c,
    ctx: str,
    *,
    assertions: list[str] | None = None,
    non_negotiables: list[str] | None = None,
    risk_flags: list[str] | None = None,
    evidence_refs: list[str] | None = None,
) -> None:
    payload = {
        "execution_context_id": ctx,
        "role": "cto",
        "domain": "network",
        "assertions": assertions or ["Must use Fortinet for SD-WAN with <=1% Sev1 increase in 6 months."],
        "non_negotiables": non_negotiables if non_negotiables is not None else ["Budget cap GBP 1.8M/year"],
        "risk_flags": risk_flags if risk_flags is not None else ["vendor-lockin"],
        "evidence_refs": evidence_refs or list(FORTINET_COMPLETE_REFS),
    }
    response = c.post("/api/human-input/role", json=payload)
    assert response.status_code == 201


def _compile_payload_with_defaults(ctx: str, **overrides: object) -> dict[str, object]:
    kwargs: dict[str, object] = {
        "llm_provider": "Copilot",
        "llm_audit_timestamp": "2026-03-10T00:00:00+00:00",
        "llm_analysis": DEFAULT_LLM_ANALYSIS,
    }
    kwargs.update(overrides)
    return _compile_payload(ctx, **kwargs)


def _copy_pack_dir(execution_id: str, destination: Path) -> Path:
    src = REPO_ROOT / "artifacts" / execution_id
    assert src.exists()
    target = destination / execution_id
    shutil.copytree(src, target)
    return target


def _run_pack_verifier(pack_dir: Path, registry_path: Path) -> tuple[int, dict]:
    result = subprocess.run(
        ["node", "scripts/verify_decision_pack.js", str(pack_dir), str(registry_path)],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        timeout=30,
    )
    payload = json.loads(result.stdout) if result.stdout.strip() else {}
    return result.returncode, payload


def _run_compile_fixture(fixture: dict, monkeypatch) -> None:
    scenario = str(fixture["scenario"])
    expected_codes = set(fixture.get("expected_codes") or [])
    c = client(strict=True, app_env="development")
    ctx = f"ctx-negative-{fixture['fixture_id']}"

    compile_payload: dict[str, object]

    if scenario == "placeholder_claim_ids":
        original_hash = app_module._sha256_text

        def patched_hash(text: str) -> str:
            seed = str(text)
            if "|" in seed and len(seed) > 20:
                return "placeholder-claim-seed-1234567890"
            return original_hash(text)

        monkeypatch.setattr(app_module, "_sha256_text", patched_hash)
        _submit_role(c, ctx)
        compile_payload = _compile_payload_with_defaults(ctx)
    elif scenario == "unresolved_evidence":
        _submit_role(
            c,
            ctx,
            assertions=["General modernization."],
            evidence_refs=["token-evidence-a", "token-evidence-b"],
        )
        compile_payload = _compile_payload(ctx)
    elif scenario == "vendor_evidence_mismatch":
        _submit_role(c, ctx, evidence_refs=PALO_ALTO_COMPLETE_REFS)
        compile_payload = _compile_payload_with_defaults(ctx)
    elif scenario == "invalid_success_metrics":
        _submit_role(c, ctx)
        compile_payload = _compile_payload_with_defaults(
            ctx,
            success_metrics=[
                {
                    "metric_name": "privacy-by-design",
                    "baseline": 1,
                    "target_value": 1,
                    "unit": "percent",
                    "measurement_window": "6 months",
                    "owner": "risk-owner",
                }
            ],
        )
    elif scenario == "missing_regulatory_constraints":
        long_reg = "REG-" + ("BETA" * 80)
        _submit_role(c, ctx, assertions=["General modernization."])
        compile_payload = _compile_payload_with_defaults(
            ctx,
            regulatory_context=[long_reg],
        )
    elif scenario == "missing_success_targets":
        long_target = "TARGET-" + ("ALPHA" * 80)
        _submit_role(c, ctx, assertions=["General modernization."])
        compile_payload = _compile_payload_with_defaults(
            ctx,
            goals=[long_target],
            success_targets=[long_target],
        )
    elif scenario == "decision_provenance_inconsistent":
        _submit_role(c, ctx)
        compile_payload = _compile_payload_with_defaults(
            ctx,
            llm_provider="Fortinet",
        )
    elif scenario == "policy_evidence_basis_missing":
        _submit_role(
            c,
            ctx,
            assertions=["General modernization."],
            evidence_refs=["token-evidence-a", "token-evidence-b"],
        )
        compile_payload = _compile_payload(ctx)
    elif scenario == "board_section_incomplete":
        _submit_role(
            c,
            ctx,
            assertions=[],
            risk_flags=[],
            evidence_refs=[
                "https://www.fortinet.com/products/secure-sd-wan",
                "urn:independent:analyst-report:2026q1",
            ],
        )
        compile_payload = _compile_payload(ctx)
    elif scenario == "review_state_incomplete":
        _submit_role(c, ctx)
        compile_payload = _compile_payload_with_defaults(
            ctx,
            requested_assurance_level="human_reviewed",
            review_state={
                "human_review_required": True,
                "human_review_completed": False,
            },
        )
    elif scenario == "stale_critical_evidence":
        stale_refs = [
            "https://www.fortinet.com/security/advisory?captured_at=2022-01-01T00:00:00Z",
            "https://www.fortinet.com/pricing/enterprise?captured_at=2022-01-01T00:00:00Z",
            "https://www.fortinet.com/operational/sla?captured_at=2026-02-01T00:00:00Z",
            "https://www.fortinet.com/commercial/contract-terms?captured_at=2026-02-01T00:00:00Z",
            "https://www.fortinet.com/deployment/runbook?captured_at=2026-02-01T00:00:00Z",
            "urn:independent:analyst-report:2026q1",
        ]
        _submit_role(c, ctx, evidence_refs=stale_refs)
        compile_payload = _compile_payload_with_defaults(
            ctx,
            requested_assurance_level="human_reviewed",
            review_state={
                "human_review_required": True,
                "human_review_completed": True,
                "reviewed_by": "reviewer-1",
                "approved_by": "approver-1",
            },
        )
    else:
        raise AssertionError(f"Unsupported compile fixture scenario: {scenario}")

    response = c.post("/api/governed-compile", json=compile_payload)
    assert response.status_code == 422
    codes = _hard_gate_codes(response)
    for code in expected_codes:
        assert code in codes


def _run_startup_fixture(fixture: dict, monkeypatch, tmp_path: Path) -> None:
    scenario = str(fixture["scenario"])
    expected_substring = str(fixture.get("expected_error_substring", ""))

    source_contracts = REPO_ROOT / "contracts"
    target_contracts = tmp_path / "contracts"
    shutil.copytree(source_contracts, target_contracts)

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("ADMIN_AUTH_ENABLED", "false")
    monkeypatch.setenv("DIIAC_STATE_DB", ":memory:")
    monkeypatch.setenv("SIGNING_ENABLED", "true")

    if scenario == "non_dev_missing_trust_registry":
        private_pem, _public_b64 = _generate_signing_material()
        monkeypatch.setenv("SIGNING_KEY_ID", "missing-prod-key")
        monkeypatch.setenv("SIGNING_PRIVATE_KEY_PEM", private_pem)
    elif scenario == "non_dev_ephemeral_signing":
        monkeypatch.delenv("SIGNING_PRIVATE_KEY_PEM", raising=False)
    else:
        raise AssertionError(f"Unsupported startup fixture scenario: {scenario}")

    with pytest.raises(RuntimeError, match=expected_substring):
        create_app()


def _run_verifier_fixture(fixture: dict, tmp_path: Path) -> None:
    scenario = str(fixture["scenario"])
    if scenario != "signature_verification_failure":
        raise AssertionError(f"Unsupported verifier fixture scenario: {scenario}")

    c = client(strict=True, app_env="development")
    ctx = f"ctx-negative-{fixture['fixture_id']}"
    _submit_role(c, ctx)
    compile_res = c.post("/api/governed-compile", json=_compile_payload_with_defaults(ctx))
    assert compile_res.status_code == 201
    execution_id = compile_res.get_json()["execution_id"]

    pack_dir = _copy_pack_dir(execution_id, tmp_path)
    sigmeta_path = pack_dir / "signed_export.sigmeta.json"
    sigmeta = json.loads(sigmeta_path.read_text(encoding="utf-8"))
    signature = str(sigmeta.get("signature", "")).strip()
    assert signature
    sigmeta["signature"] = ("A" if signature[0] != "A" else "B") + signature[1:]
    sigmeta_path.write_text(json.dumps(sigmeta, indent=2), encoding="utf-8")

    code, payload = _run_pack_verifier(pack_dir, REPO_ROOT / "contracts" / "keys" / "public_keys.json")
    assert code != 0
    assert payload.get("overall") == "FAIL"
    signature_error = str(payload.get("signature", {}).get("error", ""))
    allowed = fixture.get("expected_signature_errors") or []
    assert any(signature_error == item or signature_error.startswith(item) for item in allowed)


@pytest.mark.parametrize(
    "fixture_path",
    sorted(NEGATIVE_DIR.glob("*.json")),
    ids=lambda path: path.stem,
)
def test_negative_fixture_cases(fixture_path: Path, monkeypatch, tmp_path: Path):
    fixture = _load_fixture(fixture_path)
    mode = str(fixture["mode"])
    if mode == "compile":
        _run_compile_fixture(fixture, monkeypatch)
        return
    if mode == "startup":
        _run_startup_fixture(fixture, monkeypatch, tmp_path)
        return
    if mode == "verifier":
        _run_verifier_fixture(fixture, tmp_path)
        return
    raise AssertionError(f"Unsupported negative fixture mode: {mode}")
