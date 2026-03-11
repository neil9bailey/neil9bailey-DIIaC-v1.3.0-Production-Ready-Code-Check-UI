#!/usr/bin/env bash
# =============================================================================
# prepare-customer-release.sh
# DIIaC v1.2.0 — Transform a cloned v1.2.0 dev repo into a clean customer release
#
# Run this FROM WITHIN the customer release repo after cloning the dev repo content.
# It modifies files in-place and reports what was changed.
#
# Usage (from the root of DIIaC-V1.2.0c-Production-Customer-Release):
#   bash scripts/prepare-customer-release.sh
#
# See CUSTOMER_RELEASE_AUDIT.md for full explanation of every change made.
# =============================================================================
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SCRIPT_NAME="$(basename "$0")"
PASS=0
FAIL=0
WARN=0

green()  { printf '\033[0;32m✓ %s\033[0m\n' "$*"; }
red()    { printf '\033[0;31m✗ %s\033[0m\n' "$*"; }
yellow() { printf '\033[0;33m⚠ %s\033[0m\n' "$*"; }
header() { printf '\n\033[1;34m── %s ──\033[0m\n' "$*"; }

cd "$REPO_ROOT"

echo "=================================================================="
echo " DIIaC v1.2.0 — Customer Release Preparation Script"
echo " Running from: $REPO_ROOT"
echo "=================================================================="

# ── 1. Frontend/src/auth/authConfig.ts ───────────────────────────────────────
header "1. authConfig.ts — remove Vendorlogic fallback IDs"

AUTH_CONFIG="Frontend/src/auth/authConfig.ts"
if [ -f "$AUTH_CONFIG" ]; then
  # Remove hardcoded Vendorlogic UUID fallbacks from ENTRA_CLIENT_ID and ENTRA_TENANT_ID
  # Replace: || "b726558d-f1c6-48f7-8a3d-72d5db818d0f"  →  || ""
  # Replace: || "1384b1c5-2bae-45a1-a4b4-e94e3315eb41"  →  || ""
  if grep -q 'b726558d-f1c6-48f7-8a3d-72d5db818d0f\|1384b1c5-2bae-45a1-a4b4-e94e3315eb41' "$AUTH_CONFIG"; then
    sed -i \
      's/|| "b726558d-f1c6-48f7-8a3d-72d5db818d0f"/|| ""/g' \
      "$AUTH_CONFIG"
    sed -i \
      's/|| "1384b1c5-2bae-45a1-a4b4-e94e3315eb41"/|| ""/g' \
      "$AUTH_CONFIG"
    green "Vendorlogic Entra IDs removed from authConfig.ts defaults"
    PASS=$((PASS+1))
  else
    green "authConfig.ts already clean (no Vendorlogic IDs found)"
    PASS=$((PASS+1))
  fi
else
  red "MISSING: $AUTH_CONFIG"
  FAIL=$((FAIL+1))
fi

# ── 2. Frontend/src/auth/roleMapping.ts ──────────────────────────────────────
header "2. roleMapping.ts — clear Vendorlogic group OID defaults"

ROLE_MAP="Frontend/src/auth/roleMapping.ts"
if [ -f "$ROLE_MAP" ]; then
  if grep -q '81786818-de16-4115-b061-92fce74b00bd\|9c7dd0d4-5b44-4811-b167-e52df21092d8' "$ROLE_MAP"; then
    # Replace the DEFAULT_GROUP_MAP block content with empty object
    # The block is: const DEFAULT_GROUP_MAP: Record<string, GroupMapping> = { ... };
    python3 - <<'PYEOF'
import re, sys

path = "Frontend/src/auth/roleMapping.ts"
with open(path, "r") as f:
    content = f.read()

# Replace the DEFAULT_GROUP_MAP object literal with an empty one
pattern = r'(const DEFAULT_GROUP_MAP:\s*Record<string,\s*GroupMapping>\s*=\s*)\{[^}]*\}'
replacement = r'\1{}'
new_content = re.sub(pattern, replacement, content, flags=re.DOTALL)

