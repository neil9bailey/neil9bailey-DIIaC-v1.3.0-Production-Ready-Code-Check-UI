# CP10 Summary (Custom Domain Bind + HTTPS)

- UTC timestamp: 2026-03-11 22:55:26 +00:00
- DNS CNAME verified: diiacui.vendorlogic.io -> ui-vendorlogic-ui-prod-v130.blackpond-85ed120f.uksouth.azurecontainerapps.io
- DNS TXT verified: asuid.diiacui.vendorlogic.io present with expected value
- Hostname add: SUCCESS
- Hostname bind: SUCCESS

## Custom Domain State
- Hostname: diiacui.vendorlogic.io
- Binding type: SniEnabled
- Certificate id: /subscriptions/3ed9fa77-6bf2-4ffc-bd67-f5a442d3e5e7/resourceGroups/RG_UI_VENDORLOGIC_PROD_V130/providers/Microsoft.App/managedEnvironments/acae-vendorlogic-ui-prod-v130/managedCertificates/mc-acae-vendorlog-diiacui-vendorlo-1321
- Managed certificate name: mc-acae-vendorlog-diiacui-vendorlo-1321
- Managed certificate provisioning: Succeeded

## External Validation
- https://diiacui.vendorlogic.io -> HTTP 200
- Response content-type: text/html
- Response length: 649

## Runtime State
- Container apps running: 3
- Dedicated stack remains isolated in RG_UI_VENDORLOGIC_PROD_V130 with shared Key Vault/Entra only.
