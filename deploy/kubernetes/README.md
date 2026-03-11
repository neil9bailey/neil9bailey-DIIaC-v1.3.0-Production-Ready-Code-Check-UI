# DIIaC v1.2.0 — Kubernetes Deployment Guide

## Files

| File | Purpose |
|------|---------|
| `namespace.yaml` | `diiac` namespace |
| `secrets.yaml` | Secret template (populate before applying) |
| `persistent-volumes.yaml` | PVC definitions for artifacts, exports, audit-exports, human-input |
| `governance-runtime.yaml` | Runtime Deployment + ClusterIP Service |
| `backend-ui-bridge.yaml` | Bridge Deployment + ClusterIP Service |
| `frontend.yaml` | Frontend Deployment + ClusterIP Service |
| `ingress.yaml` | Nginx Ingress routing |

## Prerequisites

- Kubernetes 1.27+
- `kubectl` configured for your cluster
- Container images pushed to `ghcr.io/neil9bailey/diiac-*:v1.2.0`
  (or update image references to your registry)
- nginx-ingress-controller installed
- (Optional) cert-manager for automatic TLS

## Quick deploy

```bash
# 1. Create namespace
kubectl apply -f namespace.yaml

# 2. Populate secrets (edit secrets.yaml first)
#    Or use kubectl directly:
kubectl create secret generic diiac-secrets \
  --namespace diiac \
  --from-literal=ADMIN_API_TOKEN="$(openssl rand -hex 32)" \
  --from-literal=SIGNING_PRIVATE_KEY_PEM="$(cat signing_key.pem)" \
  --from-literal=OPENAI_API_KEY="sk-..."

# 3. Create persistent volumes
kubectl apply -f persistent-volumes.yaml

# 4. Deploy runtime (must come before bridge)
kubectl apply -f governance-runtime.yaml
kubectl rollout status deployment/governance-runtime -n diiac

# 5. Deploy bridge
kubectl apply -f backend-ui-bridge.yaml
kubectl rollout status deployment/backend-ui-bridge -n diiac

# 6. Deploy frontend
kubectl apply -f frontend.yaml
kubectl rollout status deployment/frontend -n diiac

# 7. Apply ingress (update host in ingress.yaml first)
kubectl apply -f ingress.yaml
```

## Verify deployment

```bash
# Check pod status
kubectl get pods -n diiac

# Check runtime health
kubectl exec -n diiac deployment/governance-runtime -- \
  wget -qO- http://localhost:8000/health

# Port-forward for local testing
kubectl port-forward -n diiac svc/governance-runtime 8000:8000
curl http://localhost:8000/health
```

## Scaling notes

- **governance-runtime**: `replicas: 1` only (SQLite single-writer constraint).
  For HA, migrate storage to shared NFS PVC or PostgreSQL.
- **backend-ui-bridge**: Stateless, scales horizontally (`replicas: 2+`).
- **frontend**: Stateless, scales horizontally (`replicas: 2+`).

## Upgrading

```bash
# Update image tags then rolling-restart:
kubectl set image deployment/governance-runtime \
  governance-runtime=ghcr.io/neil9bailey/diiac-runtime:v1.3.0 -n diiac

kubectl rollout status deployment/governance-runtime -n diiac
```

## Rollback

```bash
kubectl rollout undo deployment/governance-runtime -n diiac
kubectl rollout status deployment/governance-runtime -n diiac
```
