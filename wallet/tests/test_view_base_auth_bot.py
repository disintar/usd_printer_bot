import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import httpx
from asgiref.sync import async_to_sync
from django.db import DatabaseError
from django.test import RequestFactory, TestCase

from wallet.models import WalletAccount
from wallet.views import base


class BaseViewUtilitiesTests(TestCase):
    def setUp(self) -> None:
        self.factory = RequestFactory()

    def test_parse_json_raises_on_invalid_payload(self) -> None:
        request = self.factory.post("/x", data="{", content_type="application/json")
        with self.assertRaisesMessage(ValueError, "Invalid JSON"):
            base.parse_json(request)

    def test_get_identity_returns_none_when_token_cannot_be_resolved(self) -> None:
        request = self.factory.get("/x", HTTP_AUTHORIZATION="Bearer unresolved")
        with patch("wallet.views.base.run_sync", new=AsyncMock(return_value=None)):
            identity = async_to_sync(base.get_identity)(request)
        self.assertIsNone(identity)

    def test_get_account_for_identity_returns_none_when_related_account_missing(self) -> None:
        fake_identity = SimpleNamespace()
        with patch(
            "wallet.views.base.run_sync",
            new=AsyncMock(side_effect=WalletAccount.DoesNotExist),
        ):
            account = async_to_sync(base.get_account_for_identity)(fake_identity)
        self.assertIsNone(account)

    def test_parse_decimal_and_positive_validation_errors(self) -> None:
        with self.assertRaisesMessage(ValueError, "amount is required"):
            base.parse_decimal(None, "amount")

        with self.assertRaisesMessage(ValueError, "Invalid amount"):
            base.parse_decimal("not-a-number", "amount")

        with self.assertRaisesMessage(ValueError, "amount must be positive"):
            base.validate_positive_decimal("0", "amount")


class AuthAndBotErrorBranchTests(TestCase):
    def test_telegram_auth_returns_400_for_invalid_json(self) -> None:
        response = self.client.post("/auth/telegram", data="{", content_type="application/json")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["message"], "Invalid JSON")

    def test_telegram_auth_returns_500_on_database_error(self) -> None:
        with patch(
            "wallet.views.auth.AuthenticationService.authenticate_telegram",
            side_effect=DatabaseError("auth db failure"),
        ):
            response = self.client.post(
                "/auth/telegram",
                data=json.dumps({"telegram_user_id": 101, "username": "u"}),
                content_type="application/json",
            )
        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.json()["status"], "error")

    def test_pending_auth_accepts_invalid_json_and_still_creates_token(self) -> None:
        response = self.client.post("/auth/pending", data="{", content_type="application/json")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["data"]["token"])

    def test_complete_auth_returns_400_for_invalid_json(self) -> None:
        response = self.client.post("/auth/complete", data="{", content_type="application/json")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["message"], "Invalid JSON")

    def test_complete_auth_returns_400_when_required_fields_missing(self) -> None:
        response = self.client.post(
            "/auth/complete",
            data=json.dumps({}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["message"], "token and telegram_user_id required")

    def test_complete_auth_returns_500_when_session_creation_fails(self) -> None:
        with patch(
            "wallet.views.auth.AuthSession.create_session",
            side_effect=DatabaseError("session db failure"),
        ):
            response = self.client.post(
                "/auth/complete",
                data=json.dumps({"token": "tok", "telegram_user_id": 77}),
                content_type="application/json",
            )
        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.json()["status"], "error")

    def test_telegram_widget_returns_400_for_invalid_json(self) -> None:
        response = self.client.post("/auth/telegram/widget", data="{", content_type="application/json")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["message"], "Invalid JSON")

    def test_telegram_widget_returns_401_for_invalid_login(self) -> None:
        with patch(
            "wallet.views.auth.TelegramAuthService.verify_login_widget_data",
            return_value=None,
        ):
            response = self.client.post(
                "/auth/telegram/widget",
                data=json.dumps({"id": "1", "auth_date": "1", "hash": "h", "first_name": "A"}),
                content_type="application/json",
            )
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["message"], "Invalid Telegram login")

    def test_bot_info_returns_500_on_http_error(self) -> None:
        with patch(
            "wallet.views.bot.httpx.AsyncClient.post",
            new=AsyncMock(side_effect=httpx.TimeoutException("timeout")),
        ):
            response = self.client.get("/bot/info")
        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.json()["status"], "error")

    def test_bot_info_returns_500_when_telegram_response_not_ok(self) -> None:
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {"ok": False}
        with patch(
            "wallet.views.bot.httpx.AsyncClient.post",
            new=AsyncMock(return_value=mock_response),
        ):
            response = self.client.get("/bot/info")
        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.json()["message"], "Failed to get bot info")
