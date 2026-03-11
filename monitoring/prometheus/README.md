# DIIaC v1.2.0 — Prometheus Monitoring

## Overview

The governance runtime exposes operational metrics at `GET /admin/metrics`
(JSON format, requires admin bearer token in production).

A Prometheus scrape config and alert rules are provided for integration with
a Prometheus/Grafana stack.

## Quick start (local)

```bash
docker run -d \
  --name diiac-prometheus \
  --network diiac_v120_default \
  -p 9090:9090 \
  -v $(pwd)/monitoring/prometheus/prometheus.yml:/etc/prometheus/prometheus.yml \
  -v $(pwd)/monitoring/prometheus/alerts.yml:/etc/prometheus/alerts.yml \
  prom/prometheus:latest
```

Then open: http://localhost:9090

## Key metrics (from /admin/metrics)

| Field | Alert Code | Threshold |
|-------|-----------|-----------|
| `executions_total` | — | Informational |
| `signed_recent_executions` | MTR-001 | Min 1 when executions present |
| `ledger_record_count` | MTR-002 | Min 1 when executions present |
| `health_status` | — | Must be `OK` |
| `alerts[]` | — | Must be empty |

## Alerts

| Alert | Severity | Trigger |
|-------|---------|---------|
| `DIIaC_NoSignedExecutions` | Warning | No signed executions in last 5 executions |
| `DIIaC_LedgerEmpty` | Critical | Executions exist but ledger record count = 0 |
| `DIIaC_RuntimeDegraded` | Critical | /health returns DEGRADED |
| `DIIaC_RuntimeDown` | Critical | Runtime health check unreachable |
| `DIIaC_BridgeDown` | Critical | Bridge health check unreachable |
| `DIIaC_StorageNearFull` | Warning | PVC > 85% capacity |

## Kubernetes integration

Deploy Prometheus via the [kube-prometheus-stack](https://github.com/prometheus-community/helm-charts/tree/main/charts/kube-prometheus-stack) Helm chart:

```bash
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm install kube-prometheus-stack prometheus-community/kube-prometheus-stack \
  --namespace monitoring --create-namespace
```

Then apply a ServiceMonitor for the governance runtime:

```yaml
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: diiac-runtime
  namespace: monitoring
spec:
  selector:
    matchLabels:
      app.kubernetes.io/component: governance-runtime
  namespaceSelector:
    matchNames:
      - diiac
  endpoints:
    - port: http
      path: /health
      interval: 30s
```

## Recommended Grafana dashboard panels

1. **Executions total** — Counter: `diiac_executions_total`
2. **Signed execution rate** — `diiac_signed_recent_executions / 5`
3. **Ledger record count** — `diiac_ledger_record_count`
4. **Runtime health** — Stat: `diiac_runtime_status` (1=OK, 0=DEGRADED)
5. **Active alerts** — Table: `ALERTS{alertname=~"DIIaC.*"}`
6. **Storage utilisation** — Gauge: PVC used/capacity for `diiac-*` volumes
