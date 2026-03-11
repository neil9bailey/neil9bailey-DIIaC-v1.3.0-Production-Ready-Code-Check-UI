"""DIIaC State Persistence — SQLite write-through store.

Provides durable storage for all governance runtime state so that
trust ledger, execution history, logs, and role inputs survive
container restarts.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any


class StateStore:
    """SQLite-backed persistence for DIIaC governance runtime state."""

    def __init__(self, db_path: str | Path) -> None:
        self._conn = sqlite3.connect(
            str(db_path),
            check_same_thread=False,
        )
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=NORMAL")
        self._create_tables()

    # ── Schema ────────────────────────────────────────────────────────────

    def _create_tables(self) -> None:
        cur = self._conn.cursor()
        cur.executescript("""
            CREATE TABLE IF NOT EXISTS ledger (
                record_id   INTEGER PRIMARY KEY,
                timestamp   TEXT    NOT NULL,
                event_type  TEXT    NOT NULL,
                previous_record_hash TEXT NOT NULL,
                record_hash TEXT    NOT NULL,
                payload_json TEXT   NOT NULL
            );

            CREATE TABLE IF NOT EXISTS backend_logs (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp    TEXT    NOT NULL,
                level        TEXT    NOT NULL,
                event_id     TEXT    NOT NULL,
                message      TEXT    NOT NULL,
                execution_id TEXT
            );

            CREATE TABLE IF NOT EXISTS executions (
                execution_id         TEXT PRIMARY KEY,
                execution_context_id TEXT NOT NULL,
                created_at           TEXT NOT NULL,
                data_json            TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS role_inputs (
                id                    INTEGER PRIMARY KEY AUTOINCREMENT,
                execution_context_id  TEXT NOT NULL,
                payload_json          TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS audit_exports (
                audit_export_id   TEXT PRIMARY KEY,
                path              TEXT NOT NULL,
                created_at        TEXT NOT NULL,
                execution_ids_json TEXT NOT NULL,
                download_url      TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_backend_logs_execution
                ON backend_logs(execution_id);
            CREATE INDEX IF NOT EXISTS idx_role_inputs_ctx
                ON role_inputs(execution_context_id);
            CREATE INDEX IF NOT EXISTS idx_ledger_hash
                ON ledger(record_hash);
        """)
        self._conn.commit()

    # ── Write methods ─────────────────────────────────────────────────────

    def append_backend_log(self, evt: dict[str, Any]) -> None:
        self._conn.execute(
            "INSERT INTO backend_logs (timestamp, level, event_id, message, execution_id) "
            "VALUES (?, ?, ?, ?, ?)",
            (evt["timestamp"], evt["level"], evt["event_id"],
             evt["message"], evt.get("execution_id")),
        )
        self._conn.commit()

    def append_ledger_record(self, record: dict[str, Any]) -> None:
        core = {k: v for k, v in record.items()
                if k not in ("record_id", "timestamp", "event_type",
                             "previous_record_hash", "record_hash")}
        self._conn.execute(
            "INSERT INTO ledger (record_id, timestamp, event_type, "
            "previous_record_hash, record_hash, payload_json) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (record["record_id"], record["timestamp"], record["event_type"],
             record["previous_record_hash"], record["record_hash"],
             json.dumps(core, sort_keys=True)),
        )
        self._conn.commit()

    def save_execution(self, execution_id: str, execution: dict[str, Any]) -> None:
        ctx_id = execution.get("execution_context_id", "")
        created = execution.get("created_at", "")
        self._conn.execute(
            "INSERT OR REPLACE INTO executions "
            "(execution_id, execution_context_id, created_at, data_json) "
            "VALUES (?, ?, ?, ?)",
            (execution_id, ctx_id, created,
             json.dumps(execution, sort_keys=True, default=str)),
        )
        self._conn.commit()

    def append_role_input(self, ctx: str, payload: dict[str, Any]) -> None:
        self._conn.execute(
            "INSERT INTO role_inputs (execution_context_id, payload_json) "
            "VALUES (?, ?)",
            (ctx, json.dumps(payload, sort_keys=True)),
        )
        self._conn.commit()

    def save_audit_export(self, audit_id: str, entry: dict[str, Any]) -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO audit_exports "
            "(audit_export_id, path, created_at, execution_ids_json, download_url) "
            "VALUES (?, ?, ?, ?, ?)",
            (audit_id, entry.get("path", ""),
             entry.get("created_at", ""),
             json.dumps(entry.get("execution_ids", [])),
             entry.get("download_url", "")),
        )
        self._conn.commit()

    # ── Read methods (startup restoration) ────────────────────────────────

    def load_all_backend_logs(self) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            "SELECT timestamp, level, event_id, message, execution_id "
            "FROM backend_logs ORDER BY id"
        ).fetchall()
        return [
            {"timestamp": r[0], "level": r[1], "event_id": r[2],
             "message": r[3], "execution_id": r[4]}
            for r in rows
        ]

    def load_all_ledger_records(self) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            "SELECT record_id, timestamp, event_type, "
            "previous_record_hash, record_hash, payload_json "
            "FROM ledger ORDER BY record_id"
        ).fetchall()
        results: list[dict[str, Any]] = []
        for r in rows:
            record: dict[str, Any] = {
                "record_id": r[0],
                "timestamp": r[1],
                "event_type": r[2],
                "previous_record_hash": r[3],
                "record_hash": r[4],
            }
            record.update(json.loads(r[5]))
            results.append(record)
        return results

    def load_all_executions(self) -> dict[str, dict[str, Any]]:
        rows = self._conn.execute(
            "SELECT execution_id, data_json FROM executions"
        ).fetchall()
        return {r[0]: json.loads(r[1]) for r in rows}

    def load_all_role_inputs(self) -> dict[str, list[dict[str, Any]]]:
        rows = self._conn.execute(
            "SELECT execution_context_id, payload_json "
            "FROM role_inputs ORDER BY id"
        ).fetchall()
        result: dict[str, list[dict[str, Any]]] = {}
        for ctx, payload_json in rows:
            result.setdefault(ctx, []).append(json.loads(payload_json))
        return result

    def load_all_audit_exports(self) -> dict[str, dict[str, Any]]:
        rows = self._conn.execute(
            "SELECT audit_export_id, path, created_at, "
            "execution_ids_json, download_url FROM audit_exports"
        ).fetchall()
        return {
            r[0]: {
                "path": r[1],
                "created_at": r[2],
                "execution_ids": json.loads(r[3]),
                "download_url": r[4],
            }
            for r in rows
        }

    # ── Health check ──────────────────────────────────────────────────────

    def is_healthy(self) -> bool:
        try:
            self._conn.execute("SELECT 1").fetchone()
            return True
        except Exception:
            return False

    # ── Cleanup ───────────────────────────────────────────────────────────

    def close(self) -> None:
        self._conn.close()
