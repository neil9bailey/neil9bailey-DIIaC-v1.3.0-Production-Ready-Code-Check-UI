from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import re
import sqlite3
import threading
import uuid
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from cryptography.exceptions import InvalidSignature, UnsupportedAlgorithm
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from flask import Flask, jsonify, request, send_file
from persistence import StateStore


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _parse_utc_timestamp(value: str | None) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    candidate = value.strip()
    if candidate.endswith("Z"):
        candidate = f"{candidate[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _canonical_json(data: Any) -> str:
    return json.dumps(data, sort_keys=True, separators=(",", ":"))


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _load_profiles(profile_dir: Path) -> list[dict[str, Any]]:
    profiles: list[dict[str, Any]] = []
    for p in sorted(profile_dir.glob("*_profile_v1.json")):
        profile = json.loads(p.read_text(encoding="utf-8"))
        profile["profile_hash"] = _sha256_text(_canonical_json(profile))
        profile["file"] = p.name
        profiles.append(profile)
    return profiles


def _load_policy_packs(policy_pack_dir: Path) -> list[dict[str, Any]]:
    packs: list[dict[str, Any]] = []
    for p in sorted(policy_pack_dir.glob("*_v1.json")):
        try:
            payload = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(payload, dict):
            continue
        controls = payload.get("controls")
        if not isinstance(controls, list) or not controls:
            continue
        payload["pack_hash"] = _sha256_text(_canonical_json(payload))
        payload["file"] = p.name
        packs.append(payload)
    return packs


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
        pem_bytes = pem.strip().encode("utf-8")
        try:
            key = serialization.load_pem_private_key(pem_bytes, password=None)
        except (ValueError, TypeError, UnsupportedAlgorithm) as exc:
            raise ValueError(
                f"SIGNING_PRIVATE_KEY_PEM is set but contains invalid key data: {exc}. "
                "Ensure the value is a valid PEM-encoded Ed25519 private key. "
                "Generate one with: openssl genpkey -algorithm ed25519 -out signing_key.pem"
            ) from exc
        if not isinstance(key, Ed25519PrivateKey):
            raise ValueError(
                f"SIGNING_PRIVATE_KEY_PEM must be an Ed25519 key, "
                f"got {type(key).__name__}. Generate one with: "
                "openssl genpkey -algorithm ed25519 -out signing_key.pem"
            )
        return key, "configured"
    return Ed25519PrivateKey.generate(), "ephemeral"


def _runtime_error(
    error_code: str, message: str,
    dependency: str | None = None,
    details: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], int]:
    payload: dict[str, Any] = {
        "error": "runtime_dependency_failure",
        "error_code": error_code,
        "message": message,
    }
    if dependency:
        payload["dependency"] = dependency
    if details:
        payload["details"] = details
    return payload, 503


