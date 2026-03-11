#!/usr/bin/env bash
# DIIaC v1.2.0 -- Local staging launcher (Mac / Linux / WSL)
#
# Pulls secrets from Azure Key Vault, then starts the full Docker stack.
# Run this instead of the two-step manual process.
#
# Usage:
#   bash start-staging.sh                # pull secrets + build + start (foreground)
#   bash start-staging.sh --detach       # pull secrets + build + start (background)
#   bash start-staging.sh --no-build     # pull secrets + start without rebuild
#   bash start-staging.sh --secrets-only # pull secrets only, skip stack start
#
# Prerequisites: Docker Desktop running, Azure CLI installed, az login done.

set -euo pipefail

DETACH=false
NO_BUILD=false
SECRETS_ONLY=false

for arg in "$@"; do
    case $arg in
        -d|--detach)       DETACH=true ;;
        --no-build)        NO_BUILD=true ;;
        --secrets-only)    SECRETS_ONLY=true ;;
    esac
done

REPO_ROOT="$(cd "$(dirname "$0")" && pwd)"

ok()   { printf '\033[32m[OK]   %s\033[0m\n' "$1"; }
warn() { printf '\033[33m[WARN] %s\033[0m\n' "$1"; }
fail() { printf '\033[31m[FAIL] %s\033[0m\n' "$1"; exit 1; }
step() { printf '\n\033[36m-- Step %s : %s\033[0m\n' "$1" "$2"; }
header() { printf '\033[36m%s\033[0m\n' "$1"; }

printf '\n'
header "DIIaC v1.2.0 -- Local Staging Launcher"
header "========================================"
printf '\n'

# ── Step 1: Check Docker Desktop ──────────────────────────────────────────────
step 1 "Checking Docker Desktop"

command -v docker >/dev/null 2>&1 || \
    fail "Docker not found. Install Docker Desktop: https://www.docker.com/products/docker-desktop/"

docker info >/dev/null 2>&1 || \
    fail "Docker Desktop is not running. Start it and try again."

ok "Docker Desktop is running"

# ── Step 2: Pull secrets ──────────────────────────────────────────────────────
step 2 "Pulling secrets from Azure Key Vault"

PULL_SCRIPT="$REPO_ROOT/scripts/pull-keyvault-secrets.sh"
[ -f "$PULL_SCRIPT" ] || fail "Pull script not found at: $PULL_SCRIPT"

bash "$PULL_SCRIPT"

if [ "$SECRETS_ONLY" = true ]; then
    warn "SecretsOnly flag set -- skipping stack start."
    exit 0
fi

# ── Step 3: Verify outputs before starting ────────────────────────────────────
step 3 "Verifying outputs"

[ -f "$REPO_ROOT/.env" ]                    || fail ".env was not created by the pull script."
[ -f "$REPO_ROOT/.secrets/signing_key.pem" ] || fail ".secrets/signing_key.pem was not created by the pull script."

grep -q "BEGIN" "$REPO_ROOT/.secrets/signing_key.pem" || \
    fail ".secrets/signing_key.pem does not look like a valid PEM file."

ok ".env present"
ok ".secrets/signing_key.pem valid"

# ── Step 4: Start the stack ───────────────────────────────────────────────────
step 4 "Starting DIIaC stack"

COMPOSE_ARGS="-f docker-compose.yml -f docker-compose.staging.yml up"
[ "$NO_BUILD" = false ] && COMPOSE_ARGS="$COMPOSE_ARGS --build"
[ "$DETACH"   = true  ] && COMPOSE_ARGS="$COMPOSE_ARGS -d"

printf '\n'
[ "$NO_BUILD" = true ] && warn "NoBuild flag set -- skipping image rebuild."
[ "$DETACH"   = true ] && warn "Detach flag set -- starting in background."
printf '\n'

# shellcheck disable=SC2086
docker compose $COMPOSE_ARGS

# ── Done (detached mode only -- foreground stays in compose output) ───────────
if [ "$DETACH" = true ]; then
    printf '\n'
    header "========================================"
    header "Stack started."
    printf '\n'
    printf '  Frontend : http://localhost:5173\n'
    printf '  Runtime  : http://localhost:8000/health\n'
    printf '  Bridge   : http://localhost:3001\n'
    printf '\n'
    printf '  Follow logs : docker compose logs -f\n'
    printf '  Stop        : docker compose -f docker-compose.yml -f docker-compose.staging.yml down\n'
    printf '\n'
fi
