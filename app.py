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

    strict_deterministic_mode = os.getenv("STRICT_DETERMINISTIC_MODE", "false").lower() == "true"
    signing_enabled = os.getenv("SIGNING_ENABLED", "true").lower() != "false"
    signing_key_id = os.getenv("SIGNING_KEY_ID", "ephemeral-local-ed25519")

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
    for d in [artifacts_dir, exports_dir, audit_dir, keys_dir, profiles_dir]:
        d.mkdir(parents=True, exist_ok=True)

    public_keys_file = keys_dir / "public_keys.json"
    if not public_keys_file.exists():
        public_keys_file.write_text(
            json.dumps({"keys": [{"key_id": signing_key_id, "algorithm": "Ed25519", "public_key_b64": public_key_b64}]}, indent=2),
            encoding="utf-8",
        )

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

    def _log(message: str, level: str = "INFO", execution_id: str | None = None) -> None:
        evt = {"timestamp": _utc_now(), "level": level, "message": message, "execution_id": execution_id}
        backend_logs.append(evt)
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
    def admin_config() -> Any:
        return jsonify(
            {
                "version": "v1.1.0",
                "runtime_model": ["react-vite-frontend", "express-backend"],
                "approved_schemas": sorted(approved_schemas),
                "profiles_count": len(profiles),
            }
        )

    @app.post("/api/human-input/role")
    def role_input() -> Any:
        payload = request.get_json(silent=True) or {}
        required = ["execution_context_id", "role", "domain", "assertions", "non_negotiables", "risk_flags", "evidence_refs"]
        missing = [k for k in required if k not in payload]
        if missing:
            return jsonify({"error": "missing_fields", "missing": missing}), 400
        for arr in ["assertions", "non_negotiables", "risk_flags", "evidence_refs"]:
            if not isinstance(payload[arr], list):
                return jsonify({"error": "invalid_field", "field": arr}), 400

        ctx = payload["execution_context_id"]
        role_inputs.setdefault(ctx, []).append(payload)
        _log(f"Role input accepted for {ctx}")
        return jsonify({"stored": True, "execution_context_id": ctx, "role_count": len(role_inputs[ctx])}), 201

    @app.get("/api/business-profiles")
    def business_profiles() -> Any:
        return jsonify({"profiles": profiles, "profiles_count": len(profiles)})

    @app.post("/api/governed-compile")
    def governed_compile() -> Any:
        response, code = _build_execution(request.get_json(silent=True) or {})
        return jsonify(response), code

    @app.post("/api/compile")
    def compile_alias() -> Any:
        response, code = _build_execution(request.get_json(silent=True) or {})
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
        signed_recent = sum(1 for e in list(executions.values())[-5:] if e.get("signature"))
        return jsonify(
            {
                "health_status": "OK",
                "executions_total": len(executions),
                "signed_recent_executions": signed_recent,
                "ledger_record_count": len(ledger_logs),
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
        try:
            public_key.verify(signature, signature_payload.encode("utf-8"))
            signature_valid = True
        except Exception:
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
        valid = _verify_merkle_proof(
            leaf_hash=payload.get("leaf_hash", ""),
            siblings=payload.get("siblings", []),
            index=int(payload.get("index", 0)),
            merkle_root=payload.get("merkle_root", ""),
        )
        return jsonify({"proof_valid": valid})

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

    @app.get("/decision-pack/<execution_id>/export-signed")
    def export_signed(execution_id: str) -> Any:
        execution = executions.get(execution_id)
        if not execution:
            return jsonify({"error": "execution_not_found", "execution_id": execution_id}), 404

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

        return jsonify({"zip_path": str(zip_path), "sig_path": str(sig_path), "sigmeta_path": str(sigmeta_path), "sigmeta": sigmeta})

    @app.post("/admin/audit-export")
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
        audit_exports[audit_id] = {"path": str(out), "created_at": _utc_now()}
        _append_ledger("GOVERNANCE_AUDIT_ACCESS", {"access_type": "audit_export", "audit_export_id": audit_id})
        return jsonify({"audit_export_id": audit_id, "download_url": f"/admin/audit/exports/{audit_id}/download"}), 201

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
