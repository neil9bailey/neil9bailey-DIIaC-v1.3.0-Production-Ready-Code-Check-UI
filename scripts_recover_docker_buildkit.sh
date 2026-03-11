#!/usr/bin/env bash
set -euo pipefail

# Recovers from Docker BuildKit snapshot/cache corruption errors like:
# "failed to prepare extraction snapshot ... parent snapshot ... does not exist"

echo "[1/6] Stopping compose stack and removing orphans..."
docker compose down --remove-orphans || true

echo "[2/6] Pruning build cache..."
docker builder prune -af || true

echo "[3/6] Pruning dangling images and unused volumes/networks..."
docker system prune -af --volumes || true

echo "[4/6] (Optional) Pulling clean base images..."
docker pull node:20-bullseye || true
docker pull python:3.11-slim || true

echo "[5/6] Rebuilding backend-ui-bridge without cache..."
docker compose build --no-cache backend-ui-bridge

echo "[6/6] Rebuilding and starting full stack..."
docker compose up --build -d

echo "Done. Run 'docker compose ps' to confirm service health."
