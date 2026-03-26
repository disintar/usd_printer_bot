#!/usr/bin/env bash
set -euo pipefail

IMAGE_NAME="${1:-ai-hedge-fund-frontend}"

REGISTRY_FIRST="${REGISTRY_FIRST:-first.registry.wtf.dton.io}"
REGISTRY_SECOND="${REGISTRY_SECOND:-second.registry.wtf.dton.io}"
TAG="${TAG:-latest}"
VITE_API_URL="${VITE_API_URL:-/api}"

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
BUILD_CONTEXT="$(mktemp -d)"

cleanup() {
  rm -rf "${BUILD_CONTEXT}"
}

trap cleanup EXIT

mkdir -p "${BUILD_CONTEXT}/docker" "${BUILD_CONTEXT}/external/ai-hedge-fund/app"
cp "${SCRIPT_DIR}/docker/ai-hedge-fund-frontend.Dockerfile" "${BUILD_CONTEXT}/docker/"
cp "${SCRIPT_DIR}/docker/ai-hedge-fund-frontend.nginx.conf" "${BUILD_CONTEXT}/docker/"
cp -R "${SCRIPT_DIR}/external/ai-hedge-fund/app/frontend" "${BUILD_CONTEXT}/external/ai-hedge-fund/app/"

echo "Building image for ${IMAGE_NAME}:${TAG} (VITE_API_URL=${VITE_API_URL})"

docker build \
  -f "${BUILD_CONTEXT}/docker/ai-hedge-fund-frontend.Dockerfile" \
  --build-arg "VITE_API_URL=${VITE_API_URL}" \
  -t "${REGISTRY_FIRST}/${IMAGE_NAME}:${TAG}" \
  -t "${REGISTRY_SECOND}/${IMAGE_NAME}:${TAG}" \
  "${BUILD_CONTEXT}"

docker push "${REGISTRY_FIRST}/${IMAGE_NAME}:${TAG}"
docker push "${REGISTRY_SECOND}/${IMAGE_NAME}:${TAG}"

echo "Pushed:"
echo " - ${REGISTRY_FIRST}/${IMAGE_NAME}:${TAG}"
echo " - ${REGISTRY_SECOND}/${IMAGE_NAME}:${TAG}"