if new_content == content:
    print("WARNING: DEFAULT_GROUP_MAP pattern not matched — manual check required")
    sys.exit(1)

with open(path, "w") as f:
    f.write(new_content)

print("DEFAULT_GROUP_MAP cleared")
PYEOF
    green "Vendorlogic group OIDs removed from roleMapping.ts defaults"
    PASS=$((PASS+1))
  else
    green "roleMapping.ts already clean (no Vendorlogic OIDs found)"
    PASS=$((PASS+1))
  fi
else
  red "MISSING: $ROLE_MAP"
  FAIL=$((FAIL+1))
fi

# ── 3. Frontend/.env — replace live Vendorlogic IDs with placeholders ─────────
header "3. Frontend/.env — replace live Entra IDs with REPLACE_WITH_* placeholders"

FRONTEND_ENV="Frontend/.env"
if [ -f "$FRONTEND_ENV" ]; then
  if grep -q 'b726558d-f1c6-48f7-8a3d-72d5db818d0f\|1384b1c5-2bae-45a1-a4b4-e94e3315eb41\|81786818\|9c7dd0d4' "$FRONTEND_ENV"; then
    cat > "$FRONTEND_ENV" <<'ENVEOF'
VITE_API_BASE=http://localhost:3001

# ── Entra ID OIDC — set these to YOUR customer values ───────────────────────
# Copy from customer-config/<your-customer-id>/config.env
# Fill using: bash scripts/pull-keyvault-secrets.sh (or set manually for pre-KV)
VITE_ENTRA_CLIENT_ID=REPLACE_WITH_UI_APP_CLIENT_ID
VITE_ENTRA_TENANT_ID=REPLACE_WITH_TENANT_ID
VITE_ENTRA_REDIRECT_URI=http://localhost:5173/auth/callback

# Group OID → DIIaC role mapping
# Copy from customer-config/<your-customer-id>/config.env (VITE_ENTRA_GROUP_MAP line)
VITE_ENTRA_GROUP_MAP={"REPLACE_WITH_ADMIN_GROUP_OID":{"role":"admin"},"REPLACE_WITH_STANDARD_GROUP_OID":{"role":"standard"}}
ENVEOF
    green "Frontend/.env updated with REPLACE_WITH_* placeholders"
    PASS=$((PASS+1))
  else
    green "Frontend/.env already uses placeholders or is blank"
    PASS=$((PASS+1))
  fi
else
  yellow "Frontend/.env not found — creating from template"
  cat > "$FRONTEND_ENV" <<'ENVEOF'
VITE_API_BASE=http://localhost:3001

VITE_ENTRA_CLIENT_ID=REPLACE_WITH_UI_APP_CLIENT_ID
VITE_ENTRA_TENANT_ID=REPLACE_WITH_TENANT_ID
VITE_ENTRA_REDIRECT_URI=http://localhost:5173/auth/callback
VITE_ENTRA_GROUP_MAP={"REPLACE_WITH_ADMIN_GROUP_OID":{"role":"admin"},"REPLACE_WITH_STANDARD_GROUP_OID":{"role":"standard"}}
ENVEOF
  green "Frontend/.env created with placeholders"
  WARN=$((WARN+1))
fi

# ── 4. .env.example — sanitise commented Vendorlogic IDs ─────────────────────
header "4. .env.example — sanitise commented Vendorlogic IDs"

ENV_EXAMPLE=".env.example"
if [ -f "$ENV_EXAMPLE" ]; then
  sed -i \
    -e 's/1384b1c5-2bae-45a1-a4b4-e94e3315eb41/REPLACE_WITH_TENANT_ID/g' \
    -e 's/b726558d-f1c6-48f7-8a3d-72d5db818d0f/REPLACE_WITH_API_APP_CLIENT_ID/g' \
    -e 's/4ef7c128-a3f2-4c7d-a51d-c893e5944c88/REPLACE_WITH_ADMIN_GROUP_OID/g' \
    -e 's/c1ffce74-ccd6-49f5-810f-1754e11da6c5/REPLACE_WITH_STANDARD_GROUP_OID/g' \
    "$ENV_EXAMPLE"
  green ".env.example sanitised"
  PASS=$((PASS+1))
