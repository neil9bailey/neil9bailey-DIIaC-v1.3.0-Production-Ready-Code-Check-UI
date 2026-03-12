# CP14 Plan Summary (Runtime Sigfix)

- Resource creates: 0
- Resource modifies: 15
- Resource deletes: 0
- RG_ROOT resource operations detected: 0
- Runtime image change detected: yes
- Safe to apply: yes

## Runtime image diff line
- ~ image: "acrdiiacv130vlui.azurecr.io/diiac/governance-runtime:1.3.0-persistfix1" => "[format('{0}/{1}/governance-runtime:{2}', reference('/subscriptions/3ed9fa77-6bf2-4ffc-bd67-f5a442d3e5e7/resourceGroups/RG_UI_VENDORLOGIC_PROD_V130/providers/Microsoft.ContainerRegistry/registries/acrdiiacv130vlui', '2023-11-01-preview').loginServer, 'diiac', '1.3.0-sigfix1')]"