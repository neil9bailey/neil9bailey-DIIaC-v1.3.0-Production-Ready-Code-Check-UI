from __future__ import annotations

import base64
import hmac
import hashlib
import json
import os
import sqlite3
import time
import uuid
import zipfile
from datetime import datetime, timezone
from functools import wraps
from pathlib import Path
from typing import Any, Callable

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from flask import Flask, g, has_request_context, jsonify, request, send_file


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _canonical_json(data: Any) -> str:
    return json.dumps(data, sort_keys=True, separators=(",", ":"))


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _b64url_decode(value: str) -> bytes:
    padded = value + "=" * ((4 - len(value) % 4) % 4)
    return base64.urlsafe_b64decode(padded.encode("utf-8"))


def _load_profiles(profile_dir: Path) -> list[dict[str, Any]]:
    profiles: list[dict[str, Any]] = []
    for p in sorted(profile_dir.glob("*_profile_v1.json")):
        profile = json.loads(p.read_text(encoding="utf-8"))
        profile["profile_hash"] = _sha256_text(_canonical_json(profile))
        profile["file"] = p.name
        profiles.append(profile)
    return profiles


def _build_merkle(leaves: list[dict[str, str]]) -> dict[str, Any]:
    nodes = [leaf["leaf_hash"] for leaf in leaves]
    if not nodes:
        root = _sha256_text("")
        return {"root": root, "levels": [[root]]}

    levels = [nodes]
    current = nodes
    while len(current) > 1:
        if len(current) % 2 == 1:
            current = current + [current[-1]]
        nxt: list[str] = []
        for i in range(0, len(current), 2):
            nxt.append(_sha256_text(current[i] + current[i + 1]))
        levels.append(nxt)
        current = nxt
    return {"root": current[0], "levels": levels}


def _merkle_proof(levels: list[list[str]], index: int) -> list[str]:
    siblings: list[str] = []
    idx = index
    for level in levels[:-1]:
        if len(level) == 1:
            break
        working = level[:] if len(level) % 2 == 0 else level + [level[-1]]
        sib_idx = idx + 1 if idx % 2 == 0 else idx - 1
        siblings.append(working[sib_idx])
        idx //= 2
    return siblings


def _verify_merkle_proof(leaf_hash: str, siblings: list[str], index: int, merkle_root: str) -> bool:
    computed = leaf_hash
    idx = index
    for sib in siblings:
        if idx % 2 == 0:
            computed = _sha256_text(computed + sib)
        else:
            computed = _sha256_text(sib + computed)
        idx //= 2
    return computed == merkle_root


def _load_or_create_signing_key() -> tuple[Ed25519PrivateKey, str]:
    pem = os.getenv("SIGNING_PRIVATE_KEY_PEM")
    if pem:
        key = serialization.load_pem_private_key(pem.encode("utf-8"), password=None)
        if not isinstance(key, Ed25519PrivateKey):
            raise ValueError("SIGNING_PRIVATE_KEY_PEM must be Ed25519")
        return key, "configured"
    return Ed25519PrivateKey.generate(), "ephemeral"


