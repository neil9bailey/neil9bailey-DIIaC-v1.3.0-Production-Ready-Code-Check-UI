#!/usr/bin/env python3
"""Runtime E2E smoke runner for DIIaC baseline.

Starts app.py in a subprocess and exercises core flows over real HTTP.
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


def request(method: str, path: str, payload: dict | None = None, headers: dict | None = None) -> tuple[int, dict]:
    data = None
    req_headers = {"Content-Type": "application/json"}
    if headers:
        req_headers.update(headers)
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(BASE_URL + path, data=data, headers=req_headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = resp.read().decode("utf-8")
            return resp.status, json.loads(body) if body else {}
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8")
        parsed = json.loads(body) if body else {}
        return e.code, parsed


def wait_ready() -> None:
    for _ in range(50):
        try:
            status, _ = request("GET", "/health")
            if status == 200:
                return
        except Exception:
            pass
        time.sleep(0.2)
    raise RuntimeError("runtime did not become ready")


def main() -> int:
    env = os.environ.copy()
    env["APP_ENV"] = "development"
    env["STRICT_DETERMINISTIC_MODE"] = "true"
    env["ADMIN_AUTH_ENABLED"] = "true"
    env["ADMIN_API_TOKEN"] = "smoke-token"

    proc = subprocess.Popen([sys.executable, "app.py"], env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    try:
        wait_ready()

        status, health = request("GET", "/health")
        assert status == 200 and health.get("status") in {"OK", "DEGRADED"}

        ctx = "ctx-e2e-smoke"
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

        status, trust = request("GET", "/trust/status")
        assert status == 200 and trust["ledger_records"] >= 1

        status, _ = request("GET", "/admin/logs?source=backend")
        assert status == 200

        status, verify = request("GET", f"/verify/execution/{execution_id}")
        assert status == 200 and verify["status"] == "VERIFIABLE"

        status, _ = request("POST", "/admin/audit-export", {"execution_ids": [execution_id]})
        assert status == 201

        print("E2E runtime smoke PASSED")
        return 0
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()


if __name__ == "__main__":
    raise SystemExit(main())
