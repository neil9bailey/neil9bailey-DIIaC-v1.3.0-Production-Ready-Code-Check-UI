#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

to_az_path() {
  local p="$1"
  if command -v cygpath >/dev/null 2>&1; then
    cygpath -w "$p"
    return
  fi
  if [[ "$p" =~ ^/mnt/([a-zA-Z])/(.*)$ ]]; then
    local drive="${BASH_REMATCH[1]}"
    local tail="${BASH_REMATCH[2]}"
    drive="$(echo "$drive" | tr '[:lower:]' '[:upper:]')"
    tail="${tail//\//\\}"
    echo "${drive}:\\${tail}"
    return
  fi
  echo "$p"
}

SUBSCRIPTION_ID="3ed9fa77-6bf2-4ffc-bd67-f5a442d3e5e7"
LOCATION="uksouth"
TEMPLATE_FILE="${REPO_ROOT}/infra/aca-dedicated-ui/main.sub.bicep"
PARAM_FILE="${REPO_ROOT}/infra/aca-dedicated-ui/vendorlogic-prod.sub.bicepparam"
EVIDENCE_DIR="${REPO_ROOT}/docs/release/evidence/2026-03-11-ui-dedicated-azure"
DEPLOYMENT_NAME="diiac-ui-dedicated-$(date -u +%Y%m%d-%H%M%S)"
ACTION="plan"
DEPLOY_APPS="false"

print_usage() {
  cat <<'USAGE'
Usage:
  bash scripts/deploy-azure-dedicated-ui.sh --plan [options]
  bash scripts/deploy-azure-dedicated-ui.sh --apply [options]

Options:
  --plan                     Run validate + what-if only (default).
  --apply                    Run subscription deployment create.
  --infra-only               Override deployApps=false (create shared infra only).
  --with-apps                Override deployApps=true (create apps too).
  --subscription <id>        Azure subscription ID.
  --location <region>        Azure deployment location (subscription deployment metadata location).
  --template-file <path>     Subscription template path.
  --param-file <path>        Bicep parameter file path.
  --deployment-name <name>   Deployment name.
  --evidence-dir <path>      Evidence output directory.
  --help                     Show this message.
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --plan) ACTION="plan"; shift ;;
    --apply) ACTION="apply"; shift ;;
    --infra-only) DEPLOY_APPS="false"; shift ;;
    --with-apps) DEPLOY_APPS="true"; shift ;;
    --subscription) SUBSCRIPTION_ID="$2"; shift 2 ;;
    --location) LOCATION="$2"; shift 2 ;;
    --template-file) TEMPLATE_FILE="$2"; shift 2 ;;
    --param-file) PARAM_FILE="$2"; shift 2 ;;
    --deployment-name) DEPLOYMENT_NAME="$2"; shift 2 ;;
    --evidence-dir) EVIDENCE_DIR="$2"; shift 2 ;;
    --help|-h) print_usage; exit 0 ;;
    *) echo "Unknown argument: $1" >&2; print_usage; exit 1 ;;
  esac
done

command -v az >/dev/null 2>&1 || { echo "Azure CLI is required." >&2; exit 1; }

if [[ ! -f "${TEMPLATE_FILE}" ]]; then
  echo "Template file not found: ${TEMPLATE_FILE}" >&2
  exit 1
fi

if [[ ! -f "${PARAM_FILE}" ]]; then
  echo "Parameter file not found: ${PARAM_FILE}" >&2
  exit 1
fi

mkdir -p "${EVIDENCE_DIR}"

TEMPLATE_FILE_AZ="$(to_az_path "${TEMPLATE_FILE}")"
PARAM_FILE_AZ="$(to_az_path "${PARAM_FILE}")"

az account set --subscription "${SUBSCRIPTION_ID}"
ACCOUNT_JSON="$(az account show -o json)"
echo "${ACCOUNT_JSON}" > "${EVIDENCE_DIR}/cp4_account_context_${DEPLOYMENT_NAME}.json"

echo "Action: ${ACTION}"
echo "Subscription: ${SUBSCRIPTION_ID}"
echo "Location: ${LOCATION}"
echo "Template: ${TEMPLATE_FILE}"
echo "Parameters: ${PARAM_FILE}"
echo "Deployment name: ${DEPLOYMENT_NAME}"
echo "deployApps override: ${DEPLOY_APPS}"

COMMON_ARGS=(
  --name "${DEPLOYMENT_NAME}"
  --location "${LOCATION}"
  --template-file "${TEMPLATE_FILE_AZ}"
  --parameters "${PARAM_FILE_AZ}"
  --parameters "deployApps=${DEPLOY_APPS}"
)

if [[ "${ACTION}" == "plan" ]]; then
  az deployment sub validate "${COMMON_ARGS[@]}" -o json \
    > "${EVIDENCE_DIR}/cp4_validate_${DEPLOYMENT_NAME}.json"

  az deployment sub what-if "${COMMON_ARGS[@]}" --result-format FullResourcePayloads -o json \
    > "${EVIDENCE_DIR}/cp4_whatif_${DEPLOYMENT_NAME}.json"

  echo "Plan complete. Evidence files:"
  echo "  ${EVIDENCE_DIR}/cp4_validate_${DEPLOYMENT_NAME}.json"
  echo "  ${EVIDENCE_DIR}/cp4_whatif_${DEPLOYMENT_NAME}.json"
  exit 0
fi

if [[ "${ACTION}" == "apply" ]]; then
  az deployment sub create "${COMMON_ARGS[@]}" -o json \
    > "${EVIDENCE_DIR}/cp5_apply_${DEPLOYMENT_NAME}.json"

  az deployment sub show --name "${DEPLOYMENT_NAME}" --query "properties.outputs" -o json \
    > "${EVIDENCE_DIR}/cp5_outputs_${DEPLOYMENT_NAME}.json"

  echo "Apply complete. Evidence files:"
  echo "  ${EVIDENCE_DIR}/cp5_apply_${DEPLOYMENT_NAME}.json"
  echo "  ${EVIDENCE_DIR}/cp5_outputs_${DEPLOYMENT_NAME}.json"
  exit 0
fi

echo "Invalid action: ${ACTION}" >&2
exit 1
