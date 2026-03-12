# CP12 Summary (Entra Redirect URI Fix)

- UTC timestamp: 2026-03-11 23:16:10 +00:00
- Error addressed: AADSTS50011 redirect URI mismatch for https://diiacui.vendorlogic.io/auth/callback
- App registration: b726558d-f1c6-48f7-8a3d-72d5db818d0f (diiac-bridge-gateway)

## Before
- SPA redirects count: 4
- Included callback? False

## Change Applied
- Patched Microsoft Graph application object `spa.redirectUris` to include:
  - https://diiacui.vendorlogic.io
  - https://diiacui.vendorlogic.io/auth/callback

## After
- SPA redirects count: 6
- Includes callback? True
- Includes root URI? True

## Notes
- Frontend is already configured with redirect URI https://diiacui.vendorlogic.io/auth/callback and Entra mode is active in bridge.
- If browser cached stale auth state, retry in an incognito window.
