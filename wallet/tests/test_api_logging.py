from __future__ import annotations

from unittest.mock import patch

from django.http import HttpResponse
from django.test import RequestFactory, SimpleTestCase

from wallet.middleware import ApiRequestLoggingMiddleware


class ApiRequestLoggingMiddlewareTests(SimpleTestCase):
    def setUp(self) -> None:
        self.factory = RequestFactory()

    @patch("wallet.middleware.logger")
    def test_logs_successful_api_request(self, mock_logger) -> None:
        middleware = ApiRequestLoggingMiddleware(lambda request: HttpResponse(status=200))
        request = self.factory.get("/health", REMOTE_ADDR="127.0.0.1")

        response = middleware(request)

        self.assertEqual(response.status_code, 200)
        mock_logger.info.assert_called_once()
        log_call = mock_logger.info.call_args[0]
        self.assertEqual(
            log_call[0],
            "api_request request_id={} method={} path={} query={} status={} client_ip={} duration_ms={} response_bytes={}",
        )
        self.assertEqual(log_call[1:7], ("-", "GET", "/health", "", 200, "127.0.0.1"))

    @patch("wallet.middleware.logger")
    def test_logs_client_errors_as_warning(self, mock_logger) -> None:
        middleware = ApiRequestLoggingMiddleware(lambda request: HttpResponse(status=401))
        request = self.factory.get("/auth/session/not_valid", {"source": "test"}, REMOTE_ADDR="10.0.0.5")

        response = middleware(request)

        self.assertEqual(response.status_code, 401)
        mock_logger.warning.assert_called_once()
        log_call = mock_logger.warning.call_args[0]
        self.assertEqual(
            log_call[1:7],
            ("-", "GET", "/auth/session/not_valid", "source=test", 401, "10.0.0.5"),
        )

    @patch("wallet.middleware.logger")
    def test_logs_uncaught_api_exceptions(self, mock_logger) -> None:
        def raise_error(request):
            raise RuntimeError("boom")

        middleware = ApiRequestLoggingMiddleware(raise_error)
        request = self.factory.post("/test/buy", REMOTE_ADDR="192.168.0.7")

        with self.assertRaises(RuntimeError):
            middleware(request)

        mock_logger.exception.assert_called_once()
        log_call = mock_logger.exception.call_args[0]
        self.assertEqual(
            log_call[:6],
            (
                "api_request_failed request_id={} method={} path={} query={} client_ip={} duration_ms={}",
                "-",
                "POST",
                "/test/buy",
                "",
                "192.168.0.7",
            ),
        )

    @patch("wallet.middleware.logger")
    def test_skips_non_api_requests(self, mock_logger) -> None:
        middleware = ApiRequestLoggingMiddleware(lambda request: HttpResponse(status=200))
        request = self.factory.get("/healthz/")

        response = middleware(request)

        self.assertEqual(response.status_code, 200)
        mock_logger.info.assert_not_called()
        mock_logger.warning.assert_not_called()
        mock_logger.error.assert_not_called()
        mock_logger.exception.assert_not_called()
