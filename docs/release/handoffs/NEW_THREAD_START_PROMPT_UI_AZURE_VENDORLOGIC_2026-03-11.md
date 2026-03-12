> Handoff snapshot notice: This handoff file captures point-in-time context from 2026-03-11 and may not reflect current repository documentation updates.
# Copy/Paste Prompt For New UI Azure Deployment Thread

Use this prompt in the new thread:

```text
Proceed with deploying the already-built DIIaC UI version from F:\code\diiac\diiac_v1.3.0_ui into Azure production in the Vendorlogic tenant, alongside the existing headless build, with zero impact to current headless services.

Read first:
1) docs/release/handoffs/UI_AZURE_DEPLOYMENT_THREAD_HANDOFF_VENDORLOGIC_2026-03-11.md
2) docs/release/handoffs/vendorlogic_ui_azure_context_2026-03-11.json
3) infra/main.bicep
4) infra/main.bicepparam
5) scripts/deploy-azure.sh

Mandatory constraints:
1) No destructive changes to running headless production resources.
2) Use what-if/safe checks before any apply.
3) Keep secrets in Key Vault only (no secret values in repo).
4) Use gated checkpoints and wait for my approval at each stage.
5) Capture evidence outputs for each checkpoint.

Known facts:
- UI build is already operational locally and validated (compile/tests/build pass).
- Entra + Key Vault + Copilot integration already exists in this UI codebase.
- Tenant is 1384b1c5-2bae-45a1-a4b4-e94e3315eb41.
- Existing headless baseline is in subscription 3ed9fa77-6bf2-4ffc-bd67-f5a442d3e5e7, RG_ROOT.

Start with checkpoint 1:
- Confirm workspace and Azure context.
- Confirm final deployment topology that avoids impact to headless.
- Resolve authoritative admin group ID to use.
- Present the full checkpoint plan and ask for approval before implementation.
```


