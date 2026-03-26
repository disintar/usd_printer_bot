"""Request logging middleware for wallet API endpoints."""
from __future__ import annotations

import time
from typing import Callable

from django.http import HttpRequest, HttpResponse
from loguru import logger


class ApiRequestLoggingMiddleware:
    """Log every API request with status, latency, and uncaught errors."""

    API_PREFIXES = (
        "/auth",
        "/advisors",
        "/bot",
        "/test",
        "/ws",
    )
    HEALTH_PATH = "/health"

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        if not self._should_log(request):
            return self.get_response(request)

        started_at = time.perf_counter()
        query_string = request.META.get("QUERY_STRING", "")
        request_id = self._request_id(request)
        logger.debug(
            "api_request.begin request_id={} method={} path={} query={} client_ip={} user_agent={} headers={}",
            request_id,
            request.method,
            request.path,
            query_string,
            self._client_ip(request),
            request.META.get("HTTP_USER_AGENT", ""),
            self._request_headers_snapshot(request),
        )

        try:
            response = self.get_response(request)
        except Exception:
            duration_ms = self._duration_ms(started_at)
            logger.exception(
                "api_request_failed request_id={} method={} path={} query={} client_ip={} duration_ms={}",
                request_id,
                request.method,
                request.path,
                query_string,
                self._client_ip(request),
                duration_ms,
            )
            raise

        duration_ms = self._duration_ms(started_at)
        self._log_response(request, response, duration_ms, request_id)
        return response

    def _should_log(self, request: HttpRequest) -> bool:
        if request.path == self.HEALTH_PATH:
            return True
        return request.path.startswith(self.API_PREFIXES)

    def _log_response(
        self,
        request: HttpRequest,
        response: HttpResponse,
        duration_ms: int,
        request_id: str,
    ) -> None:
        log_message = (
            "api_request request_id={} method={} path={} query={} status={} client_ip={} duration_ms={}"
        )
        log_args = (
            request_id,
            request.method,
            request.path,
            request.META.get("QUERY_STRING", ""),
            response.status_code,
            self._client_ip(request),
            duration_ms,
        )
        response_size = self._response_size(response)
        if response_size >= 0:
            log_message += " response_bytes={}"
            log_args = (*log_args, response_size)

        logger.debug(
            "api_request.end request_id={} method={} path={} status={} content_type={} response_preview={}",
            request_id,
            request.method,
            request.path,
            response.status_code,
            response.get("Content-Type", ""),
            self._response_preview(response),
        )

        if response.status_code >= 500:
            logger.error(log_message, *log_args)
        elif response.status_code >= 400:
            logger.warning(log_message, *log_args)
        else:
            logger.info(log_message, *log_args)

    def _client_ip(self, request: HttpRequest) -> str:
        forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR", "")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        return request.META.get("REMOTE_ADDR", "-")

    def _duration_ms(self, started_at: float) -> int:
        return round((time.perf_counter() - started_at) * 1000)

    def _response_size(self, response: HttpResponse) -> int:
        try:
            if hasattr(response, "content") and response.content is not None:
                return len(response.content)
        except Exception:
            return -1
        return -1

    def _response_preview(self, response: HttpResponse, limit: int = 180) -> str:
        try:
            if not hasattr(response, "content") or response.content is None:
                return ""
            content = response.content
            if isinstance(content, bytes):
                preview = content[:limit].decode("utf-8", errors="replace")
            else:
                preview = str(content)[:limit]
            return preview.replace("\n", "\\n")
        except Exception:
            return ""

    def _request_headers_snapshot(self, request: HttpRequest) -> dict[str, str]:
        allowed_meta = {
            "HTTP_USER_AGENT": "user-agent",
            "HTTP_ACCEPT": "accept",
            "HTTP_CONTENT_TYPE": "content-type",
            "HTTP_X_REQUEST_ID": "x-request-id",
            "CONTENT_TYPE": "content-type",
            "CONTENT_LENGTH": "content-length",
        }
        snapshot: dict[str, str] = {}
        for meta_key, name in allowed_meta.items():
            value = request.META.get(meta_key)
            if value:
                snapshot[name] = str(value)
        authorization = request.META.get("HTTP_AUTHORIZATION")
        if authorization:
            snapshot["authorization"] = self._masked_token(str(authorization))
        return snapshot

    def _request_id(self, request: HttpRequest) -> str:
        return (
            str(request.META.get("HTTP_X_REQUEST_ID", "")).strip()
            or str(request.META.get("HTTP_X_CORRELATION_ID", "")).strip()
            or "-"
        )

    def _masked_token(self, value: str) -> str:
        if len(value) <= 12:
            return "***"
        return f"{value[:8]}...{value[-4:]}"