else
  yellow ".env.example not found — skipping"
  WARN=$((WARN+1))
fi

# ── 5. customer-config/ — remove Vendorlogic instance, keep only _template ────
header "5. customer-config/ — remove vendorlogic instance folder"

if [ -d "customer-config/vendorlogic" ]; then
  rm -rf "customer-config/vendorlogic"
  green "customer-config/vendorlogic/ removed"
  PASS=$((PASS+1))
else
  green "customer-config/vendorlogic/ not present (already clean)"
  PASS=$((PASS+1))
fi

if [ -d "customer-config/_template" ]; then
  green "customer-config/_template/ present"
  PASS=$((PASS+1))
else
  red "MISSING: customer-config/_template/ — customer onboarding template not present"
  FAIL=$((FAIL+1))
fi

# ── 6. pull-keyvault-secrets.sh — parameterise customer config path ───────────
header "6. pull-keyvault-secrets.sh — parameterise CUSTOMER_ID"

KV_SCRIPT="scripts/pull-keyvault-secrets.sh"
if [ -f "$KV_SCRIPT" ]; then
  if grep -q 'customer-config/vendorlogic' "$KV_SCRIPT"; then
    sed -i \
      's|customer-config/vendorlogic/config.env|customer-config/${CUSTOMER_ID}/config.env|g' \
      "$KV_SCRIPT"

    # Insert CUSTOMER_ID resolution block before the CUSTOMER_CONFIG line
    python3 - <<'PYEOF'
import re

path = "scripts/pull-keyvault-secrets.sh"
with open(path, "r") as f:
    content = f.read()

customer_id_block = '''# Customer instance ID — must match the folder under customer-config/
CUSTOMER_ID="${DIIAC_CUSTOMER_ID:-}"
if [ -z "$CUSTOMER_ID" ]; then
  echo ""
  echo "ERROR: DIIAC_CUSTOMER_ID is not set."
  echo "Set it to the name of your config folder under customer-config/."
  echo "Example:"
  echo "  DIIAC_CUSTOMER_ID=acme-corp bash scripts/pull-keyvault-secrets.sh"
  echo ""
  exit 1
fi

'''

# Insert before the CUSTOMER_CONFIG= line
content = re.sub(
    r'(CUSTOMER_CONFIG=)',
    customer_id_block + r'\1',
    content,
    count=1
)

with open(path, "w") as f:
    f.write(content)
PYEOF
    green "pull-keyvault-secrets.sh parameterised with DIIAC_CUSTOMER_ID"
    PASS=$((PASS+1))
  else
    green "pull-keyvault-secrets.sh already parameterised"
    PASS=$((PASS+1))
  fi
else
  yellow "scripts/pull-keyvault-secrets.sh not found — skipping"
  WARN=$((WARN+1))
fi

# ── 7. pull-keyvault-secrets.ps1 — same treatment ────────────────────────────
KV_SCRIPT_PS="scripts/pull-keyvault-secrets.ps1"
if [ -f "$KV_SCRIPT_PS" ]; then
  if grep -q 'customer-config/vendorlogic\|customer-config\\vendorlogic' "$KV_SCRIPT_PS"; then
    sed -i \
      's|customer-config/vendorlogic|customer-config/$env:DIIAC_CUSTOMER_ID|g' \
      "$KV_SCRIPT_PS"
    sed -i \
      's|customer-config\\vendorlogic|customer-config\\$env:DIIAC_CUSTOMER_ID|g' \
      "$KV_SCRIPT_PS"
    green "pull-keyvault-secrets.ps1 parameterised"
    PASS=$((PASS+1))
  else
    green "pull-keyvault-secrets.ps1 already parameterised"
    PASS=$((PASS+1))
  fi
fi

# ── 8. openapi.yaml — update GitHub repo URL ─────────────────────────────────
header "8. openapi.yaml — update GitHub URL to customer release repo"

