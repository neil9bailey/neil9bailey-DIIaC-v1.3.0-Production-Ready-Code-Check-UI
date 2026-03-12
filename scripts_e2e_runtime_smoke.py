#!/usr/bin/env python3
"""Runtime E2E smoke runner for DIIaC baseline.

Starts app.py in a subprocess and exercises core flows over real HTTP.
"""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request

def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def request(base_url: str, method: str, path: str, payload: dict | None = None, headers: dict | None = None) -> tuple[int, dict]:
    data = None
    req_headers = {"Content-Type": "application/json"}
    if headers:
        req_headers.update(headers)
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(base_url + path, data=data, headers=req_headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = resp.read().decode("utf-8")
            return resp.status, json.loads(body) if body else {}
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8")
        parsed = json.loads(body) if body else {}
        return e.code, parsed


def wait_ready(base_url: str) -> None:
    for _ in range(50):
        try:
            status, _ = request(base_url, "GET", "/health")
            if status == 200:
                return
        except Exception:
            pass
        time.sleep(0.2)
    raise RuntimeError("runtime did not become ready")


def main() -> int:
    runtime_port = _find_free_port()
    base_url = f"http://127.0.0.1:{runtime_port}"
    env = os.environ.copy()
    env["APP_ENV"] = "development"
    env["STRICT_DETERMINISTIC_MODE"] = "true"
    env["ADMIN_AUTH_ENABLED"] = "true"
    env["ADMIN_API_TOKEN"] = "smoke-token"
    env["PORT"] = str(runtime_port)

    proc = subprocess.Popen([sys.executable, "app.py"], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
    try:
        wait_ready(base_url)

        status, health = request(base_url, "GET", "/health")
        assert status == 200 and health.get("status") in {"OK", "DEGRADED"}

        ctx = f"ctx-e2e-smoke-{int(time.time())}"
        status, _ = request(base_url, "POST", "/api/human-input/role", {
            "execution_context_id": ctx,
            "role": "cto",
            "domain": "network",
            "assertions": ["Deliver >=15% cycle-time reduction in <=6 months with <=1% Sev1 increase."],
            "non_negotiables": ["Budget cap GBP 1.8M/year"],
            "risk_flags": ["r1"],
            "evidence_refs": [
                "https://www.fortinet.com/products/secure-sd-wan",
                "urn:independent:analyst-report:2026q1",
            ],
        })
        assert status == 201

        status, compile_payload = request(base_url, "POST", "/api/governed-compile", {
            "execution_context_id": ctx,
            "profile_id": "transport_profile_v1",
            "schema_id": "GENERAL_SOLUTION_BOARD_REPORT_V1",
            "reasoning_level": "R4",
            "policy_level": "P4",
        })
        assert status == 201
        execution_id = compile_payload["execution_id"]

        status, trust = request(base_url, "GET", "/trust/status")
        assert status == 200 and trust["ledger_records"] >= 1

        status, _ = request(base_url, "GET", "/admin/logs?source=backend")
        assert status == 200

        status, verify = request(base_url, "GET", f"/verify/execution/{execution_id}")
        assert status == 200 and verify["status"] == "VERIFIABLE"

        status, _ = request(base_url, "POST", "/admin/audit-export", {"execution_ids": [execution_id]})
        assert status in {200, 201}

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
