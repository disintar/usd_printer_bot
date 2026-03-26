#!/usr/bin/env bash
set -euo pipefail

IMAGE_NAME="${1:-dbablo-miniapp}"

REGISTRY_FIRST="${REGISTRY_FIRST:-first.registry.wtf.dton.io}"
REGISTRY_SECOND="${REGISTRY_SECOND:-second.registry.wtf.dton.io}"
TAG="${TAG:-latest}"
VITE_API_URL="${VITE_API_URL:-/api}"

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

echo "Building image for ${IMAGE_NAME}:${TAG} (VITE_API_URL=${VITE_API_URL})"

docker build \
  -f "${SCRIPT_DIR}/docker/dbablo-miniapp.Dockerfile" \
  --build-arg "VITE_API_URL=${VITE_API_URL}" \
  -t "${REGISTRY_FIRST}/${IMAGE_NAME}:${TAG}" \
  -t "${REGISTRY_SECOND}/${IMAGE_NAME}:${TAG}" \
  "${SCRIPT_DIR}"

docker push "${REGISTRY_FIRST}/${IMAGE_NAME}:${TAG}"
docker push "${REGISTRY_SECOND}/${IMAGE_NAME}:${TAG}"

echo "Pushed:"
echo " - ${REGISTRY_FIRST}/${IMAGE_NAME}:${TAG}"
echo " - ${REGISTRY_SECOND}/${IMAGE_NAME}:${TAG}"
