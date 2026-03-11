from __future__ import annotations

import base64
import hashlib
import json
import os
import uuid
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from cryptography.exceptions import InvalidSignature, UnsupportedAlgorithm
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from flask import Flask, jsonify, request, send_file
from persistence import StateStore


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


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

    strict_deterministic_mode = os.getenv("STRICT_DETERMINISTIC_MODE", "false").lower() == "true"
    signing_enabled = os.getenv("SIGNING_ENABLED", "true").lower() != "false"
    signing_key_id = os.getenv("SIGNING_KEY_ID", "ephemeral-local-ed25519")

    admin_auth_enabled = os.getenv("ADMIN_AUTH_ENABLED", "true").lower() != "false"
    runtime_env = os.getenv("APP_ENV", "production").lower()
    admin_api_token = os.getenv("ADMIN_API_TOKEN", "")

    private_key, key_mode = _load_or_create_signing_key()
    public_key = private_key.public_key()
    public_key_b64 = base64.b64encode(
        public_key.public_bytes(encoding=serialization.Encoding.Raw, format=serialization.PublicFormat.Raw)
    ).decode("utf-8")

    artifacts_dir = Path.cwd() / "artifacts"
    exports_dir = Path.cwd() / "exports"
    audit_dir = Path.cwd() / "audit_exports"
    keys_dir = Path.cwd() / "contracts" / "keys"
    profiles_dir = Path.cwd() / "contracts" / "business-profiles"
    state_dir = Path.cwd() / "state"
    for d in [artifacts_dir, exports_dir, audit_dir, keys_dir, profiles_dir, state_dir]:
        d.mkdir(parents=True, exist_ok=True)

    db_path = os.getenv("DIIAC_STATE_DB", str(state_dir / "diiac_state.db"))
    store = StateStore(db_path)

    public_keys_file = keys_dir / "public_keys.json"
    if not public_keys_file.exists():
        public_keys_file.write_text(
            json.dumps({"keys": [{
                "key_id": signing_key_id,
                "algorithm": "Ed25519",
                "public_key_b64": public_key_b64,
            }]}, indent=2),
            encoding="utf-8",
        )

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
        checks["database"] = store.is_healthy()
        hard_failures = [v for v in checks.values() if v is False]
        return {
            "overall_ready": len(hard_failures) == 0,
            "checks": checks,
        }

    backend_logs: list[dict[str, Any]] = store.load_all_backend_logs()
    ledger_logs: list[dict[str, Any]] = store.load_all_ledger_records()
    executions: dict[str, dict[str, Any]] = store.load_all_executions()
    role_inputs: dict[str, list[dict[str, Any]]] = store.load_all_role_inputs()
    audit_exports: dict[str, dict[str, Any]] = store.load_all_audit_exports()
    execution_logs: dict[str, list[dict[str, Any]]] = {}
    for evt in backend_logs:
        if evt.get("execution_id"):
            execution_logs.setdefault(evt["execution_id"], []).append(evt)
    profile_overrides: list[dict[str, Any]] = []

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
        store.append_ledger_record(record)
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

    def _extract_options_from_llm(llm_analysis: dict[str, Any]) -> list[dict[str, str]]:
        """Extract solution options from LLM analysis output.

        The LLM may return options under various keys — this function
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
        return options

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
            ("vmware", "VMware"),
            ("zscaler", "Zscaler"),
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

    def _extract_intent_signals(intent_text: str) -> dict[str, Any]:
        t = intent_text.lower()
        signals: dict[str, Any] = {
            "regulatory_constraints": [],
            "security_constraints": [],
            "financial_constraints": [],
            "success_targets": [],
        }
        for token, label in [
            ("gdpr", "GDPR"), ("nis2", "NIS2"), ("dora", "DORA"), ("iso27001", "ISO27001"),
            ("eu ai act", "EU AI Act"), ("ai act", "EU AI Act"), ("fca", "FCA"),
            ("pci dss", "PCI DSS"), ("sox", "SOX"), ("hipaa", "HIPAA"),
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
        ]:
            if token in t and label not in signals["security_constraints"]:
                signals["security_constraints"].append(label)
        if "capex" in t or "budget" in t or "cost" in t:
            signals["financial_constraints"].append("Budget/cost constraint detected")
        if "license" in t or "subscription" in t or "per seat" in t or "per-seat" in t:
            signals["financial_constraints"].append("Licensing/subscription cost detected")
        for marker in ["incident", "operating cost", "resilience", "uptime", "availability",
                        "delivery velocity", "code quality", "response time", "sla",
                        "customer satisfaction", "resolution rate", "accuracy"]:
            if marker in t and marker not in signals["success_targets"]:
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
                        f"  - Confidence: {rec.get('confidence_level')} "
                        f"({rec.get('confidence_score')}) — "
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
        execution_id = (
            str(uuid.uuid5(uuid.NAMESPACE_URL, f"diiac:{context_hash}"))
            if strict_deterministic_mode else str(uuid.uuid4())
        )

        required_sections = profile["required_sections"]

        # Extract LLM analysis if provided by the bridge
        llm_analysis = payload.get("llm_analysis")
        llm_provider = payload.get("llm_provider")

        intent_text_parts = []
        for role_item in role_bundle:
            intent_text_parts.extend([
                *role_item.get("assertions", []),
                *role_item.get("non_negotiables", []),
                *role_item.get("risk_flags", []),
            ])
        intent_text = " | ".join([v for v in intent_text_parts if isinstance(v, str)])

        # When LLM analysis is present, extract options from LLM output;
        # otherwise fall back to keyword-matched templates
        llm_options: list[dict[str, str]] = []
        llm_sections: list[dict[str, str]] = []
        if isinstance(llm_analysis, dict) and llm_analysis:
            llm_options = _extract_options_from_llm(llm_analysis)
            llm_sections = _extract_sections_from_llm(llm_analysis)
            option_profiles = llm_options if llm_options else _derive_solution_options(
                intent_text, preferred_vendors=_extract_named_vendors(intent_text)
            )
        else:
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
        if not vendor_rows:
            return {
                "error": "no_solution_options",
                "message": "No solution options could be derived from the provided inputs.",
            }, 400
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
                "Confidence is derived from deterministic scoring, "
                "control compliance, evidence completeness and "
                "governance mode checks."
            ),
            "control_failure_reasons": control_failure_reasons,
            "claim_ids": evidence_ids_seed,
        }

        # When LLM analysis is present, merge LLM sections (extracted earlier)
        # with deterministic sections; otherwise use templates only
        if isinstance(llm_analysis, dict) and llm_analysis:
            deterministic_sections = _build_human_readable_sections(
                execution_id, profile, schema_id, rp, role_bundle, recommendation,
                vendor_rows=vendor_rows, compliance_matrix=compliance_matrix,
                governance_modes=governance_modes,
            )
            # LLM sections take priority; deterministic sections fill gaps
            by_title: dict[str, dict[str, str]] = {}
            for s in deterministic_sections:
                by_title[s["title"]] = s
            for s in llm_sections:
                by_title[s["title"]] = s
            draft_sections = list(by_title.values())
        else:
            draft_sections = _build_human_readable_sections(
                execution_id, profile, schema_id, rp, role_bundle, recommendation,
                vendor_rows=vendor_rows, compliance_matrix=compliance_matrix,
                governance_modes=governance_modes,
            )
        sections = _enforce_sections(required_sections, draft_sections)

        evidence_entries: list[dict[str, Any]] = []
        for idx, section in enumerate(sections, start=1):
            source_role = role_bundle[(idx - 1) % len(role_bundle)]["role"] if role_bundle else "system"
            source_ref = (
                role_bundle[(idx - 1) % len(role_bundle)]
                .get("evidence_refs", [f"auto-ref-{idx}"])[0]
                if role_bundle else f"placeholder-{idx}"
            )
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
                "decision_basis": (
                    f"LLM-analysed content ({llm_provider}) governed by deterministic scoring + profile/policy controls"
                    if isinstance(llm_analysis, dict) and llm_analysis
                    else "Deterministic weighted scoring + profile/policy controls + role evidence"
                ),
                "decision_status": recommendation["decision_status"],
                "governance_modes": governance_modes,
                "control_failure_reasons": recommendation["control_failure_reasons"],
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
        # Include the raw LLM analysis as a governed artifact for full auditability
        if isinstance(llm_analysis, dict) and llm_analysis:
            artifacts_payloads["llm_analysis_raw.json"] = {
                "provider": llm_provider,
                "analysis": llm_analysis,
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
                "version": "v1.2.0",
                "runtime_model": ["react-vite-frontend", "express-backend"],
                "approved_schemas": sorted(approved_schemas),
                "profiles_count": len(profiles),
                "admin_auth_enabled": admin_auth_enabled,
                "runtime_env": runtime_env,
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
        store.append_role_input(ctx, payload)
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
            "key_registry_ok": signing_enabled and public_keys_file.exists(),
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
        data = json.loads(public_keys_file.read_text(encoding="utf-8"))
        return jsonify(data)

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
            signed_at = json.loads(sigmeta_file.read_text())["signed_at"]
        except (OSError, json.JSONDecodeError, KeyError) as exc:
            _log(f"Signature metadata unavailable: {exc}", level="ERROR", execution_id=execution["execution_id"])
            response, code = _runtime_error(
                error_code="SIGNATURE_METADATA_UNAVAILABLE",
                message="Signature metadata is unavailable for pack verification.",
                dependency="artifact_storage",
            )
            return jsonify(response), code

        sigmeta = {
            "execution_id": execution["execution_id"],
            "pack_hash": execution["pack_hash"],
            "merkle_root": execution["merkle_root"],
            "manifest_hash": execution["manifest_hash"],
            "signed_at": signed_at,
        }
        signature_payload = _canonical_json(sigmeta)
        signature_valid = False
        try:
            signature = base64.b64decode(execution["signature"])
        except Exception as exc:
            _log(f"Signature base64 decode error: {exc}",
                 level="ERROR", execution_id=execution["execution_id"])
            signature = b""

        if signature:
            try:
                public_key.verify(
                    signature, signature_payload.encode("utf-8"),
                )
                signature_valid = True
            except InvalidSignature:
                signature_valid = False

        hash_valid = payload.get("pack_hash") == execution["pack_hash"]
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
        if not execution:
            return jsonify({"error": "execution_not_found", "execution_id": execution_id}), 404
        return jsonify({"execution_id": execution_id, "reports": execution.get("artifacts", [])})

    return app


if __name__ == "__main__":
    create_app().run(host="0.0.0.0", port=8000)  # noqa: S104 — Docker requires all-interface bind