def create_app() -> Flask:
    app = Flask(__name__)

    app.config["MAX_CONTENT_LENGTH"] = int(os.getenv("MAX_REQUEST_BYTES", str(1024 * 1024)))

    strict_deterministic_mode = os.getenv("STRICT_DETERMINISTIC_MODE", "false").lower() == "true"
    signing_enabled = os.getenv("SIGNING_ENABLED", "true").lower() != "false"
    signing_key_id = os.getenv("SIGNING_KEY_ID", "ephemeral-local-ed25519")

    private_key, key_mode = _load_or_create_signing_key()
    public_key = private_key.public_key()
    public_key_b64 = base64.b64encode(
        public_key.public_bytes(encoding=serialization.Encoding.Raw, format=serialization.PublicFormat.Raw)
    ).decode("utf-8")

    data_root = Path(os.getenv("DIIAC_DATA_ROOT", str(Path(__file__).resolve().parent))).resolve()
    artifacts_dir = data_root / "artifacts"
    exports_dir = data_root / "exports"
    audit_dir = data_root / "audit_exports"
    keys_dir = data_root / "contracts" / "keys"
    profiles_dir = data_root / "contracts" / "business-profiles"
    runtime_dir = data_root / "runtime"
    for d in [artifacts_dir, exports_dir, audit_dir, keys_dir, profiles_dir, runtime_dir]:
        d.mkdir(parents=True, exist_ok=True)

    db_path = runtime_dir / "diiac_runtime.db"

    def _db_conn() -> sqlite3.Connection:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db() -> None:
        with _db_conn() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS role_inputs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    execution_context_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS executions (
                    execution_id TEXT PRIMARY KEY,
                    profile_id TEXT NOT NULL,
                    schema_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    pack_hash TEXT NOT NULL,
                    manifest_hash TEXT NOT NULL,
                    merkle_root TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS backend_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    level TEXT NOT NULL,
                    message TEXT NOT NULL,
                    execution_id TEXT,
                    payload_json TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS ledger_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    record_id INTEGER NOT NULL,
                    timestamp TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    execution_id TEXT,
                    pack_hash TEXT,
                    manifest_hash TEXT,
                    merkle_root TEXT,
                    previous_record_hash TEXT,
                    record_hash TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS audit_exports (
                    audit_export_id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    path TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                );
                """
            )

    _init_db()

    public_keys_file = keys_dir / "public_keys.json"
    if public_keys_file.exists():
        try:
            registry = json.loads(public_keys_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            registry = {"keys": []}
    else:
        registry = {"keys": []}

    keys = registry.get("keys") if isinstance(registry, dict) else []
    if not isinstance(keys, list):
        keys = []

    desired_key = {"key_id": signing_key_id, "algorithm": "Ed25519", "public_key_b64": public_key_b64}
    if not any(
        isinstance(k, dict)
        and k.get("key_id") == signing_key_id
        and k.get("algorithm") == "Ed25519"
        and k.get("public_key_b64") == public_key_b64
        for k in keys
    ):
        keys = [k for k in keys if isinstance(k, dict) and k.get("key_id") != signing_key_id]
        keys.append(desired_key)

    public_keys_file.write_text(json.dumps({"keys": keys}, indent=2), encoding="utf-8")

    profiles = _load_profiles(profiles_dir)
    profiles_by_id = {p["profile_id"]: p for p in profiles}

    backend_logs: list[dict[str, Any]] = []
    ledger_logs: list[dict[str, Any]] = []
    execution_logs: dict[str, list[dict[str, Any]]] = {}
    executions: dict[str, dict[str, Any]] = {}
    role_inputs: dict[str, list[dict[str, Any]]] = {}
    audit_exports: dict[str, dict[str, Any]] = {}
    profile_overrides: list[dict[str, Any]] = []

    approved_schemas = {"GENERAL_SOLUTION_BOARD_REPORT_V1", "RFQ_TEMPLATE_V1", "SLA_SCHEDULE_V1", "TECHNICAL_SOLUTION_BOARD_REPORT_V1"}

    enforce_admin_auth = os.getenv("ENFORCE_ADMIN_AUTH", "false").lower() == "true"
    admin_api_key = os.getenv("ADMIN_API_KEY", "")
    jwt_secret = os.getenv("JWT_SECRET", "")
    jwt_issuer = os.getenv("JWT_ISSUER", "diiac")
    jwt_audience = os.getenv("JWT_AUDIENCE", "diiac-admin")

    request_metrics: dict[str, dict[str, float | int]] = {}

    def _persist_row(sql: str, params: tuple[Any, ...]) -> None:
        with _db_conn() as conn:
            conn.execute(sql, params)

    @app.before_request
    def _request_start() -> None:
        g.request_started_at = time.perf_counter()
        request_id = request.headers.get("X-Request-ID") or _sha256_text(f"{time.time_ns()}:{uuid.uuid4().hex}")[:16]
        g.request_id = request_id

    @app.after_request
    def _request_finish(response: Any) -> Any:
        if has_request_context() and hasattr(g, "request_started_at"):
            duration_ms = (time.perf_counter() - g.request_started_at) * 1000.0
            route = request.path
            metric = request_metrics.setdefault(route, {"count": 0, "errors": 0, "total_ms": 0.0, "max_ms": 0.0})
            metric["count"] = int(metric["count"]) + 1
            metric["total_ms"] = float(metric["total_ms"]) + duration_ms
            metric["max_ms"] = max(float(metric["max_ms"]), duration_ms)
            if response.status_code >= 400:
                metric["errors"] = int(metric["errors"]) + 1
            response.headers["X-Request-ID"] = getattr(g, "request_id", "")
            response.headers["X-Response-Time-Ms"] = f"{duration_ms:.2f}"
        return response

    def _admin_guard() -> Any | None:
        if not enforce_admin_auth:
            return None
        role = request.headers.get("x-role", "").lower()
        key = request.headers.get("x-api-key", "")
        auth_header = request.headers.get("Authorization", "")

        jwt_ok = False
        if auth_header.startswith("Bearer ") and jwt_secret:
            token = auth_header.split(" ", 1)[1].strip()
            jwt_ok = _verify_admin_jwt(token)

        key_ok = bool(admin_api_key and key == admin_api_key)
        if role != "admin" or not (key_ok or jwt_ok):
            return jsonify({"error": "forbidden", "message": "admin authentication required"}), 403
        return None

    def _verify_admin_jwt(token: str) -> bool:
        try:
            parts = token.split(".")
            if len(parts) != 3:
                return False
            header_b64, payload_b64, sig_b64 = parts
            signing_input = f"{header_b64}.{payload_b64}".encode("utf-8")
            expected_sig = hmac.new(jwt_secret.encode("utf-8"), signing_input, hashlib.sha256).digest()
            provided_sig = _b64url_decode(sig_b64)
            if not hmac.compare_digest(expected_sig, provided_sig):
                return False

            header = json.loads(_b64url_decode(header_b64).decode("utf-8"))
            payload = json.loads(_b64url_decode(payload_b64).decode("utf-8"))
            if header.get("alg") != "HS256":
                return False
            now = int(time.time())
            if int(payload.get("exp", 0)) < now:
                return False
            if payload.get("iss") != jwt_issuer or payload.get("aud") != jwt_audience:
                return False
            roles = payload.get("roles")
            if isinstance(roles, list):
                return "admin" in [str(r).lower() for r in roles]
            return str(payload.get("role", "")).lower() == "admin"
        except Exception:
            return False

    def _admin_protected(fn: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(fn)
        def _wrapped(*args: Any, **kwargs: Any) -> Any:
            denied = _admin_guard()
            if denied:
                return denied
            return fn(*args, **kwargs)

        return _wrapped

    def _normalize_compile_payload(payload: dict[str, Any]) -> dict[str, Any]:
        normalized = dict(payload)
        if "profile_id" not in normalized and "business_profile" in normalized:
            normalized["profile_id"] = normalized.get("business_profile")
        if "schema_id" not in normalized and "schema" in normalized:
            normalized["schema_id"] = normalized.get("schema")
        normalized.setdefault("reasoning_level", "R4")
        normalized.setdefault("policy_level", "P4")
        return normalized

    def _validate_compile_payload(payload: dict[str, Any]) -> tuple[bool, dict[str, Any] | None]:
        required = ["execution_context_id", "profile_id", "schema_id", "reasoning_level", "policy_level"]
        missing = [k for k in required if k not in payload]
        if missing:
            return False, {"error": "missing_fields", "missing": missing}
        if not isinstance(payload.get("execution_context_id"), str) or not payload.get("execution_context_id").strip():
            return False, {"error": "invalid_field", "field": "execution_context_id"}
        if payload.get("reasoning_level") not in {"R0", "R1", "R2", "R3", "R4", "R5"}:
            return False, {"error": "invalid_field", "field": "reasoning_level"}
        if payload.get("policy_level") not in {"P0", "P1", "P2", "P3", "P4", "P5"}:
            return False, {"error": "invalid_field", "field": "policy_level"}
        return True, None

    def _validate_role_payload(payload: dict[str, Any]) -> tuple[bool, dict[str, Any] | None]:
        required = ["execution_context_id", "role", "domain", "assertions", "non_negotiables", "risk_flags", "evidence_refs"]
        missing = [k for k in required if k not in payload]
        if missing:
            return False, {"error": "missing_fields", "missing": missing}
        allowed_roles = {
            "IT_SECTOR_LEAD",
            "ACTING_CTO",
            "ENTERPRISE_ARCHITECT",
            "PRINCIPAL_ENGINEER",
            "CIO",
            "CSO",
            "cto",
            "cso",
            "cio",
            "ea",
            "principal_engineer",
        }
        if payload.get("role") not in allowed_roles:
            return False, {"error": "invalid_field", "field": "role"}
        for arr in ["assertions", "non_negotiables", "risk_flags", "evidence_refs"]:
            if not isinstance(payload.get(arr), list):
                return False, {"error": "invalid_field", "field": arr}
        return True, None

    def _rehydrate_state_from_db() -> None:
        with _db_conn() as conn:
            for row in conn.execute("SELECT payload_json FROM role_inputs ORDER BY id ASC").fetchall():
                payload = json.loads(row["payload_json"])
                ctx = payload.get("execution_context_id")
                if ctx:
                    role_inputs.setdefault(ctx, []).append(payload)
            for row in conn.execute("SELECT payload_json FROM executions ORDER BY created_at ASC").fetchall():
                payload = json.loads(row["payload_json"])
                eid = payload.get("execution_id")
                if eid:
                    executions[eid] = payload
            for row in conn.execute("SELECT payload_json FROM backend_logs ORDER BY id ASC").fetchall():
                evt = json.loads(row["payload_json"])
                backend_logs.append(evt)
                execution_id = evt.get("execution_id")
                if execution_id:
                    execution_logs.setdefault(execution_id, []).append(evt)
            for row in conn.execute("SELECT payload_json FROM ledger_logs ORDER BY id ASC").fetchall():
                ledger_logs.append(json.loads(row["payload_json"]))
            for row in conn.execute("SELECT audit_export_id, created_at, path FROM audit_exports ORDER BY created_at ASC").fetchall():
                audit_exports[row["audit_export_id"]] = {"path": row["path"], "created_at": row["created_at"]}

    _rehydrate_state_from_db()

    def _log(message: str, level: str = "INFO", execution_id: str | None = None) -> None:
        evt = {
            "timestamp": _utc_now(),
            "level": level,
            "message": message,
            "execution_id": execution_id,
            "request_id": getattr(g, "request_id", None) if has_request_context() else None,
        }
        backend_logs.append(evt)
        _persist_row(
            "INSERT INTO backend_logs(timestamp, level, message, execution_id, payload_json) VALUES (?, ?, ?, ?, ?)",
            (evt["timestamp"], level, message, execution_id, json.dumps(evt)),
        )
        if execution_id:
            execution_logs.setdefault(execution_id, []).append(evt)

    def _append_ledger(event_type: str, payload: dict[str, Any]) -> dict[str, Any]:
        prev = ledger_logs[-1]["record_hash"] if ledger_logs else "0" * 64
        record_core = {
            "record_id": len(ledger_logs) + 1,
            "timestamp": _utc_now(),
            "event_type": event_type,
            "request_id": getattr(g, "request_id", None) if has_request_context() else None,
            "previous_record_hash": prev,
            **payload,
        }
        record_hash = _sha256_text(_canonical_json(record_core))
        record = {**record_core, "record_hash": record_hash}
        ledger_logs.append(record)
        _persist_row(
            """INSERT INTO ledger_logs(record_id, timestamp, event_type, execution_id, pack_hash, manifest_hash, merkle_root, previous_record_hash, record_hash, payload_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                record.get("record_id"),
                record.get("timestamp"),
                event_type,
                record.get("execution_id"),
                record.get("pack_hash"),
                record.get("manifest_hash"),
                record.get("merkle_root"),
                record.get("previous_record_hash"),
                record.get("record_hash"),
                json.dumps(record),
            ),
        )
        return record

    def _deterministic_score(seed: str, label: str) -> float:
        val = int(_sha256_text(f"{seed}:{label}")[:8], 16)
        return round(50 + (val % 5000) / 100, 2)

    def _enforce_sections(required_sections: list[str], draft_sections: list[dict[str, str]]) -> list[dict[str, str]]:
        by_title = {s["title"]: s for s in draft_sections}
        return [
            by_title.get(title, {"title": title, "content": "PLACEHOLDER: deterministically enforced missing section."})
            for title in required_sections
        ]

    def _build_execution(payload: dict[str, Any]) -> tuple[dict[str, Any], int]:
        profile_id = payload.get("profile_id", "transport_profile_v1")
        schema_id = payload.get("schema_id", "GENERAL_SOLUTION_BOARD_REPORT_V1")
        schema_version = payload.get("schema_version", "1.0.0")
        rp = {"reasoning_level": payload.get("reasoning_level", "R4"), "policy_level": payload.get("policy_level", "P4")}
        context_id = payload.get("execution_context_id") or f"ctx-{uuid.uuid4().hex[:8]}"

        profile = profiles_by_id.get(profile_id)
        if profile is None:
            return {"error": "profile_not_found", "profile_id": profile_id}, 400
        if schema_id not in approved_schemas:
            return {"error": "schema_not_approved", "schema_id": schema_id}, 403
        if schema_id not in profile["allowed_schemas"]:
            return {"error": "schema_not_allowed_for_profile", "profile_id": profile_id, "schema_id": schema_id}, 403

        role_bundle = role_inputs.get(context_id, [])
        seed_payload = {
            "context_id": context_id,
            "profile_id": profile_id,
            "profile_hash": profile["profile_hash"],
            "schema_id": schema_id,
            "schema_version": schema_version,
            "rp": rp,
            "role_bundle": role_bundle,
            "request_payload": payload,
        }
        context_hash = _sha256_text(_canonical_json(seed_payload))
        execution_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"diiac:{context_hash}")) if strict_deterministic_mode else str(uuid.uuid4())

        required_sections = profile["required_sections"]
        draft_sections = [
            {"title": "Executive Summary", "content": f"Deterministic summary for {execution_id[:12]}"},
            {"title": "Context", "content": f"Profile={profile_id}; Schema={schema_id}; RP={rp['reasoning_level']}/{rp['policy_level']}"},
            {"title": "Success Metrics", "content": "Deterministic governance success metrics."},
        ]
        sections = _enforce_sections(required_sections, draft_sections)

        evidence_entries: list[dict[str, Any]] = []
        for idx, section in enumerate(sections, start=1):
            source_role = role_bundle[(idx - 1) % len(role_bundle)]["role"] if role_bundle else "system"
            source_ref = role_bundle[(idx - 1) % len(role_bundle)].get("evidence_refs", [f"auto-ref-{idx}"])[0] if role_bundle else f"placeholder-{idx}"
            evidence_entries.append(
                {
                    "claim_id": f"claim-{idx}",
                    "report_section": section["title"],
                    "source_role": source_role,
                    "source_ref": source_ref,
                    "policy_ref": f"{rp['reasoning_level']}/{rp['policy_level']}",
                    "confidence_reason": "Deterministic evidence linkage",
                }
            )

        weights = profile["scoring_weights"]
        scores = {k: _deterministic_score(context_hash, k) for k in weights}
        total = round(sum(scores[k] * weights[k] for k in weights), 2)
        recommendation = {
            "major_recommendation": "Proceed with candidate A",
            "score": total,
            "claim_ids": [e["claim_id"] for e in evidence_entries[:3]],
        }

        board_report = {
            "execution_id": execution_id,
            "schema_id": schema_id,
            "profile_id": profile_id,
            "sections": sections,
            "major_recommendations": [recommendation],
        }
        evidence_trace_map = {
            "execution_id": execution_id,
            "entries": evidence_entries,
            "recommendation_claim_links": [
                {"recommendation": recommendation["major_recommendation"], "claim_ids": recommendation["claim_ids"]}
            ],
        }
        schema_contract = {
            "schema_id": schema_id,
            "schema_version": schema_version,
            "schema_hash": _sha256_text(f"{schema_id}:{schema_version}"),
        }
        profile_snapshot = {
            "profile_id": profile["profile_id"],
            "profile_hash": profile["profile_hash"],
            "sector": profile["sector"],
            "default_reasoning_level": profile["default_reasoning_level"],
            "default_policy_level": profile["default_policy_level"],
        }
        required_controls = set(profile.get("required_controls", []))
        provided_controls = set(payload.get("controls", list(required_controls)))
        compliance_matrix = {
            "required_controls": sorted(required_controls),
            "provided_controls": sorted(provided_controls),
            "satisfied_controls": sorted(required_controls.intersection(provided_controls)),
            "all_required_satisfied": required_controls.issubset(provided_controls),
        }
        vendor_scoring_matrix = {
            "execution_id": execution_id,
            "deterministic": True,
            "rows": [{"vendor": "candidate-A", "weights": weights, "scores": scores, "total": total}],
        }
        deterministic_log = {
            "strict_deterministic_mode": strict_deterministic_mode,
            "context_hash": context_hash,
            "stages": [
                {"stage": "collect_role_inputs", "hash": _sha256_text(context_hash + "1")},
                {"stage": "normalize_claims", "hash": _sha256_text(context_hash + "2")},
                {"stage": "bind_schema", "hash": _sha256_text(context_hash + "3")},
                {"stage": "generate_structured_draft", "hash": _sha256_text(context_hash + "4")},
                {"stage": "enforce_rp_sections", "hash": _sha256_text(context_hash + "5")},
                {"stage": "render_reports", "hash": _sha256_text(context_hash + "6")},
            ],
        }

        artifacts_payloads: dict[str, Any] = {
            "board_report.json": board_report,
            "deterministic_compilation_log.json": deterministic_log,
            "evidence_trace_map.json": evidence_trace_map,
            "role_input_bundle.json": {"execution_context_id": context_id, "roles": role_bundle},
            "schema_contract.json": schema_contract,
            "vendor_scoring_matrix.json": vendor_scoring_matrix,
            "business_profile_snapshot.json": profile_snapshot,
            "profile_compliance_matrix.json": compliance_matrix,
            "profile_override_log.json": profile_overrides,
            "down_select_recommendation.json": recommendation,
            "trace_map.json": evidence_trace_map,
            "scoring.json": vendor_scoring_matrix,
        }

        artifact_hashes = {name: _sha256_text(_canonical_json(payload)) for name, payload in artifacts_payloads.items()}
        leaves = [
            {"name": name, "hash": artifact_hashes[name], "leaf_hash": _sha256_text(f"{name}:{artifact_hashes[name]}")}
            for name in sorted(artifact_hashes)
        ]
        merkle = _build_merkle(leaves)
        pack_hash = _sha256_text("".join(artifact_hashes[name] for name in sorted(artifact_hashes)))

        manifest = {
            "execution_id": execution_id,
            "context_hash": context_hash,
            "profile_id": profile_id,
            "profile_hash": profile_snapshot["profile_hash"],
            "schema_id": schema_id,
            "schema_hash": schema_contract["schema_hash"],
            "pack_hash": pack_hash,
            "merkle": {
                "algorithm": "sha256",
                "leaf_canonicalization": "sha256(name + ':' + hash)",
                "leaf_count": len(leaves),
                "leaves": leaves,
                "merkle_root": merkle["root"],
            },
        }
        manifest_hash = _sha256_text(_canonical_json(manifest))
        manifest["manifest_hash"] = manifest_hash

        signing_payload = {
            "execution_id": execution_id,
            "pack_hash": pack_hash,
            "merkle_root": merkle["root"],
            "manifest_hash": manifest_hash,
            "signed_at": _utc_now(),
        }
        signing_payload_json = _canonical_json(signing_payload)
        sig_b64 = ""
        if signing_enabled:
            sig_b64 = base64.b64encode(private_key.sign(signing_payload_json.encode("utf-8"))).decode("utf-8")

        artifacts_payloads["governance_manifest.json"] = manifest
        artifacts_payloads["signed_export.sigmeta.json"] = {
            "signature_alg": "Ed25519",
            "signing_key_id": signing_key_id,
            "signed_at": signing_payload["signed_at"],
            "execution_id": execution_id,
            "pack_hash": pack_hash,
            "merkle_root": merkle["root"],
            "manifest_hash": manifest_hash,
            "signature": sig_b64,
            "signature_payload": signing_payload,
        }
        artifacts_payloads["signed_export.sig"] = sig_b64

        exec_dir = artifacts_dir / execution_id
        exec_dir.mkdir(exist_ok=True)
        for name, content in artifacts_payloads.items():
            fpath = exec_dir / name
            if isinstance(content, str):
                fpath.write_text(content, encoding="utf-8")
            else:
                fpath.write_text(json.dumps(content, indent=2), encoding="utf-8")

        record = _append_ledger(
            "GOVERNED_MULTI_ROLE_COMPILE",
            {
                "execution_id": execution_id,
                "pack_hash": pack_hash,
                "manifest_hash": manifest_hash,
                "merkle_root": merkle["root"],
            },
        )

        execution = {
            "execution_id": execution_id,
            "execution_context_id": context_id,
            "status": "VERIFIABLE",
            "strict_deterministic_mode": strict_deterministic_mode,
            "context_hash": context_hash,
            "pack_hash": pack_hash,
            "manifest_hash": manifest_hash,
            "merkle_root": merkle["root"],
            "ledger_record_hash": record["record_hash"],
            "signature": sig_b64,
            "signing_key_id": signing_key_id,
            "profile_id": profile_id,
            "schema_id": schema_id,
            "rp_levels": rp,
            "board_report": board_report,
            "evidence_trace_map": evidence_trace_map,
            "vendor_scoring_matrix": vendor_scoring_matrix,
            "down_select_recommendation": recommendation,
            "deterministic_compilation_log": deterministic_log,
            "schema_contract": schema_contract,
            "business_profile_snapshot": profile_snapshot,
            "profile_compliance_matrix": compliance_matrix,
            "profile_override_log": profile_overrides,
            "governance_manifest": manifest,
            "artifacts": sorted(list(artifacts_payloads.keys())),
            "created_at": _utc_now(),
        }
        executions[execution_id] = execution
        _persist_row(
            """INSERT OR REPLACE INTO executions(execution_id, profile_id, schema_id, status, pack_hash, manifest_hash, merkle_root, created_at, payload_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                execution_id,
                profile_id,
                schema_id,
                execution.get("status", "VERIFIABLE"),
                pack_hash,
                manifest_hash,
                merkle["root"],
                execution["created_at"],
                json.dumps(execution),
            ),
        )
        _log("Governed compile committed", execution_id=execution_id)

        return {
            "execution_id": execution_id,
            "context_hash": context_hash,
            "pack_hash": pack_hash,
            "manifest_hash": manifest_hash,
            "merkle_root": merkle["root"],
            "profile_id": profile_id,
            "schema_id": schema_id,
            "rp_levels": rp,
            "execution_state": {
                "signature_present": bool(sig_b64),
                "signing_enabled": signing_enabled,
            },
        }, 201

    @app.get("/health")
    def health() -> Any:
        return jsonify({"status": "OK", "timestamp": _utc_now()})

    @app.get("/admin/health")
    @_admin_protected
    def admin_health() -> Any:
        return jsonify(
            {
                "status": "OK",
                "strict_deterministic_mode": strict_deterministic_mode,
                "signing_enabled": signing_enabled,
                "signing_key_id": signing_key_id,
                "key_mode": key_mode,
                "ledger_record_count": len(ledger_logs),
                "timestamp": _utc_now(),
            }
        )

    @app.get("/admin/config")
    @_admin_protected
    def admin_config() -> Any:
        return jsonify(
            {
                "version": "v1.1.0",
                "runtime_model": ["flask-governance-runtime", "optional-node-ui-bridge"],
                "approved_schemas": sorted(approved_schemas),
                "profiles_count": len(profiles),
            }
        )

    @app.post("/api/human-input/role")
    def role_input() -> Any:
        payload = request.get_json(silent=True) or {}
        ok, error = _validate_role_payload(payload)
        if not ok:
            return jsonify(error), 400

        ctx = payload["execution_context_id"]
        role_inputs.setdefault(ctx, []).append(payload)
        _persist_row(
            "INSERT INTO role_inputs(execution_context_id, role, created_at, payload_json) VALUES (?, ?, ?, ?)",
            (ctx, str(payload.get("role", "")), _utc_now(), json.dumps(payload)),
        )
        _log(f"Role input accepted for {ctx}")
        return jsonify({"stored": True, "execution_context_id": ctx, "role_count": len(role_inputs[ctx])}), 201

    @app.get("/api/business-profiles")
    def business_profiles() -> Any:
        return jsonify({"profiles": profiles, "profiles_count": len(profiles)})

    @app.post("/api/governed-compile")
    def governed_compile() -> Any:
        payload = _normalize_compile_payload(request.get_json(silent=True) or {})
        ok, error = _validate_compile_payload(payload)
        if not ok:
            return jsonify(error), 400
        response, code = _build_execution(payload)
        return jsonify(response), code

    @app.post("/api/compile")
    def compile_alias() -> Any:
        response, code = _build_execution(request.get_json(silent=True) or {})
        return jsonify(response), code

    @app.post("/govern/decision")
    def govern_decision() -> Any:
        payload = _normalize_compile_payload(request.get_json(silent=True) or {})
        ok, error = _validate_compile_payload(payload)
        if not ok:
            return jsonify(error), 400
        response, code = _build_execution(payload)
        return jsonify(response), code

    @app.post("/api/impact/policy")
    def impact_policy() -> Any:
        payload = request.get_json(silent=True) or {}
        impact_text = str(payload.get("policy_text") or payload.get("text") or "")
        severity = "LOW"
        lowered = impact_text.lower()
        if any(term in lowered for term in ["critical", "outage", "breach", "safety"]):
            severity = "HIGH"
        elif any(term in lowered for term in ["risk", "degraded", "warning", "issue"]):
            severity = "MEDIUM"
        return jsonify(
            {
                "severity": severity,
                "impact_summary": {
                    "input_length": len(impact_text),
                    "keywords_detected": sorted(
                        keyword for keyword in ["critical", "outage", "breach", "safety", "risk", "degraded", "warning", "issue"]
                        if keyword in lowered
                    ),
                    "deterministic": True,
                },
            }
        )

    @app.get("/admin/executions")
    @_admin_protected
    def admin_executions() -> Any:
        page = max(int(request.args.get("page", 1)), 1)
        page_size = min(max(int(request.args.get("page_size", 20)), 1), 200)
        profile_id = request.args.get("profile_id")
        schema_id = request.args.get("schema_id")

        filtered = list(executions.values())
        if profile_id:
            filtered = [e for e in filtered if e.get("profile_id") == profile_id]
        if schema_id:
            filtered = [e for e in filtered if e.get("schema_id") == schema_id]

        total = len(filtered)
        start = (page - 1) * page_size
        end = start + page_size
        return jsonify({"executions": filtered[start:end], "page": page, "page_size": page_size, "total": total})

    @app.get("/admin/executions/<execution_id>/logs")
    @_admin_protected
    def admin_execution_logs(execution_id: str) -> Any:
        if execution_id not in executions:
            return jsonify({"error": "execution_not_found", "execution_id": execution_id}), 404
        _append_ledger("GOVERNANCE_AUDIT_ACCESS", {"access_type": "execution_logs", "execution_id": execution_id})
        return jsonify({"logs": execution_logs.get(execution_id, [])})

    @app.get("/admin/logs")
    @_admin_protected
    def admin_logs() -> Any:
        source = request.args.get("source", "backend")
        level = request.args.get("level")
        logs = backend_logs if source == "backend" else ledger_logs
        if level:
            logs = [l for l in logs if l.get("level") == level]
        _append_ledger("GOVERNANCE_AUDIT_ACCESS", {"access_type": "admin_logs", "source": source})
        return jsonify({"logs": logs})

    @app.get("/admin/logs/backend")
    @_admin_protected
    def admin_logs_backend() -> Any:
        return jsonify({"logs": backend_logs})

    @app.get("/admin/logs/ledger")
    @_admin_protected
    def admin_logs_ledger() -> Any:
        return jsonify({"logs": ledger_logs})

    @app.get("/admin/metrics")
    @_admin_protected
    def admin_metrics() -> Any:
        signed_recent = sum(1 for e in list(executions.values())[-5:] if e.get("signature"))
        route_metrics: dict[str, dict[str, Any]] = {}
        for route, stats in request_metrics.items():
            count = int(stats["count"])
            total_ms = float(stats["total_ms"])
            avg_ms = round(total_ms / count, 3) if count else 0.0
            route_metrics[route] = {
                "count": count,
                "errors": int(stats["errors"]),
                "avg_ms": avg_ms,
                "max_ms": round(float(stats["max_ms"]), 3),
            }
        return jsonify(
            {
                "health_status": "OK",
                "executions_total": len(executions),
                "signed_recent_executions": signed_recent,
                "ledger_record_count": len(ledger_logs),
                "routes": route_metrics,
                "last_updated": _utc_now(),
            }
        )

    @app.get("/executions/<execution_id>/diff/<other_execution_id>")
    def execution_diff(execution_id: str, other_execution_id: str) -> Any:
        base = executions.get(execution_id)
        other = executions.get(other_execution_id)
        if not base or not other:
            return jsonify({"error": "execution_not_found"}), 404
        base_sections = {s["title"]: s.get("content", "") for s in base.get("board_report", {}).get("sections", [])}
        other_sections = {s["title"]: s.get("content", "") for s in other.get("board_report", {}).get("sections", [])}
        all_titles = sorted(set(base_sections) | set(other_sections))
        section_diff = [
            {
                "title": title,
                "changed": base_sections.get(title) != other_sections.get(title),
                "left_present": title in base_sections,
                "right_present": title in other_sections,
            }
            for title in all_titles
        ]
        artifact_set_a = set(base.get("artifacts", []))
        artifact_set_b = set(other.get("artifacts", []))
        return jsonify(
            {
                "execution_id": execution_id,
                "other_execution_id": other_execution_id,
                "pack_hash_changed": base.get("pack_hash") != other.get("pack_hash"),
                "manifest_hash_changed": base.get("manifest_hash") != other.get("manifest_hash"),
                "artifacts_added": sorted(list(artifact_set_b - artifact_set_a)),
                "artifacts_removed": sorted(list(artifact_set_a - artifact_set_b)),
                "section_diff": section_diff,
            }
        )

    @app.get("/executions/<execution_id>/trace-map")
    def execution_trace_map(execution_id: str) -> Any:
        execution = executions.get(execution_id)
        if not execution:
            return jsonify({"error": "execution_not_found", "execution_id": execution_id}), 404
        return jsonify(execution["evidence_trace_map"])

    @app.get("/executions/<execution_id>/scoring")
    def execution_scoring(execution_id: str) -> Any:
        execution = executions.get(execution_id)
        if not execution:
            return jsonify({"error": "execution_not_found", "execution_id": execution_id}), 404
        return jsonify({"scoring": execution["vendor_scoring_matrix"], "recommendation": execution["down_select_recommendation"]})

    @app.get("/executions/<execution_id>/merkle")
    def execution_merkle(execution_id: str) -> Any:
        execution = executions.get(execution_id)
        if not execution:
            return jsonify({"error": "execution_not_found", "execution_id": execution_id}), 404
        return jsonify(execution["governance_manifest"]["merkle"])

    @app.get("/executions/<execution_id>/merkle/proof/<artefact_name>")
    def execution_merkle_proof(execution_id: str, artefact_name: str) -> Any:
        execution = executions.get(execution_id)
        if not execution:
            return jsonify({"error": "execution_not_found", "execution_id": execution_id}), 404
        leaves = execution["governance_manifest"]["merkle"]["leaves"]
        names = [l["name"] for l in leaves]
        if artefact_name not in names:
            return jsonify({"error": "artefact_not_found", "artefact_name": artefact_name}), 404
        index = names.index(artefact_name)
        leaf_hash = leaves[index]["leaf_hash"]
        levels = _build_merkle(leaves)["levels"]
        siblings = _merkle_proof(levels, index)
        return jsonify(
            {
                "artefact_name": artefact_name,
                "leaf_hash": leaf_hash,
                "index": index,
                "siblings": siblings,
                "merkle_root": execution["merkle_root"],
            }
        )

    @app.get("/verify/public-keys")
    def verify_public_keys() -> Any:
        data = json.loads(public_keys_file.read_text(encoding="utf-8"))
        return jsonify(data)

    @app.get("/verify/execution/<execution_id>")
    def verify_execution(execution_id: str) -> Any:
        execution = executions.get(execution_id)
        if not execution:
            return jsonify({"error": "execution_not_found", "execution_id": execution_id}), 404
        ledger_match = any(r.get("execution_id") == execution_id and r.get("pack_hash") == execution["pack_hash"] for r in ledger_logs)
        return jsonify(
            {
                "execution_id": execution_id,
                "pack_hash": execution["pack_hash"],
                "manifest_hash": execution["manifest_hash"],
                "merkle_root": execution["merkle_root"],
                "ledger_record_hash": execution["ledger_record_hash"],
                "signature_present": bool(execution.get("signature")),
                "status": "VERIFIABLE" if ledger_match else "NOT_VERIFIABLE",
                "ledger_match": ledger_match,
            }
        )

    @app.post("/verify/pack")
    def verify_pack() -> Any:
        payload = request.get_json(silent=True) or {}
        execution = executions.get(payload.get("execution_id"))
        if not execution:
            return jsonify({"error": "execution_not_found", "execution_id": payload.get("execution_id")}), 404

        sigmeta = {
            "execution_id": execution["execution_id"],
            "pack_hash": execution["pack_hash"],
            "merkle_root": execution["merkle_root"],
            "manifest_hash": execution["manifest_hash"],
            "signed_at": json.loads((artifacts_dir / execution["execution_id"] / "signed_export.sigmeta.json").read_text())["signed_at"],
        }
        signature_payload = _canonical_json(sigmeta)
        signature = base64.b64decode(execution["signature"])
        registry_data = json.loads(public_keys_file.read_text(encoding="utf-8"))
        registry_key = next(
            (
                k
                for k in registry_data.get("keys", [])
                if isinstance(k, dict)
                and k.get("key_id") == execution.get("signing_key_id")
                and k.get("algorithm") == "Ed25519"
            ),
            None,
        )
        if not registry_key:
            return jsonify({"signature_valid": False, "error": "signing_key_not_found", "overall_valid": False}), 400
        try:
            key_bytes = base64.b64decode(registry_key["public_key_b64"])
            Ed25519PublicKey.from_public_bytes(key_bytes).verify(signature, signature_payload.encode("utf-8"))
            signature_valid = True
        except Exception:
            signature_valid = False

        requested_pack_hash = payload.get("pack_hash", execution["pack_hash"])
        hash_valid = requested_pack_hash == execution["pack_hash"]
        manifest_consistent = payload.get("manifest_hash", execution["manifest_hash"]) == execution["manifest_hash"]
        return jsonify(
            {
                "signature_valid": signature_valid,
                "hash_valid": hash_valid,
                "manifest_consistent": manifest_consistent,
                "overall_valid": bool(signature_valid and hash_valid and manifest_consistent),
            }
        )

    @app.post("/verify/merkle-proof")
    def verify_merkle_proof() -> Any:
        payload = request.get_json(silent=True) or {}
        siblings = payload.get("siblings", [])
        if not isinstance(siblings, list):
            return jsonify({"error": "invalid_siblings", "message": "siblings must be an array"}), 400

        try:
            index = int(payload.get("index", 0))
        except (TypeError, ValueError):
            return jsonify({"error": "invalid_index", "message": "index must be an integer"}), 400

        valid = _verify_merkle_proof(
            leaf_hash=payload.get("leaf_hash", ""),
            siblings=siblings,
            index=index,
            merkle_root=payload.get("merkle_root", ""),
        )
        return jsonify({"proof_valid": valid})

    @app.post("/verify/replay")
    def verify_replay() -> Any:
        payload = request.get_json(silent=True) or {}
        required = ["execution_context_id", "profile_id", "schema_id", "reasoning_level", "policy_level"]
        missing = [k for k in required if k not in payload]
        if missing:
            return jsonify({"error": "missing_fields", "missing": missing}), 400

        context_id = payload["execution_context_id"]
        role_bundle = role_inputs.get(context_id, [])
        seed_payload = {
            "context_id": context_id,
            "profile_id": payload["profile_id"],
            "profile_hash": profiles_by_id.get(payload["profile_id"], {}).get("profile_hash"),
            "schema_id": payload["schema_id"],
            "schema_version": payload.get("schema_version", "1.0.0"),
            "rp": {
                "reasoning_level": payload["reasoning_level"],
                "policy_level": payload["policy_level"],
            },
            "role_bundle": role_bundle,
            "request_payload": payload,
        }
        context_hash = _sha256_text(_canonical_json(seed_payload))
        expected_execution_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"diiac:{context_hash}"))
        actual = executions.get(expected_execution_id)
        replay_valid = bool(strict_deterministic_mode and actual is not None)

        certificate = {
            "execution_context_id": context_id,
            "expected_execution_id": expected_execution_id,
            "context_hash": context_hash,
            "replay_valid": replay_valid,
            "strict_deterministic_mode": strict_deterministic_mode,
            "verified_at": _utc_now(),
            "pack_hash": actual.get("pack_hash") if actual else None,
        }
        cert_dir = artifacts_dir / (expected_execution_id if actual else f"replay-{context_hash[:12]}")
        cert_dir.mkdir(parents=True, exist_ok=True)
        cert_path = cert_dir / "replay_certificate.json"
        cert_path.write_text(json.dumps(certificate, indent=2), encoding="utf-8")
        return jsonify({**certificate, "certificate_path": str(cert_path)})

    @app.get("/trust/status")
    def trust_status() -> Any:
        latest = ledger_logs[-1] if ledger_logs else None
        return jsonify(
            {
                "ledger_records": len(ledger_logs),
                "latest_record_hash": latest["record_hash"] if latest else None,
                "latest_merkle_root": latest.get("merkle_root") if latest else None,
            }
        )

    def _prepare_export_files(execution_id: str) -> tuple[Path, Path, Path, dict[str, Any]]:
        execution = executions[execution_id]
        pack_dir = artifacts_dir / execution_id
        zip_path = exports_dir / f"decision-pack_{execution_id}.zip"
        sig_path = exports_dir / f"decision-pack_{execution_id}.sig"
        sigmeta_path = exports_dir / f"decision-pack_{execution_id}.sigmeta.json"

        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for p in sorted(pack_dir.iterdir()):
                zf.write(p, arcname=p.name)

        zip_bytes = zip_path.read_bytes()
        zip_sha256 = _sha256_bytes(zip_bytes)
        signature = private_key.sign(zip_bytes)
        sig_b64 = base64.b64encode(signature).decode("utf-8")
        sig_path.write_text(sig_b64, encoding="utf-8")

        sigmeta = {
            "signature_alg": "Ed25519",
            "signing_key_id": signing_key_id,
            "signed_at": _utc_now(),
            "zip_sha256": zip_sha256,
            "execution_id": execution_id,
            "pack_hash": execution["pack_hash"],
            "merkle_root": execution["merkle_root"],
            "manifest_hash": execution["manifest_hash"],
        }
        sigmeta_path.write_text(json.dumps(sigmeta, indent=2), encoding="utf-8")
        return zip_path, sig_path, sigmeta_path, sigmeta

    @app.get("/decision-pack/<execution_id>/export")
    def export_pack(execution_id: str) -> Any:
        if execution_id not in executions:
            return jsonify({"error": "execution_not_found", "execution_id": execution_id}), 404
        zip_path, _, _, _ = _prepare_export_files(execution_id)
        return send_file(zip_path, as_attachment=True, download_name=f"decision-pack_{execution_id}.zip")

    @app.get("/decision-pack/<execution_id>/export-signed")
    def export_signed(execution_id: str) -> Any:
        if execution_id not in executions:
            return jsonify({"error": "execution_not_found", "execution_id": execution_id}), 404

        zip_path, sig_path, sigmeta_path, sigmeta = _prepare_export_files(execution_id)
        return jsonify({"zip_path": str(zip_path), "sig_path": str(sig_path), "sigmeta_path": str(sigmeta_path), "sigmeta": sigmeta})

    @app.post("/admin/audit-export")
    @_admin_protected
    def admin_audit_export() -> Any:
        payload = request.get_json(silent=True) or {}
        execution_ids = payload.get("execution_ids") or list(executions.keys())
        selected = [executions[e] for e in execution_ids if e in executions]
        if not selected:
            return jsonify({"error": "no_executions_selected"}), 400

        audit_id = f"audit-{uuid.uuid4().hex[:12]}"
        out = audit_dir / f"{audit_id}.json"
        verify_snapshots = [
            {
                "execution_id": e["execution_id"],
                "pack_hash": e["pack_hash"],
                "merkle_root": e["merkle_root"],
                "manifest_hash": e["manifest_hash"],
                "signature_present": bool(e.get("signature")),
            }
            for e in selected
        ]
        bundle = {
            "audit_manifest": {
                "audit_export_id": audit_id,
                "generated_at": _utc_now(),
                "execution_ids": execution_ids,
            },
            "ledger_slice": [l for l in ledger_logs if l.get("execution_id") in execution_ids],
            "verify_execution_snapshots": verify_snapshots,
            "logs": [l for l in backend_logs if l.get("execution_id") in execution_ids or l.get("execution_id") is None][-200:],
        }
        out.write_text(json.dumps(bundle, indent=2), encoding="utf-8")
        created_at = _utc_now()
        audit_exports[audit_id] = {"path": str(out), "created_at": created_at}
        _persist_row(
            "INSERT OR REPLACE INTO audit_exports(audit_export_id, created_at, path, payload_json) VALUES (?, ?, ?, ?)",
            (audit_id, created_at, str(out), json.dumps(bundle)),
        )
        _append_ledger("GOVERNANCE_AUDIT_ACCESS", {"access_type": "audit_export", "audit_export_id": audit_id})
        return jsonify({"audit_export_id": audit_id, "download_url": f"/admin/audit/exports/{audit_id}/download"}), 201

    @app.post("/admin/audit/exports")
    @_admin_protected
    def admin_audit_exports_alias() -> Any:
        return admin_audit_export()

    @app.get("/admin/audit/exports/<export_id>/download")
    @_admin_protected
    def download_audit(export_id: str) -> Any:
        entry = audit_exports.get(export_id)
        if not entry:
            return jsonify({"error": "audit_export_not_found", "audit_export_id": export_id}), 404
        return send_file(entry["path"], as_attachment=True)

    @app.get("/admin/audit-export/<export_id>/download")
    @_admin_protected
    def download_audit_alias(export_id: str) -> Any:
        return download_audit(export_id)

    @app.get("/admin/db/status")
    @_admin_protected
    def admin_db_status() -> Any:
        key_registry_ok = False
        try:
            registry = json.loads(public_keys_file.read_text(encoding="utf-8"))
            key_registry_ok = isinstance(registry, dict) and isinstance(registry.get("keys"), list)
        except Exception:
            key_registry_ok = False

        profiles_integrity = {
            "total": len(profiles),
            "invalid": sum(1 for p in profiles if "profile_id" not in p or "profile_hash" not in p),
        }
        with _db_conn() as conn:
            tables = ["role_inputs", "executions", "backend_logs", "ledger_logs", "audit_exports"]
            counts = {t: conn.execute(f"SELECT COUNT(*) as c FROM {t}").fetchone()["c"] for t in tables}
        return jsonify(
            {
                "db_path": str(db_path),
                "tables": counts,
                "integrity": {
                    "key_registry_ok": key_registry_ok,
                    "profiles": profiles_integrity,
                },
            }
        )

    @app.get("/admin/db/table/<table_name>")
    @_admin_protected
    def admin_db_table(table_name: str) -> Any:
        allowed = {"role_inputs", "executions", "backend_logs", "ledger_logs", "audit_exports"}
        if table_name not in allowed:
            return jsonify({"error": "table_not_allowed", "table": table_name}), 400
        limit = min(max(int(request.args.get("limit", 50)), 1), 500)
        with _db_conn() as conn:
            rows = [dict(r) for r in conn.execute(f"SELECT * FROM {table_name} ORDER BY ROWID DESC LIMIT ?", (limit,)).fetchall()]
        return jsonify({"table": table_name, "limit": limit, "rows": rows})

    @app.post("/admin/db/maintenance/compact")
    @_admin_protected
    def admin_db_compact() -> Any:
        with _db_conn() as conn:
            conn.execute("VACUUM")
        return jsonify({"status": "ok", "operation": "vacuum", "timestamp": _utc_now()})

    @app.get("/trust")
    def trust_alias() -> Any:
        return trust_status()

    @app.post("/api/human-input")
    def human_input_alias() -> Any:
        payload = request.get_json(silent=True) or {}
        text = payload.get("text", "")
        if not isinstance(text, str):
            return jsonify({"error": "invalid_text"}), 400
        _log("Human input accepted")
        return jsonify({"accepted": True, "length": len(text)}), 201

    @app.get("/executions/<execution_id>/reports")
    def execution_reports(execution_id: str) -> Any:
        execution = executions.get(execution_id)
        if not execution:
            return jsonify({"error": "execution_not_found", "execution_id": execution_id}), 404
        return jsonify({"execution_id": execution_id, "reports": execution.get("artifacts", [])})

    return app


if __name__ == "__main__":
    create_app().run(host="0.0.0.0", port=8000)
