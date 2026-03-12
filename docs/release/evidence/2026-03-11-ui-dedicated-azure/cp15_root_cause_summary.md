# CP15 Runtime Crash Root Cause

- Failing revision: `rt-vendorlogic-ui-prod-v130--0000003`
- Image: `acrdiiacv130vlui.azurecr.io/diiac/governance-runtime:1.3.0-sigfix1`
- Crash signature (Log Analytics): `sqlite3.OperationalError: database is locked`
- Stack location:
  - `/app/persistence.py`, line 23 (`PRAGMA journal_mode=WAL`)
  - called from `/app/app.py`, line 233 (`store = StateStore(db_path)`)

## Why this happened

`/app/state` is mounted to Azure Files. WAL mode can be unsupported/locked on network-backed SQLite files, causing startup failure and container crash-loop.

## Code fix prepared

- Added resilient SQLite pragma setup in `persistence.py`:
  - tries `journal_mode=WAL`
  - falls back to `journal_mode=DELETE` on `sqlite3.OperationalError`
  - keeps `synchronous=NORMAL` best-effort
- Added regression test: `tests/test_persistence.py::test_state_store_falls_back_when_wal_is_locked`
- Built/pushed runtime image tag: `1.3.0-sigfix2`
