#!/usr/bin/env python3
"""Production-mode readiness validation for DIIaC baseline.

Starts app.py in production mode and validates security/runtime invariants:
- admin auth denial/allow behavior
- deterministic compile + verification path
- signed export + audit export behavior
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request

BASE_URL = "http://127.0.0.1:8000"
ADMIN_TOKEN = "production-readiness-token"


def request(method: str, path: str, payload: dict | None = None, headers: dict | None = None) -> tuple[int, dict]:
    body = None
    req_headers = {"Content-Type": "application/json"}
    if headers:
        req_headers.update(headers)
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")

    req = urllib.request.Request(BASE_URL + path, data=body, headers=req_headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            text = response.read().decode("utf-8")
            return response.status, (json.loads(text) if text else {})
    except urllib.error.HTTPError as exc:
        text = exc.read().decode("utf-8")
        return exc.code, (json.loads(text) if text else {})


def wait_ready() -> None:
    for _ in range(75):
        try:
            status, _ = request("GET", "/health")
            if status == 200:
                return
        except Exception:
            pass
        time.sleep(0.2)
    raise RuntimeError("runtime did not become ready in production mode")


def main() -> int:
    env = os.environ.copy()
    env["APP_ENV"] = "production"
    env["STRICT_DETERMINISTIC_MODE"] = "true"
    env["ADMIN_AUTH_ENABLED"] = "true"
    env["ADMIN_API_TOKEN"] = ADMIN_TOKEN

    proc = subprocess.Popen([sys.executable, "app.py"], env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

    try:
        wait_ready()

        # Admin endpoints must deny without token.
        status, denied = request("GET", "/admin/health")
        assert status == 401 and denied.get("error") == "admin_auth_required"

        # Admin endpoints must allow with token.
        status, admin_health = request("GET", "/admin/health", headers={"Authorization": f"Bearer {ADMIN_TOKEN}"})
        assert status == 200 and admin_health.get("status") in {"OK", "DEGRADED"}

        # Sensitive admin write endpoint must deny without token.
        status, denied_audit = request("POST", "/admin/audit-export", {"execution_ids": []})
        assert status == 401 and denied_audit.get("error") == "admin_auth_required"

        # Submit role + compile.
        ctx = "ctx-production-readiness"
        status, _ = request("POST", "/api/human-input/role", {
            "execution_context_id": ctx,
            "role": "cto",
            "domain": "network",
            "assertions": ["a1"],
            "non_negotiables": ["n1"],
            "risk_flags": ["r1"],
            "evidence_refs": ["ref-1"],
        })
        assert status == 201

        status, compile_payload = request("POST", "/api/governed-compile", {
            "execution_context_id": ctx,
            "profile_id": "transport_profile_v1",
            "schema_id": "GENERAL_SOLUTION_BOARD_REPORT_V1",
            "reasoning_level": "R4",
            "policy_level": "P4",
        })
        assert status == 201
        execution_id = compile_payload["execution_id"]

        # Verify execution.
        status, verify_exec = request("GET", f"/verify/execution/{execution_id}")
        assert status == 200 and verify_exec.get("status") == "VERIFIABLE"

        # Verify pack with returned hashes.
        status, verify_pack = request("POST", "/verify/pack", {
            "execution_id": execution_id,
            "pack_hash": verify_exec["pack_hash"],
            "manifest_hash": verify_exec["manifest_hash"],
        })
        assert status == 200 and verify_pack.get("overall_valid") is True

        # Signed export.
        status, exported = request("GET", f"/decision-pack/{execution_id}/export-signed")
        assert status == 200 and exported["sigmeta"]["execution_id"] == execution_id

        # Admin audit export with token.
        status, audit_export = request(
            "POST",
            "/admin/audit-export",
            {"execution_ids": [execution_id]},
            headers={"Authorization": f"Bearer {ADMIN_TOKEN}"},
        )
        assert status == 201 and audit_export.get("audit_export_id")

        # Download audit export with token.
        audit_id = audit_export["audit_export_id"]
        status, _ = request("GET", f"/admin/audit/exports/{audit_id}/download", headers={"Authorization": f"Bearer {ADMIN_TOKEN}"})
        assert status == 200

        # Metrics with token should include threshold recommendations.
        status, metrics = request("GET", "/admin/metrics", headers={"Authorization": f"Bearer {ADMIN_TOKEN}"})
        assert status == 200 and "threshold_recommendations" in metrics

        print("Production readiness check PASSED")
        return 0
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()


if __name__ == "__main__":
    raise SystemExit(main())
