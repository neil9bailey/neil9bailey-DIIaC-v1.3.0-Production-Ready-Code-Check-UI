from __future__ import annotations

import base64
import hashlib
import json
import os
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from flask import Flask, jsonify, request, send_file


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


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


# ── Signing Provider Abstraction ──────────────────────────────────────────────
# Extend by adding a new subclass and registering it in _create_signing_provider.
# The local provider (Ed25519) is the default and requires no extra dependencies.
# The Azure Key Vault provider (ES256) requires:
#   azure-keyvault-keys>=4.8 and azure-identity>=1.15
# Switch by setting SIGNING_PROVIDER=azure-keyvault (see DIIAC_KEY_VAULT_PLAN.md).

class SigningProvider:
    """Abstract signing provider. All concrete providers must implement this interface."""

    def sign(self, payload: bytes) -> bytes:
        raise NotImplementedError

    def algorithm(self) -> str:
        raise NotImplementedError

    def key_id(self) -> str:
        raise NotImplementedError

    def public_key_b64(self) -> str:
        raise NotImplementedError

    def sign_b64(self, payload: bytes) -> str:
        return base64.b64encode(self.sign(payload)).decode("utf-8")

    def verify_signature(self, signature: bytes, payload: bytes) -> bool:
        raise NotImplementedError

    def provider_name(self) -> str:
        raise NotImplementedError

    def key_mode(self) -> str:
        return "unknown"


class LocalEdDSASigner(SigningProvider):
    """Local Ed25519 signer. Ephemeral by default; inject SIGNING_PRIVATE_KEY_PEM for persistence.

    This is the correct provider for: development, pilots, demos, and diligence environments.
    It is not suitable for regulated production (no HSM, no key lifecycle governance).
    """

    def __init__(self) -> None:
        pem = os.getenv("SIGNING_PRIVATE_KEY_PEM")
        if pem:
            key = serialization.load_pem_private_key(pem.encode("utf-8"), password=None)
            if not isinstance(key, Ed25519PrivateKey):
                raise ValueError("SIGNING_PRIVATE_KEY_PEM must be Ed25519")
            self._key = key
            self._mode = "configured"
        else:
            self._key = Ed25519PrivateKey.generate()
            self._mode = "ephemeral"
        self._key_id = os.getenv("SIGNING_KEY_ID", "ephemeral-local-ed25519")

    def sign(self, payload: bytes) -> bytes:
        return self._key.sign(payload)

    def verify_signature(self, signature: bytes, payload: bytes) -> bool:
        try:
            self._key.public_key().verify(signature, payload)
            return True
        except Exception:
            return False

    def algorithm(self) -> str:
        return "Ed25519"

    def key_id(self) -> str:
        return self._key_id

    def public_key_b64(self) -> str:
        pub = self._key.public_key()
        return base64.b64encode(
            pub.public_bytes(encoding=serialization.Encoding.Raw, format=serialization.PublicFormat.Raw)
        ).decode("utf-8")

    def provider_name(self) -> str:
        return "local"

    def key_mode(self) -> str:
        return self._mode


