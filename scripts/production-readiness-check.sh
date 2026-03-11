#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

log() {
  printf '\n==> %s\n' "$1"
}

log "Python test suite"
(
  cd "$ROOT_DIR"
  pytest -q
)

log "Backend JavaScript syntax checks"
(
  cd "$ROOT_DIR/backend-ui-bridge"
  node --check server.js
  node --check providers/chatgpt.js
  node --check providers/copilot.js
  node --check llm-ingestion/ingestRouter.js
  node --check llm-ingestion/store.js
)

log "Frontend lint"
(
  cd "$ROOT_DIR/Frontend"
  npm run lint
)

log "Frontend production build"
(
  cd "$ROOT_DIR/Frontend"
  npm run build
)

log "Production readiness checks completed successfully"
