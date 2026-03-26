#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "${ROOT_DIR}"

PYTHON_BIN="${PYTHON_BIN:-python}"
if [[ -x "${ROOT_DIR}/.venv/bin/python" ]]; then
  PYTHON_BIN="${ROOT_DIR}/.venv/bin/python"
fi
NPM_BIN="${NPM_BIN:-npm}"

# Load .env file if it exists
if [[ -f "${ROOT_DIR}/.env" ]]; then
  set -a
  # shellcheck source=/dev/null
  source "${ROOT_DIR}/.env"
  set +a
fi

PORT="${PORT:-8000}"
HOST="${HOST:-127.0.0.1}"
BACKEND_URL="http://${HOST}:${PORT}"

export PYTHONUNBUFFERED=1
export FMP_ENABLED="${FMP_ENABLED:-false}"
export PRICE_CRON_ENABLED="${PRICE_CRON_ENABLED:-true}"
export PRICE_CRON_INTERVAL_SECONDS="${PRICE_CRON_INTERVAL_SECONDS:-1}"
export TEST_TIME_WARP_ENABLED="true"
export TEST_TIME_WARP_INTERVAL_SECONDS="${TEST_TIME_WARP_INTERVAL_SECONDS:-1}"
export BACKEND_URL="${BACKEND_URL}"
export BOT_ENABLED="${BOT_ENABLED:-false}"
export TELEGRAM_BOT_TOKEN="${TELEGRAM_BOT_TOKEN:-}"
export OPENAI_TIMEOUT_SECONDS="120"
export FRONTEND_ENABLED="${FRONTEND_ENABLED:-true}"
export FRONTEND_HOST="${FRONTEND_HOST:-127.0.0.1}"
export FRONTEND_PORT="${FRONTEND_PORT:-5173}"
export LOAD_HISTORY_ON_START="${LOAD_HISTORY_ON_START:-true}"
export VITE_DEV_PROXY_TARGET="${VITE_DEV_PROXY_TARGET:-${BACKEND_URL}}"
export VITE_API_URL="${VITE_API_URL:-/api}"

echo "[start_local] migrate"
"${PYTHON_BIN}" manage.py migrate --noinput

BACKEND_PID=""
PRICE_CRON_PID=""
TIME_WARP_PID=""
BOT_PID=""
FRONTEND_PID=""

cleanup() {
  set +e
  for pid in "${FRONTEND_PID}" "${BOT_PID}" "${TIME_WARP_PID}" "${PRICE_CRON_PID}" "${BACKEND_PID}"; do
    if [[ -n "${pid}" ]]; then
      kill "${pid}" >/dev/null 2>&1 || true
      wait "${pid}" >/dev/null 2>&1 || true
    fi
  done
}

trap cleanup EXIT INT TERM

if [[ "${BOT_ENABLED}" == "true" ]]; then
  # Keep a single polling consumer for Telegram getUpdates.
  pkill -f "bot.telegram_bot" >/dev/null 2>&1 || true
fi

if [[ "${LOAD_HISTORY_ON_START}" == "true" ]]; then
  echo "[start_local] load historical prices (best effort)"
  "${PYTHON_BIN}" manage.py load_historical_prices || echo "[start_local] warning: load_historical_prices failed, continuing"
fi

echo "[start_local] backend ${BACKEND_URL}"
"${PYTHON_BIN}" manage.py runserver "${HOST}:${PORT}" --noreload &
BACKEND_PID=$!

if [[ "${PRICE_CRON_ENABLED}" == "true" ]]; then
  echo "[start_local] price cron each ${PRICE_CRON_INTERVAL_SECONDS}s"
  "${PYTHON_BIN}" manage.py run_price_cron --interval-seconds "${PRICE_CRON_INTERVAL_SECONDS}" &
  PRICE_CRON_PID=$!
fi

if [[ "${TEST_TIME_WARP_ENABLED}" == "true" ]]; then
  echo "[start_local] test time-warp cron each ${TEST_TIME_WARP_INTERVAL_SECONDS}s (1s=1h)"
  "${PYTHON_BIN}" manage.py run_price_cron --interval-seconds "${TEST_TIME_WARP_INTERVAL_SECONDS}" --test-time-warp &
  TIME_WARP_PID=$!
fi

if [[ "${FRONTEND_ENABLED}" == "true" ]]; then
  echo "[start_local] frontend http://${FRONTEND_HOST}:${FRONTEND_PORT} (proxy -> ${VITE_DEV_PROXY_TARGET})"
  (
    cd "${ROOT_DIR}/app/frontend"
    "${NPM_BIN}" run dev -- --host "${FRONTEND_HOST}" --port "${FRONTEND_PORT}"
  ) &
  FRONTEND_PID=$!
fi

echo "[start_local] running. all logs stream to this terminal"
echo "[start_local] press Ctrl+C to stop all services"
if [[ "${FRONTEND_ENABLED}" == "true" ]]; then
  echo "[start_local] open miniapp at http://${FRONTEND_HOST}:${FRONTEND_PORT}"
fi

wait "${BACKEND_PID}"
