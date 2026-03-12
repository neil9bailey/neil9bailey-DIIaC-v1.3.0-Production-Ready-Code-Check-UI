# CP8 Summary (Build + Push Images)

- UTC timestamp: 2026-03-11 22:09:58 +00:00
- Build/push status: SUCCESS
- Build/push log: docs/release/evidence/2026-03-11-ui-dedicated-azure/cp8_build_push_20260311-220036.log
- Container Apps in subscription after CP8: 0

## Images Verified in ACR
- runtime: acrdiiacv130vlui.azurecr.io/diiac/governance-runtime:1.3.0-adminheaderfix
  digest: sha256:fcf056764396cb48c9a7edb00a9f09e9b9b29d1940ac9d95e89d87a913820085
  created: 2026-03-11T22:02:08.0837034Z
- bridge: acrdiiacv130vlui.azurecr.io/diiac/backend-ui-bridge:1.3.0-ingressfix
  digest: sha256:ebd219c44a00fc1a95b1780848a151820571ef16b5aa30edf21aa0cd44bd083d
  created: 2026-03-11T22:04:03.1416628Z
- frontend: acrdiiacv130vlui.azurecr.io/diiac/frontend:1.3.0-groupmapfix
  digest: sha256:396320ab29175ed65618dffc7a6e9650d4fe3968777408d12f9f9f4e1a258003
  created: 2026-03-11T22:08:14.0563219Z

## Notes
- Applied non-destructive script fix to remove CRLF from ACR login server in bash (`tr -d '\r'`).
- No infrastructure or app deployment executed in CP8; this checkpoint only builds and pushes images.
