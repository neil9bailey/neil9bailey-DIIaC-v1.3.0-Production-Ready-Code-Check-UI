from __future__ import annotations

import sqlite3

from persistence import StateStore


def test_state_store_falls_back_when_wal_is_locked(monkeypatch, tmp_path):
    real_connect = sqlite3.connect
    calls = {"wal": 0, "delete": 0}

    class ConnectionProxy:
        def __init__(self, inner):
            self._inner = inner

        def execute(self, sql, *args, **kwargs):
            if sql == "PRAGMA journal_mode=WAL":
                calls["wal"] += 1
                raise sqlite3.OperationalError("database is locked")
            if sql == "PRAGMA journal_mode=DELETE":
                calls["delete"] += 1
            return self._inner.execute(sql, *args, **kwargs)

        def executescript(self, script):
            return self._inner.executescript(script)

        def cursor(self):
            return self._inner.cursor()

        def commit(self):
            return self._inner.commit()

        def close(self):
            return self._inner.close()

    def fake_connect(*args, **kwargs):
        return ConnectionProxy(real_connect(*args, **kwargs))

    monkeypatch.setattr(sqlite3, "connect", fake_connect)

    store = StateStore(tmp_path / "state.db")
    assert calls["wal"] == 1
    assert calls["delete"] == 1
    assert store.is_healthy() is True


def test_state_store_tolerates_table_init_lock_when_schema_exists(monkeypatch, tmp_path):
    db_path = tmp_path / "state.db"
    conn = sqlite3.connect(str(db_path))
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS ledger (
            record_id INTEGER PRIMARY KEY,
            timestamp TEXT NOT NULL,
            event_type TEXT NOT NULL,
            previous_record_hash TEXT NOT NULL,
            record_hash TEXT NOT NULL,
            payload_json TEXT NOT NULL
        );
        """
    )
    conn.commit()
    conn.close()

    def fail_create_tables(_self):
        raise sqlite3.OperationalError("database is locked")

    monkeypatch.setattr(StateStore, "_create_tables", fail_create_tables)

    store = StateStore(db_path)
    assert store.is_healthy() is True


def test_state_store_uses_nolock_uri_when_enabled(monkeypatch, tmp_path):
    real_connect = sqlite3.connect
    captured: dict[str, object] = {}

    def fake_connect(*args, **kwargs):
        captured["database"] = args[0] if args else None
        captured["uri"] = kwargs.get("uri", False)
        return real_connect(":memory:", check_same_thread=False)

    monkeypatch.setenv("DIIAC_SQLITE_NOLOCK", "true")
    monkeypatch.setattr(sqlite3, "connect", fake_connect)

    store = StateStore(tmp_path / "state.db")
    assert str(captured.get("database", "")).startswith("file:")
    assert "nolock=1" in str(captured.get("database", ""))
    assert captured.get("uri") is True
    assert store.is_healthy() is True
