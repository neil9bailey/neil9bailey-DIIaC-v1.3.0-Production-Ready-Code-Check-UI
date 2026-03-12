# CP11 Auth Mode Fix Summary

- UTC timestamp: 2026-03-11 23:11:11 +00:00
- Deployment: diiac-ui-dedicated-cp11-authfix-20260311-230359
- Frontend image tag deployed: 1.3.0-groupmapfix-hostfix-entrafix
- UI image live: acrdiiacv130vlui.azurecr.io/diiac/frontend:1.3.0-groupmapfix-hostfix-entrafix
- UI provisioning/running: Succeeded / Running

## Root Cause
- Frontend bundle had build-time fallbacks (`localhost:3001` and `localhost:5173/auth/callback`), which caused auth status fetch failure and UI fallback to legacy auth mode.

## Fix Applied
- Rebuilt frontend with explicit Vite build args for API base, Entra client/tenant, redirect URI, and group map.
- New bundle checks: localhost_api=False, localhost_redirect=False, bridge_url=True, custom_redirect=True
- Bridge /auth/status: {"auth_mode":"entra_jwt_rs256","entra_enabled":true,"tenant_id":"1384b1c5-2bae-45a1-a4b4-e94e3315eb41","audience":"api://b726558d-f1c6-48f7-8a3d-72d5db818d0f","llm_provider_mode":"copilot_only"}

## Custom Domain
- Re-bound custom domain after app revision rollout removed hostname binding.
- Hostname bindings active: 1
- Binding: diiacui.vendorlogic.io (SniEnabled)

## Validation
- https://diiacui.vendorlogic.io returns HTTP 200
- Live bridge auth mode is Entra RS256 (not legacy).
