#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

ACR_NAME="acrdiiacv130vlui"
REPOSITORY_PREFIX="diiac"
RUNTIME_TAG="1.3.0-adminheaderfix"
BRIDGE_TAG="1.3.0-ingressfix"
FRONTEND_TAG="1.3.0-groupmapfix"
PUSH_LATEST="false"
VITE_API_BASE="https://br-vendorlogic-ui-prod-v130.blackpond-85ed120f.uksouth.azurecontainerapps.io"
VITE_ENTRA_CLIENT_ID="b726558d-f1c6-48f7-8a3d-72d5db818d0f"
VITE_ENTRA_TENANT_ID="1384b1c5-2bae-45a1-a4b4-e94e3315eb41"
VITE_ENTRA_REDIRECT_URI="https://diiacui.vendorlogic.io/auth/callback"
VITE_ENTRA_GROUP_MAP='{"81786818-de16-4115-b061-92fce74b00bd":{"role":"admin"},"9c7dd0d4-5b44-4811-b167-e52df21092d8":{"role":"standard"}}'

print_usage() {
  cat <<'USAGE'
Usage:
  bash scripts/build-push-dedicated-ui-images.sh [options]

Options:
  --acr-name <name>            Destination ACR name.
  --repo-prefix <prefix>       Repository prefix (default: diiac).
  --runtime-tag <tag>          Runtime image tag.
  --bridge-tag <tag>           Bridge image tag.
  --frontend-tag <tag>         Frontend image tag.
  --vite-api-base <url>        Frontend API base URL baked at build time.
  --vite-entra-client-id <id>  Frontend Entra client ID baked at build time.
  --vite-entra-tenant-id <id>  Frontend Entra tenant ID baked at build time.
  --vite-entra-redirect-uri <url>
                               Frontend Entra redirect URI baked at build time.
  --vite-entra-group-map <json>
                               Frontend role/group map JSON baked at build time.
  --push-latest                Also push :latest tags for all images.
  --help                       Show this message.
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --acr-name) ACR_NAME="$2"; shift 2 ;;
    --repo-prefix) REPOSITORY_PREFIX="$2"; shift 2 ;;
    --runtime-tag) RUNTIME_TAG="$2"; shift 2 ;;
    --bridge-tag) BRIDGE_TAG="$2"; shift 2 ;;
    --frontend-tag) FRONTEND_TAG="$2"; shift 2 ;;
    --vite-api-base) VITE_API_BASE="$2"; shift 2 ;;
    --vite-entra-client-id) VITE_ENTRA_CLIENT_ID="$2"; shift 2 ;;
    --vite-entra-tenant-id) VITE_ENTRA_TENANT_ID="$2"; shift 2 ;;
    --vite-entra-redirect-uri) VITE_ENTRA_REDIRECT_URI="$2"; shift 2 ;;
    --vite-entra-group-map) VITE_ENTRA_GROUP_MAP="$2"; shift 2 ;;
    --push-latest) PUSH_LATEST="true"; shift ;;
    --help|-h) print_usage; exit 0 ;;
    *) echo "Unknown argument: $1" >&2; print_usage; exit 1 ;;
  esac
done

command -v az >/dev/null 2>&1 || { echo "Azure CLI is required." >&2; exit 1; }
command -v docker >/dev/null 2>&1 || { echo "Docker is required." >&2; exit 1; }

az acr show --name "${ACR_NAME}" --query "name" -o tsv >/dev/null
az acr login --name "${ACR_NAME}"

ACR_LOGIN_SERVER="$(az acr show --name "${ACR_NAME}" --query "loginServer" -o tsv | tr -d '\r')"

RUNTIME_IMAGE="${ACR_LOGIN_SERVER}/${REPOSITORY_PREFIX}/governance-runtime:${RUNTIME_TAG}"
BRIDGE_IMAGE="${ACR_LOGIN_SERVER}/${REPOSITORY_PREFIX}/backend-ui-bridge:${BRIDGE_TAG}"
FRONTEND_IMAGE="${ACR_LOGIN_SERVER}/${REPOSITORY_PREFIX}/frontend:${FRONTEND_TAG}"

echo "Building runtime image: ${RUNTIME_IMAGE}"
docker build \
  -f "${REPO_ROOT}/Dockerfile.runtime" \
  -t "${RUNTIME_IMAGE}" \
  "${REPO_ROOT}"
docker push "${RUNTIME_IMAGE}"

echo "Building bridge image: ${BRIDGE_IMAGE}"
docker build \
  -f "${REPO_ROOT}/backend-ui-bridge/Dockerfile" \
  -t "${BRIDGE_IMAGE}" \
  "${REPO_ROOT}/backend-ui-bridge"
docker push "${BRIDGE_IMAGE}"

echo "Building frontend image: ${FRONTEND_IMAGE}"
docker build \
  -f "${REPO_ROOT}/Frontend/Dockerfile" \
  -t "${FRONTEND_IMAGE}" \
  --build-arg "VITE_API_BASE=${VITE_API_BASE}" \
  --build-arg "VITE_ENTRA_CLIENT_ID=${VITE_ENTRA_CLIENT_ID}" \
  --build-arg "VITE_ENTRA_TENANT_ID=${VITE_ENTRA_TENANT_ID}" \
  --build-arg "VITE_ENTRA_REDIRECT_URI=${VITE_ENTRA_REDIRECT_URI}" \
  --build-arg "VITE_ENTRA_GROUP_MAP=${VITE_ENTRA_GROUP_MAP}" \
  "${REPO_ROOT}/Frontend"
docker push "${FRONTEND_IMAGE}"

if [[ "${PUSH_LATEST}" == "true" ]]; then
  RUNTIME_LATEST="${ACR_LOGIN_SERVER}/${REPOSITORY_PREFIX}/governance-runtime:latest"
  BRIDGE_LATEST="${ACR_LOGIN_SERVER}/${REPOSITORY_PREFIX}/backend-ui-bridge:latest"
  FRONTEND_LATEST="${ACR_LOGIN_SERVER}/${REPOSITORY_PREFIX}/frontend:latest"

  docker tag "${RUNTIME_IMAGE}" "${RUNTIME_LATEST}"
  docker tag "${BRIDGE_IMAGE}" "${BRIDGE_LATEST}"
  docker tag "${FRONTEND_IMAGE}" "${FRONTEND_LATEST}"

  docker push "${RUNTIME_LATEST}"
  docker push "${BRIDGE_LATEST}"
  docker push "${FRONTEND_LATEST}"
fi

echo "Image push complete."
echo "Runtime:  ${RUNTIME_IMAGE}"
echo "Bridge:   ${BRIDGE_IMAGE}"
echo "Frontend: ${FRONTEND_IMAGE}"
