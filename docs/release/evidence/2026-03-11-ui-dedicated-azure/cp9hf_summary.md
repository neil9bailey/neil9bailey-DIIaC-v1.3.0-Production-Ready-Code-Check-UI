# CP9-HF Summary (UI Host Allowlist Hotfix)

- UTC timestamp: 2026-03-11 22:36:52 +00:00
- Deployment: diiac-ui-dedicated-cp9hf-20260311-223126
- Frontend tag: 1.3.0-groupmapfix-hostfix
- Validate/What-if/Apply: SUCCESS / SUCCESS / SUCCESS
- What-if summary: resource create=0, resource modify=6, resource delete=0 (property-level diffs only)

## Result
- UI container image now: acrdiiacv130vlui.azurecr.io/diiac/frontend:1.3.0-groupmapfix-hostfix
- UI Azure FQDN: ui-vendorlogic-ui-prod-v130.blackpond-85ed120f.uksouth.azurecontainerapps.io
- UI probe status: 200
- Bridge auth status probe: 200
- Frontend digest: sha256:e47d06fe07c6339daae55bb17aea28d276d3622e27c557fce0d781f963448597

## DNS Values For IONOS
- CNAME host: diiacui
- CNAME target: ui-vendorlogic-ui-prod-v130.blackpond-85ed120f.uksouth.azurecontainerapps.io
- TXT host: asuid.diiacui
- TXT value: B01B517DF534900404CD467B96A1A1B57E73B6E8EEDF856F26751B5C518EA101

