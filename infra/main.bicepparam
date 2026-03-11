// DIIaC v1.2.0 — Vendorlogic Azure Landing Zone Parameters
//
// These are PUBLIC identifiers sourced from customer-config/vendorlogic/config.env.
// NO secrets are stored here — secrets live in Azure Key Vault.

using './main.bicep'

param customerName = 'vendorlogic'
param location = 'uksouth'
param diiacVersion = '1.2.0'

// ── Entra ID (from customer-config/vendorlogic/config.env) ──────────────────
param entraTenantId = '1384b1c5-2bae-45a1-a4b4-e94e3315eb41'
param entraApiAppId = 'b726558d-f1c6-48f7-8a3d-72d5db818d0f'
param entraUiAppId = 'b726558d-f1c6-48f7-8a3d-72d5db818d0f'
param entraAdminGroupId = '81786818-de16-4115-b061-92fce74b00bd'
param entraStandardGroupId = '9c7dd0d4-5b44-4811-b167-e52df21092d8'

// ── LLM ──────────────────────────────────────────────────────────────────────
param openaiModel = 'gpt-4o-mini'
param copilotModel = 'gpt-4o'

// ── Networking ───────────────────────────────────────────────────────────────
param dnsLabel = 'diiac-vendorlogic'

// ── Container sizing (adjust for load) ───────────────────────────────────────
param runtimeCpu = '0.5'
param runtimeMemory = '1.0'
param bridgeCpu = '0.5'
param bridgeMemory = '1.0'
param frontendCpu = '0.25'
param frontendMemory = '0.5'
