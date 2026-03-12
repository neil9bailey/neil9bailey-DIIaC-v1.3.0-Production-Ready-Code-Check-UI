# CP17 Closeout Summary

- Deployment: diiac-ui-dedicated-cp17-nolock-apply-20260312-031733
- Runtime active revision: rt-vendorlogic-ui-prod-v130--0000006
- Runtime health: Healthy
- Runtime running state: RunningAtMaxScale
- Runtime replicas: 1
- Runtime image: acrdiiacv130vlui.azurecr.io/diiac/governance-runtime:1.3.0-sigfix4
- Runtime env includes DIIAC_SQLITE_NOLOCK: true
- UI custom domain HTTP: 200
- Bridge /health HTTP: 200
- Bridge /readiness HTTP: 200

## Notes

- Fixed startup crash-loop caused by SQLite file locking on Azure Files-backed state DB.
- Applied runtime resilience updates in persistence layer and runtime image tag 1.3.0-sigfix4.
- In-container post-deploy pack generation/verification is temporarily blocked by Azure Container Apps exec rate limit (429 retry-after 600s).