class AzureKeyVaultSigner(SigningProvider):
    """Azure Key Vault signing provider using ES256 (ECDSA P-256, HSM-backed).

    Supports both DIIaC-managed vaults and customer-managed vaults (preferred for
    enterprise deployments). Set KEYVAULT_TENANT_ID to route credentials to the
    customer's own Azure AD tenant — mirrors the ENTRA_EXPECTED_TENANT_ID pattern.

    ⚠️  Azure Key Vault does NOT support Ed25519. ES256 (ECDSA P-256) is the
        correct HSM-backed alternative and is accepted by all major regulators
        (GDPR, ISO 27001, SOC 2, NIS2).

    Required packages (add to requirements.txt before enabling):
        azure-keyvault-keys>=4.8
        azure-identity>=1.15

    Required env vars:
        SIGNING_PROVIDER=azure-keyvault
        KEYVAULT_URL          — https://kv-customer-prod.vault.azure.net
        KEYVAULT_KEY_NAME     — diiac-signing-v1
        KEYVAULT_TENANT_ID    — customer's Azure AD tenant ID (customer-managed vault)
        KEYVAULT_KEY_VERSION  — (optional) pin to a specific key version

    Authentication: DefaultAzureCredential — honours Managed Identity in Azure;
    set AZURE_CLIENT_ID / AZURE_CLIENT_SECRET for service principal (local dev or
    cross-tenant scenarios where Managed Identity is not in the customer's tenant).

    Customer-managed model: the customer owns the vault and the key. DIIaC holds
    Key Vault Crypto User (sign only). DIIaC never creates, exports, or rotates keys.
    This matches the Entra ID ownership model exactly.

    Ledger format, manifest, and verification endpoints are unchanged.
    Only signature_alg changes from 'Ed25519' to 'ES256'.
    """

    def __init__(self) -> None:
        try:
            from azure.keyvault.keys import KeyClient  # type: ignore[import]
            from azure.keyvault.keys.crypto import CryptographyClient, SignatureAlgorithm  # type: ignore[import]
            from azure.identity import DefaultAzureCredential  # type: ignore[import]
        except ImportError as exc:
            raise RuntimeError(
                "SIGNING_PROVIDER=azure-keyvault requires azure-keyvault-keys>=4.8 and "
                "azure-identity>=1.15. Add them to requirements.txt and rebuild the container. "
                "See DIIAC_KEY_VAULT_PLAN.md for full setup instructions."
            ) from exc

        vault_url = os.getenv("KEYVAULT_URL", "").rstrip("/")
        key_name = os.getenv("KEYVAULT_KEY_NAME", "diiac-signing-v1")
        key_version = os.getenv("KEYVAULT_KEY_VERSION", "")
        # KEYVAULT_TENANT_ID routes credentials to the customer's Azure AD tenant.
        # Falls back to AZURE_TENANT_ID if not set. Omit for same-tenant deployments.
        tenant_id = os.getenv("KEYVAULT_TENANT_ID") or os.getenv("AZURE_TENANT_ID") or None

        if not vault_url:
            raise ValueError("KEYVAULT_URL is required when SIGNING_PROVIDER=azure-keyvault")

        credential = DefaultAzureCredential(tenant_id=tenant_id) if tenant_id else DefaultAzureCredential()
        key_url = f"{vault_url}/keys/{key_name}" + (f"/{key_version}" if key_version else "")
        self._crypto_client = CryptographyClient(key_url, credential)
        self._SignatureAlgorithm = SignatureAlgorithm
        self._key_id = key_url
        self._tenant_id = tenant_id or "managed-identity-default"

        # Retrieve and cache public key for verification publishing
        key_client = KeyClient(vault_url=vault_url, credential=credential)
        kv_key = key_client.get_key(key_name, version=key_version or None)
        self._pub_b64 = self._jwk_to_der_b64(kv_key.key)

    @staticmethod
    def _jwk_to_der_b64(jwk: Any) -> str:
        """Convert Azure JWK P-256 key to DER-encoded SubjectPublicKeyInfo, base64."""
        from cryptography.hazmat.primitives.asymmetric.ec import EllipticCurvePublicNumbers, SECP256R1
        from cryptography.hazmat.backends import default_backend

        def _pad(s: str) -> str:
            return s + "=" * (-len(s) % 4)

        x = int.from_bytes(base64.urlsafe_b64decode(_pad(jwk.x)), "big")
        y = int.from_bytes(base64.urlsafe_b64decode(_pad(jwk.y)), "big")
        pub_key = EllipticCurvePublicNumbers(x=x, y=y, curve=SECP256R1()).public_key(default_backend())
        der = pub_key.public_bytes(
            encoding=serialization.Encoding.DER,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        return base64.b64encode(der).decode("utf-8")

    def sign(self, payload: bytes) -> bytes:
        import hashlib
        digest = hashlib.sha256(payload).digest()
        result = self._crypto_client.sign(self._SignatureAlgorithm.es256, digest)
        return result.signature

    def verify_signature(self, signature: bytes, payload: bytes) -> bool:
        try:
            import hashlib
            digest = hashlib.sha256(payload).digest()
            result = self._crypto_client.verify(self._SignatureAlgorithm.es256, digest, signature)
            return result.is_valid
        except Exception:
            return False

    def algorithm(self) -> str:
        return "ES256"

    def key_id(self) -> str:
        return self._key_id

    def public_key_b64(self) -> str:
        return self._pub_b64

    def provider_name(self) -> str:
        return "azure-keyvault"

    def key_mode(self) -> str:
        return "hsm"

    def tenant_id(self) -> str:
        return self._tenant_id


def _create_signing_provider() -> SigningProvider:
    """Factory: read SIGNING_PROVIDER and return the configured provider instance."""
    name = os.getenv("SIGNING_PROVIDER", "local").lower().replace("_", "-")
    if name in ("local", "local-ed25519"):
        return LocalEdDSASigner()
    if name in ("azure-keyvault", "akv"):
        return AzureKeyVaultSigner()
    raise ValueError(f"Unknown SIGNING_PROVIDER={name!r}. Supported: 'local', 'azure-keyvault'.")


def _verify_signature_dispatch(
    signature_alg: str | None,
    signing_key_id: str | None,
    signature_b64: str,
    signature_payload: bytes,
    public_keys_data: dict[str, Any],
) -> tuple[bool, str | None, str | None]:
    """Algorithm-aware signature verification dispatcher.

    Reads signature_alg from signed_export.sigmeta.json as the canonical source of
    truth, finds the matching public key by signing_key_id, and verifies using the
    correct algorithm implementation.

    Returns: (signature_valid, error_code, error_detail)
    Supported algorithms: Ed25519, ES256 (ECDSA P-256).
    """
    if not signature_alg:
        return False, "missing_signature_alg", "signature_alg not found in signed_export.sigmeta.json"

    if not signature_b64:
        return False, "missing_signature", "signature not found in signed_export.sigmeta.json"

    # Validate algorithm before key lookup so callers get a clear unsupported_signature_alg error.
    alg = signature_alg.upper()
    if alg not in ("ED25519", "ES256"):
        return (
            False,
            "unsupported_signature_alg",
            f"Unsupported signature_alg={signature_alg!r}. Supported: Ed25519, ES256",
        )

    key_entry = next(
        (k for k in public_keys_data.get("keys", []) if k.get("key_id") == signing_key_id),
        None,
    )
    if key_entry is None:
        return False, "public_key_not_found", f"No public key found for key_id={signing_key_id!r}"

    try:
        signature = base64.b64decode(signature_b64)
    except Exception:
        return False, "signature_verification_failed", "signature is not valid base64"

    if alg == "ED25519":
        try:
            pub_bytes = base64.b64decode(key_entry["public_key_b64"])
            pub_key = Ed25519PublicKey.from_public_bytes(pub_bytes)
            pub_key.verify(signature, signature_payload)
            return True, None, None
        except Exception:
            return False, "signature_verification_failed", "Ed25519 verification failed"

    if alg == "ES256":
        try:
            from cryptography.hazmat.primitives.asymmetric.ec import ECDSA
            from cryptography.hazmat.primitives.hashes import SHA256
            from cryptography.hazmat.primitives.serialization import load_der_public_key
            pub_der = base64.b64decode(key_entry["public_key_b64"])
            pub_key = load_der_public_key(pub_der)
            pub_key.verify(signature, signature_payload, ECDSA(SHA256()))  # type: ignore[arg-type]
            return True, None, None
        except Exception:
            return False, "signature_verification_failed", "ES256 verification failed"

    return (
        False,
        "unsupported_signature_alg",
        f"Unsupported signature_alg={signature_alg!r}. Supported: Ed25519, ES256",
    )


def _runtime_error(error_code: str, message: str, dependency: str | None = None, details: dict[str, Any] | None = None) -> tuple[dict[str, Any], int]:
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

    strict_deterministic_mode = os.getenv("STRICT_DETERMINISTIC_MODE", "false").lower() == "true"
    signing_enabled = os.getenv("SIGNING_ENABLED", "true").lower() != "false"
    ledger_freeze = os.getenv("LEDGER_FREEZE", "false").lower() == "true"

    admin_auth_enabled = os.getenv("ADMIN_AUTH_ENABLED", "true").lower() != "false"
    runtime_env = os.getenv("APP_ENV", "production").lower()
    admin_api_token = os.getenv("ADMIN_API_TOKEN", "")

    signing_provider = _create_signing_provider()
    signing_key_id = signing_provider.key_id()
    public_key_b64 = signing_provider.public_key_b64()

    artifacts_dir = Path.cwd() / "artifacts"
    exports_dir = Path.cwd() / "exports"
    audit_dir = Path.cwd() / "audit_exports"
    keys_dir = Path.cwd() / "contracts" / "keys"
    profiles_dir = Path.cwd() / "contracts" / "business-profiles"
    for d in [artifacts_dir, exports_dir, audit_dir, keys_dir, profiles_dir]:
        d.mkdir(parents=True, exist_ok=True)

    public_keys_file = keys_dir / "public_keys.json"
    # Always register the current signing provider's key so verify_pack can look it up by key_id.
    # Existing entries for other key_ids are preserved (supports mixed Ed25519 + ES256 ledgers).
    try:
        existing_keys_data = json.loads(public_keys_file.read_text(encoding="utf-8")) if public_keys_file.exists() else {"keys": []}
    except (OSError, json.JSONDecodeError):
        existing_keys_data = {"keys": []}
    current_entry = {"key_id": signing_key_id, "algorithm": signing_provider.algorithm(), "public_key_b64": public_key_b64}
    merged_keys = [k for k in existing_keys_data.get("keys", []) if k.get("key_id") != signing_key_id]
    merged_keys.append(current_entry)
    public_keys_file.write_text(json.dumps({"keys": merged_keys}, indent=2), encoding="utf-8")

    profiles = _load_profiles(profiles_dir)
    profiles_by_id = {p["profile_id"]: p for p in profiles}

    def _readiness_checks() -> dict[str, Any]:
        checks = {
            "artifact_storage": artifacts_dir.exists() and artifacts_dir.is_dir() and os.access(artifacts_dir, os.W_OK),
            "export_storage": exports_dir.exists() and exports_dir.is_dir() and os.access(exports_dir, os.W_OK),
            "audit_storage": audit_dir.exists() and audit_dir.is_dir() and os.access(audit_dir, os.W_OK),
            "contracts_profiles": profiles_dir.exists() and profiles_dir.is_dir() and len(profiles) > 0,
            "contracts_keys": public_keys_file.exists(),
        }
        database_url = os.getenv("DATABASE_URL", "").strip()
        checks["database"] = "not_configured" if not database_url else "configured"
        hard_failures = [v for v in checks.values() if v is False]
        return {
            "overall_ready": len(hard_failures) == 0,
            "checks": checks,
        }

    backend_logs: list[dict[str, Any]] = []
    ledger_logs: list[dict[str, Any]] = []
    execution_logs: dict[str, list[dict[str, Any]]] = {}
    executions: dict[str, dict[str, Any]] = {}
    role_inputs: dict[str, list[dict[str, Any]]] = {}
    audit_exports: dict[str, dict[str, Any]] = {}
    profile_overrides: list[dict[str, Any]] = []

    approved_schemas = {"GENERAL_SOLUTION_BOARD_REPORT_V1", "RFQ_TEMPLATE_V1", "SLA_SCHEDULE_V1", "TECHNICAL_SOLUTION_BOARD_REPORT_V1"}

    ROLE_FIELD_MAX = 64
    CONTEXT_ID_MAX = 128
    LIST_ITEM_MAX = 512
    LIST_MAX_ITEMS = 50
    HUMAN_TEXT_MAX = 8000
    EXECUTION_IDS_MAX = 100

    def _validate_string_field(payload: dict[str, Any], field: str, max_len: int) -> tuple[dict[str, Any], int] | None:
        value = payload.get(field)
        if not isinstance(value, str):
            return {"error": "invalid_field_type", "field": field, "expected": "string"}, 400
        if not value.strip():
            return {"error": "invalid_field", "field": field, "message": "must be non-empty"}, 400
        if len(value) > max_len:
            return {"error": "field_too_long", "field": field, "max_length": max_len}, 400
        return None

    def _validate_string_list_field(payload: dict[str, Any], field: str, max_items: int = LIST_MAX_ITEMS, max_item_len: int = LIST_ITEM_MAX) -> tuple[dict[str, Any], int] | None:
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
        if execution_id:
            execution_logs.setdefault(execution_id, []).append(evt)

    def _append_ledger(event_type: str, payload: dict[str, Any]) -> dict[str, Any]:
        if ledger_freeze:
            return {"frozen": True, "ledger_freeze_active": True, "event_type": event_type}
        prev = ledger_logs[-1]["record_hash"] if ledger_logs else "0" * 64
        record_core = {
            "record_id": len(ledger_logs) + 1,
            "timestamp": _utc_now(),
            "event_type": event_type,
            "previous_record_hash": prev,
            **payload,
        }
        record_hash = _sha256_text(_canonical_json(record_core))
        record = {**record_core, "record_hash": record_hash}
        ledger_logs.append(record)
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

    def _first_non_empty(values: list[str], default: str) -> str:
        for value in values:
            if isinstance(value, str) and value.strip():
                return value.strip()
        return default

    def _extract_named_vendors(intent_text: str) -> list[str]:
        t = intent_text.lower()
        known = [
            ("palo alto networks", "Palo Alto Networks"),
            ("palo-alto", "Palo Alto Networks"),
            ("fortinet", "Fortinet"),
            ("cisco", "Cisco"),
            ("vmware", "VMware"),
            ("zscaler", "Zscaler"),
        ]
        names: list[str] = []
        for token, display in known:
            if token in t and display not in names:
                names.append(display)
        return names

    def _derive_solution_options(intent_text: str, preferred_vendors: list[str] | None = None) -> list[dict[str, str]]:
        if preferred_vendors:
            focus_lines = [
                "Security-led SD-WAN, zero-trust policy enforcement, and global operations maturity",
                "Cost-aware hybrid WAN delivery with deterministic controls and staged migration assurance",
                "Balanced long-term viability, regulatory alignment, and operational resilience",
            ]
            return [
                {"vendor": vendor, "focus": focus_lines[idx % len(focus_lines)]}
                for idx, vendor in enumerate(preferred_vendors)
            ]
        t = intent_text.lower()
        if any(k in t for k in ["wan", "sd-wan", "sase", "ztna", "network", "ot", "iot"]):
            return [
                {"vendor": "SecureEdge Managed SD-WAN + SASE", "focus": "Zero-trust edge transformation and policy-based routing"},
                {"vendor": "ResilienceNet Hybrid WAN", "focus": "High-availability backbone with staged migration controls"},
                {"vendor": "CloudFabric Secure Access", "focus": "Cloud-native secure connectivity with rapid branch onboarding"},
            ]
        if any(k in t for k in ["data", "platform", "analytics", "lake", "warehouse"]):
            return [
                {"vendor": "DataCore Unified Platform", "focus": "Governed data ingestion and analytics lifecycle"},
                {"vendor": "InsightMesh Enterprise Lakehouse", "focus": "Elastic analytics with policy-bound access controls"},
                {"vendor": "TrustedFabric Data Grid", "focus": "Cross-domain interoperability and lineage assurance"},
            ]
        return [
            {"vendor": "Option-Alpha Governed Delivery", "focus": "Balanced risk and measurable transformation outcomes"},
            {"vendor": "Option-Beta Accelerated Modernization", "focus": "Time-to-value with moderate operational change"},
            {"vendor": "Option-Gamma Conservative Transition", "focus": "Lowest transition risk with slower benefit realization"},
        ]

    def _extract_intent_signals(intent_text: str) -> dict[str, Any]:
        t = intent_text.lower()
        signals: dict[str, Any] = {
            "regulatory_constraints": [],
            "security_constraints": [],
            "financial_constraints": [],
            "success_targets": [],
        }
        for token, label in [("gdpr", "GDPR"), ("nis2", "NIS2"), ("dora", "DORA"), ("iso27001", "ISO27001")]:
            if token in t:
                signals["regulatory_constraints"].append(label)
        for token, label in [("zero trust", "Zero Trust"), ("ztna", "ZTNA"), ("sase", "SASE"), ("encryption", "Encryption")]:
            if token in t:
                signals["security_constraints"].append(label)
        if "capex" in t or "budget" in t or "cost" in t:
            signals["financial_constraints"].append("Budget/cost constraint detected")
        for marker in ["incident", "operating cost", "resilience", "uptime", "availability"]:
            if marker in t:
                signals["success_targets"].append(marker)
        return signals

    def _build_option_assessment(vendor_rows: list[dict[str, Any]], intent_signals: dict[str, Any]) -> list[dict[str, Any]]:
        """Produce deterministic, human-readable option detail blocks for board consumption."""
        assessment: list[dict[str, Any]] = []
        for idx, row in enumerate(vendor_rows, start=1):
            weights = row.get("weights", {})
            scores = row.get("scores", {})
            assessment.append(
                {
                    "rank": idx,
                    "vendor": row.get("vendor"),
                    "focus": row.get("focus"),
                    "score": row.get("total"),
                    "security_fit": round(float(scores.get("security_fit", 0.0)), 2),
                    "delivery_fit": round(float(scores.get("delivery_fit", 0.0)), 2),
                    "operating_model_fit": round(float(scores.get("operating_model_fit", 0.0)), 2),
                    "financial_fit": round(float(scores.get("financial_fit", 0.0)), 2),
                    "weights": weights,
                    "fit_summary": [
                        f"Regulatory alignment signals: {', '.join(intent_signals.get('regulatory_constraints', [])) or 'none explicit'}",
                        f"Security priorities detected: {', '.join(intent_signals.get('security_constraints', [])) or 'none explicit'}",
                        f"Financial constraints: {', '.join(intent_signals.get('financial_constraints', [])) or 'none explicit'}",
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
            f"Primary objective: {_first_non_empty(all_assertions, 'Deliver a deterministic, auditable decision outcome.')}"
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

        metric_candidates = sorted(set(all_non_negotiables)) or sorted(set(all_assertions[:3]))
        metric_lines = metric_candidates or ["Deterministic pack hash + signature verification pass rate remains 100%."]
        success_metrics = "\n".join([f"- {line}" for line in metric_lines])

        ranking_lines = []
        if vendor_rows:
            ranking_lines = [f"{row['vendor']} ({row['total']})" for row in vendor_rows[:3]]

        compliance_note = ""
        if compliance_matrix:
            compliance_note = (
                " All required controls satisfied."
                if compliance_matrix.get("all_required_satisfied")
                else " Some required controls are missing and require remediation before approval."
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
            f"# DIIaC Board Report — {board_report['execution_id']}",
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
                        f"  - Confidence: {rec.get('confidence_level')} ({rec.get('confidence_score')}) — {rec.get('confidence_rationale')}"
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
            lines.append("")

        if board_report.get("intent_coverage"):
            ic = board_report.get("intent_coverage", {})
            lines.append("## Intent Coverage")
            for k in ["regulatory_constraints", "security_constraints", "financial_constraints", "success_targets"]:
                vals = ic.get(k, [])
                lines.append(f"- {k}: {', '.join(vals) if vals else 'none detected'}")
            lines.append("")

        if board_report.get("implementation_plan"):
            lines.append("## Implementation Plan")
            for step in board_report.get("implementation_plan", []):
                lines.append(f"- {step}")
            lines.append("")

        return "\n".join(lines).strip() + "\n"

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
        governance_modes = [m.strip() for m in payload.get("governance_modes", []) if isinstance(m, str) and m.strip()]
        seed_payload = {
            "context_id": context_id,
            "profile_id": profile_id,
            "profile_hash": profile["profile_hash"],
            "schema_id": schema_id,
            "schema_version": schema_version,
            "rp": rp,
            "role_bundle": role_bundle,
            "request_payload": payload,
            "governance_modes": governance_modes,
        }
        context_hash = _sha256_text(_canonical_json(seed_payload))
        execution_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"diiac:{context_hash}")) if strict_deterministic_mode else str(uuid.uuid4())

        required_sections = profile["required_sections"]

        intent_text_parts = []
        for role_item in role_bundle:
            intent_text_parts.extend([*role_item.get("assertions", []), *role_item.get("non_negotiables", []), *role_item.get("risk_flags", [])])
        intent_text = " | ".join([v for v in intent_text_parts if isinstance(v, str)])
        preferred_vendors = _extract_named_vendors(intent_text)
        option_profiles = _derive_solution_options(intent_text, preferred_vendors=preferred_vendors)
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
        ranked_options = _build_option_assessment(vendor_rows, intent_signals)

        selected = vendor_rows[0]

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
        evidence_ids_seed = evidence_ref_pool[:5] or [f"claim-{i}" for i in range(1, min(len(required_sections), 3) + 1)]
        assumptions = [
            "Cost model assumptions are based on provided capex/opex targets and current market benchmarks.",
            "Operational baseline and incident data provided in role evidence is assumed accurate and current.",
            "Supplier capability statements and migration constraints captured in assertions are assumed complete.",
        ]
        risk_treatment = {
            "strategy": "mitigate",
            "actions": [
                "Contractual protections and break clauses to reduce lock-in risk",
                "Phased migration with rollback controls to reduce service disruption",
                "Security validation and assurance gates prior to production cutover",
            ],
        }

        control_failure_reasons: list[str] = []
        if not compliance_matrix["all_required_satisfied"]:
            missing_controls = sorted(required_controls.difference(provided_controls))
            control_failure_reasons.append(f"missing required controls: {', '.join(missing_controls)}")

        constraints_mode_auto_controls = False
        if any("CONSTRAINTS-FIRST" in m.upper() for m in governance_modes) and "controls" not in payload:
            constraints_mode_auto_controls = True

        decision_allowed = len(control_failure_reasons) == 0
        confidence_score = round(
            max(0.0, min(100.0, selected["total"] - (8.0 * len(control_failure_reasons)) + min(6.0, len(role_bundle) * 2.0))),
            2,
        )
        confidence_level = "HIGH" if confidence_score >= 80 else ("MEDIUM" if confidence_score >= 60 else "LOW")

        recommendation = {
            "major_recommendation": (
                f"Select {selected['vendor']} for controlled implementation"
                if decision_allowed
                else "Decision not recommended pending control remediation"
            ),
            "selected_vendor": selected["vendor"] if decision_allowed else None,
            "score": selected["total"],
            "alternatives": [row["vendor"] for row in vendor_rows[1:]],
            "decision_status": "recommended" if decision_allowed else "not_recommended",
            "decision_drivers": [
                f"Top weighted score under deterministic evaluation ({selected['total']})",
                f"Solution focus: {selected.get('focus')}",
                "Aligned with required controls and governance policy constraints",
                "Supports measurable resilience, security and operating model outcomes",
            ] + (["CONSTRAINTS-FIRST controls inferred from active business profile"] if constraints_mode_auto_controls else []),
            "recommended_option_profile": next((o for o in ranked_options if o.get("vendor") == selected["vendor"]), None),
            "ranked_options": ranked_options,
            "evidence_ids": evidence_ids_seed,
            "assumptions": assumptions,
            "risk_treatment": risk_treatment,
            "confidence_score": confidence_score,
            "confidence_level": confidence_level,
            "confidence_rationale": (
                "Confidence is derived from deterministic scoring, control compliance, evidence completeness and governance mode checks."
            ),
            "control_failure_reasons": control_failure_reasons,
            "claim_ids": evidence_ids_seed,
        }

        draft_sections = _build_human_readable_sections(
            execution_id,
            profile,
            schema_id,
            rp,
            role_bundle,
            recommendation,
            vendor_rows=vendor_rows,
            compliance_matrix=compliance_matrix,
            governance_modes=governance_modes,
        )
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

        recommendation["claim_ids"] = [e["claim_id"] for e in evidence_entries[:3]]
        recommendation["evidence_ids"] = sorted(set(recommendation["evidence_ids"] + recommendation["claim_ids"]))[:6]

        board_report = {
            "execution_id": execution_id,
            "schema_id": schema_id,
            "profile_id": profile_id,
            "sections": sections,
            "major_recommendations": [recommendation],
            "ranked_options": ranked_options,
            "intent_coverage": intent_signals,
            "decision_summary": {
                "selected_vendor": recommendation["selected_vendor"],
                "alternatives_considered": recommendation["alternatives"],
                "confidence_score": recommendation["confidence_score"],
                "confidence_level": recommendation["confidence_level"],
                "confidence_rationale": recommendation["confidence_rationale"],
                "decision_basis": "Deterministic weighted scoring + profile/policy controls + role evidence",
                "decision_status": recommendation["decision_status"],
                "governance_modes": governance_modes,
                "control_failure_reasons": recommendation["control_failure_reasons"],
                "constraints_mode_controls_source": "profile_required_controls" if constraints_mode_auto_controls else "explicit_or_default",
            },
            "implementation_plan": [
                "Phase 1 (0-30 days): baseline architecture, migration wave plan, and KPI instrumentation.",
                "Phase 2 (31-90 days): pilot deployment with zero-downtime controls and security hardening.",
                "Phase 3 (91-180 days): scaled rollout, assurance audits, and benefits realization tracking.",
            ],
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
        vendor_scoring_matrix = {
            "execution_id": execution_id,
            "deterministic": True,
            "rows": vendor_rows,
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
            "board_report.md": _render_board_report_markdown(board_report),
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
            "governance_modes": governance_modes,
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
            sig_b64 = signing_provider.sign_b64(signing_payload_json.encode("utf-8"))

        artifacts_payloads["governance_manifest.json"] = manifest
        artifacts_payloads["signed_export.sigmeta.json"] = {
            "signature_alg": signing_provider.algorithm(),
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
            "governance_modes": governance_modes,
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
            "execution_state": {
                "signature_present": bool(sig_b64),
                "signing_enabled": signing_enabled,
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
        if not expected or authz != expected:
            return jsonify({"error": "admin_auth_required", "message": "Valid admin bearer token required."}), 401
        return None

    @app.get("/health")
    def health() -> Any:
        readiness = _readiness_checks()
        return jsonify({"status": "OK" if readiness["overall_ready"] else "DEGRADED", "readiness": readiness, "timestamp": _utc_now()})

    @app.get("/admin/health")
    def admin_health() -> Any:
        readiness = _readiness_checks()
        return jsonify(
            {
                "status": "OK" if readiness["overall_ready"] else "DEGRADED",
                "strict_deterministic_mode": strict_deterministic_mode,
                "signing_enabled": signing_enabled,
                "signing_provider": signing_provider.provider_name(),
                "signing_key_id": signing_key_id,
                "signing_algorithm": signing_provider.algorithm(),
                "key_mode": signing_provider.key_mode(),
                "keyvault_tenant_id": getattr(signing_provider, "tenant_id", lambda: None)(),
                "ledger_freeze": ledger_freeze,
                "ledger_record_count": len(ledger_logs),
                "readiness": readiness,
                "timestamp": _utc_now(),
            }
        )

    @app.get("/admin/config")
    def admin_config() -> Any:
        return jsonify(
            {
                "version": "v1.2.0",
                "runtime_model": ["react-vite-frontend", "express-backend"],
                "approved_schemas": sorted(approved_schemas),
                "profiles_count": len(profiles),
                "admin_auth_enabled": admin_auth_enabled,
                "runtime_env": runtime_env,
                "ledger_freeze": ledger_freeze,
                "signing_provider": signing_provider.provider_name(),
                "signing_algorithm": signing_provider.algorithm(),
                "signing_key_id": signing_key_id,
                "signing_key_mode": signing_provider.key_mode(),
            }
        )

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

        ctx = payload["execution_context_id"]
        role_inputs.setdefault(ctx, []).append(payload)
        _log(f"Role input accepted for {ctx}")
        return jsonify({"stored": True, "execution_context_id": ctx, "role_count": len(role_inputs[ctx])}), 201

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
            logs = [l for l in logs if l.get("level") == level]
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
        exec_list = list(executions.values())
        executions_total = len(exec_list)
        signed_recent = sum(1 for e in exec_list[-5:] if e.get("signature"))
        unsigned_total = sum(1 for e in exec_list if not e.get("signature"))
        ledger_record_count = len(ledger_logs)
        audit_exports_count = len(audit_exports)
        error_log_count = sum(1 for log in backend_logs if log.get("level") == "ERROR")
        backend_log_count = len(backend_logs)

        status = "OK"
        alerts: list[str] = []

        if executions_total > 0 and signed_recent == 0:
            status = "WARN"
            alerts.append("MTR-001: No signed executions in the latest window.")
        if executions_total > 0 and ledger_record_count == 0:
            status = "WARN"
            alerts.append("MTR-002: Execution data exists but ledger record count is zero.")
        if unsigned_total > 0:
            status = "WARN"
            alerts.append(f"MTR-003: {unsigned_total} unsigned execution(s) detected — signing may be disabled or key unavailable.")
        if backend_log_count > 0 and error_log_count > 0:
            error_rate_pct = round(error_log_count / backend_log_count * 100, 1)
            if error_rate_pct > 5:
                status = "WARN"
                alerts.append(f"MTR-004: Error log rate {error_rate_pct}% exceeds 5% threshold ({error_log_count}/{backend_log_count} events).")
        if ledger_record_count > 1:
            broken = any(
                ledger_logs[i]["record_hash"] != ledger_logs[i + 1]["previous_record_hash"]
                for i in range(len(ledger_logs) - 1)
            )
            if broken:
                status = "WARN"
                alerts.append("MTR-005: Ledger hash chain integrity check failed — records may have been tampered.")

        incident_triage = {
            "MTR-001": {
                "summary": "No signed executions in recent window.",
                "likely_cause": "Signing key not configured or signing disabled (SIGNING_PRIVATE_KEY_PEM unset).",
                "remediation": ["Verify SIGNING_PRIVATE_KEY_PEM env var is set.", "Check /admin/health signing_enabled and key_mode fields.", "Re-run a governed compile and confirm signature_present=true in the response."],
            },
            "MTR-002": {
                "summary": "Executions present but trust ledger is empty.",
                "likely_cause": "Ledger append path failing silently or app restarted between compile and ledger write.",
                "remediation": ["Review /admin/logs/backend for ERROR events around compile time.", "Restart runtime and run a fresh governed compile to confirm ledger growth via /trust/status."],
            },
            "MTR-003": {
                "summary": "One or more executions lack Ed25519 signatures.",
                "likely_cause": "Executions completed while signing was disabled or key was ephemeral and lost on restart.",
                "remediation": ["Set SIGNING_PRIVATE_KEY_PEM to a stable persistent key.", "Re-run affected compile contexts to produce new signed executions.", "Unsigned packs should not be used for audit or attestation purposes."],
            },
            "MTR-004": {
                "summary": "Error log rate exceeds acceptable threshold.",
                "likely_cause": "Repeated runtime dependency failures (storage, export, or verify paths).",
                "remediation": ["Review /admin/logs/backend filtered to ERROR level.", "Check disk/storage availability for artifact_storage, export_storage, and audit_storage paths.", "Investigate any 503 responses on /api/governed-compile or /admin/audit-export."],
            },
            "MTR-005": {
                "summary": "Trust ledger hash chain is broken.",
                "likely_cause": "In-memory ledger was modified outside normal append path, or records were reordered.",
                "remediation": ["Do not use this ledger for audit or attestation until resolved.", "Restart runtime and replay compile contexts from source role inputs.", "Validate that no direct manipulation of ledger_logs occurred in custom middleware."],
            },
        }

        return jsonify(
            {
                "health_status": status,
                "executions_total": executions_total,
                "signed_recent_executions": signed_recent,
                "unsigned_executions_total": unsigned_total,
                "ledger_record_count": ledger_record_count,
                "audit_exports_count": audit_exports_count,
                "error_log_count": error_log_count,
                "backend_log_count": backend_log_count,
                "alerts": alerts,
                "threshold_recommendations": {
                    "signed_recent_executions_min": 1,
                    "ledger_record_count_min_when_executions_present": 1,
                    "unsigned_executions_max": 0,
                    "error_log_rate_max_pct": 5,
                    "audit_export_retention_days": 90,
                },
                "incident_triage": {k: v for k, v in incident_triage.items() if any(a.startswith(k) for a in alerts)},
                "last_updated": _utc_now(),
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

        # v1.2.2: read signature_alg and signing_key_id from sigmeta (additive fields)
        sig_alg: str | None = None
        sig_key_id: str | None = None
        try:
            sigmeta_raw = json.loads((artifacts_dir / execution_id / "signed_export.sigmeta.json").read_text())
            sig_alg = sigmeta_raw.get("signature_alg")
            sig_key_id = sigmeta_raw.get("signing_key_id")
        except (OSError, json.JSONDecodeError):
            pass

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
                # v1.2.2 additive fields
                "signature_alg": sig_alg,
                "signing_key_id": sig_key_id,
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

        # v1.2.2: read full sigmeta — signature_alg is the canonical source for dispatch
        try:
            sigmeta_raw = json.loads(
                (artifacts_dir / execution["execution_id"] / "signed_export.sigmeta.json").read_text()
            )
        except (OSError, json.JSONDecodeError) as exc:
            _log(f"Signature metadata unavailable: {exc}", level="ERROR", execution_id=execution["execution_id"])
            response, code = _runtime_error(
                error_code="SIGNATURE_METADATA_UNAVAILABLE",
                message="Signature metadata is unavailable for pack verification.",
                dependency="artifact_storage",
            )
            return jsonify(response), code

        sig_alg: str | None = sigmeta_raw.get("signature_alg")
        sig_key_id: str | None = sigmeta_raw.get("signing_key_id")
        sig_b64: str = sigmeta_raw.get("signature", "")
        signed_at: str = sigmeta_raw.get("signed_at", "")

        try:
            pub_keys_data = json.loads(public_keys_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            _log(f"Public keys file unavailable: {exc}", level="ERROR")
            response, code = _runtime_error(
                error_code="SIGNATURE_METADATA_UNAVAILABLE",
                message="Public keys file is unavailable for pack verification.",
                dependency="artifact_storage",
            )
            return jsonify(response), code

        sigmeta_obj = {
            "execution_id": execution["execution_id"],
            "pack_hash": execution["pack_hash"],
            "merkle_root": execution["merkle_root"],
            "manifest_hash": execution["manifest_hash"],
            "signed_at": signed_at,
        }
        signature_payload = _canonical_json(sigmeta_obj)

        sig_valid, error_code, _error_detail = _verify_signature_dispatch(
            signature_alg=sig_alg,
            signing_key_id=sig_key_id,
            signature_b64=sig_b64,
            signature_payload=signature_payload.encode("utf-8"),
            public_keys_data=pub_keys_data,
        )

        hash_valid = payload.get("pack_hash") == execution["pack_hash"]
        manifest_consistent = payload.get("manifest_hash", execution["manifest_hash"]) == execution["manifest_hash"]

        result: dict[str, Any] = {
            "signature_valid": sig_valid,
            "hash_valid": hash_valid,
            "manifest_consistent": manifest_consistent,
            "overall_valid": bool(sig_valid and hash_valid and manifest_consistent),
            # v1.2.2 additive fields
            "signature_alg": sig_alg,
            "signing_key_id": sig_key_id,
            "verification_provider": "algorithm_dispatch",
        }
        if error_code:
            result["error_code"] = error_code
        return jsonify(result)

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
        profile = profiles_by_id.get(payload["profile_id"])
        if profile is None:
            return jsonify({"error": "profile_not_found", "profile_id": payload["profile_id"]}), 404

        role_bundle = role_inputs.get(context_id, [])
        governance_modes = [m.strip() for m in payload.get("governance_modes", []) if isinstance(m, str) and m.strip()]
        seed_payload = {
            "context_id": context_id,
            "profile_id": payload["profile_id"],
            "profile_hash": profile.get("profile_hash"),
            "schema_id": payload["schema_id"],
            "schema_version": payload.get("schema_version", "1.0.0"),
            "rp": {
                "reasoning_level": payload["reasoning_level"],
                "policy_level": payload["policy_level"],
            },
            "role_bundle": role_bundle,
            "request_payload": payload,
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
                "latest_record_hash": latest["record_hash"] if latest else None,
                "latest_merkle_root": latest.get("merkle_root") if latest else None,
            }
        )

    def _generate_signed_export_artifacts(execution_id: str, execution: dict[str, Any]) -> tuple[Path, Path, Path, dict[str, Any]]:
        pack_dir = artifacts_dir / execution_id
        zip_path = exports_dir / f"decision-pack_{execution_id}.zip"
        sig_path = exports_dir / f"decision-pack_{execution_id}.sig"
        sigmeta_path = exports_dir / f"decision-pack_{execution_id}.sigmeta.json"

        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for p in sorted(pack_dir.iterdir()):
                zf.write(p, arcname=p.name)

        zip_bytes = zip_path.read_bytes()
        zip_sha256 = _sha256_bytes(zip_bytes)
        sig_b64 = signing_provider.sign_b64(zip_bytes)
        sig_path.write_text(sig_b64, encoding="utf-8")

        sigmeta = {
            "signature_alg": signing_provider.algorithm(),
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
    def export_decision_pack(execution_id: str) -> Any:
        execution = executions.get(execution_id)
        if not execution:
            return jsonify({"error": "execution_not_found", "execution_id": execution_id}), 404

        try:
            zip_path, _sig_path, _sigmeta_path, _sigmeta = _generate_signed_export_artifacts(execution_id, execution)
        except OSError as exc:
            _log(f"Export storage failure: {exc}", level="ERROR", execution_id=execution_id)
            response, code = _runtime_error(
                error_code="EXPORT_STORAGE_UNAVAILABLE",
                message="Export storage is unavailable during decision-pack export.",
                dependency="export_storage",
            )
            return jsonify(response), code

        return send_file(zip_path, as_attachment=True, mimetype="application/zip")

    @app.get("/decision-pack/<execution_id>/export-signed")
    def export_signed(execution_id: str) -> Any:
        execution = executions.get(execution_id)
        if not execution:
            return jsonify({"error": "execution_not_found", "execution_id": execution_id}), 404

        try:
            zip_path, sig_path, sigmeta_path, sigmeta = _generate_signed_export_artifacts(execution_id, execution)
        except OSError as exc:
            _log(f"Export storage failure: {exc}", level="ERROR", execution_id=execution_id)
            response, code = _runtime_error(
                error_code="EXPORT_STORAGE_UNAVAILABLE",
                message="Export storage is unavailable during signed export.",
                dependency="export_storage",
            )
            return jsonify(response), code

        return jsonify({"zip_path": str(zip_path), "sig_path": str(sig_path), "sigmeta_path": str(sigmeta_path), "sigmeta": sigmeta})

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
            "ledger_slice": [l for l in ledger_logs if l.get("execution_id") in execution_ids],
            "verify_execution_snapshots": verify_snapshots,
            "logs": [l for l in backend_logs if l.get("execution_id") in execution_ids or l.get("execution_id") is None][-200:],
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
        if not execution:
            return jsonify({"error": "execution_not_found", "execution_id": execution_id}), 404
        return jsonify({"execution_id": execution_id, "reports": execution.get("artifacts", [])})

    return app


if __name__ == "__main__":
    create_app().run(host="0.0.0.0", port=8000)