def create_app() -> Flask:
    app = Flask(__name__)

    def _env_int(name: str, default: int, minimum: int = 0, maximum: int | None = None) -> int:
        raw = os.getenv(name, str(default))
        try:
            parsed = int(raw)
        except (TypeError, ValueError):
            return default
        if parsed < minimum:
            return minimum
        if maximum is not None and parsed > maximum:
            return maximum
        return parsed

    def _env_float(name: str, default: float, minimum: float = 0.0, maximum: float | None = None) -> float:
        raw = os.getenv(name, str(default))
        try:
            parsed = float(raw)
        except (TypeError, ValueError):
            return default
        if parsed < minimum:
            return minimum
        if maximum is not None and parsed > maximum:
            return maximum
        return parsed

    strict_deterministic_mode = os.getenv("STRICT_DETERMINISTIC_MODE", "false").lower() == "true"
    signing_enabled = os.getenv("SIGNING_ENABLED", "true").lower() != "false"
    signing_key_id = os.getenv("SIGNING_KEY_ID", "ephemeral-local-ed25519")
    signature_payload_schema_version = (
        os.getenv("SIGNATURE_PAYLOAD_SCHEMA_VERSION", "diiac-signature-payload-v1").strip()
        or "diiac-signature-payload-v1"
    )

    admin_auth_enabled = os.getenv("ADMIN_AUTH_ENABLED", "true").lower() != "false"
    runtime_env = os.getenv("APP_ENV", "production").lower()
    dev_runtime_envs = {"dev", "development", "local", "test"}
    is_dev_runtime = runtime_env in dev_runtime_envs
    allow_ephemeral_signing = is_dev_runtime
    trust_registry_mode = (
        os.getenv("TRUST_REGISTRY_MODE", "auto_dev" if is_dev_runtime else "external").strip().lower()
        or ("auto_dev" if is_dev_runtime else "external")
    )
    allow_registry_autoregister = is_dev_runtime and trust_registry_mode != "external"
    external_trust_registry = (
        trust_registry_mode == "external"
        or os.getenv("EXTERNAL_TRUST_REGISTRY", "false").lower() == "true"
    )
    app_version = os.getenv("APP_VERSION", "v1.3.0-ui")
    admin_api_token = os.getenv("ADMIN_API_TOKEN", "")
    profile_lock_id = (os.getenv("DIIAC_PROFILE_LOCK_ID", "") or "").strip()
    required_governance_modes = [
        "FIRST-PRINCIPLES MODE",
        "DEVIL'S ADVOCATE MODE",
        "CONSTRAINTS-FIRST MODE",
    ]
    policy_pack_enforce = os.getenv("POLICY_PACK_ENFORCE", "true").lower() != "false"
    evidence_min_strong_refs = _env_int("EVIDENCE_MIN_STRONG_REFS", default=2, minimum=0, maximum=10)
    evidence_min_claim_coverage = _env_float("EVIDENCE_MIN_CLAIM_COVERAGE", default=0.6, minimum=0.0, maximum=1.0)
    evidence_require_fresh_llm = os.getenv("EVIDENCE_REQUIRE_FRESH_LLM", "true").lower() != "false"
    llm_audit_min_timestamp = (
        _parse_utc_timestamp(os.getenv("LLM_AUDIT_MIN_TIMESTAMP", "2025-01-01T00:00:00+00:00"))
        or datetime(2025, 1, 1, tzinfo=UTC)
    )

    private_key, key_mode = _load_or_create_signing_key()
    if signing_enabled and key_mode == "ephemeral" and not allow_ephemeral_signing:
        raise RuntimeError(
            "SIGNING_PRIVATE_KEY_PEM must be configured for non-development environments; "
            "ephemeral signing is disabled."
        )
    public_key = private_key.public_key()
    public_key_b64 = base64.b64encode(
        public_key.public_bytes(encoding=serialization.Encoding.Raw, format=serialization.PublicFormat.Raw)
    ).decode("utf-8")

    artifacts_dir = Path.cwd() / "artifacts"
    exports_dir = Path.cwd() / "exports"
    audit_dir = Path.cwd() / "audit_exports"
    keys_dir = Path.cwd() / "contracts" / "keys"
    profiles_dir = Path.cwd() / "contracts" / "business-profiles"
    policy_pack_dir = Path.cwd() / "contracts" / "policy-packs"
    state_dir = Path.cwd() / "state"
    for d in [artifacts_dir, exports_dir, audit_dir, keys_dir, profiles_dir, policy_pack_dir, state_dir]:
        d.mkdir(parents=True, exist_ok=True)

    db_path = os.getenv("DIIAC_STATE_DB", str(state_dir / "diiac_state.db"))
    store = StateStore(db_path)

    public_keys_file = keys_dir / "public_keys.json"
    local_dev_key_ids = {"ephemeral-local-ed25519", "diiac-local-dev", "local-dev-ed25519"}
    key_registry_file_exists = public_keys_file.exists()
    if key_registry_file_exists:
        try:
            key_registry = json.loads(public_keys_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            key_registry = {"keys": []}
    else:
        key_registry = {"keys": []}

    raw_keys = key_registry.get("keys")
    if not isinstance(raw_keys, list):
        raw_keys = []

    registry_structural_issues = False
    normalized_keys: list[dict[str, Any]] = []
    seen_key_ids: set[str] = set()
    for entry in raw_keys:
        if not isinstance(entry, dict):
            registry_structural_issues = True
            continue
        key_id = str(entry.get("key_id", "")).strip()
        entry_public_key = str(entry.get("public_key_b64", "")).strip()
        if not key_id or not entry_public_key:
            registry_structural_issues = True
            continue
        if key_id in seen_key_ids:
            registry_structural_issues = True
            continue
        seen_key_ids.add(key_id)
        normalized_keys.append(
            {
                "key_id": key_id,
                "algorithm": "Ed25519",
                "public_key_b64": entry_public_key,
            }
        )

    active_key_in_registry_file = any(entry.get("key_id") == signing_key_id for entry in normalized_keys)
    registry_updated = False
    key_registry_update_performed = False
    if allow_registry_autoregister:
        if not active_key_in_registry_file:
            normalized_keys.append(
                {
                    "key_id": signing_key_id,
                    "algorithm": "Ed25519",
                    "public_key_b64": public_key_b64,
                }
            )
            registry_updated = True
            active_key_in_registry_file = True
        for entry in normalized_keys:
            if entry.get("key_id") != signing_key_id:
                continue
            if entry.get("algorithm") != "Ed25519":
                entry["algorithm"] = "Ed25519"
                registry_updated = True
            if entry.get("public_key_b64") != public_key_b64:
                entry["public_key_b64"] = public_key_b64
                registry_updated = True
            break
        key_registry["keys"] = normalized_keys
        if (not key_registry_file_exists) or registry_updated or registry_structural_issues:
            public_keys_file.write_text(json.dumps(key_registry, indent=2), encoding="utf-8")
            key_registry_update_performed = True
    else:
        key_registry["keys"] = normalized_keys

    active_entry = next((entry for entry in normalized_keys if entry.get("key_id") == signing_key_id), None)
    active_key_registered = active_entry is not None
    active_key_matches_public = bool(active_entry and active_entry.get("public_key_b64") == public_key_b64)
    registered_key_count = len(
        [entry for entry in normalized_keys if isinstance(entry, dict) and entry.get("key_id")]
    )
    local_or_ephemeral_signing = (key_mode != "configured") or (signing_key_id in local_dev_key_ids)
    if not signing_enabled:
        trust_source = "signing_disabled"
    elif local_or_ephemeral_signing:
        trust_source = "dev_local_signing"
    elif external_trust_registry:
        trust_source = "external_trust_registry"
    else:
        trust_source = "managed_signing"

    production_trust_ready = bool(
        signing_enabled
        and key_mode == "configured"
        and active_key_registered
        and active_key_matches_public
        and registered_key_count > 0
        and trust_source in {"managed_signing", "external_trust_registry"}
    )
    signing_trust_warnings: list[str] = []
    if signing_enabled and local_or_ephemeral_signing:
        signing_trust_warnings.append(
            "Signing key is local/ephemeral. Configure managed production key material before live deployment."
        )
    if signing_enabled and not active_key_registered:
        signing_trust_warnings.append("Active signing key is not present in contracts key registry.")
    if signing_enabled and active_key_registered and not active_key_matches_public:
        signing_trust_warnings.append(
            "Active signing key entry does not match runtime key material."
        )
    if signing_enabled and registry_structural_issues:
        signing_trust_warnings.append(
            "Public key registry contains invalid/duplicate entries and should be remediated."
        )
    if signing_enabled and key_registry_update_performed and allow_registry_autoregister:
        signing_trust_warnings.append(
            "Signing trust registry was auto-updated in development mode; this path is disabled for non-dev environments."
        )

    if signing_enabled and not is_dev_runtime:
        if key_mode != "configured":
            raise RuntimeError(
                "Non-development runtime requires SIGNING_PRIVATE_KEY_PEM. Ephemeral signing is blocked."
            )
        if not active_key_registered:
            raise RuntimeError(
                f"Signing key '{signing_key_id}' is not present in contracts/keys/public_keys.json."
            )
        if not active_key_matches_public:
            raise RuntimeError(
                f"Signing key '{signing_key_id}' does not match registered public key material."
            )

    profiles = _load_profiles(profiles_dir)
    profiles_by_id = {p["profile_id"]: p for p in profiles}
    policy_packs = _load_policy_packs(policy_pack_dir)

    def _readiness_checks() -> dict[str, Any]:
        checks = {
            "artifact_storage": artifacts_dir.exists() and artifacts_dir.is_dir() and os.access(artifacts_dir, os.W_OK),
            "export_storage": exports_dir.exists() and exports_dir.is_dir() and os.access(exports_dir, os.W_OK),
            "audit_storage": audit_dir.exists() and audit_dir.is_dir() and os.access(audit_dir, os.W_OK),
            "contracts_profiles": profiles_dir.exists() and profiles_dir.is_dir() and len(profiles) > 0,
            "contracts_keys": (
                public_keys_file.exists()
                and registered_key_count > 0
                and active_key_registered
                and active_key_matches_public
            ),
            "policy_packs_loaded": policy_pack_dir.exists() and policy_pack_dir.is_dir() and len(policy_packs) > 0,
            "signing_trust_ready": (not signing_enabled) or production_trust_ready,
        }
        checks["database"] = store.is_healthy()
        hard_failures = [v for v in checks.values() if v is False]
        return {
            "overall_ready": len(hard_failures) == 0,
            "checks": checks,
        }

    backend_logs: list[dict[str, Any]] = store.load_all_backend_logs()
    ledger_logs: list[dict[str, Any]] = store.load_all_ledger_records()
    ledger_append_lock = threading.Lock()
    executions: dict[str, dict[str, Any]] = store.load_all_executions()
    role_inputs: dict[str, list[dict[str, Any]]] = store.load_all_role_inputs()
    audit_exports: dict[str, dict[str, Any]] = store.load_all_audit_exports()
    execution_logs: dict[str, list[dict[str, Any]]] = {}
    for evt in backend_logs:
        if evt.get("execution_id"):
            execution_logs.setdefault(evt["execution_id"], []).append(evt)
    # Verify ledger hash chain integrity on restore
    ledger_chain_valid = True
    for i, record in enumerate(ledger_logs):
        expected_prev = ledger_logs[i - 1]["record_hash"] if i > 0 else "0" * 64
        if record.get("previous_record_hash") != expected_prev:
            ledger_chain_valid = False
            break

    approved_schemas = {
        "GENERAL_SOLUTION_BOARD_REPORT_V1", "RFQ_TEMPLATE_V1",
        "SLA_SCHEDULE_V1", "TECHNICAL_SOLUTION_BOARD_REPORT_V1",
    }

    ROLE_FIELD_MAX = 64
    CONTEXT_ID_MAX = 128
    LIST_ITEM_MAX = 512
    LIST_MAX_ITEMS = 50
    HUMAN_TEXT_MAX = 8000
    EXECUTION_IDS_MAX = 100

    def _validate_string_field(
        payload: dict[str, Any], field: str, max_len: int,
    ) -> tuple[dict[str, Any], int] | None:
        value = payload.get(field)
        if not isinstance(value, str):
            return {"error": "invalid_field_type", "field": field, "expected": "string"}, 400
        if not value.strip():
            return {"error": "invalid_field", "field": field, "message": "must be non-empty"}, 400
        if len(value) > max_len:
            return {"error": "field_too_long", "field": field, "max_length": max_len}, 400
        return None

    def _validate_string_list_field(
        payload: dict[str, Any], field: str,
        max_items: int = LIST_MAX_ITEMS,
        max_item_len: int = LIST_ITEM_MAX,
    ) -> tuple[dict[str, Any], int] | None:
        value = payload.get(field)
        if not isinstance(value, list):
            return {"error": "invalid_field", "field": field}, 400
        if len(value) > max_items:
            return {"error": "list_too_long", "field": field, "max_items": max_items}, 400
        for item in value:
            if not isinstance(item, str):
                return {"error": "invalid_list_item_type", "field": field, "expected": "string"}, 400
            if not item.strip():
                return {"error": "invalid_list_item", "field": field, "message": "items must be non-empty strings"}, 400
            if len(item) > max_item_len:
                return {"error": "list_item_too_long", "field": field, "max_item_length": max_item_len}, 400
        return None

    def _validate_compile_payload(payload: dict[str, Any]) -> tuple[dict[str, Any], int] | None:
        for f, max_len in {
            "execution_context_id": CONTEXT_ID_MAX,
            "profile_id": CONTEXT_ID_MAX,
            "schema_id": CONTEXT_ID_MAX,
            "schema_version": 32,
            "reasoning_level": 8,
            "policy_level": 8,
        }.items():
            if f in payload and payload.get(f) is not None:
                err = _validate_string_field(payload, f, max_len)
                if err:
                    return err
        if "controls" in payload:
            err = _validate_string_list_field(payload, "controls")
            if err:
                return err
        if "governance_modes" in payload:
            err = _validate_string_list_field(payload, "governance_modes")
            if err:
                return err
        return None

    def _normalize_string_list(value: Any) -> list[str]:
        if isinstance(value, list):
            return [item.strip() for item in value if isinstance(item, str) and item.strip()]
        if isinstance(value, str) and value.strip():
            return [value.strip()]
        return []

    def _normalize_governance_modes(raw_modes: Any) -> tuple[list[str], list[str]]:
        seen: set[str] = set()
        normalized: list[str] = []
        if isinstance(raw_modes, list):
            for mode in raw_modes:
                if not isinstance(mode, str):
                    continue
                item = mode.strip()
                if not item:
                    continue
                key = item.upper()
                if key in seen:
                    continue
                seen.add(key)
                normalized.append(item)
        auto_added: list[str] = []
        for required_mode in required_governance_modes:
            key = required_mode.upper()
            if key in seen:
                continue
            normalized.append(required_mode)
            seen.add(key)
            auto_added.append(required_mode)
        return normalized, auto_added

    def _role_input_idempotency_key(payload: dict[str, Any]) -> str:
        provided_key = payload.get("idempotency_key")
        if isinstance(provided_key, str) and provided_key.strip():
            return provided_key.strip()[:128]
        normalized_payload = {
            "execution_context_id": str(payload.get("execution_context_id", "")).strip().lower(),
            "role": str(payload.get("role", "")).strip().lower(),
            "domain": str(payload.get("domain", "")).strip().lower(),
            "assertions": _normalize_string_list(payload.get("assertions")),
            "non_negotiables": _normalize_string_list(payload.get("non_negotiables")),
            "risk_flags": _normalize_string_list(payload.get("risk_flags")),
            "evidence_refs": _normalize_string_list(payload.get("evidence_refs")),
        }
        return f"role-{_sha256_text(_canonical_json(normalized_payload))[:24]}"

    def _validate_replay_payload(payload: dict[str, Any]) -> tuple[dict[str, Any], int] | None:
        required_fields = {
            "execution_context_id": CONTEXT_ID_MAX,
            "profile_id": CONTEXT_ID_MAX,
            "schema_id": CONTEXT_ID_MAX,
            "reasoning_level": 8,
            "policy_level": 8,
        }
        missing = [field for field in required_fields if field not in payload]
        if missing:
            return {"error": "missing_fields", "missing": missing}, 400

        for field, max_len in required_fields.items():
            err = _validate_string_field(payload, field, max_len)
            if err:
                return err

        if "schema_version" in payload and payload.get("schema_version") is not None:
            err = _validate_string_field(payload, "schema_version", 32)
            if err:
                return err

        if "governance_modes" in payload:
            err = _validate_string_list_field(payload, "governance_modes")
            if err:
                return err

        return None

    def _event_id(message: str, level: str) -> str:
        key = f"{level}:{message}"
        return f"EVT-{_sha256_text(key)[:12].upper()}"

    def _log(message: str, level: str = "INFO", execution_id: str | None = None) -> None:
        evt = {
            "timestamp": _utc_now(),
            "level": level,
            "event_id": _event_id(message, level),
            "message": message,
            "execution_id": execution_id,
        }
        backend_logs.append(evt)
        store.append_backend_log(evt)
        if execution_id:
            execution_logs.setdefault(execution_id, []).append(evt)

    def _append_ledger(event_type: str, payload: dict[str, Any]) -> dict[str, Any]:
        nonlocal ledger_chain_valid
        with ledger_append_lock:
            for _ in range(2):
                latest_record = store.load_latest_ledger_record()
                prev = latest_record["record_hash"] if latest_record else "0" * 64
                next_record_id = int(latest_record["record_id"]) + 1 if latest_record else 1
                record_core = {
                    "record_id": next_record_id,
                    "timestamp": _utc_now(),
                    "event_type": event_type,
                    "previous_record_hash": prev,
                    **payload,
                }
                record_hash = _sha256_text(_canonical_json(record_core))
                record = {**record_core, "record_hash": record_hash}
                try:
                    store.append_ledger_record(record)
                except sqlite3.IntegrityError:
                    continue

                # If runtime memory is out-of-sync with persisted ledger, refresh.
                if not ledger_logs or ledger_logs[-1].get("record_hash") != prev:
                    ledger_logs[:] = store.load_all_ledger_records()
                else:
                    ledger_logs.append(record)

                # Keep chain validity flag current after successful append
                ledger_chain_valid = True
                return record
        raise RuntimeError("Ledger append failed after retry due to record_id contention.")

    def _build_signature_payload(
        *,
        execution_id: str,
        pack_hash: str,
        merkle_root: str,
        manifest_hash: str,
        signed_at: str,
    ) -> dict[str, str]:
        return {
            "signature_payload_schema_version": signature_payload_schema_version,
            "signature_scope": "execution_manifest",
            "execution_id": execution_id,
            "pack_hash": pack_hash,
            "merkle_root": merkle_root,
            "manifest_hash": manifest_hash,
            "signed_at": signed_at,
        }

    def _resolve_public_key_for_key_id(key_id: str) -> tuple[Ed25519PublicKey | None, str | None]:
        if not isinstance(key_id, str) or not key_id.strip():
            return None, "missing_signing_key_id"
        key_entry = next(
            (
                entry for entry in key_registry.get("keys", [])
                if isinstance(entry, dict) and entry.get("key_id") == key_id
            ),
            None,
        )
        if not key_entry:
            return None, "signing_key_not_registered"
        public_key_b64 = key_entry.get("public_key_b64")
        if not isinstance(public_key_b64, str) or not public_key_b64.strip():
            return None, "invalid_registered_public_key"
        try:
            public_key_bytes = base64.b64decode(public_key_b64)
        except Exception:
            return None, "invalid_registered_public_key"
        try:
            return Ed25519PublicKey.from_public_bytes(public_key_bytes), None
        except Exception:
            return None, "invalid_registered_public_key"

    def _canonical_signature_payload_bytes(signature_payload: Any) -> tuple[bytes | None, str | None, str | None]:
        if not isinstance(signature_payload, dict):
            return None, "invalid_signature_payload", None
        schema_version = signature_payload.get("signature_payload_schema_version")
        if not isinstance(schema_version, str) or not schema_version.strip():
            return None, "missing_signature_payload_schema_version", None
        canonical = _canonical_json(signature_payload)
        return canonical.encode("utf-8"), None, schema_version.strip()

    def _verify_signature_contract(
        *,
        signature_payload: Any,
        signature_b64: str,
        signing_key_id_value: str,
    ) -> dict[str, Any]:
        verification = {
            "verified": False,
            "verified_at": _utc_now(),
            "error": None,
            "signing_key_id": signing_key_id_value,
            "payload_schema_version": None,
            "trust_source": trust_source,
        }
        if not signing_enabled:
            verification["error"] = "signing_disabled"
            return verification
        if not isinstance(signature_b64, str) or not signature_b64.strip():
            verification["error"] = "missing_signature"
            return verification
        payload_bytes, payload_error, schema_version = _canonical_signature_payload_bytes(signature_payload)
        verification["payload_schema_version"] = schema_version
        if payload_error:
            verification["error"] = payload_error
            return verification
        public_key_for_verify, key_error = _resolve_public_key_for_key_id(signing_key_id_value)
        if key_error:
            verification["error"] = key_error
            return verification
        try:
            signature_bytes = base64.b64decode(signature_b64)
        except Exception:
            verification["error"] = "invalid_signature_encoding"
            return verification
        try:
            public_key_for_verify.verify(signature_bytes, payload_bytes)
            verification["verified"] = True
            return verification
        except InvalidSignature:
            verification["error"] = "invalid_signature"
            return verification

    def _deterministic_score(seed: str, label: str) -> float:
        val = int(_sha256_text(f"{seed}:{label}")[:8], 16)
        return round(50 + (val % 5000) / 100, 2)

    def _enforce_sections(required_sections: list[str], draft_sections: list[dict[str, str]]) -> list[dict[str, str]]:
        by_title = {s["title"]: s for s in draft_sections}
        return [
            by_title.get(title, {"title": title, "content": "PLACEHOLDER: deterministically enforced missing section."})
            for title in required_sections
        ]

    def _first_non_empty(values: list[str], default: str) -> str:
        for value in values:
            if isinstance(value, str) and value.strip():
                return value.strip()
        return default

    def _vendor_identity_key(vendor_name: str) -> str:
        key = re.sub(r"[^a-z0-9]+", " ", vendor_name.lower()).strip()
        alias_prefixes = {
            "fortinet secure sd wan": "fortinet",
            "palo alto networks prisma sd wan": "palo alto networks",
            "cisco secure sd wan": "cisco",
        }
        for prefix, canonical in alias_prefixes.items():
            if key == canonical or key.startswith(prefix):
                return canonical
        return key

    def _dedupe_option_profiles(option_profiles: list[dict[str, str]]) -> list[dict[str, str]]:
        deduped: list[dict[str, str]] = []
        seen_by_key: dict[str, int] = {}
        for option in option_profiles:
            vendor = str(option.get("vendor", "")).strip()
            if not vendor:
                continue
            focus = str(option.get("focus", "")).strip()
            key = _vendor_identity_key(vendor)
            if key not in seen_by_key:
                seen_by_key[key] = len(deduped)
                deduped.append({"vendor": vendor[:200], "focus": focus[:500]})
                continue
            existing_idx = seen_by_key[key]
            existing_focus = deduped[existing_idx].get("focus", "")
            if len(focus) > len(existing_focus):
                deduped[existing_idx]["focus"] = focus[:500]
        return deduped

    def _is_placeholder_vendor_name(vendor_name: str) -> bool:
        key = _vendor_identity_key(vendor_name)
        if not key:
            return True
        placeholder_patterns = [
            r"vendor\s+[a-z0-9]+",
            r"provider\s+[a-z0-9]+",
            r"candidate\s+[a-z0-9]+",
            r"vendor\s+(alpha|beta|gamma|delta|one|two|three|four|five)",
        ]
        if any(re.fullmatch(pattern, key) for pattern in placeholder_patterns):
            return True
        return key in {"vendor", "provider", "candidate"}

    def _sanitize_option_profiles(option_profiles: list[dict[str, str]]) -> tuple[list[dict[str, str]], list[str]]:
        filtered: list[dict[str, str]] = []
        rejected: list[str] = []
        for option in option_profiles:
            vendor = str(option.get("vendor", "")).strip()
            focus = str(option.get("focus", "")).strip()
            if not vendor:
                continue
            if _is_placeholder_vendor_name(vendor):
                rejected.append(vendor[:200])
                continue
            filtered.append({"vendor": vendor[:200], "focus": focus[:500]})
        return _dedupe_option_profiles(filtered), sorted(set(rejected))

    def _classify_evidence_ref(source_ref: str) -> dict[str, Any]:
        ref = source_ref.strip()
        lower_ref = ref.lower()
        if lower_ref.startswith("placeholder-") or lower_ref.startswith("auto-ref-"):
            category = "placeholder"
            strength = "weak"
        elif lower_ref.startswith("llm-output-"):
            category = "model_output_hash"
            strength = "moderate"
        elif (
            lower_ref.startswith("http://")
            or lower_ref.startswith("https://")
            or lower_ref.startswith("urn:")
            or lower_ref.startswith("sha256:")
            or "/" in ref
            or "\\" in ref
            or re.search(r"\.(pdf|docx?|md|txt|json)$", lower_ref)
        ):
            category = "document_or_uri"
            strength = "strong"
        elif re.fullmatch(r"[a-z0-9_-]+-evidence-\d+", lower_ref):
            category = "named_token"
            strength = "weak"
        else:
            category = "generic_token"
            strength = "weak"
        return {
            "source_ref": ref,
            "category": category,
            "strength": strength,
        }

    def _build_recommendation_locked_sections(
        role_bundle: list[dict[str, Any]],
        recommendation: dict[str, Any],
    ) -> dict[str, str]:
        all_assertions = [
            a for role_item in role_bundle for a in role_item.get("assertions", [])
            if isinstance(a, str) and a.strip()
        ]
        objective = _first_non_empty(
            all_assertions,
            "Deliver a deterministic, auditable decision outcome.",
        )
        vendor = recommendation.get("selected_vendor") or "no approved selection"
        summary = (
            f"objective: {objective}\n"
            f"recommendation: {recommendation.get('major_recommendation')} "
            f"(selected_vendor={vendor}, score={recommendation.get('score')})."
        )
        down_select = (
            f"{recommendation.get('major_recommendation')} with deterministic weighted score "
            f"{recommendation.get('score')}."
        )
        return {
            "Executive Summary": summary,
            "Down-Select Recommendation": down_select,
        }

    def _extract_options_from_llm(llm_analysis: dict[str, Any]) -> list[dict[str, str]]:
        """Extract solution options from LLM analysis output.

        The LLM may return options under various keys - this function
        normalises them into the [{vendor, focus}] format the governance
        pipeline expects.
        """
        options: list[dict[str, str]] = []

        # Try common structures the LLM might return
        for key in ("vendor_scoring", "options", "solution_options", "recommendations",
                     "board_recommendation", "market_analysis"):
            section = llm_analysis.get(key)
            if not section:
                continue
            if isinstance(section, dict):
                # Might be a single recommendation or a dict of options
                if "options" in section and isinstance(section["options"], list):
                    section = section["options"]
                elif "vendors" in section and isinstance(section["vendors"], list):
                    section = section["vendors"]
                elif "recommendation" in section or "decision" in section:
                    rec_text = section.get("recommendation") or section.get("decision") or ""
                    if isinstance(rec_text, str) and rec_text.strip():
                        options.append({"vendor": rec_text[:120], "focus": "LLM-recommended approach"})
                    continue
                else:
                    continue
            if isinstance(section, list):
                for item in section:
                    if isinstance(item, dict):
                        name = (
                            item.get("vendor") or item.get("name") or item.get("option")
                            or item.get("provider") or item.get("solution") or ""
                        )
                        focus = (
                            item.get("focus") or item.get("rationale") or item.get("description")
                            or item.get("summary") or item.get("recommendation") or ""
                        )
                        if isinstance(name, str) and name.strip():
                            options.append({"vendor": name.strip()[:200], "focus": str(focus).strip()[:500]})
                    elif isinstance(item, str) and item.strip():
                        options.append({"vendor": item.strip()[:200], "focus": "LLM-identified option"})
        return _dedupe_option_profiles(options)

    def _extract_sections_from_llm(llm_analysis: dict[str, Any]) -> list[dict[str, str]]:
        """Build human-readable board report sections from LLM analysis output."""
        sections: list[dict[str, str]] = []
        # Map LLM section keys to board report titles
        section_map = {
            "executive_summary": "Executive Summary",
            "strategic_context": "Context",
            "risk_matrix": "Risk Register",
            "risk_register": "Risk Register",
            "financial_model": "Financial Analysis",
            "scenario_analysis": "Scenario Analysis",
            "implementation_roadmap": "Implementation Plan",
            "governance_implications": "Governance Implications",
            "market_analysis": "Market Analysis",
            "vendor_scoring": "Vendor Assessment",
            "board_recommendation": "Down-Select Recommendation",
            "regulatory_position": "Regulatory Position",
            "audit_trail": "Audit Trail",
            "success_metrics": "Success Metrics",
        }
        for key, title in section_map.items():
            val = llm_analysis.get(key)
            if not val:
                continue
            if isinstance(val, dict):
                # Flatten dict to readable text
                lines = []
                for k, v in val.items():
                    if isinstance(v, list):
                        lines.append(f"{k}: {', '.join(str(i) for i in v)}")
                    else:
                        lines.append(f"{k}: {v}")
                content = "\n".join(lines)
            elif isinstance(val, list):
                content = "\n".join(f"- {item}" if isinstance(item, str) else f"- {json.dumps(item)}" for item in val)
            else:
                content = str(val)
            if content.strip():
                sections.append({"title": title, "content": content.strip()})
        return sections

    def _extract_named_vendors(intent_text: str) -> list[str]:
        t = intent_text.lower()
        known = [
            ("palo alto networks", "Palo Alto Networks"),
            ("palo-alto", "Palo Alto Networks"),
            ("fortinet", "Fortinet"),
            ("cisco", "Cisco"),
            ("vmware velocloud", "VMware VeloCloud"),
            ("vmware", "VMware"),
            ("versa networks", "Versa Networks"),
            ("versa", "Versa Networks"),
            ("zscaler", "Zscaler"),
            ("cato networks", "Cato Networks"),
            ("cato", "Cato Networks"),
            ("netskope", "Netskope"),
            ("cloudflare", "Cloudflare"),
            ("aruba", "HPE Aruba"),
            ("silver peak", "HPE Aruba"),
            ("juniper", "Juniper Networks"),
            ("github copilot", "GitHub Copilot"),
            ("copilot", "GitHub Copilot"),
            ("openai", "OpenAI"),
            ("chatgpt", "OpenAI ChatGPT"),
            ("anthropic", "Anthropic Claude"),
            ("google gemini", "Google Gemini"),
            ("gemini", "Google Gemini"),
            ("amazon bedrock", "Amazon Bedrock"),
            ("azure openai", "Azure OpenAI Service"),
            ("aws", "Amazon Web Services"),
            ("microsoft azure", "Microsoft Azure"),
            ("google cloud", "Google Cloud Platform"),
        ]
        names: list[str] = []
        for token, display in known:
            if token in t and display not in names:
                names.append(display)
        return names

    def _vendors_align(candidate_vendor: str, preferred_vendor: str) -> bool:
        candidate_key = _vendor_identity_key(candidate_vendor)
        preferred_key = _vendor_identity_key(preferred_vendor)
        if not candidate_key or not preferred_key:
            return False
        return (
            candidate_key == preferred_key
            or candidate_key.startswith(preferred_key)
            or preferred_key.startswith(candidate_key)
            or candidate_key in preferred_key
            or preferred_key in candidate_key
        )

    def _extract_preferred_vendor(assertions: list[str]) -> str | None:
        preference_markers = (
            "recommend",
            "recommended",
            "primary",
            "must use",
            "must adopt",
            "standardize on",
            "prefer",
            "selected vendor",
        )
        discovered: list[str] = []
        for assertion in assertions:
            if not isinstance(assertion, str) or not assertion.strip():
                continue
            lower_assertion = assertion.lower()
            if not any(marker in lower_assertion for marker in preference_markers):
                continue
            for vendor in _extract_named_vendors(assertion):
                if vendor not in discovered:
                    discovered.append(vendor)
        if len(discovered) == 1:
            return discovered[0]
        return None

    def _derive_solution_options(intent_text: str, preferred_vendors: list[str] | None = None) -> list[dict[str, str]]:
        if preferred_vendors:
            focus_lines = [
                "Security-led delivery, zero-trust policy enforcement, and global operations maturity",
                "Cost-aware governed delivery with deterministic controls and staged migration assurance",
                "Balanced long-term viability, regulatory alignment, and operational resilience",
            ]
            return [
                {"vendor": vendor, "focus": focus_lines[idx % len(focus_lines)]}
                for idx, vendor in enumerate(preferred_vendors)
            ]
        t = intent_text.lower()
        # AI / LLM / code-assistant use cases
        if any(k in t for k in ["copilot", "chatgpt", "openai", "llm", "ai assistant", "ai-assisted",
                                 "code generation", "code review", "generative ai", "gen ai", "genai",
                                 "large language model", "gpt", "machine learning model", "ml model"]):
            return [
                {"vendor": "Governed AI Copilot Framework",
                 "focus": "Policy-bound code assistance with human-in-the-loop review gates and IP protection"},
                {"vendor": "Enterprise LLM Gateway",
                 "focus": "Centralized API governance, PII filtering, and prompt audit controls"},
                {"vendor": "Adaptive AI Integration Platform",
                 "focus": "Multi-model orchestration with deterministic guardrails and compliance logging"},
            ]
        # Cybersecurity use cases
        if any(k in t for k in ["cyber", "security operations", "soc", "siem", "threat", "incident response",
                                 "vulnerability", "penetration test", "pentest", "endpoint detection"]):
            return [
                {"vendor": "CyberShield Managed Detection & Response",
                 "focus": "24/7 threat monitoring with automated containment and compliance reporting"},
                {"vendor": "ThreatFabric Security Platform",
                 "focus": "Unified SIEM/SOAR with deterministic incident workflows"},
                {"vendor": "ZeroExposure Cyber Resilience",
                 "focus": "Proactive vulnerability management with continuous assurance controls"},
            ]
        # Cloud / infrastructure use cases
        if any(k in t for k in ["cloud", "infrastructure", "iaas", "paas", "saas", "migration",
                                 "containerisation", "containerization", "kubernetes", "devops"]):
            return [
                {"vendor": "GovCloud Managed Infrastructure",
                 "focus": "Sovereign cloud hosting with regulatory-aligned operational controls"},
                {"vendor": "HybridScale Cloud Platform",
                 "focus": "Multi-cloud orchestration with cost governance and workload portability"},
                {"vendor": "SecureStack Container Services",
                 "focus": "Hardened container platform with deterministic deployment pipelines"},
            ]
        # Network / SD-WAN use cases
        if any(k in t for k in ["wan", "sd-wan", "sase", "ztna", "network", "ot", "iot"]):
            return [
                {"vendor": "SecureEdge Managed SD-WAN + SASE",
                 "focus": "Zero-trust edge transformation and policy-based routing"},
                {"vendor": "ResilienceNet Hybrid WAN",
                 "focus": "High-availability backbone with staged migration controls"},
                {"vendor": "CloudFabric Secure Access",
                 "focus": "Cloud-native secure connectivity with rapid branch onboarding"},
            ]
        # Data platform use cases
        if any(k in t for k in ["data", "platform", "analytics", "lake", "warehouse"]):
            return [
                {"vendor": "DataCore Unified Platform", "focus": "Governed data ingestion and analytics lifecycle"},
                {"vendor": "InsightMesh Enterprise Lakehouse", "focus": "Elastic analytics with policy-bound access controls"},
                {"vendor": "TrustedFabric Data Grid", "focus": "Cross-domain interoperability and lineage assurance"},
            ]
        # Customer support / contact centre use cases
        if any(k in t for k in ["customer support", "contact centre", "contact center", "helpdesk",
                                 "help desk", "support portal", "customer-facing", "customer facing",
                                 "first-line", "first line", "chatbot"]):
            return [
                {"vendor": "GovAssist Intelligent Support Platform",
                 "focus": "Compliant customer interaction automation with human escalation controls"},
                {"vendor": "TrustDialog Conversational AI",
                 "focus": "PII-safe conversational engine with audit trail and sentiment monitoring"},
                {"vendor": "SmartResolve Service Automation",
                 "focus": "Deterministic triage workflows with SLA-bound response governance"},
            ]
        return [
            {"vendor": "Option-Alpha Governed Delivery", "focus": "Balanced risk and measurable transformation outcomes"},
            {"vendor": "Option-Beta Accelerated Modernization", "focus": "Time-to-value with moderate operational change"},
            {"vendor": "Option-Gamma Conservative Transition", "focus": "Lowest transition risk with slower benefit realization"},
        ]

    def _extract_explicit_intent_targets(intent_text: str) -> list[str]:
        cleaned = re.sub(r"\s+", " ", intent_text or "").strip()
        if not cleaned:
            return []
        candidates: list[str] = []
        sentence_chunks = re.split(r"(?<=[\.;])\s+", cleaned)
        target_markers = (
            "%", ">=", "<=", "gbp", "usd", "eur", "$", "£", "€",
            "month", "months", "week", "weeks", "day", "days",
            "q1", "q2", "q3", "q4", "sev1", "severe", "incident",
            "uptime", "availability", "cycle-time", "cycle time",
            "latency", "response time",
        )
        for chunk in sentence_chunks:
            text = chunk.strip(" -")
            lower = text.lower()
            if not text:
                continue
            if any(marker in lower for marker in target_markers) and any(ch.isdigit() for ch in lower):
                candidates.append(text[:220])

        # Capture compact inequality or threshold fragments that may appear inline.
        for match in re.findall(r"(?:>=|<=|>|<)\s*\d+(?:\.\d+)?\s*%?", cleaned):
            fragment = str(match).strip()
            if fragment:
                candidates.append(fragment)

        deduped: list[str] = []
        seen: set[str] = set()
        for item in candidates:
            key = item.lower()
            if key in seen:
                continue
            seen.add(key)
            deduped.append(item)
        return deduped[:12]

    def _extract_intent_signals(intent_text: str) -> dict[str, Any]:
        t = intent_text.lower()
        signals: dict[str, Any] = {
            "regulatory_constraints": [],
            "security_constraints": [],
            "financial_constraints": [],
            "success_targets": [],
            "explicit_targets": _extract_explicit_intent_targets(intent_text),
        }
        for token, label in [
            ("gdpr", "GDPR"), ("uk gdpr", "UK GDPR"), ("nis2", "NIS2"), ("dora", "DORA"), ("iso27001", "ISO27001"),
            ("eu ai act", "EU AI Act"), ("ai act", "EU AI Act"), ("fca", "FCA"),
            ("pci dss", "PCI DSS"), ("sox", "SOX"), ("hipaa", "HIPAA"),
            ("uk data residency", "UK Data Residency"), ("data residency", "Data Residency"),
            ("regulated", "Regulated Environment"), ("compliance", "Compliance Requirement"),
        ]:
            if token in t and label not in signals["regulatory_constraints"]:
                signals["regulatory_constraints"].append(label)
        for token, label in [
            ("zero trust", "Zero Trust"), ("ztna", "ZTNA"), ("sase", "SASE"), ("encryption", "Encryption"),
            ("pii", "PII Protection"), ("pii mask", "PII Masking"), ("data masking", "Data Masking"),
            ("prompt injection", "Prompt Injection Prevention"), ("guardrail", "AI Guardrails"),
            ("human-in-the-loop", "Human-in-the-Loop"), ("human in the loop", "Human-in-the-Loop"),
            ("human oversight", "Human Oversight"), ("review gate", "Review Gates"),
            ("audit", "Audit Controls"), ("ip protection", "IP Protection"),
            ("data loss prevention", "Data Loss Prevention"), ("dlp", "Data Loss Prevention"),
            ("entra", "Entra ID Controls"), ("entra id", "Entra ID Controls"),
            ("privacy-by-design", "Privacy by Design"), ("deterministic-governance", "Deterministic Governance"),
            ("deterministic governance", "Deterministic Governance"), ("audit export", "Audit Export"),
        ]:
            if token in t and label not in signals["security_constraints"]:
                signals["security_constraints"].append(label)
        if "capex" in t or "budget" in t or "cost" in t:
            signals["financial_constraints"].append("Budget/cost constraint detected")
        if "license" in t or "subscription" in t or "per seat" in t or "per-seat" in t:
            signals["financial_constraints"].append("Licensing/subscription cost detected")
        if "vendor lock" in t or "vendor-lock" in t or "lock-in" in t or "vendor lock-in" in t:
            signals["financial_constraints"].append("Vendor lock-in risk detected")
        for marker in ["incident", "operating cost", "resilience", "uptime", "availability",
                        "delivery velocity", "code quality", "response time", "sla",
                        "customer satisfaction", "resolution rate", "accuracy",
                        "deterministic governance", "deterministic-governance",
                        "auditability", "production-readiness", "reproducible outputs",
                        "board-ready", "audit export"]:
            if marker in t and marker not in signals["success_targets"]:
                signals["success_targets"].append(marker)
        if signals["explicit_targets"] and "explicit_targets_present" not in signals["success_targets"]:
            signals["success_targets"].append("explicit_targets_present")
        return signals

    def _build_option_assessment(vendor_rows: list[dict[str, Any]], intent_signals: dict[str, Any]) -> list[dict[str, Any]]:
        """Produce deterministic, human-readable option detail blocks for board consumption."""
        assessment: list[dict[str, Any]] = []
        for idx, row in enumerate(vendor_rows, start=1):
            weights = row.get("weights", {})
            scores = row.get("scores", {})
            security_fit = round(float(scores.get("security", 0.0)), 2)
            delivery_fit = round(
                (float(scores.get("operations", 0.0)) + float(scores.get("resilience", 0.0))) / 2,
                2,
            )
            operating_model_fit = round(
                (float(scores.get("interoperability", 0.0)) + float(scores.get("resilience", 0.0))) / 2,
                2,
            )
            financial_fit = round(float(scores.get("commercial", 0.0)), 2)
            assessment.append(
                {
                    "rank": idx,
                    "vendor": row.get("vendor"),
                    "focus": row.get("focus"),
                    "score": row.get("total"),
                    "security_fit": security_fit,
                    "delivery_fit": delivery_fit,
                    "operating_model_fit": operating_model_fit,
                    "financial_fit": financial_fit,
                    "weights": weights,
                    "score_dimensions": {
                        "security": round(float(scores.get("security", 0.0)), 2),
                        "resilience": round(float(scores.get("resilience", 0.0)), 2),
                        "interoperability": round(float(scores.get("interoperability", 0.0)), 2),
                        "operations": round(float(scores.get("operations", 0.0)), 2),
                        "commercial": round(float(scores.get("commercial", 0.0)), 2),
                    },
                    "fit_summary": [
                        "Regulatory alignment signals: "
                        f"{', '.join(intent_signals.get('regulatory_constraints', [])) or 'none explicit'}",
                        "Security priorities detected: "
                        f"{', '.join(intent_signals.get('security_constraints', [])) or 'none explicit'}",
                        "Financial constraints: "
                        f"{', '.join(intent_signals.get('financial_constraints', [])) or 'none explicit'}",
                    ],
                }
            )
        return assessment

    def _build_human_readable_sections(
        execution_id: str,
        profile: dict[str, Any],
        schema_id: str,
        rp: dict[str, str],
        role_bundle: list[dict[str, Any]],
        recommendation: dict[str, Any],
        vendor_rows: list[dict[str, Any]] | None = None,
        compliance_matrix: dict[str, Any] | None = None,
        governance_modes: list[str] | None = None,
        intent_signals: dict[str, Any] | None = None,
    ) -> list[dict[str, str]]:
        all_assertions = [a for r in role_bundle for a in r.get("assertions", []) if isinstance(a, str) and a.strip()]
        all_non_negotiables = [a for r in role_bundle for a in r.get("non_negotiables", []) if isinstance(a, str) and a.strip()]
        all_risk_flags = [a for r in role_bundle for a in r.get("risk_flags", []) if isinstance(a, str) and a.strip()]

        roles = [r.get("role", "unknown") for r in role_bundle]
        domains: list[str] = []
        for r in role_bundle:
            raw_domain = str(r.get("domain", "unknown"))
            for d in [x.strip() for x in raw_domain.split(",") if x.strip()]:
                if d not in domains:
                    domains.append(d)
        executive_summary = (
            f"Execution {execution_id[:12]} for profile '{profile['profile_id']}' in sector {profile['sector']} "
            f"was compiled under {rp['reasoning_level']}/{rp['policy_level']}. "
            f"Primary objective: {_first_non_empty(all_assertions, 'Deliver a deterministic, auditable decision outcome.')} "
            f"Final recommendation: {recommendation.get('major_recommendation')}."
        )

        context = (
            f"Schema={schema_id}; Jurisdiction={profile['jurisdiction']}; Risk appetite={profile['risk_appetite']}. "
            f"Roles engaged ({len(role_bundle)}): {', '.join(roles) if roles else 'none supplied'}. "
            f"Domains covered: {', '.join(domains) if domains else 'not specified'}. "
            f"Governance modes: {', '.join(governance_modes) if governance_modes else 'default deterministic governance'}."
        )

        risk_lines = sorted(set(all_risk_flags)) or [
            "No explicit role risk flags provided; maintain standard governance controls and audit monitoring."
        ]
        risk_register = "\n".join([f"- {line}" for line in risk_lines])

        explicit_targets = [
            target for target in (intent_signals or {}).get("explicit_targets", [])
            if isinstance(target, str) and target.strip()
        ]
        metric_candidates = explicit_targets + sorted(set(all_non_negotiables)) + sorted(set(all_assertions[:3]))
        deduped_metric_candidates: list[str] = []
        seen_metric_candidates: set[str] = set()
        for candidate in metric_candidates:
            key = candidate.strip().lower()
            if not key or key in seen_metric_candidates:
                continue
            seen_metric_candidates.add(key)
            deduped_metric_candidates.append(candidate.strip())
        metric_lines = deduped_metric_candidates or [
            "Deterministic pack hash + signature verification pass rate remains 100%.",
        ]
        success_metrics = "\n".join([f"- {line}" for line in metric_lines])

        ranking_lines = []
        if vendor_rows:
            ranking_lines = [f"{row['vendor']} ({row['total']})" for row in vendor_rows[:3]]

        compliance_note = ""
        if compliance_matrix:
            compliance_note = (
                " All required internal control signals were satisfied."
                if compliance_matrix.get("all_required_satisfied")
                else " Some required internal control signals are missing and require remediation before approval."
            )

        recommendation_rationale = (
            f"{recommendation['major_recommendation']} with deterministic weighted score {recommendation['score']}. "
            f"Ranked options: {', '.join(ranking_lines) if ranking_lines else 'n/a'}. "
            f"Rationale inputs considered: {len(all_assertions)} assertions, {len(all_non_negotiables)} non-negotiables, "
            f"{len(all_risk_flags)} risk flags." + compliance_note
        )

        return [
            {"title": "Executive Summary", "content": executive_summary},
            {"title": "Context", "content": context},
            {"title": "Risk Register", "content": risk_register},
            {"title": "Success Metrics", "content": success_metrics},
            {"title": "Down-Select Recommendation", "content": recommendation_rationale},
        ]

    def _render_board_report_markdown(board_report: dict[str, Any]) -> str:
        lines = [
            f"# DIIaC Board Report - {board_report['execution_id']}",
            "",
            f"- Schema: {board_report['schema_id']}",
            f"- Profile: {board_report['profile_id']}",
            "",
        ]
        for section in board_report.get("sections", []):
            lines.append(f"## {section.get('title', 'Untitled')}")
            lines.append(section.get("content", ""))
            lines.append("")

        recs = board_report.get("major_recommendations", [])
        if recs:
            lines.append("## Major Recommendations")
            for rec in recs:
                lines.append(f"- {rec.get('major_recommendation')}: score={rec.get('score')}")
                if rec.get("recommended_option_profile"):
                    profile = rec.get("recommended_option_profile", {})
                    lines.append(
                        f"  - Option profile: {profile.get('vendor')} | focus={profile.get('focus')} | rank={profile.get('rank')}"
                    )
                if rec.get("alternatives"):
                    lines.append(f"  - Alternatives considered: {', '.join(rec.get('alternatives', []))}")
                if rec.get("decision_drivers"):
                    for d in rec.get("decision_drivers", []):
                        lines.append(f"  - Driver: {d}")
                if rec.get("evidence_ids"):
                    lines.append(f"  - Evidence IDs: {', '.join(rec.get('evidence_ids', []))}")
                if rec.get("assumptions"):
                    lines.append("  - Assumptions:")
                    for a in rec.get("assumptions", []):
                        lines.append(f"    - {a}")
                if rec.get("risk_treatment"):
                    lines.append(f"  - Risk treatment strategy: {rec.get('risk_treatment', {}).get('strategy')}")
                    for a in rec.get("risk_treatment", {}).get("actions", []):
                        lines.append(f"    - {a}")
                if rec.get("confidence_rationale"):
                    lines.append(
                        f"  - Confidence: {rec.get('confidence_level')} "
                        f"({rec.get('confidence_score')}) - "
                        f"{rec.get('confidence_rationale')}"
                    )
            lines.append("")

        if board_report.get("ranked_options"):
            lines.append("## Ranked Option Detail")
            for option in board_report.get("ranked_options", []):
                lines.append(
                    f"- #{option.get('rank')} {option.get('vendor')} | score={option.get('score')} | focus={option.get('focus')}"
                )
                lines.append(
                    "  - Fit breakdown: "
                    f"security={option.get('security_fit')}, delivery={option.get('delivery_fit')}, "
                    f"operating_model={option.get('operating_model_fit')}, financial={option.get('financial_fit')}"
                )
                for line in option.get("fit_summary", []):
                    lines.append(f"  - {line}")
            lines.append("")

        if board_report.get("intent_coverage"):
            ic = board_report.get("intent_coverage", {})
            lines.append("## Intent Coverage")
            lines.append(
                f"- Regulatory constraints: {', '.join(ic.get('regulatory_constraints', [])) or 'none explicit'}"
            )
            lines.append(
                f"- Security constraints: {', '.join(ic.get('security_constraints', [])) or 'none explicit'}"
            )
            lines.append(
                f"- Financial constraints: {', '.join(ic.get('financial_constraints', [])) or 'none explicit'}"
            )
            lines.append(f"- Success targets: {', '.join(ic.get('success_targets', [])) or 'none explicit'}")
            lines.append("")

        if board_report.get("decision_summary"):
            ds = board_report.get("decision_summary", {})
            lines.append("## Decision Summary")
            lines.append(f"- Status: {ds.get('decision_status')}")
            lines.append(f"- Confidence: {ds.get('confidence_level')} ({ds.get('confidence_score')})")
            lines.append(f"- Basis: {ds.get('decision_basis')}")
            if ds.get("control_failure_reasons"):
                lines.append("- Control Failure Reasons:")
                for r in ds.get("control_failure_reasons", []):
                    lines.append(f"  - {r}")
            if ds.get("quality_gate_failures"):
                lines.append("- Quality Gate Failures:")
                for r in ds.get("quality_gate_failures", []):
                    lines.append(f"  - {r}")
            if ds.get("policy_pack_summary"):
                lines.append("- Policy Pack Summary:")
                for item in ds.get("policy_pack_summary", []):
                    if not isinstance(item, dict):
                        continue
                    lines.append(
                        f"  - {item.get('pack_id')}: fail_count={item.get('fail_count')}"
                    )
            lines.append("")

        if board_report.get("implementation_plan"):
            lines.append("## Implementation Plan")
            for step in board_report.get("implementation_plan", []):
                lines.append(f"- {step}")
            lines.append("")

        return "\n".join(lines).strip() + "\n"

    def _build_execution(payload: dict[str, Any]) -> tuple[dict[str, Any], int]:
        requested_profile_id = payload.get("profile_id", "it_enterprise_profile_v1")
        profile_id = requested_profile_id
        schema_id = payload.get("schema_id", "GENERAL_SOLUTION_BOARD_REPORT_V1")
        schema_version = payload.get("schema_version", "1.0.0")
        rp = {"reasoning_level": payload.get("reasoning_level", "R4"), "policy_level": payload.get("policy_level", "P4")}
        context_id = payload.get("execution_context_id") or f"ctx-{uuid.uuid4().hex[:8]}"
        execution_profile_overrides: list[dict[str, Any]] = []
        llm_analysis = payload.get("llm_analysis")
        llm_provider = payload.get("llm_provider")
        llm_analysis_hash = (
            _sha256_text(_canonical_json(llm_analysis))
            if isinstance(llm_analysis, dict) and llm_analysis
            else None
        )

        if profile_lock_id and profile_lock_id in profiles_by_id and requested_profile_id != profile_lock_id:
            profile_id = profile_lock_id
            execution_profile_overrides.append(
                {
                    "type": "PROFILE_LOCK_OVERRIDE",
                    "requested_profile_id": requested_profile_id,
                    "effective_profile_id": profile_id,
                }
            )

        profile = profiles_by_id.get(profile_id)
        if profile is None:
            return {"error": "profile_not_found", "profile_id": profile_id}, 400
        if schema_id not in approved_schemas:
            return {"error": "schema_not_approved", "schema_id": schema_id}, 403
        if schema_id not in profile["allowed_schemas"]:
            return {"error": "schema_not_allowed_for_profile", "profile_id": profile_id, "schema_id": schema_id}, 403

        raw_role_bundle = role_inputs.get(context_id, [])
        role_bundle: list[dict[str, Any]] = []
        for idx, role_item in enumerate(raw_role_bundle, start=1):
            if not isinstance(role_item, dict):
                continue
            evidence_refs = _normalize_string_list(role_item.get("evidence_refs"))
            role_bundle.append(
                {
                    "execution_context_id": context_id,
                    "role": str(role_item.get("role", "unknown"))[:ROLE_FIELD_MAX],
                    "domain": str(role_item.get("domain", "unknown"))[:ROLE_FIELD_MAX],
                    "assertions": _normalize_string_list(role_item.get("assertions")),
                    "non_negotiables": _normalize_string_list(role_item.get("non_negotiables")),
                    "risk_flags": _normalize_string_list(role_item.get("risk_flags")),
                    "evidence_refs": evidence_refs or [f"auto-ref-{idx}"],
                }
            )
        if not role_bundle:
            inline_assertions = _normalize_string_list(payload.get("assertions")) or [
                "Deterministic governed compile initiated from inline payload."
            ]
            inline_non_negotiables = _normalize_string_list(payload.get("non_negotiables")) or ["deterministic-governance"]
            inline_risk_flags = _normalize_string_list(payload.get("risk_flags")) or ["llm-hallucination-risk"]
            inline_evidence_refs = _normalize_string_list(payload.get("evidence_refs"))
            if not inline_evidence_refs and llm_analysis_hash:
                inline_evidence_refs = [f"llm-output-{llm_analysis_hash[:16]}"]
            if not inline_evidence_refs:
                inline_evidence_refs = [f"inline-payload-{_sha256_text(context_id)[:12]}"]

            role_bundle = [
                {
                    "execution_context_id": context_id,
                    "role": str(payload.get("role", "CIO"))[:ROLE_FIELD_MAX],
                    "domain": str(payload.get("domain", "decision"))[:ROLE_FIELD_MAX],
                    "assertions": inline_assertions,
                    "non_negotiables": inline_non_negotiables,
                    "risk_flags": inline_risk_flags,
                    "evidence_refs": inline_evidence_refs,
                }
            ]
            execution_profile_overrides.append(
                {
                    "type": "INLINE_ROLE_PAYLOAD_USED",
                    "reason": "No persisted role inputs were found for execution context.",
                    "execution_context_id": context_id,
                }
            )
        governance_modes, auto_added_modes = _normalize_governance_modes(payload.get("governance_modes", []))
        if auto_added_modes:
            execution_profile_overrides.append(
                {
                    "type": "GOVERNANCE_MODE_ENFORCEMENT",
                    "auto_added_modes": auto_added_modes,
                    "required_modes": required_governance_modes,
                }
            )
        effective_request_payload = dict(payload)
        effective_request_payload.pop("llm_analysis", None)
        effective_request_payload["llm_analysis_hash"] = llm_analysis_hash
        effective_request_payload["profile_id"] = profile_id
        effective_request_payload["governance_modes"] = governance_modes
        deterministic_input_snapshot = {
            "context_id": context_id,
            "profile_id": profile_id,
            "profile_hash": profile["profile_hash"],
            "schema_id": schema_id,
            "schema_version": schema_version,
            "rp": rp,
            "role_bundle": role_bundle,
            "request_payload": effective_request_payload,
            "governance_modes": governance_modes,
        }
        deterministic_input_snapshot_hash = _sha256_text(_canonical_json(deterministic_input_snapshot))
        context_hash = deterministic_input_snapshot_hash
        execution_id = (
            str(uuid.uuid5(uuid.NAMESPACE_URL, f"diiac:{context_hash}"))
            if strict_deterministic_mode else str(uuid.uuid4())
        )

        required_sections = profile["required_sections"]

        human_intent_text = payload.get("human_intent")
        if not isinstance(human_intent_text, str):
            human_intent_text = ""
        intent_text_parts: list[str] = [human_intent_text.strip()] if human_intent_text.strip() else []
        all_assertions: list[str] = []
        all_non_negotiables: list[str] = []
        all_risk_flags: list[str] = []
        for role_item in role_bundle:
            role_assertions = _normalize_string_list(role_item.get("assertions"))
            role_non_negotiables = _normalize_string_list(role_item.get("non_negotiables"))
            role_risk_flags = _normalize_string_list(role_item.get("risk_flags"))
            all_assertions.extend(role_assertions)
            all_non_negotiables.extend(role_non_negotiables)
            all_risk_flags.extend(role_risk_flags)
            intent_text_parts.extend(role_assertions)
            intent_text_parts.extend(role_non_negotiables)
            intent_text_parts.extend(role_risk_flags)
        intent_text = " | ".join(intent_text_parts)

        # When LLM analysis is present, extract options from LLM output;
        # otherwise fall back to keyword-matched templates
        llm_options: list[dict[str, str]] = []
        llm_sections: list[dict[str, str]] = []
        rejected_llm_vendors: list[str] = []
        llm_option_fallback_reason = None
        if isinstance(llm_analysis, dict) and llm_analysis:
            llm_options_raw = _extract_options_from_llm(llm_analysis)
            llm_options, rejected_llm_vendors = _sanitize_option_profiles(llm_options_raw)
            llm_sections = _extract_sections_from_llm(llm_analysis)
            preferred_vendors = _extract_named_vendors(intent_text)
            option_profiles = llm_options if llm_options else _derive_solution_options(
                intent_text, preferred_vendors=preferred_vendors
            )
            if not llm_options:
                llm_option_fallback_reason = (
                    "LLM options did not pass vendor specificity checks; deterministic fallback options were used."
                )
        else:
            preferred_vendors = _extract_named_vendors(intent_text)
            option_profiles = _derive_solution_options(intent_text, preferred_vendors=preferred_vendors)
        option_profiles = _dedupe_option_profiles(option_profiles)
        intent_signals = _extract_intent_signals(intent_text)

        weights = profile["scoring_weights"]
        vendor_rows: list[dict[str, Any]] = []
        for option in option_profiles:
            vendor = option["vendor"]
            vendor_scores = {k: _deterministic_score(context_hash, f"{vendor}:{k}") for k in weights}
            vendor_total = round(sum(vendor_scores[k] * weights[k] for k in weights), 2)
            vendor_rows.append({
                "vendor": vendor,
                "focus": option["focus"],
                "weights": weights,
                "scores": vendor_scores,
                "total": vendor_total,
            })
        vendor_rows.sort(key=lambda row: row["total"], reverse=True)
        if not vendor_rows:
            return {
                "error": "no_solution_options",
                "message": "No solution options could be derived from the provided inputs.",
            }, 400
        ranked_options = _build_option_assessment(vendor_rows, intent_signals)

        selected = vendor_rows[0]
        preferred_vendor = _extract_preferred_vendor(all_assertions)
        objective_vendor_conflict_reason = None
        if preferred_vendor and not _vendors_align(selected["vendor"], preferred_vendor):
            objective_vendor_conflict_reason = (
                "objective vendor preference conflict: "
                f"asserted preference '{preferred_vendor}' does not align with deterministic top-ranked "
                f"option '{selected['vendor']}'."
            )

        required_controls = set(profile.get("required_controls", []))
        provided_controls = set(payload.get("controls", list(required_controls)))
        compliance_matrix = {
            "required_controls": sorted(required_controls),
            "provided_controls": sorted(provided_controls),
            "satisfied_controls": sorted(required_controls.intersection(provided_controls)),
            "all_required_satisfied": required_controls.issubset(provided_controls),
        }

        evidence_ref_pool = [
            ref
            for role in role_bundle
            for ref in role.get("evidence_refs", [])
            if isinstance(ref, str) and ref.strip()
        ]
        evidence_ref_details = [
            _classify_evidence_ref(ref) for ref in sorted(set(evidence_ref_pool))
        ]
        evidence_objects: list[dict[str, Any]] = []
        for detail in evidence_ref_details:
            source_ref = detail["source_ref"]
            evidence_id = f"evidence-{_sha256_text(source_ref)[:16]}"
            strength = detail["strength"]
            category = detail["category"]
            resolvable = strength in {"strong", "moderate"} and category != "placeholder"
            evidence_objects.append(
                {
                    "evidence_id": evidence_id,
                    "source_ref": source_ref,
                    "category": category,
                    "strength": strength,
                    "resolvable": resolvable,
                    "origin": "role_input",
                    "capture_id": f"evcap-{_sha256_text(f'{context_hash}:{source_ref}')[:16]}",
                }
            )
        strong_evidence_refs = [item["source_ref"] for item in evidence_ref_details if item["strength"] == "strong"]
        weak_evidence_refs = [item["source_ref"] for item in evidence_ref_details if item["strength"] == "weak"]
        placeholder_evidence_refs = [item["source_ref"] for item in evidence_ref_details if item["category"] == "placeholder"]
        unresolved_evidence_refs = [item["source_ref"] for item in evidence_objects if not item["resolvable"]]
        evidence_ids_seed = (
            [item["evidence_id"] for item in evidence_objects if item["resolvable"]][:5]
            if evidence_ref_details
            else [f"derived-evidence-{context_hash[:10]}-{i}" for i in range(1, min(len(required_sections), 3) + 1)]
        )
        assumptions = [
            "Cost model assumptions are based on provided capex/opex targets and current market benchmarks.",
            "Operational baseline and incident data provided in role evidence is assumed accurate and current.",
            "Supplier capability statements and migration constraints captured in assertions are assumed complete.",
        ]
        guardrails = sorted(set(all_non_negotiables)) or [
            "privacy-by-design",
            "deterministic-governance",
        ]
        residual_risks = sorted(set(all_risk_flags)) or [
            "vendor-lockin",
            "service-disruption-during-migration",
        ]
        success_metric_targets: list[str] = []
        for candidate in (
            [target for target in intent_signals.get("explicit_targets", []) if isinstance(target, str)]
            + guardrails
            + sorted(set(all_assertions[:3]))
        ):
            key = candidate.strip().lower()
            if key and key not in {item.lower() for item in success_metric_targets}:
                success_metric_targets.append(candidate.strip())
        disqualifiers: list[str] = []
        risk_treatment = {
            "strategy": "mitigate",
            "actions": [
                "Contractual protections and break clauses to reduce lock-in risk",
                "Phased migration with rollback controls to reduce service disruption",
                "Security validation and assurance gates prior to production cutover",
            ],
        }

        base_control_failure_reasons: list[str] = []
        if not compliance_matrix["all_required_satisfied"]:
            missing_controls = sorted(required_controls.difference(provided_controls))
            base_control_failure_reasons.append(f"missing required controls: {', '.join(missing_controls)}")
        if objective_vendor_conflict_reason:
            base_control_failure_reasons.append(objective_vendor_conflict_reason)

        constraints_mode_auto_controls = False
        if any("CONSTRAINTS-FIRST" in m.upper() for m in governance_modes) and "controls" not in payload:
            constraints_mode_auto_controls = True

        llm_audit_timestamp = None
        llm_audit_timestamp_source = None
        llm_provider_reported_timestamp = None
        llm_freshness = "UNKNOWN"
        llm_freshness_issue = None
        if isinstance(llm_analysis, dict) and llm_analysis:
            raw_audit_timestamp = None
            audit_trail = llm_analysis.get("audit_trail")
            if isinstance(audit_trail, dict):
                raw_audit_timestamp = audit_trail.get("timestamp")
                provider_reported = audit_trail.get("provider_reported_timestamp")
                if isinstance(provider_reported, str) and provider_reported.strip():
                    llm_provider_reported_timestamp = provider_reported.strip()
            if llm_provider_reported_timestamp is None and isinstance(raw_audit_timestamp, str) and raw_audit_timestamp.strip():
                llm_provider_reported_timestamp = raw_audit_timestamp.strip()

            raw_payload_audit_timestamp = payload.get("llm_audit_timestamp")
            parsed_payload_audit_timestamp = _parse_utc_timestamp(raw_payload_audit_timestamp)
            parsed_report_audit_timestamp = _parse_utc_timestamp(raw_audit_timestamp)

            parsed_audit_timestamp = parsed_payload_audit_timestamp or parsed_report_audit_timestamp
            if parsed_payload_audit_timestamp is not None:
                llm_audit_timestamp_source = "payload.llm_audit_timestamp"
            elif parsed_report_audit_timestamp is not None:
                llm_audit_timestamp_source = "llm_analysis.audit_trail.timestamp"

            if parsed_audit_timestamp is None:
                llm_freshness = "MISSING_OR_INVALID"
                llm_freshness_issue = (
                    "LLM analysis did not provide a valid audit timestamp for evidence freshness validation."
                )
            else:
                llm_audit_timestamp = parsed_audit_timestamp.isoformat()
                if parsed_audit_timestamp >= llm_audit_min_timestamp:
                    llm_freshness = "CURRENT"
                else:
                    llm_freshness = "STALE"
                    llm_freshness_issue = (
                        f"LLM audit timestamp ({parsed_audit_timestamp.isoformat()}) is older than "
                        f"minimum accepted freshness ({llm_audit_min_timestamp.isoformat()})."
                    )

        supporting_evidence_refs = [
            item["source_ref"]
            for item in evidence_ref_details
            if item["strength"] in {"strong", "moderate"}
        ]
        evidence_claim_coverage = (
            round(len(supporting_evidence_refs) / max(1, len(evidence_ref_details)), 2)
            if evidence_ref_details
            else 0.0
        )

        quality_gate_failures: list[str] = []
        if len(strong_evidence_refs) < evidence_min_strong_refs:
            quality_gate_failures.append(
                f"strong evidence refs {len(strong_evidence_refs)} below minimum {evidence_min_strong_refs}"
            )
        if placeholder_evidence_refs:
            quality_gate_failures.append(
                f"placeholder evidence refs present ({len(placeholder_evidence_refs)}); replace with concrete evidence objects"
            )
        if unresolved_evidence_refs:
            quality_gate_failures.append(
                f"unresolved evidence refs present ({len(unresolved_evidence_refs)}); all claims require concrete resolvable evidence"
            )
        if evidence_claim_coverage < evidence_min_claim_coverage:
            quality_gate_failures.append(
                f"evidence coverage {evidence_claim_coverage:.2f} below minimum {evidence_min_claim_coverage:.2f}"
            )
        if (
            evidence_require_fresh_llm
            and isinstance(llm_analysis, dict)
            and llm_analysis
            and llm_freshness != "CURRENT"
        ):
            quality_gate_failures.append(
                f"llm evidence freshness requirement failed (status={llm_freshness})"
            )

        policy_signals = {
            "deterministic_compile": strict_deterministic_mode,
            "human_oversight_present": bool(role_bundle),
            "traceability_present": bool(evidence_ref_details),
            "strong_evidence_present": bool(strong_evidence_refs),
            "supporting_evidence_present": bool(supporting_evidence_refs),
            "llm_freshness_current": llm_freshness == "CURRENT",
            "risk_assessment_present": any(
                _normalize_string_list(role_item.get("risk_flags")) for role_item in role_bundle
            ),
            "non_negotiables_present": any(
                _normalize_string_list(role_item.get("non_negotiables")) for role_item in role_bundle
            ),
            "profile_controls_satisfied": compliance_matrix["all_required_satisfied"],
            "governance_modes_present": bool(governance_modes),
            "logging_enabled": True,
            "signature_configured": signing_enabled,
        }

        policy_pack_results: list[dict[str, Any]] = []
        policy_pack_failures: list[str] = []
        for pack in policy_packs:
            controls = pack.get("controls")
            if not isinstance(controls, list):
                continue
            control_results: list[dict[str, Any]] = []
            fail_count = 0
            for control in controls:
                if not isinstance(control, dict):
                    continue
                control_id = str(control.get("control_id", "UNSPECIFIED_CONTROL"))[:128]
                required_signals = [
                    signal
                    for signal in control.get("required_signals", [])
                    if isinstance(signal, str) and signal.strip()
                ]
                missing_signals = [signal for signal in required_signals if not policy_signals.get(signal, False)]
                status = "PASS" if not missing_signals else "FAIL"
                if status == "FAIL":
                    fail_count += 1
                    if policy_pack_enforce and control_id not in policy_pack_failures:
                        policy_pack_failures.append(control_id)
                evidence_backed_signals = {
                    "traceability_present",
                    "supporting_evidence_present",
                    "strong_evidence_present",
                    "llm_freshness_current",
                    "profile_controls_satisfied",
                }
                if missing_signals:
                    assurance_level = "asserted"
                elif any(signal in evidence_backed_signals for signal in required_signals):
                    assurance_level = "evidenced"
                else:
                    assurance_level = "asserted"
                control_results.append(
                    {
                        "control_id": control_id,
                        "title": control.get("title"),
                        "reference": control.get("reference"),
                        "status": status,
                        "assessment_status": status,
                        "assessment_mode": "control_signal_assessment",
                        "assurance_level": assurance_level,
                        "compliance_position": "not_legal_determination",
                        "required_signals": required_signals,
                        "missing_signals": missing_signals,
                        "evidence_basis": [
                            {
                                "signal": signal,
                                "present": bool(policy_signals.get(signal, False)),
                            }
                            for signal in required_signals
                        ],
                    }
                )
            policy_pack_results.append(
                {
                    "pack_id": pack.get("pack_id"),
                    "jurisdiction": pack.get("jurisdiction"),
                    "version": pack.get("version"),
                    "pack_hash": pack.get("pack_hash"),
                    "enforced": policy_pack_enforce,
                    "assessment_mode": "control_signal_assessment",
                    "compliance_notice": (
                        "PASS/FAIL indicates internal control-signal assessment only and is not a legal compliance determination."
                    ),
                    "summary": {
                        "total_controls": len(control_results),
                        "pass_count": len([c for c in control_results if c.get("status") == "PASS"]),
                        "fail_count": fail_count,
                    },
                    "controls": control_results,
                }
            )

        accuracy_warnings: list[str] = []
        if not strong_evidence_refs:
            accuracy_warnings.append("No strong document/URI evidence references were provided.")
        if weak_evidence_refs:
            accuracy_warnings.append(
                f"Weak evidence references detected ({len(weak_evidence_refs)}). Add URI/document/hash-based refs for stronger traceability."
            )
        if placeholder_evidence_refs:
            accuracy_warnings.append("Placeholder evidence references detected; replace with durable references.")
        if unresolved_evidence_refs:
            accuracy_warnings.append(
                "Unresolved evidence references detected; bind each claim to concrete resolvable evidence objects."
            )
        if rejected_llm_vendors:
            accuracy_warnings.append(
                "LLM returned generic/placeholder vendor labels that were rejected: "
                + ", ".join(rejected_llm_vendors[:5])
            )
        if llm_option_fallback_reason:
            accuracy_warnings.append(llm_option_fallback_reason)
        if llm_freshness_issue:
            accuracy_warnings.append(llm_freshness_issue)
        if objective_vendor_conflict_reason:
            accuracy_warnings.append(
                "Objective preference and deterministic recommendation conflict; board adjudication required."
            )
        for quality_failure in quality_gate_failures:
            accuracy_warnings.append(f"Quality gate: {quality_failure}")
        if policy_pack_failures:
            accuracy_warnings.append(
                "Policy pack controls failed: " + ", ".join(policy_pack_failures[:8])
            )

        evidence_quality_penalty = 0.0
        if not strong_evidence_refs:
            evidence_quality_penalty += 3.0
        if weak_evidence_refs:
            evidence_quality_penalty += min(6.0, len(weak_evidence_refs))
        if placeholder_evidence_refs:
            evidence_quality_penalty += 4.0
        if unresolved_evidence_refs:
            evidence_quality_penalty += min(8.0, len(unresolved_evidence_refs))
        if llm_freshness == "STALE":
            evidence_quality_penalty += 5.0
        elif llm_freshness == "MISSING_OR_INVALID":
            evidence_quality_penalty += 6.0
        if objective_vendor_conflict_reason:
            evidence_quality_penalty += 8.0
        if quality_gate_failures:
            evidence_quality_penalty += min(12.0, len(quality_gate_failures) * 4.0)
        if policy_pack_failures:
            evidence_quality_penalty += min(12.0, len(policy_pack_failures) * 2.0)

        control_failure_reasons = base_control_failure_reasons + [
            f"policy_pack_control_failed:{control_id}" for control_id in policy_pack_failures
        ]
        disqualifiers.extend([f"control_failure:{reason}" for reason in control_failure_reasons])
        disqualifiers.extend([f"quality_gate:{reason}" for reason in quality_gate_failures])
        if objective_vendor_conflict_reason:
            disqualifiers.append("objective_vendor_preference_conflict")
        deduped_disqualifiers: list[str] = []
        seen_disqualifiers: set[str] = set()
        for item in disqualifiers:
            key = item.strip().lower()
            if not key or key in seen_disqualifiers:
                continue
            seen_disqualifiers.add(key)
            deduped_disqualifiers.append(item.strip())
        disqualifiers = deduped_disqualifiers
        decision_allowed = len(control_failure_reasons) == 0
        evidence_ready = len(quality_gate_failures) == 0
        confidence_score = round(
            max(
                0.0,
                min(
                    100.0,
                    selected["total"]
                    - (8.0 * len(control_failure_reasons))
                    - evidence_quality_penalty
                    + min(6.0, len(role_bundle) * 2.0),
                ),
            ),
            2,
        )
        confidence_level = "HIGH" if confidence_score >= 80 else ("MEDIUM" if confidence_score >= 60 else "LOW")
        confidence_rationale = (
            "Confidence is derived from deterministic scoring, control compliance, evidence quality/freshness, "
            "and governance mode checks."
        )

        alternative_vendors: list[str] = []
        seen_vendor_keys = {_vendor_identity_key(selected["vendor"])}
        for row in vendor_rows[1:]:
            vendor_name = row["vendor"]
            vendor_key = _vendor_identity_key(vendor_name)
            if vendor_key in seen_vendor_keys:
                continue
            seen_vendor_keys.add(vendor_key)
            alternative_vendors.append(vendor_name)

        decision_status = (
            "recommended"
            if decision_allowed and evidence_ready
            else ("needs_more_evidence" if decision_allowed else "not_recommended")
        )
        recommendation = {
            "major_recommendation": (
                f"Select {selected['vendor']} for controlled implementation"
                if decision_status == "recommended"
                else (
                    "Additional evidence is required before a final recommendation can be issued"
                    if decision_status == "needs_more_evidence"
                    else "Decision not recommended pending control remediation"
                )
            ),
            "selected_vendor": selected["vendor"] if decision_status == "recommended" else None,
            "score": selected["total"],
            "alternatives": alternative_vendors,
            "decision_status": decision_status,
            "decision_drivers": [
                f"Top weighted score under deterministic evaluation ({selected['total']})",
                f"Solution focus: {selected.get('focus')}",
                "Aligned with required controls and governance policy constraints",
                "Supports measurable resilience, security and operating model outcomes",
            ]
            + (["CONSTRAINTS-FIRST controls inferred from active business profile"] if constraints_mode_auto_controls else [])
            + (["Objective preference mismatch detected; manual board adjudication required"] if objective_vendor_conflict_reason else []),
            "recommended_option_profile": next((o for o in ranked_options if o.get("vendor") == selected["vendor"]), None),
            "ranked_options": ranked_options,
            "evidence_ids": evidence_ids_seed,
            "evidence_quality": {
                "refs_total": len(evidence_ref_details),
                "strong_refs": strong_evidence_refs,
                "weak_refs": weak_evidence_refs,
                "placeholder_refs": placeholder_evidence_refs,
                "unresolved_refs": unresolved_evidence_refs,
                "details": evidence_ref_details,
                "evidence_objects": evidence_objects,
                "llm_audit_timestamp": llm_audit_timestamp,
                "llm_audit_timestamp_source": llm_audit_timestamp_source,
                "llm_provider_reported_timestamp": llm_provider_reported_timestamp,
                "llm_freshness": llm_freshness,
                "supporting_refs": supporting_evidence_refs,
                "claim_coverage": evidence_claim_coverage,
                "gates": {
                    "min_strong_refs": evidence_min_strong_refs,
                    "min_claim_coverage": evidence_min_claim_coverage,
                    "require_fresh_llm": evidence_require_fresh_llm,
                },
            },
            "success_metrics": success_metric_targets,
            "guardrails": guardrails,
            "disqualifiers": disqualifiers,
            "residual_risks": residual_risks,
            "assumptions": assumptions,
            "risk_treatment": risk_treatment,
            "confidence_score": confidence_score,
            "confidence_level": confidence_level,
            "confidence_rationale": confidence_rationale,
            "accuracy_warnings": accuracy_warnings,
            "quality_gate_failures": quality_gate_failures,
            "signing_trust": {
                "signing_key_id": signing_key_id,
                "key_mode": key_mode,
                "trust_source": trust_source,
                "trust_registry_mode": trust_registry_mode,
                "allow_registry_autoregister": allow_registry_autoregister,
                "active_key_registered": active_key_registered,
                "registered_key_count": registered_key_count,
                "production_trust_ready": production_trust_ready,
                "warnings": signing_trust_warnings,
            },
            "control_failure_reasons": control_failure_reasons,
            "policy_pack_compliance": policy_pack_results,
            "policy_assessment_notice": (
                "Policy pack results are internal control-signal assessments and not independent legal compliance determinations."
            ),
            "claim_ids": evidence_ids_seed,
        }

        # When LLM analysis is present, merge LLM sections (extracted earlier)
        # with deterministic sections; otherwise use templates only
        if isinstance(llm_analysis, dict) and llm_analysis:
            deterministic_sections = _build_human_readable_sections(
                execution_id, profile, schema_id, rp, role_bundle, recommendation,
                vendor_rows=vendor_rows, compliance_matrix=compliance_matrix,
                governance_modes=governance_modes, intent_signals=intent_signals,
            )
            # Keep decision-critical sections deterministic to avoid recommendation drift.
            recommendation_locked_titles = {"Executive Summary", "Down-Select Recommendation"}
            by_title: dict[str, dict[str, str]] = {}
            for s in deterministic_sections:
                by_title[s["title"]] = s
            for s in llm_sections:
                if s.get("title") in recommendation_locked_titles:
                    continue
                by_title[s["title"]] = s
            draft_sections = list(by_title.values())
        else:
            draft_sections = _build_human_readable_sections(
                execution_id, profile, schema_id, rp, role_bundle, recommendation,
                vendor_rows=vendor_rows, compliance_matrix=compliance_matrix,
                governance_modes=governance_modes, intent_signals=intent_signals,
            )
        sections = _enforce_sections(required_sections, draft_sections)
        locked_sections = _build_recommendation_locked_sections(role_bundle, recommendation)
        sections = [
            {
                "title": section["title"],
                "content": locked_sections.get(section["title"], section["content"]),
            }
            for section in sections
        ]

        success_metrics_section = next(
            (
                section for section in sections
                if str(section.get("title", "")).strip().lower() == "success metrics"
            ),
            None,
        )
        success_metrics_text = str((success_metrics_section or {}).get("content", "")).strip()
        explicit_targets = [
            target for target in intent_signals.get("explicit_targets", [])
            if isinstance(target, str) and target.strip()
        ]
        missing_intent_targets = [
            target for target in explicit_targets
            if target.lower() not in success_metrics_text.lower()
        ]
        required_report_fields = {
            "success_metrics_present": bool(recommendation.get("success_metrics")),
            "guardrails_present": bool(recommendation.get("guardrails")),
            "assumptions_present": bool(recommendation.get("assumptions")),
            "disqualifiers_present": isinstance(recommendation.get("disqualifiers"), list),
            "residual_risks_present": bool(recommendation.get("residual_risks")),
            "success_metrics_section_present": success_metrics_section is not None and bool(success_metrics_text),
            "intent_targets_preserved": len(missing_intent_targets) == 0,
        }
        report_completeness_failures = [
            field for field, passed in required_report_fields.items()
            if not passed
        ]
        if report_completeness_failures:
            failure_message = (
                "board_report_completeness_failed: " + ", ".join(report_completeness_failures)
            )
            if failure_message not in recommendation["quality_gate_failures"]:
                recommendation["quality_gate_failures"].append(failure_message)
            if failure_message not in recommendation["accuracy_warnings"]:
                recommendation["accuracy_warnings"].append(
                    "Board report completeness validation failed for required decision fields."
                )
            if recommendation["decision_status"] == "recommended":
                recommendation["decision_status"] = "needs_more_evidence"
                recommendation["selected_vendor"] = None
                recommendation["major_recommendation"] = (
                    "Additional evidence is required before a final recommendation can be issued"
                )
        if missing_intent_targets:
            recommendation["accuracy_warnings"].append(
                "Some explicit intent targets were not preserved verbatim in Success Metrics."
            )
        report_completeness = {
            "checks": required_report_fields,
            "missing_intent_targets": missing_intent_targets,
            "status": "PASS" if not report_completeness_failures else "FAIL",
            "failure_count": len(report_completeness_failures),
        }

        evidence_by_id = {item["evidence_id"]: item for item in evidence_objects}
        evidence_by_ref = {item["source_ref"]: item for item in evidence_objects}
        fallback_evidence_ids = [item["evidence_id"] for item in evidence_objects if item["resolvable"]]
        if not fallback_evidence_ids:
            fallback_evidence_ids = [item["evidence_id"] for item in evidence_objects]

        role_to_evidence_ids: dict[str, list[str]] = {}
        for role_item in role_bundle:
            role_name = str(role_item.get("role", "unknown"))
            role_refs = _normalize_string_list(role_item.get("evidence_refs"))
            role_ids = [
                evidence_by_ref[ref]["evidence_id"]
                for ref in role_refs
                if ref in evidence_by_ref
            ]
            if role_ids:
                role_to_evidence_ids[role_name] = role_ids

        evidence_entries: list[dict[str, Any]] = []
        unresolved_claim_bindings = 0
        for idx, section in enumerate(sections, start=1):
            source_role = role_bundle[(idx - 1) % len(role_bundle)]["role"] if role_bundle else "system"
            candidate_evidence_ids = role_to_evidence_ids.get(source_role, fallback_evidence_ids)
            candidate_evidence_ids = [e_id for e_id in candidate_evidence_ids if e_id in evidence_by_id][:3]
            unresolved = len(candidate_evidence_ids) == 0
            if unresolved:
                unresolved_claim_bindings += 1
                candidate_evidence_ids = [f"unresolved-evidence-{idx}"]
            source_refs = [
                evidence_by_id[e_id]["source_ref"]
                for e_id in candidate_evidence_ids
                if e_id in evidence_by_id
            ]
            primary_source_ref = source_refs[0] if source_refs else f"unresolved-claim-source-{idx}"
            primary_meta = _classify_evidence_ref(primary_source_ref)
            claim_seed = f"{execution_id}:{section['title']}:{'|'.join(candidate_evidence_ids)}"
            claim_id = f"claim-{_sha256_text(claim_seed)[:16]}"
            evidence_entries.append(
                {
                    "claim_id": claim_id,
                    "report_section": section["title"],
                    "source_role": source_role,
                    "source_ref": primary_source_ref,
                    "source_refs": source_refs,
                    "evidence_ids": candidate_evidence_ids,
                    "source_ref_strength": primary_meta["strength"],
                    "source_ref_category": primary_meta["category"],
                    "policy_ref": f"{rp['reasoning_level']}/{rp['policy_level']}",
                    "confidence_reason": "Deterministic evidence linkage",
                    "binding_status": "UNRESOLVED" if unresolved else "BOUND",
                }
            )

        if unresolved_claim_bindings > 0:
            unresolved_issue = (
                f"unresolved claim-to-evidence bindings ({unresolved_claim_bindings})"
            )
            if unresolved_issue not in recommendation["quality_gate_failures"]:
                recommendation["quality_gate_failures"].append(unresolved_issue)
            if unresolved_issue not in recommendation["accuracy_warnings"]:
                recommendation["accuracy_warnings"].append(
                    "One or more report claims are not bound to concrete evidence objects."
                )
            if unresolved_issue not in recommendation["disqualifiers"]:
                recommendation["disqualifiers"].append(unresolved_issue)
            if recommendation["decision_status"] == "recommended":
                recommendation["decision_status"] = "needs_more_evidence"
                recommendation["selected_vendor"] = None
                recommendation["major_recommendation"] = (
                    "Additional evidence is required before a final recommendation can be issued"
                )
                recommendation["decision_drivers"].append(
                    "Claim-to-evidence bindings are incomplete; recommendation held pending evidence closure."
                )

        recommendation["claim_ids"] = [e["claim_id"] for e in evidence_entries[:3]]
        recommendation["evidence_ids"] = sorted(set(recommendation["evidence_ids"] + recommendation["claim_ids"]))[:6]

        board_report = {
            "execution_id": execution_id,
            "schema_id": schema_id,
            "profile_id": profile_id,
            "sections": sections,
            "report_completeness": report_completeness,
            "major_recommendations": [recommendation],
            "ranked_options": ranked_options,
            "intent_coverage": intent_signals,
            "decision_summary": {
                "selected_vendor": recommendation["selected_vendor"],
                "alternatives_considered": recommendation["alternatives"],
                "confidence_score": recommendation["confidence_score"],
                "confidence_level": recommendation["confidence_level"],
                "confidence_rationale": recommendation["confidence_rationale"],
                "decision_basis": (
                    f"LLM-analysed content ({llm_provider}) governed by deterministic scoring + profile/policy controls"
                    if isinstance(llm_analysis, dict) and llm_analysis
                    else "Deterministic weighted scoring + profile/policy controls + role evidence"
                ),
                "decision_status": recommendation["decision_status"],
                "governance_modes": governance_modes,
                "control_failure_reasons": recommendation["control_failure_reasons"],
                "quality_gate_failures": recommendation["quality_gate_failures"],
                "accuracy_warnings": recommendation["accuracy_warnings"],
                "signing_trust": recommendation["signing_trust"],
                "success_metrics": recommendation.get("success_metrics", []),
                "guardrails": recommendation.get("guardrails", []),
                "disqualifiers": recommendation.get("disqualifiers", []),
                "residual_risks": recommendation.get("residual_risks", []),
                "assumptions": recommendation.get("assumptions", []),
                "policy_assessment_notice": recommendation.get("policy_assessment_notice"),
                "policy_pack_summary": [
                    {
                        "pack_id": item.get("pack_id"),
                        "fail_count": item.get("summary", {}).get("fail_count"),
                    }
                    for item in policy_pack_results
                ],
                "report_completeness": report_completeness,
                "constraints_mode_controls_source": (
                    "profile_required_controls"
                    if constraints_mode_auto_controls
                    else "explicit_or_default"
                ),
            },
            "implementation_plan": [
                "Phase 1 (0-30 days): baseline architecture, migration wave plan, and KPI instrumentation.",
                "Phase 2 (31-90 days): pilot deployment with zero-downtime controls and security hardening.",
                "Phase 3 (91-180 days): scaled rollout, assurance audits, and benefits realization tracking.",
            ],
            "llm_provenance": (
                {
                    "provider": llm_provider,
                    "content_source": "llm_analysis",
                    "governance_layer": "DIIaC deterministic scoring, signing, merkle, audit",
                    "llm_sections_used": len(llm_sections),
                    "llm_options_used": len(llm_options),
                }
                if isinstance(llm_analysis, dict) and llm_analysis
                else None
            ),
            "policy_pack_compliance": policy_pack_results,
            "deterministic_input_snapshot_hash": deterministic_input_snapshot_hash,
        }
        evidence_trace_map = {
            "execution_id": execution_id,
            "evidence_objects": evidence_objects,
            "entries": evidence_entries,
            "recommendation_claim_links": [
                {"recommendation": recommendation["major_recommendation"], "claim_ids": recommendation["claim_ids"]}
            ],
            "binding_summary": {
                "total_claims": len(evidence_entries),
                "unresolved_claim_bindings": unresolved_claim_bindings,
            },
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
        vendor_scoring_matrix = {
            "execution_id": execution_id,
            "deterministic": True,
            "rows": vendor_rows,
        }
        deterministic_log = {
            "strict_deterministic_mode": strict_deterministic_mode,
            "context_hash": context_hash,
            "stages": [
                {"stage": "freeze_deterministic_input", "hash": _sha256_text(context_hash + "0"), "status": "PASS"},
                {"stage": "collect_role_inputs", "hash": _sha256_text(context_hash + "1"), "status": "PASS"},
                {"stage": "normalize_claims", "hash": _sha256_text(context_hash + "2"), "status": "PASS"},
                {"stage": "bind_schema", "hash": _sha256_text(context_hash + "3"), "status": "PASS"},
                {"stage": "generate_structured_draft", "hash": _sha256_text(context_hash + "4"), "status": "PASS"},
                {"stage": "enforce_rp_sections", "hash": _sha256_text(context_hash + "5"), "status": "PASS"},
                {"stage": "render_reports", "hash": _sha256_text(context_hash + "6"), "status": "PASS"},
            ],
        }

        artifacts_payloads: dict[str, Any] = {
            "board_report.json": board_report,
            "board_report.md": _render_board_report_markdown(board_report),
            "deterministic_compilation_log.json": deterministic_log,
            "deterministic_input_snapshot.json": {
                "execution_id": execution_id,
                "input_snapshot_hash": deterministic_input_snapshot_hash,
                "snapshot": deterministic_input_snapshot,
            },
            "evidence_trace_map.json": evidence_trace_map,
            "evidence_objects.json": evidence_objects,
            "role_input_bundle.json": {"execution_context_id": context_id, "roles": role_bundle},
            "schema_contract.json": schema_contract,
            "vendor_scoring_matrix.json": vendor_scoring_matrix,
            "business_profile_snapshot.json": profile_snapshot,
            "profile_compliance_matrix.json": compliance_matrix,
            "policy_pack_compliance.json": policy_pack_results,
            "report_completeness.json": report_completeness,
            "profile_override_log.json": execution_profile_overrides,
            "down_select_recommendation.json": recommendation,
            "trace_map.json": evidence_trace_map,
            "scoring.json": vendor_scoring_matrix,
        }
        # Include the raw LLM analysis as a governed artifact for full auditability
        if isinstance(llm_analysis, dict) and llm_analysis:
            artifacts_payloads["llm_analysis_raw.json"] = {
                "provider": llm_provider,
                "analysis": llm_analysis,
                "audit_timestamp": llm_audit_timestamp,
                "audit_timestamp_source": llm_audit_timestamp_source,
                "provider_reported_audit_timestamp": llm_provider_reported_timestamp,
                "audit_freshness": llm_freshness,
                "governed_at": _utc_now(),
                "llm_output_hash": _sha256_text(_canonical_json(llm_analysis)),
            }

        artifact_hashes = {
            name: _sha256_text(payload if isinstance(payload, str) else _canonical_json(payload))
            for name, payload in artifacts_payloads.items()
        }
        leaves = [
            {"name": name, "hash": artifact_hashes[name], "leaf_hash": _sha256_text(f"{name}:{artifact_hashes[name]}")}
            for name in sorted(artifact_hashes)
        ]
        merkle = _build_merkle(leaves)
        pack_hash = _sha256_text("".join(artifact_hashes[name] for name in sorted(artifact_hashes)))

        manifest = {
            "execution_id": execution_id,
            "context_hash": context_hash,
            "deterministic_input_snapshot_hash": deterministic_input_snapshot_hash,
            "profile_id": profile_id,
            "profile_hash": profile_snapshot["profile_hash"],
            "schema_id": schema_id,
            "schema_hash": schema_contract["schema_hash"],
            "pack_hash": pack_hash,
            "governance_modes": governance_modes,
            "policy_packs": [item.get("pack_id") for item in policy_pack_results],
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

        signed_at = _utc_now()
        signing_payload = _build_signature_payload(
            execution_id=execution_id,
            pack_hash=pack_hash,
            merkle_root=merkle["root"],
            manifest_hash=manifest_hash,
            signed_at=signed_at,
        )
        signing_payload_json = _canonical_json(signing_payload)
        sig_b64 = ""
        if signing_enabled:
            sig_b64 = base64.b64encode(private_key.sign(signing_payload_json.encode("utf-8"))).decode("utf-8")
        signature_verification = _verify_signature_contract(
            signature_payload=signing_payload,
            signature_b64=sig_b64,
            signing_key_id_value=signing_key_id,
        )
        if signing_enabled and not signature_verification.get("verified", False):
            _log(
                "Signing verification failed immediately after signing; governed compile aborted.",
                level="ERROR",
                execution_id=execution_id,
            )
            return _runtime_error(
                error_code="SIGNATURE_VERIFICATION_FAILED",
                message=(
                    "Signature verification failed immediately after signing. "
                    "Compilation aborted to preserve trust guarantees."
                ),
                dependency="signing_trust",
                details=signature_verification,
            )
        trusted_public_key_b64 = active_entry.get("public_key_b64") if isinstance(active_entry, dict) else None

        artifacts_payloads["governance_manifest.json"] = manifest
        artifacts_payloads["signed_export.sigmeta.json"] = {
            "signature_alg": "Ed25519",
            "signing_key_id": signing_key_id,
            "signature_payload_schema_version": signature_payload_schema_version,
            "signature_scope": "execution_manifest",
            "signed_at": signing_payload["signed_at"],
            "execution_id": execution_id,
            "pack_hash": pack_hash,
            "merkle_root": merkle["root"],
            "manifest_hash": manifest_hash,
            "signature": sig_b64,
            "signature_payload": signing_payload,
            "trust_source": trust_source,
            "trust_registry_mode": trust_registry_mode,
            "public_key_b64": trusted_public_key_b64,
            "verification": signature_verification,
        }
        artifacts_payloads["signed_export.sig"] = sig_b64
        artifacts_payloads["verification_manifest.json"] = {
            "verification_manifest_version": "diiac-verification-manifest-v1",
            "execution_id": execution_id,
            "pack_hash": pack_hash,
            "manifest_hash": manifest_hash,
            "merkle_root": merkle["root"],
            "signature_alg": "Ed25519",
            "signature": sig_b64,
            "signature_payload_schema_version": signature_payload_schema_version,
            "signature_payload": signing_payload,
            "signing_key_id": signing_key_id,
            "trust_source": trust_source,
            "trust_registry_mode": trust_registry_mode,
            "public_key_b64": trusted_public_key_b64,
            "verification": signature_verification,
            "offline_verification": {
                "script": "scripts/verify_decision_pack.js",
                "notes": "Use exported signed_export.sigmeta.json + verification_manifest.json for offline authenticity checks.",
            },
        }
        artifacts_payloads["verification_instructions.md"] = (
            "# Decision Pack Offline Verification\n\n"
            "1. Open `governance_manifest.json` and `signed_export.sigmeta.json`.\n"
            "2. Verify artifact hashes and Merkle root from the manifest.\n"
            "3. Verify `signed_export.sig` against canonical `signature_payload` using Ed25519.\n"
            "4. Validate `pack_hash`, `manifest_hash`, and `merkle_root` alignment.\n"
            "5. Confirm verification status is PASS before relying on this pack.\n"
        )
        artifacts_payloads["replay_certificate.json"] = {
            "execution_id": execution_id,
            "strict_deterministic_mode": strict_deterministic_mode,
            "context_hash": context_hash,
            "input_snapshot_hash": deterministic_input_snapshot_hash,
            "expected_execution_id": (
                str(uuid.uuid5(uuid.NAMESPACE_URL, f"diiac:{context_hash}"))
                if strict_deterministic_mode
                else execution_id
            ),
            "pack_hash": pack_hash,
            "manifest_hash": manifest_hash,
            "signed_at": signing_payload["signed_at"],
            "status": "REPLAY_READY" if strict_deterministic_mode else "NON_STRICT_MODE",
        }

        exec_dir = artifacts_dir / execution_id
        exec_dir.mkdir(exist_ok=True)
        for name, content in artifacts_payloads.items():
            fpath = exec_dir / name
            if isinstance(content, str):
                # Write bytes directly to avoid platform newline translation
                # that can break deterministic hash verification for text artifacts.
                fpath.write_bytes(content.encode("utf-8"))
            else:
                fpath.write_bytes(json.dumps(content, indent=2).encode("utf-8"))

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
            "signature_payload_schema_version": signature_payload_schema_version,
            "signature_verification": signature_verification,
            "trust_source": trust_source,
            "profile_id": profile_id,
            "schema_id": schema_id,
            "rp_levels": rp,
            "governance_modes": governance_modes,
            "board_report": board_report,
            "evidence_trace_map": evidence_trace_map,
            "vendor_scoring_matrix": vendor_scoring_matrix,
            "down_select_recommendation": recommendation,
            "deterministic_compilation_log": deterministic_log,
            "schema_contract": schema_contract,
            "business_profile_snapshot": profile_snapshot,
            "profile_compliance_matrix": compliance_matrix,
            "profile_override_log": execution_profile_overrides,
            "governance_manifest": manifest,
            "deterministic_input_snapshot_hash": deterministic_input_snapshot_hash,
            "policy_pack_compliance": policy_pack_results,
            "artifacts": sorted(list(artifacts_payloads.keys())),
            "created_at": _utc_now(),
        }
        executions[execution_id] = execution
        store.save_execution(execution_id, execution)
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
            "governance_modes": governance_modes,
            "decision_summary": board_report["decision_summary"],
            "deterministic_input_snapshot_hash": deterministic_input_snapshot_hash,
            "execution_state": {
                "signature_present": bool(sig_b64),
                "signing_enabled": signing_enabled,
                "signature_payload_schema_version": signature_payload_schema_version,
                "signature_verified": bool(signature_verification.get("verified")),
                "trust_source": trust_source,
            },
        }, 201


    @app.before_request
    def require_admin_auth() -> Any:
        if not request.path.startswith("/admin"):
            return None

        auth_required = admin_auth_enabled and runtime_env not in {"dev", "development"}
        if not auth_required:
            return None

        authz = request.headers.get("Authorization", "")
        expected = f"Bearer {admin_api_token}" if admin_api_token else ""
        if not expected or not hmac.compare_digest(authz, expected):
            return jsonify({"error": "admin_auth_required", "message": "Valid admin bearer token required."}), 401
        return None

    @app.get("/health")
    def health() -> Any:
        readiness = _readiness_checks()
        status = "OK" if readiness["overall_ready"] else "DEGRADED"
        return jsonify({
            "status": status,
            "readiness": readiness,
            "timestamp": _utc_now(),
        })

    @app.get("/admin/health")
    def admin_health() -> Any:
        readiness = _readiness_checks()
        return jsonify(
            {
                "status": "OK" if readiness["overall_ready"] else "DEGRADED",
                "strict_deterministic_mode": strict_deterministic_mode,
                "signing_enabled": signing_enabled,
                "signing_key_id": signing_key_id,
                "key_mode": key_mode,
                "trust_source": trust_source,
                "trust_registry_mode": trust_registry_mode,
                "allow_registry_autoregister": allow_registry_autoregister,
                "key_registry_update_performed": key_registry_update_performed,
                "signature_payload_schema_version": signature_payload_schema_version,
                "production_trust_ready": production_trust_ready,
                "signing_trust_warnings": signing_trust_warnings,
                "ledger_record_count": len(ledger_logs),
                "ledger_chain_valid": ledger_chain_valid,
                "readiness": readiness,
                "timestamp": _utc_now(),
            }
        )

    @app.get("/admin/config")
    def admin_config() -> Any:
        return jsonify(
            {
                "version": app_version,
                "runtime_model": ["react-vite-frontend", "express-backend"],
                "approved_schemas": sorted(approved_schemas),
                "profiles_count": len(profiles),
                "policy_packs": [p.get("pack_id") for p in policy_packs if isinstance(p, dict)],
                "policy_pack_enforce": policy_pack_enforce,
                "evidence_gate_config": {
                    "min_strong_refs": evidence_min_strong_refs,
                    "min_claim_coverage": evidence_min_claim_coverage,
                    "require_fresh_llm": evidence_require_fresh_llm,
                    "llm_audit_min_timestamp": llm_audit_min_timestamp.isoformat(),
                },
                "signing_trust": {
                    "signing_enabled": signing_enabled,
                    "signing_key_id": signing_key_id,
                    "key_mode": key_mode,
                    "trust_source": trust_source,
                    "trust_registry_mode": trust_registry_mode,
                    "allow_registry_autoregister": allow_registry_autoregister,
                    "signature_payload_schema_version": signature_payload_schema_version,
                    "production_trust_ready": production_trust_ready,
                },
                "admin_auth_enabled": admin_auth_enabled,
                "runtime_env": runtime_env,
            }
        )

    @app.get("/admin/config/contract")
    def admin_config_contract() -> Any:
        profile_ids = sorted(
            [p.get("profile_id") for p in profiles if isinstance(p, dict) and isinstance(p.get("profile_id"), str)]
        )
        policy_pack_ids = sorted(
            [p.get("pack_id") for p in policy_packs if isinstance(p, dict) and isinstance(p.get("pack_id"), str)]
        )
        approved_schema_list = sorted(approved_schemas)
        contract_payload = {
            "profiles": {
                "count": len(profile_ids),
                "ids": profile_ids,
                "hash": _sha256_text(_canonical_json(profile_ids)),
            },
            "policy_packs": {
                "count": len(policy_pack_ids),
                "ids": policy_pack_ids,
                "hash": _sha256_text(_canonical_json(policy_pack_ids)),
            },
            "approved_schemas": {
                "count": len(approved_schema_list),
                "ids": approved_schema_list,
                "hash": _sha256_text(_canonical_json(approved_schema_list)),
            },
        }
        contract_payload["contract_hash"] = _sha256_text(_canonical_json(contract_payload))
        contract_payload["generated_at"] = _utc_now()
        return jsonify(contract_payload)

    @app.post("/api/human-input/role")
    def role_input() -> Any:
        payload = request.get_json(silent=True) or {}
        required = ["execution_context_id", "role", "domain", "assertions", "non_negotiables", "risk_flags", "evidence_refs"]
        missing = [k for k in required if k not in payload]
        if missing:
            return jsonify({"error": "missing_fields", "missing": missing}), 400

        for field, max_len in {"execution_context_id": CONTEXT_ID_MAX, "role": ROLE_FIELD_MAX, "domain": ROLE_FIELD_MAX}.items():
            err = _validate_string_field(payload, field, max_len)
            if err:
                response, code = err
                return jsonify(response), code

        for arr in ["assertions", "non_negotiables", "risk_flags", "evidence_refs"]:
            err = _validate_string_list_field(payload, arr)
            if err:
                response, code = err
                return jsonify(response), code
        if "idempotency_key" in payload:
            err = _validate_string_field(payload, "idempotency_key", 128)
            if err:
                response, code = err
                return jsonify(response), code

        ctx = payload["execution_context_id"]
        evidence_ref_warnings = []
        for ref in payload.get("evidence_refs", []):
            classification = _classify_evidence_ref(ref)
            if classification["strength"] == "weak":
                evidence_ref_warnings.append(
                    f"Weak evidence ref '{ref}' ({classification['category']}). Prefer URI/document/hash references."
                )
        role_inputs.setdefault(ctx, [])
        idempotency_key = _role_input_idempotency_key(payload)
        for existing in role_inputs[ctx]:
            existing_key = _role_input_idempotency_key(existing)
            if existing_key == idempotency_key:
                return jsonify({
                    "stored": False,
                    "duplicate_ignored": True,
                    "execution_context_id": ctx,
                    "role_count": len(role_inputs[ctx]),
                    "idempotency_key": idempotency_key,
                    "evidence_ref_warnings": evidence_ref_warnings,
                }), 200

        persisted_payload = {
            "execution_context_id": payload["execution_context_id"],
            "role": payload["role"],
            "domain": payload["domain"],
            "assertions": _normalize_string_list(payload.get("assertions")),
            "non_negotiables": _normalize_string_list(payload.get("non_negotiables")),
            "risk_flags": _normalize_string_list(payload.get("risk_flags")),
            "evidence_refs": _normalize_string_list(payload.get("evidence_refs")),
            "idempotency_key": idempotency_key,
            "submitted_at": _utc_now(),
        }
        role_inputs[ctx].append(persisted_payload)
        store.append_role_input(ctx, persisted_payload)
        _log(f"Role input accepted for {ctx} (idempotency_key={idempotency_key})")
        return jsonify({
            "stored": True,
            "execution_context_id": ctx,
            "role_count": len(role_inputs[ctx]),
            "idempotency_key": idempotency_key,
            "evidence_ref_warnings": evidence_ref_warnings,
        }), 201

    @app.get("/api/business-profiles")
    def business_profiles() -> Any:
        return jsonify({"profiles": profiles, "profiles_count": len(profiles)})

    def _execute_compile_request(payload: dict[str, Any]) -> tuple[dict[str, Any], int]:
        try:
            return _build_execution(payload)
        except OSError as exc:
            _log(f"Artifact storage failure: {exc}", level="ERROR")
            return _runtime_error(
                error_code="ARTIFACT_STORAGE_UNAVAILABLE",
                message="Artifact storage is unavailable during governed compile.",
                dependency="artifact_storage",
            )
        except TimeoutError as exc:
            _log(f"Runtime dependency timeout: {exc}", level="ERROR")
            return _runtime_error(
                error_code="RUNTIME_DEPENDENCY_TIMEOUT",
                message="Runtime dependency timed out during governed compile.",
                dependency="runtime_dependency",
            )
        except Exception as exc:
            _log(f"Unhandled governed compile exception: {exc}", level="ERROR")
            return {
                "error": "governed_compile_internal_error",
                "message": "Governed compile failed due to an internal runtime exception.",
                "details": str(exc),
            }, 500

    @app.post("/api/governed-compile")
    def governed_compile() -> Any:
        payload = request.get_json(silent=True) or {}
        err = _validate_compile_payload(payload)
        if err:
            response, code = err
            return jsonify(response), code
        response, code = _execute_compile_request(payload)
        return jsonify(response), code

    @app.post("/api/compile")
    def compile_alias() -> Any:
        payload = request.get_json(silent=True) or {}
        err = _validate_compile_payload(payload)
        if err:
            response, code = err
            return jsonify(response), code
        response, code = _execute_compile_request(payload)
        return jsonify(response), code

    @app.get("/admin/executions")
    def admin_executions() -> Any:
        return jsonify({"executions": list(executions.values())})

    @app.get("/admin/executions/<execution_id>/logs")
    def admin_execution_logs(execution_id: str) -> Any:
        if execution_id not in executions:
            return jsonify({"error": "execution_not_found", "execution_id": execution_id}), 404
        _append_ledger("GOVERNANCE_AUDIT_ACCESS", {"access_type": "execution_logs", "execution_id": execution_id})
        return jsonify({"logs": execution_logs.get(execution_id, [])})

    @app.get("/admin/logs")
    def admin_logs() -> Any:
        source = request.args.get("source", "backend")
        level = request.args.get("level")
        logs = backend_logs if source == "backend" else ledger_logs
        if level:
            logs = [entry for entry in logs if entry.get("level") == level]
        _append_ledger("GOVERNANCE_AUDIT_ACCESS", {"access_type": "admin_logs", "source": source})
        return jsonify({"logs": logs})

    @app.get("/admin/logs/backend")
    def admin_logs_backend() -> Any:
        return jsonify({"logs": backend_logs})

    @app.get("/admin/logs/ledger")
    def admin_logs_ledger() -> Any:
        return jsonify({"logs": ledger_logs})

    @app.get("/admin/metrics")
    def admin_metrics() -> Any:
        signed_recent = sum(1 for e in list(executions.values())[-5:] if e.get("signature"))
        executions_total = len(executions)
        ledger_record_count = len(ledger_logs)
        status = "OK"
        alerts: list[str] = []

        if executions_total > 0 and signed_recent == 0:
            status = "WARN"
            alerts.append("MTR-001: No signed executions in the latest window.")
        if executions_total > 0 and ledger_record_count == 0:
            status = "WARN"
            alerts.append("MTR-002: Execution data exists but ledger record count is zero.")

        return jsonify(
            {
                "health_status": status,
                "executions_total": executions_total,
                "signed_recent_executions": signed_recent,
                "ledger_record_count": ledger_record_count,
                "alerts": alerts,
                "threshold_recommendations": {
                    "signed_recent_executions_min": 1,
                    "ledger_record_count_min_when_executions_present": 1,
                },
                "last_updated": _utc_now(),
            }
        )

    @app.get("/admin/db/status")
    def admin_db_status() -> Any:
        tables = {
            "backend_logs": len(backend_logs),
            "ledger": len(ledger_logs),
            "executions": len(executions),
            "role_inputs": sum(len(v) for v in role_inputs.values()),
            "audit_exports": len(audit_exports),
        }
        integrity = {
            "ok": store.is_healthy() and ledger_chain_valid,
            "db_healthy": store.is_healthy(),
            "ledger_chain_valid": ledger_chain_valid,
            "key_registry_ok": signing_enabled and public_keys_file.exists() and registered_key_count > 0 and active_key_registered,
            "production_trust_ready": production_trust_ready,
            "trust_source": trust_source,
            "trust_registry_mode": trust_registry_mode,
            "signature_payload_schema_version": signature_payload_schema_version,
            "signing_trust_warnings": signing_trust_warnings,
        }
        db_path_str = str(db_path)
        db_size = Path(db_path_str).stat().st_size if db_path_str != ":memory:" and Path(db_path_str).exists() else 0
        return jsonify({
            "db_path": db_path_str,
            "db_size_bytes": db_size,
            "tables": tables,
            "integrity": integrity,
            "timestamp": _utc_now(),
        })

    @app.get("/admin/db/table/<table_name>")
    def admin_db_table(table_name: str) -> Any:
        allowed = {"backend_logs", "ledger", "executions", "role_inputs", "audit_exports"}
        if table_name not in allowed:
            return jsonify({"error": "invalid_table", "allowed": sorted(allowed)}), 400
        data_map = {
            "backend_logs": backend_logs,
            "ledger": ledger_logs,
            "executions": list(executions.values()),
            "role_inputs": [
                {"execution_context_id": k, "inputs": v}
                for k, v in role_inputs.items()
            ],
            "audit_exports": list(audit_exports.values()),
        }
        rows = data_map[table_name]
        return jsonify({"table": table_name, "row_count": len(rows), "rows": rows[-100:]})

    @app.post("/admin/db/maintenance/compact")
    def admin_db_compact() -> Any:
        try:
            store._conn.execute("VACUUM")
            db_path_str = str(db_path)
            db_size = (
                Path(db_path_str).stat().st_size
                if db_path_str != ":memory:" and Path(db_path_str).exists()
                else 0
            )
            _log("Database VACUUM completed")
            return jsonify({
                "compacted": True,
                "db_size_bytes_after": db_size,
                "timestamp": _utc_now(),
            })
        except Exception as exc:
            return jsonify({"compacted": False, "error": str(exc)}), 500

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
        names = [leaf["name"] for leaf in leaves]
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
        return jsonify(key_registry)

    @app.get("/verify/execution/<execution_id>")
    def verify_execution(execution_id: str) -> Any:
        execution = executions.get(execution_id)
        if not execution:
            return jsonify({"error": "execution_not_found", "execution_id": execution_id}), 404
        ledger_match = any(
            r.get("execution_id") == execution_id
            and r.get("pack_hash") == execution["pack_hash"]
            for r in ledger_logs
        )
        return jsonify(
            {
                "execution_id": execution_id,
                "pack_hash": execution["pack_hash"],
                "manifest_hash": execution["manifest_hash"],
                "merkle_root": execution["merkle_root"],
                "ledger_record_hash": execution["ledger_record_hash"],
                "signature_present": bool(execution.get("signature")),
                "signature_payload_schema_version": execution.get("signature_payload_schema_version"),
                "signing_key_id": execution.get("signing_key_id"),
                "trust_source": execution.get("trust_source"),
                "status": "VERIFIABLE" if ledger_match else "NOT_VERIFIABLE",
                "ledger_match": ledger_match,
            }
        )

    @app.post("/verify/pack")
    def verify_pack() -> Any:
        payload = request.get_json(silent=True) or {}
        err = _validate_string_field(payload, "execution_id", CONTEXT_ID_MAX)
        if err:
            response, code = err
            return jsonify(response), code
        err = _validate_string_field(payload, "pack_hash", 128)
        if err:
            response, code = err
            return jsonify(response), code
        if "manifest_hash" in payload:
            err = _validate_string_field(payload, "manifest_hash", 128)
            if err:
                response, code = err
                return jsonify(response), code

        execution = executions.get(payload.get("execution_id"))
        if not execution:
            return jsonify({"error": "execution_not_found", "execution_id": payload.get("execution_id")}), 404

        try:
            sigmeta_file = (
                artifacts_dir / execution["execution_id"]
                / "signed_export.sigmeta.json"
            )
            sigmeta = json.loads(sigmeta_file.read_text())
        except (OSError, json.JSONDecodeError, KeyError) as exc:
            _log(f"Signature metadata unavailable: {exc}", level="ERROR", execution_id=execution["execution_id"])
            response, code = _runtime_error(
                error_code="SIGNATURE_METADATA_UNAVAILABLE",
                message="Signature metadata is unavailable for pack verification.",
                dependency="artifact_storage",
            )
            return jsonify(response), code

        signature_payload = sigmeta.get("signature_payload")
        signature_b64 = sigmeta.get("signature")
        if not isinstance(signature_b64, str) or not signature_b64.strip():
            sig_file = artifacts_dir / execution["execution_id"] / "signed_export.sig"
            try:
                signature_b64 = sig_file.read_text(encoding="utf-8").strip()
            except OSError:
                signature_b64 = ""
        signing_key_id_value = sigmeta.get("signing_key_id", execution.get("signing_key_id", signing_key_id))
        signature_check = _verify_signature_contract(
            signature_payload=signature_payload,
            signature_b64=signature_b64,
            signing_key_id_value=str(signing_key_id_value),
        )

        payload_alignment = {
            "execution_id": sigmeta.get("execution_id") == execution["execution_id"],
            "pack_hash": sigmeta.get("pack_hash") == execution["pack_hash"],
            "merkle_root": sigmeta.get("merkle_root") == execution["merkle_root"],
            "manifest_hash": sigmeta.get("manifest_hash") == execution["manifest_hash"],
        }
        schema_version = sigmeta.get("signature_payload_schema_version")
        schema_version_valid = isinstance(schema_version, str) and bool(schema_version.strip())

        hash_valid = payload.get("pack_hash") == execution["pack_hash"]
        manifest_consistent = payload.get("manifest_hash", execution["manifest_hash"]) == execution["manifest_hash"]
        overall_valid = bool(
            signature_check.get("verified")
            and hash_valid
            and manifest_consistent
            and all(payload_alignment.values())
            and schema_version_valid
        )
        return jsonify(
            {
                "signature_valid": bool(signature_check.get("verified")),
                "signature_error": signature_check.get("error"),
                "signature_payload_schema_version": schema_version,
                "signing_key_id": signing_key_id_value,
                "payload_alignment": payload_alignment,
                "hash_valid": hash_valid,
                "manifest_consistent": manifest_consistent,
                "overall_valid": overall_valid,
            }
        )

    @app.post("/verify/export")
    def verify_export_bundle() -> Any:
        payload = request.get_json(silent=True) or {}
        err = _validate_string_field(payload, "execution_id", CONTEXT_ID_MAX)
        if err:
            response, code = err
            return jsonify(response), code
        execution_id = payload["execution_id"]
        execution = executions.get(execution_id)
        if not execution:
            return jsonify({"error": "execution_not_found", "execution_id": execution_id}), 404

        sigmeta_file = exports_dir / f"decision-pack_{execution_id}.sigmeta.json"
        sig_file = exports_dir / f"decision-pack_{execution_id}.sig"
        zip_file = exports_dir / f"decision-pack_{execution_id}.zip"
        try:
            sigmeta = json.loads(sigmeta_file.read_text(encoding="utf-8"))
            sig_b64 = sig_file.read_text(encoding="utf-8").strip()
            zip_sha256 = _sha256_bytes(zip_file.read_bytes())
        except (OSError, json.JSONDecodeError) as exc:
            response, code = _runtime_error(
                error_code="EXPORT_VERIFICATION_ARTIFACTS_UNAVAILABLE",
                message="Signed export bundle artifacts are unavailable for verification.",
                dependency="export_storage",
                details={"error": str(exc)},
            )
            return jsonify(response), code

        signature_check = _verify_signature_contract(
            signature_payload=sigmeta.get("signature_payload"),
            signature_b64=sig_b64,
            signing_key_id_value=str(sigmeta.get("signing_key_id", signing_key_id)),
        )
        expected_zip_sha = (
            sigmeta.get("export_bundle", {})
            if isinstance(sigmeta.get("export_bundle"), dict)
            else {}
        ).get("zip_sha256")
        zip_hash_valid = isinstance(expected_zip_sha, str) and expected_zip_sha == zip_sha256
        return jsonify(
            {
                "execution_id": execution_id,
                "signature_valid": bool(signature_check.get("verified")),
                "signature_error": signature_check.get("error"),
                "zip_hash_valid": zip_hash_valid,
                "zip_sha256": zip_sha256,
                "overall_valid": bool(signature_check.get("verified") and zip_hash_valid),
            }
        )

    @app.post("/verify/merkle-proof")
    def verify_merkle_proof() -> Any:
        payload = request.get_json(silent=True) or {}
        err = _validate_string_field(payload, "leaf_hash", 128)
        if err:
            response, code = err
            return jsonify(response), code
        err = _validate_string_field(payload, "merkle_root", 128)
        if err:
            response, code = err
            return jsonify(response), code
        siblings = payload.get("siblings", [])
        if not isinstance(siblings, list) or len(siblings) > LIST_MAX_ITEMS:
            return jsonify({"error": "invalid_field", "field": "siblings"}), 400
        for sib in siblings:
            if not isinstance(sib, str) or len(sib) > 128:
                return jsonify({"error": "invalid_list_item", "field": "siblings"}), 400
        if not isinstance(payload.get("index", 0), int):
            return jsonify({"error": "invalid_field_type", "field": "index", "expected": "integer"}), 400

        valid = _verify_merkle_proof(
            leaf_hash=payload.get("leaf_hash", ""),
            siblings=payload.get("siblings", []),
            index=int(payload.get("index", 0)),
            merkle_root=payload.get("merkle_root", ""),
        )
        return jsonify({"proof_valid": valid})

    @app.post("/verify/replay")
    def verify_replay() -> Any:
        payload = request.get_json(silent=True) or {}
        err = _validate_replay_payload(payload)
        if err:
            response, code = err
            return jsonify(response), code

        context_id = payload["execution_context_id"]
        effective_profile_id = payload["profile_id"]
        if profile_lock_id and profile_lock_id in profiles_by_id:
            effective_profile_id = profile_lock_id
        profile = profiles_by_id.get(effective_profile_id)
        if profile is None:
            return jsonify({"error": "profile_not_found", "profile_id": effective_profile_id}), 404

        raw_role_bundle = role_inputs.get(context_id, [])
        role_bundle: list[dict[str, Any]] = []
        for idx, role_item in enumerate(raw_role_bundle, start=1):
            if not isinstance(role_item, dict):
                continue
            evidence_refs = _normalize_string_list(role_item.get("evidence_refs"))
            role_bundle.append(
                {
                    "execution_context_id": context_id,
                    "role": str(role_item.get("role", "unknown"))[:ROLE_FIELD_MAX],
                    "domain": str(role_item.get("domain", "unknown"))[:ROLE_FIELD_MAX],
                    "assertions": _normalize_string_list(role_item.get("assertions")),
                    "non_negotiables": _normalize_string_list(role_item.get("non_negotiables")),
                    "risk_flags": _normalize_string_list(role_item.get("risk_flags")),
                    "evidence_refs": evidence_refs or [f"auto-ref-{idx}"],
                }
            )
        llm_analysis = payload.get("llm_analysis")
        llm_analysis_hash = (
            _sha256_text(_canonical_json(llm_analysis))
            if isinstance(llm_analysis, dict) and llm_analysis
            else None
        )
        if not role_bundle:
            inline_assertions = _normalize_string_list(payload.get("assertions")) or [
                "Deterministic governed compile initiated from inline payload."
            ]
            inline_non_negotiables = _normalize_string_list(payload.get("non_negotiables")) or ["deterministic-governance"]
            inline_risk_flags = _normalize_string_list(payload.get("risk_flags")) or ["llm-hallucination-risk"]
            inline_evidence_refs = _normalize_string_list(payload.get("evidence_refs"))
            if not inline_evidence_refs and llm_analysis_hash:
                inline_evidence_refs = [f"llm-output-{llm_analysis_hash[:16]}"]
            if not inline_evidence_refs:
                inline_evidence_refs = [f"inline-payload-{_sha256_text(context_id)[:12]}"]

            role_bundle = [
                {
                    "execution_context_id": context_id,
                    "role": str(payload.get("role", "CIO"))[:ROLE_FIELD_MAX],
                    "domain": str(payload.get("domain", "decision"))[:ROLE_FIELD_MAX],
                    "assertions": inline_assertions,
                    "non_negotiables": inline_non_negotiables,
                    "risk_flags": inline_risk_flags,
                    "evidence_refs": inline_evidence_refs,
                }
            ]
        governance_modes, _ = _normalize_governance_modes(payload.get("governance_modes", []))
        effective_payload = dict(payload)
        effective_payload.pop("llm_analysis", None)
        effective_payload["llm_analysis_hash"] = llm_analysis_hash
        effective_payload["profile_id"] = effective_profile_id
        effective_payload["governance_modes"] = governance_modes
        seed_payload = {
            "context_id": context_id,
            "profile_id": effective_profile_id,
            "profile_hash": profile.get("profile_hash"),
            "schema_id": payload["schema_id"],
            "schema_version": payload.get("schema_version", "1.0.0"),
            "rp": {
                "reasoning_level": payload["reasoning_level"],
                "policy_level": payload["policy_level"],
            },
            "role_bundle": role_bundle,
            "request_payload": effective_payload,
            "governance_modes": governance_modes,
        }
        context_hash = _sha256_text(_canonical_json(seed_payload))
        expected_execution_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"diiac:{context_hash}"))
        execution = executions.get(expected_execution_id)
        replay_valid = bool(strict_deterministic_mode and execution is not None)

        certificate = {
            "execution_context_id": context_id,
            "expected_execution_id": expected_execution_id,
            "context_hash": context_hash,
            "replay_valid": replay_valid,
            "strict_deterministic_mode": strict_deterministic_mode,
            "verified_at": _utc_now(),
            "pack_hash": execution.get("pack_hash") if execution else None,
        }
        cert_dir = artifacts_dir / (expected_execution_id if execution else f"replay-{context_hash[:12]}")
        cert_dir.mkdir(parents=True, exist_ok=True)
        cert_path = cert_dir / "replay_certificate.json"
        try:
            cert_path.write_text(json.dumps(certificate, indent=2), encoding="utf-8")
        except OSError as exc:
            _log(f"Replay certificate storage failure: {exc}", level="ERROR")
            response, code = _runtime_error(
                error_code="ARTIFACT_STORAGE_UNAVAILABLE",
                message="Artifact storage is unavailable during replay verification.",
                dependency="artifact_storage",
            )
            return jsonify(response), code

        return jsonify({**certificate, "certificate_path": str(cert_path)})

    @app.get("/trust/status")
    def trust_status() -> Any:
        latest = ledger_logs[-1] if ledger_logs else None
        return jsonify(
            {
                "ledger_records": len(ledger_logs),
                "ledger_chain_valid": ledger_chain_valid,
                "latest_record_hash": latest["record_hash"] if latest else None,
                "latest_merkle_root": latest.get("merkle_root") if latest else None,
            }
        )

    def _generate_signed_export_artifacts(
        execution_id: str, execution: dict[str, Any],
    ) -> tuple[Path, Path, Path, dict[str, Any]]:
        pack_dir = artifacts_dir / execution_id
        zip_path = exports_dir / f"decision-pack_{execution_id}.zip"
        sig_path = exports_dir / f"decision-pack_{execution_id}.sig"
        sigmeta_path = exports_dir / f"decision-pack_{execution_id}.sigmeta.json"

        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for p in sorted(pack_dir.iterdir()):
                zf.write(p, arcname=p.name)

        zip_bytes = zip_path.read_bytes()
        zip_sha256 = _sha256_bytes(zip_bytes)
        artifact_sigmeta_path = pack_dir / "signed_export.sigmeta.json"
        artifact_sig_path = pack_dir / "signed_export.sig"
        if not artifact_sigmeta_path.exists():
            raise OSError("Missing signed_export.sigmeta.json in execution artifacts.")
        artifact_sigmeta = json.loads(artifact_sigmeta_path.read_text(encoding="utf-8"))
        sig_b64 = str(artifact_sigmeta.get("signature", "")).strip()
        if not sig_b64 and artifact_sig_path.exists():
            sig_b64 = artifact_sig_path.read_text(encoding="utf-8").strip()
        signing_key_for_verify = str(artifact_sigmeta.get("signing_key_id", signing_key_id))
        signature_verification = _verify_signature_contract(
            signature_payload=artifact_sigmeta.get("signature_payload"),
            signature_b64=sig_b64,
            signing_key_id_value=signing_key_for_verify,
        )
        if signing_enabled and not signature_verification.get("verified", False):
            raise RuntimeError(
                "Signed export verification failed before export publication: "
                f"{signature_verification.get('error')}"
            )

        sig_path.write_text(sig_b64, encoding="utf-8")

        sigmeta = dict(artifact_sigmeta)
        sigmeta["signature"] = sig_b64
        sigmeta["signature_payload_schema_version"] = (
            sigmeta.get("signature_payload_schema_version") or signature_payload_schema_version
        )
        sigmeta["export_bundle"] = {
            "zip_sha256": zip_sha256,
            "zip_file": zip_path.name,
            "generated_at": _utc_now(),
        }
        sigmeta["export_verification"] = signature_verification
        sigmeta_path.write_text(json.dumps(sigmeta, indent=2), encoding="utf-8")
        return zip_path, sig_path, sigmeta_path, sigmeta

    @app.get("/decision-pack/<execution_id>/export")
    def export_decision_pack(execution_id: str) -> Any:
        execution = executions.get(execution_id)
        if not execution:
            return jsonify({"error": "execution_not_found", "execution_id": execution_id}), 404

        try:
            zip_path, _sig_path, _sigmeta_path, _sigmeta = _generate_signed_export_artifacts(execution_id, execution)
        except RuntimeError as exc:
            _log(f"Export signature verification failure: {exc}", level="ERROR", execution_id=execution_id)
            response, code = _runtime_error(
                error_code="SIGNED_EXPORT_VERIFICATION_FAILED",
                message="Signed export verification failed before export release.",
                dependency="signing_trust",
                details={"error": str(exc)},
            )
            return jsonify(response), code
        except OSError as exc:
            _log(f"Export storage failure: {exc}", level="ERROR", execution_id=execution_id)
            response, code = _runtime_error(
                error_code="EXPORT_STORAGE_UNAVAILABLE",
                message="Export storage is unavailable during decision-pack export.",
                dependency="export_storage",
            )
            return jsonify(response), code

        _log(
            "Decision-pack export generated with signature verification status "
            f"{_sigmeta.get('export_verification', {}).get('verified')}",
            execution_id=execution_id,
        )
        return send_file(zip_path, as_attachment=True, mimetype="application/zip")

    @app.get("/decision-pack/<execution_id>/export-signed")
    def export_signed(execution_id: str) -> Any:
        execution = executions.get(execution_id)
        if not execution:
            return jsonify({"error": "execution_not_found", "execution_id": execution_id}), 404

        try:
            zip_path, sig_path, sigmeta_path, sigmeta = _generate_signed_export_artifacts(execution_id, execution)
        except RuntimeError as exc:
            _log(f"Export signature verification failure: {exc}", level="ERROR", execution_id=execution_id)
            response, code = _runtime_error(
                error_code="SIGNED_EXPORT_VERIFICATION_FAILED",
                message="Signed export verification failed before export release.",
                dependency="signing_trust",
                details={"error": str(exc)},
            )
            return jsonify(response), code
        except OSError as exc:
            _log(f"Export storage failure: {exc}", level="ERROR", execution_id=execution_id)
            response, code = _runtime_error(
                error_code="EXPORT_STORAGE_UNAVAILABLE",
                message="Export storage is unavailable during signed export.",
                dependency="export_storage",
            )
            return jsonify(response), code

        _log(
            "Signed export metadata generated with signature verification status "
            f"{sigmeta.get('export_verification', {}).get('verified')}",
            execution_id=execution_id,
        )
        return jsonify({
            "zip_path": str(zip_path),
            "sig_path": str(sig_path),
            "sigmeta_path": str(sigmeta_path),
            "sigmeta": sigmeta,
        })

    @app.post("/admin/audit-export")
    def admin_audit_export() -> Any:
        payload = request.get_json(silent=True) or {}
        execution_ids = payload.get("execution_ids") or list(executions.keys())
        if not isinstance(execution_ids, list):
            return jsonify({"error": "invalid_field", "field": "execution_ids"}), 400
        if len(execution_ids) > EXECUTION_IDS_MAX:
            return jsonify({"error": "list_too_long", "field": "execution_ids", "max_items": EXECUTION_IDS_MAX}), 400
        for execution_id in execution_ids:
            if not isinstance(execution_id, str) or len(execution_id) > CONTEXT_ID_MAX:
                return jsonify({"error": "invalid_list_item", "field": "execution_ids"}), 400
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
            "ledger_slice": [
                entry for entry in ledger_logs
                if entry.get("execution_id") in execution_ids
            ],
            "verify_execution_snapshots": verify_snapshots,
            "logs": [
                entry for entry in backend_logs
                if entry.get("execution_id") in execution_ids
                or entry.get("execution_id") is None
            ][-200:],
        }
        try:
            out.write_text(json.dumps(bundle, indent=2), encoding="utf-8")
        except OSError as exc:
            _log(f"Audit export storage failure: {exc}", level="ERROR")
            response, code = _runtime_error(
                error_code="AUDIT_STORAGE_UNAVAILABLE",
                message="Audit storage is unavailable during audit export.",
                dependency="audit_storage",
            )
            return jsonify(response), code
        audit_exports[audit_id] = {
            "path": str(out),
            "created_at": _utc_now(),
            "execution_ids": execution_ids,
            "download_url": f"/admin/audit/exports/{audit_id}/download",
        }
        store.save_audit_export(audit_id, audit_exports[audit_id])
        _append_ledger("GOVERNANCE_AUDIT_ACCESS", {"access_type": "audit_export", "audit_export_id": audit_id})
        relative_path = str(out.relative_to(Path.cwd())) if str(out).startswith(str(Path.cwd())) else f"audit_exports/{out.name}"
        return jsonify(
            {
                "audit_export_id": audit_id,
                "download_url": f"/admin/audit/exports/{audit_id}/download",
                "storage_path": str(out),
                "storage_path_relative": relative_path,
            }
        ), 201

    @app.get("/admin/audit/exports")
    def list_audit_exports() -> Any:
        items: list[dict[str, Any]] = []
        for export_id, entry in sorted(audit_exports.items(), key=lambda x: x[1].get("created_at", ""), reverse=True):
            path = Path(entry.get("path", ""))
            exists = path.exists()
            size = path.stat().st_size if exists else 0
            items.append(
                {
                    "audit_export_id": export_id,
                    "created_at": entry.get("created_at"),
                    "execution_ids": entry.get("execution_ids", []),
                    "download_url": entry.get("download_url") or f"/admin/audit/exports/{export_id}/download",
                    "storage_path": str(path),
                    "storage_path_relative": (
                        str(path.relative_to(Path.cwd()))
                        if str(path).startswith(str(Path.cwd()))
                        else f"audit_exports/{path.name}"
                    ),
                    "exists": exists,
                    "size_bytes": size,
                }
            )
        return jsonify({"exports": items, "count": len(items)})

    @app.post("/admin/audit/exports")
    def admin_audit_exports_alias() -> Any:
        return admin_audit_export()

    @app.get("/admin/audit/exports/<export_id>/download")
    def download_audit(export_id: str) -> Any:
        entry = audit_exports.get(export_id)
        if not entry:
            return jsonify({"error": "audit_export_not_found", "audit_export_id": export_id}), 404
        return send_file(entry["path"], as_attachment=True)

    @app.get("/admin/audit-export/<export_id>/download")
    def download_audit_alias(export_id: str) -> Any:
        return download_audit(export_id)

    @app.get("/trust")
    def trust_alias() -> Any:
        return trust_status()

    @app.post("/api/human-input")
    def human_input_alias() -> Any:
        payload = request.get_json(silent=True) or {}
        text = payload.get("text", "")
        if not isinstance(text, str):
            return jsonify({"error": "invalid_text"}), 400
        if not text.strip():
            return jsonify({"error": "invalid_text", "message": "text must be non-empty"}), 400
        if len(text) > HUMAN_TEXT_MAX:
            return jsonify({"error": "field_too_long", "field": "text", "max_length": HUMAN_TEXT_MAX}), 400
        _log("Human input accepted")
        return jsonify({"accepted": True, "length": len(text)}), 201

    @app.get("/executions/<execution_id>/reports")
    def execution_reports(execution_id: str) -> Any:
        execution = executions.get(execution_id)
        reports: list[str] = []

        if execution:
            reports = [
                name for name in execution.get("artifacts", [])
                if isinstance(name, str) and name.strip()
            ]

        exec_dir = artifacts_dir / execution_id
        if exec_dir.exists() and exec_dir.is_dir():
            disk_reports = sorted([item.name for item in exec_dir.iterdir() if item.is_file()])
            if reports:
                seen = set(reports)
                for name in disk_reports:
                    if name not in seen:
                        reports.append(name)
            else:
                reports = disk_reports

        if not reports:
            return jsonify({"error": "execution_not_found", "execution_id": execution_id}), 404

        return jsonify({"execution_id": execution_id, "reports": reports})

    @app.get("/executions/<execution_id>/reports/<file_name>")
    def execution_report_file(execution_id: str, file_name: str) -> Any:
        safe_name = Path(file_name).name
        if not safe_name or safe_name != file_name:
            return jsonify({"error": "invalid_path"}), 400

        exec_dir = (artifacts_dir / execution_id).resolve()
        if not exec_dir.exists() or not exec_dir.is_dir():
            return jsonify({"error": "execution_not_found", "execution_id": execution_id}), 404

        target = (exec_dir / safe_name).resolve()
        if target.parent != exec_dir:
            return jsonify({"error": "invalid_path"}), 400
        if not target.exists() or not target.is_file():
            return jsonify({"error": "report_not_found", "execution_id": execution_id, "file": safe_name}), 404

        return send_file(target, as_attachment=False)

    return app


if __name__ == "__main__":
    create_app().run(host="0.0.0.0", port=8000)  # noqa: S104 — Docker requires all-interface bind
