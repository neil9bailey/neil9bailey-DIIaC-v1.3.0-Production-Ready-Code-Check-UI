# CP4 - Pre-Apply Safety Checks (What-If) Summary

Date: 2026-03-11
Status: Blocked by platform quota (no apply executed)

## Commands executed

1. Subscription-scope `validate` and `what-if` for dedicated deployment templates.
2. Region feasibility checks (`uksouth`, `ukwest`).
3. Container Apps usage and managed environment inventory checks.
4. Post-check to verify no dedicated RG/resources were created.

## Results

### 1) `uksouth` validation
- Status: FAILED
- Error code: `MaxNumberOfRegionalEnvironmentsInSubExceeded`
- Meaning: subscription already has max `ManagedEnvironmentCount` in UK South.

### 2) `ukwest` validation and what-if
- Status: FAILED (both infra-only and with-apps)
- Error code: `MaxNumberOfGlobalEnvironmentsInSubExceeded`
- Meaning: this subscription currently cannot host more than one Container Apps environment globally.

### 3) Quota evidence
- `uksouth` usage shows `ManagedEnvironmentCount` = `1/1`.
- `ukwest` regional usage is `0/1`, but global subscription policy still blocks second ACA environment.

### 4) No-impact post-check
- `RG_UI_VENDORLOGIC_PROD_V130` exists: `false`.
- Resources in `RG_UI_VENDORLOGIC_PROD_V130`: `[]`.
- Existing `RG_ROOT` inventory snapshot captured after checks.

## Conclusion

The approved dedicated-ACA-environment topology cannot be applied in subscription `3ed9fa77-6bf2-4ffc-bd67-f5a442d3e5e7` due enforced Container Apps environment limit.

No resources were applied or modified during CP4.
