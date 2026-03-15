import json
from pathlib import Path

from tests.test_admin_console import _compile_payload, client


GOLDEN_DIR = Path(__file__).resolve().parents[1] / "tests" / "golden"


def _run_golden_fixture(fixture_name: str) -> None:
    fixture_path = GOLDEN_DIR / f"{fixture_name}.json"
    fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
    c = client(strict=True, app_env="development")
    ctx = fixture["context_id"]
    role_payload = dict(fixture["role_input"])
    role_payload["execution_context_id"] = ctx

    role_res = c.post("/api/human-input/role", json=role_payload)
    assert role_res.status_code == 201

    compile_payload = _compile_payload(
        ctx,
        profile_id=fixture["profile_id"],
        **fixture.get("compile_overrides", {}),
    )
    compile_res = c.post("/api/governed-compile", json=compile_payload)
    assert compile_res.status_code == 201
    payload = compile_res.get_json()
    execution_id = payload["execution_id"]

    all_execs = c.get("/admin/executions", headers={"Authorization": "Bearer test-admin-token"}).get_json()["executions"]
    execution = next(item for item in all_execs if item["execution_id"] == execution_id)
    recommendation = execution["down_select_recommendation"]
    expected = fixture["expected"]

    sections = [section["title"] for section in execution["board_report"]["sections"]]
    assert sections == expected["board_sections"]
    assert recommendation["claim_ids"] == expected["claim_ids"]

    required_policy_fields = set(expected["policy_control_required_fields"])
    first_control = recommendation["policy_pack_compliance"][0]["controls"][0]
    assert required_policy_fields.issubset(set(first_control.keys()))

    trust_bundle = json.loads((Path.cwd() / "artifacts" / execution_id / "trust_bundle.json").read_text(encoding="utf-8"))
    for key_name in expected["trust_required_fields"]:
        assert key_name in trust_bundle
    historical_keys = trust_bundle.get("historical_keys", [])
    assert all("valid_from" in key and "valid_to" in key for key in historical_keys if isinstance(key, dict))

    kpi_keys = set(expected["kpi_required_fields"])
    for metric in recommendation.get("success_metrics", []):
        assert kpi_keys.issubset(set(metric.keys()))


def golden_it_enterprise_export():
    _run_golden_fixture("golden_it_enterprise_export")


def golden_transport_export():
    _run_golden_fixture("golden_transport_export")


def golden_finance_export():
    _run_golden_fixture("golden_finance_export")


def test_golden_it_enterprise_export():
    golden_it_enterprise_export()


def test_golden_transport_export():
    golden_transport_export()


def test_golden_finance_export():
    golden_finance_export()
