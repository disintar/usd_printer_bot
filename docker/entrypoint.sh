#!/usr/bin/env bash
set -euo pipefail

MODE="${1:-web}"

python manage.py migrate --noinput

if [[ "${MODE}" == "bot" ]]; then
  exec python -m bot.telegram_bot
fi

if [[ "${MODE}" == "web" ]]; then
  PRICE_CRON_ENABLED="${PRICE_CRON_ENABLED:-true}"
  PRICE_CRON_INTERVAL_SECONDS="${PRICE_CRON_INTERVAL_SECONDS:-60}"
  TEST_TIME_WARP_ENABLED="${TEST_TIME_WARP_ENABLED:-true}"
  TEST_TIME_WARP_INTERVAL_SECONDS="${TEST_TIME_WARP_INTERVAL_SECONDS:-1}"

  CRON_PID=""
  TIME_WARP_PID=""
  WEB_PID=""

  if [[ "${PRICE_CRON_ENABLED}" == "true" ]]; then
    python manage.py run_price_cron --interval-seconds "${PRICE_CRON_INTERVAL_SECONDS}" &
    CRON_PID=$!
  fi

  if [[ "${TEST_TIME_WARP_ENABLED}" == "true" ]]; then
    python manage.py run_price_cron --interval-seconds "${TEST_TIME_WARP_INTERVAL_SECONDS}" --test-time-warp &
    TIME_WARP_PID=$!
  fi

  cleanup() {
    if [[ -n "${WEB_PID}" ]]; then
      kill "${WEB_PID}" >/dev/null 2>&1 || true
      wait "${WEB_PID}" >/dev/null 2>&1 || true
    fi
    if [[ -n "${CRON_PID}" ]]; then
      kill "${CRON_PID}" >/dev/null 2>&1 || true
      wait "${CRON_PID}" >/dev/null 2>&1 || true
    fi
    if [[ -n "${TIME_WARP_PID}" ]]; then
      kill "${TIME_WARP_PID}" >/dev/null 2>&1 || true
      wait "${TIME_WARP_PID}" >/dev/null 2>&1 || true
    fi
  }

  trap cleanup EXIT INT TERM

  # Use uvicorn for async Django with ASGI
  exec uvicorn config.asgi:application --host 0.0.0.0 --port 8000 --loop asyncio
fi

# Fallback to uvicorn
exec uvicorn config.asgi:application --host 0.0.0.0 --port 8000 --loop asyncio