OPENAPI="openapi.yaml"
if [ -f "$OPENAPI" ]; then
  sed -i \
    's|neil9bailey/DIIaC-v1.2.0-Production-Ready-Code-Check|neil9bailey/DIIaC-V1.2.0c-Production-Customer-Release|g' \
    "$OPENAPI"
  green "openapi.yaml GitHub URL updated"
  PASS=$((PASS+1))
else
  yellow "openapi.yaml not found — skipping"
  WARN=$((WARN+1))
fi

# ── 9. Remove internal-only documents ────────────────────────────────────────
header "9. Remove internal Vendorlogic documents"

INTERNAL_DOCS=(
  "HANDOFF.md"
  "PRODUCT_ROADMAP_V1_3_0.md"
  "BASELINE_STATUS_AND_FUTURE_ENHANCEMENTS.md"
  "RELEASE_LOCK_V1_2_0.md"
  "CUSTOMER_FORK_MODEL.md"
  "DIIAC_V1_2_0_COMPREHENSIVE_BRIEFING.md"
  "DIIAC_V1_2_0_DEBUG_AND_TEST_REPORT.md"
  "DIIAC_ARCHITECTURE_ALIGNMENT_REPORT.md"
  "VENDORLOGIC_LOCAL_STAGING_GUIDE.md"
  "VENDORLOGIC_DEPLOYMENT_GUIDE.md"
  "COPILOT_ENTRA_PRODUCTION_CHECKLIST.md"
  "CUSTOMER_RELEASE_AUDIT.md"
)

for doc in "${INTERNAL_DOCS[@]}"; do
  if [ -f "$doc" ]; then
    rm "$doc"
    green "Removed: $doc"
    PASS=$((PASS+1))
  else
    green "Not present (already clean): $doc"
    PASS=$((PASS+1))
  fi
done

# ── 10. Remove this script from customer release ──────────────────────────────
header "10. Clean up this preparation script"

yellow "Note: scripts/prepare-customer-release.sh should be removed from the customer release repo."
yellow "Delete it manually or run: rm scripts/prepare-customer-release.sh"
WARN=$((WARN+1))

# ── 11. Verify KEY_VAULT_TRANSITION.md is present ────────────────────────────
header "11. Verify Key Vault transition guide is present"

if [ -f "KEY_VAULT_TRANSITION.md" ]; then
  green "KEY_VAULT_TRANSITION.md present"
  PASS=$((PASS+1))
else
  red "MISSING: KEY_VAULT_TRANSITION.md — add it from dev repo"
  FAIL=$((FAIL+1))
fi

# ── 12. Verify customer-config/_template/ has config.env ──────────────────────
header "12. Verify customer config template is complete"

if [ -f "customer-config/_template/config.env" ]; then
  # Confirm all REPLACE_WITH_* placeholders are still present (not filled in)
  if grep -q 'REPLACE_WITH_' "customer-config/_template/config.env"; then
    green "customer-config/_template/config.env is a valid template (has REPLACE_WITH_* placeholders)"
    PASS=$((PASS+1))
  else
    yellow "customer-config/_template/config.env may have been filled in — check for REPLACE_WITH_* values"
    WARN=$((WARN+1))
  fi
else
  red "MISSING: customer-config/_template/config.env"
  FAIL=$((FAIL+1))
fi

# ── Summary ───────────────────────────────────────────────────────────────────
echo ""
echo "=================================================================="
echo " Customer Release Preparation — Complete"
echo "=================================================================="
printf " %s Passed   %s Warnings   %s Failed\n" "$PASS" "$WARN" "$FAIL"
echo ""

if [ "$FAIL" -gt 0 ]; then
  echo " ✗ ATTENTION: $FAIL check(s) failed. Review output above before releasing."
  echo ""
  exit 1
elif [ "$WARN" -gt 0 ]; then
  echo " ⚠ Complete, but $WARN manual step(s) remain. See warnings above."
  echo ""
else
  echo " ✓ All checks passed. Review git diff, then commit and tag:"
  echo ""
  echo "   git add -A"
  echo "   git commit -m 'chore: prepare v1.2.0 customer release baseline'"
  echo "   git tag v1.2.0"
  echo "   git push origin main --tags"
  echo ""
fi
