from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
from django.test import SimpleTestCase, override_settings

from wallet.services.llm_advice import LlmAdviceError, LlmAdviceService


class LlmAdviceServiceTests(SimpleTestCase):
    @override_settings(
        OPENAI_API_KEY="test-key",
        OPENAI_BASE_URL="https://api.minimax.io/v1",
        OPENAI_MODEL="MiniMax-M2.7-highspeed",
        OPENAI_TIMEOUT_SECONDS=5.0,
    )
    @patch("wallet.services.llm_advice.httpx.AsyncClient")
    def test_complete_tool_input_uses_single_http_request(self, client_class: MagicMock) -> None:
        """Test that complete_tool_input makes a single HTTP request with OpenAI-compatible format."""
        response = MagicMock()
        # OpenAI-compatible response with tool_calls
        response.json.return_value = {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "tool_calls": [
                            {
                                "id": "call_123",
                                "type": "function",
                                "function": {
                                    "name": "emit_portfolio_actions",
                                    "arguments": '{"actions": []}',
                                },
                            }
                        ],
                    }
                }
            ]
        }
        response.raise_for_status.return_value = None
        response.status_code = 200

        client = AsyncMock()
        client.post = AsyncMock(return_value=response)
        client_class.return_value.__aenter__.return_value = client

        async def run_test():
            return await LlmAdviceService.complete_tool_input(
                system_prompt="system",
                user_prompt="user",
                tool_name="emit_portfolio_actions",
                tool_description="desc",
                input_schema={"type": "object", "properties": {}, "additionalProperties": False},
            )

        result = asyncio.run(run_test())

        self.assertEqual(result["actions"], [])
        self.assertEqual(client.post.call_count, 1)

    @override_settings(
        OPENAI_API_KEY="test-key",
        OPENAI_BASE_URL="https://api.minimax.io/v1",
        OPENAI_MODEL="MiniMax-M2.7-highspeed",
        OPENAI_TIMEOUT_SECONDS=5.0,
    )
    @patch("wallet.services.llm_advice.httpx.AsyncClient")
    def test_complete_tool_input_does_not_retry_on_timeout(self, client_class: MagicMock) -> None:
        """Test that timeout is not retried (no streaming fallback)."""
        client = AsyncMock()
        client.post = AsyncMock(side_effect=httpx.TimeoutException("timeout"))
        client_class.return_value.__aenter__.return_value = client

        async def run_test():
            return await LlmAdviceService.complete_tool_input(
                system_prompt="system",
                user_prompt="user",
                tool_name="emit_portfolio_actions",
                tool_description="desc",
                input_schema={"type": "object", "properties": {}, "additionalProperties": False},
            )

        with self.assertRaises(LlmAdviceError):
            asyncio.run(run_test())

        self.assertEqual(client.post.call_count, 1)

    @override_settings(
        OPENAI_API_KEY="test-key",
        OPENAI_BASE_URL="https://api.minimax.io/v1",
        OPENAI_MODEL="MiniMax-M2.7-highspeed",
        OPENAI_TIMEOUT_SECONDS=5.0,
    )
    @patch("wallet.services.llm_advice.httpx.AsyncClient")
    def test_complete_json_returns_parsed_json(self, client_class: MagicMock) -> None:
        """Test that complete_json returns parsed JSON from OpenAI-compatible response."""
        response = MagicMock()
        response.json.return_value = {
            "choices": [
                {
                    "message": {
                        "content": '{"result": "success", "value": 42}',
                    }
                }
            ]
        }
        response.raise_for_status.return_value = None
        response.status_code = 200

        client = AsyncMock()
        client.post = AsyncMock(return_value=response)
        client_class.return_value.__aenter__.return_value = client

        async def run_test():
            return await LlmAdviceService.complete_json(
                system_prompt="system",
                user_prompt="user",
            )

        result = asyncio.run(run_test())

        self.assertEqual(result["result"], "success")
        self.assertEqual(result["value"], 42)
        self.assertEqual(client.post.call_count, 1)

    @override_settings(
        OPENAI_API_KEY="test-key",
        OPENAI_BASE_URL="https://api.minimax.io/v1",
        OPENAI_MODEL="MiniMax-M2.7-highspeed",
        OPENAI_TIMEOUT_SECONDS=5.0,
    )
    @patch("wallet.services.llm_advice.httpx.AsyncClient")
    def test_complete_json_extracts_json_from_think_and_code_fence(
        self, client_class: MagicMock
    ) -> None:
        response = MagicMock()
        response.json.return_value = {
            "choices": [
                {
                    "message": {
                        "content": (
                            "<think>internal reasoning</think>\n\n"
                            "```json\n"
                            '{"recommendation":"hold","summary":"ok","advisor_notes":[]}'
                            "\n```"
                        ),
                    }
                }
            ]
        }
        response.raise_for_status.return_value = None
        response.status_code = 200

        client = AsyncMock()
        client.post = AsyncMock(return_value=response)
        client_class.return_value.__aenter__.return_value = client

        async def run_test():
            return await LlmAdviceService.complete_json(
                system_prompt="system",
                user_prompt="user",
            )

        result = asyncio.run(run_test())

        self.assertEqual(result["recommendation"], "hold")
        self.assertEqual(result["summary"], "ok")
        self.assertEqual(client.post.call_count, 1)

    @override_settings(
        OPENAI_API_KEY="test-key",
        OPENAI_BASE_URL="https://api.minimax.io/v1",
        OPENAI_MODEL="MiniMax-M2.7-highspeed",
        OPENAI_TIMEOUT_SECONDS=5.0,
    )
    @patch("wallet.services.llm_advice.httpx.AsyncClient")
    def test_complete_tool_input_falls_back_to_json_content_when_tool_calls_missing(
        self, client_class: MagicMock
    ) -> None:
        response = MagicMock()
        response.json.return_value = {
            "choices": [
                {
                    "message": {
                        "content": '{"actions":[{"asset_id":"AAPLx","action":"hold","reason":"ok"}]}',
                    }
                }
            ]
        }
        response.raise_for_status.return_value = None
        response.status_code = 200

        client = AsyncMock()
        client.post = AsyncMock(return_value=response)
        client_class.return_value.__aenter__.return_value = client

        async def run_test():
            return await LlmAdviceService.complete_tool_input(
                system_prompt="system",
                user_prompt="user",
                tool_name="emit_portfolio_actions",
                tool_description="desc",
                input_schema={"type": "object", "properties": {}, "additionalProperties": False},
            )

        result = asyncio.run(run_test())

        self.assertEqual(result["actions"][0]["action"], "hold")
        self.assertEqual(client.post.call_count, 1)
