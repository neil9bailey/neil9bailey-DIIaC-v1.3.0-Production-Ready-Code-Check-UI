$ErrorActionPreference = 'Stop'

Write-Host "[1/6] Stopping compose stack and removing orphans..."
try { docker compose down --remove-orphans } catch { Write-Warning $_ }

Write-Host "[2/6] Pruning build cache..."
try { docker builder prune -af } catch { Write-Warning $_ }

Write-Host "[3/6] Pruning dangling images and unused volumes/networks..."
try { docker system prune -af --volumes } catch { Write-Warning $_ }

Write-Host "[4/6] (Optional) Pulling clean base images..."
try { docker pull node:20-bullseye } catch { Write-Warning $_ }
try { docker pull python:3.11-slim } catch { Write-Warning $_ }

Write-Host "[5/6] Rebuilding backend-ui-bridge without cache..."
docker compose build --no-cache backend-ui-bridge

Write-Host "[6/6] Rebuilding and starting full stack..."
docker compose up --build -d

Write-Host "Done. Run 'docker compose ps' to confirm service health."
