"""Simplified LLM advice service for MiniMax with proper timeout handling."""
from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass

import httpx
from django.conf import settings
from loguru import logger


class LlmAdviceError(ValueError):
    """Raised when the LLM endpoint is unavailable or returns invalid output."""


@dataclass(frozen=True)
class LlmMessage:
    """Single chat message for the LLM API."""

    role: str
    content: str


class LlmAdviceService:
    """Async client used for recommendation and reasoning tasks with MiniMax."""

    # Default timeout for LLM requests (120 seconds)
    DEFAULT_TIMEOUT_SECONDS = 120.0

    @classmethod
    async def complete_json(
        cls,
        system_prompt: str,
        user_prompt: str,
        timeout_seconds: float | None = None,
    ) -> dict[str, object]:
        """
        Run a chat completion and parse a JSON object from the response.

        Args:
            system_prompt: System prompt for the LLM
            user_prompt: User prompt for the LLM
            timeout_seconds: Request timeout in seconds (default: 120)

        Returns:
            Parsed JSON response from the LLM
        """
        api_key = str(getattr(settings, "OPENAI_API_KEY", "")).strip()
        base_url = str(getattr(settings, "OPENAI_BASE_URL", "")).strip()

        if not api_key:
            raise LlmAdviceError("OPENAI_API_KEY is not configured")
        if not base_url:
            raise LlmAdviceError("OPENAI_BASE_URL is not configured")

        messages = [
            LlmMessage(role="system", content=system_prompt),
            LlmMessage(role="user", content=user_prompt),
        ]

        # Use streaming=False for simpler, more reliable responses
        payload = {
            "model": getattr(settings, "OPENAI_MODEL", "MiniMax-M2.7-highspeed"),
            "messages": [{"role": item.role, "content": item.content} for item in messages],
            "temperature": float(getattr(settings, "OPENAI_TEMPERATURE", 0.0)),
            "max_tokens": int(getattr(settings, "OPENAI_MAX_TOKENS", 1024)),
            "stream": False,
        }

        if getattr(settings, "OPENAI_FORCE_JSON_OBJECT", True):
            payload["response_format"] = {"type": "json_object"}

        effective_timeout = (
            float(timeout_seconds)
            if timeout_seconds is not None
            else float(getattr(settings, "OPENAI_TIMEOUT_SECONDS", cls.DEFAULT_TIMEOUT_SECONDS))
        )

        started_at = time.perf_counter()
        logger.info(
            "llm.complete_json begin model={} base_url={} timeout_seconds={} user_prompt_chars={}",
            payload["model"],
            base_url,
            effective_timeout,
            len(user_prompt),
        )

        response_json = await cls._post_once(
            base_url=base_url,
            api_key=api_key,
            payload=payload,
            timeout_seconds=effective_timeout,
        )

        result = cls._decode_response_json(response_json)
        logger.info(
            "llm.complete_json success model={} total_ms={} keys={}",
            payload["model"],
            round((time.perf_counter() - started_at) * 1000),
            ",".join(result.keys()),
        )
        return result

    @classmethod
    async def complete_tool_input(
        cls,
        *,
        system_prompt: str,
        user_prompt: str,
        tool_name: str,
        tool_description: str,
        input_schema: dict[str, object],
        timeout_seconds: float | None = None,
    ) -> dict[str, object]:
        """
        Generate tool input using the LLM with function calling.

        Args:
            system_prompt: System prompt for the LLM
            user_prompt: User prompt for the LLM
            tool_name: Name of the tool to generate input for
            tool_description: Description of the tool
            input_schema: JSON schema for the tool input
            timeout_seconds: Request timeout in seconds

        Returns:
            Tool input as a dictionary
        """
        api_key = str(getattr(settings, "OPENAI_API_KEY", "")).strip()
        base_url = str(getattr(settings, "OPENAI_BASE_URL", "")).strip()

        if not api_key:
            raise LlmAdviceError("OPENAI_API_KEY is not configured")
        if not base_url:
            raise LlmAdviceError("OPENAI_BASE_URL is not configured")

        messages = [
            LlmMessage(role="system", content=system_prompt),
            LlmMessage(role="user", content=user_prompt),
        ]

        effective_timeout = (
            float(timeout_seconds)
            if timeout_seconds is not None
            else float(getattr(settings, "OPENAI_TIMEOUT_SECONDS", cls.DEFAULT_TIMEOUT_SECONDS))
        )

        started_at = time.perf_counter()
        logger.info(
            "llm.complete_tool_input begin tool_name={} timeout_seconds={}",
            tool_name,
            effective_timeout,
        )

        # Use non-streaming for reliability
        payload = {
            "model": getattr(settings, "OPENAI_MODEL", "MiniMax-M2.7-highspeed"),
            "messages": [{"role": item.role, "content": item.content} for item in messages],
            "temperature": float(getattr(settings, "OPENAI_TEMPERATURE", 0.0)),
            "max_tokens": int(getattr(settings, "OPENAI_MAX_TOKENS", 1024)),
            "stream": False,
            "tools": [
                {
                    "type": "function",
                    "function": {
                        "name": tool_name,
                        "description": tool_description,
                        "parameters": input_schema,
                    },
                }
            ],
            "tool_choice": {"type": "function", "function": {"name": tool_name}},
        }

        response_json = await cls._post_once(
            base_url=base_url,
            api_key=api_key,
            payload=payload,
            timeout_seconds=effective_timeout,
        )

        tool_input = cls._extract_tool_input(response_json)
        logger.info(
            "llm.complete_tool_input success tool_name={} total_ms={}",
            tool_name,
            round((time.perf_counter() - started_at) * 1000),
        )
        return tool_input

    @staticmethod
    async def _post_once(
        base_url: str,
        api_key: str,
        payload: dict[str, object],
        timeout_seconds: float,
    ) -> dict[str, object]:
        """
        Make a single HTTP POST to the LLM API.

        Args:
            base_url: Base URL of the LLM API
            api_key: API key for authentication
            payload: Request payload
            timeout_seconds: Request timeout

        Returns:
            Parsed JSON response
        """
        url = f"{base_url.rstrip('/')}/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        started_at = time.perf_counter()
        logger.info(
            "llm._post_once.request url={} model={} timeout={}s",
            url,
            payload.get("model", "unknown"),
            timeout_seconds,
        )
        try:
            async with httpx.AsyncClient(timeout=timeout_seconds) as client:
                response = await client.post(url, headers=headers, json=payload)
                elapsed_ms = round((time.perf_counter() - started_at) * 1000)
                logger.info(
                    "llm._post_once.response url={} status={} elapsed_ms={}",
                    url,
                    response.status_code,
                    elapsed_ms,
                )
                response.raise_for_status()
                result = response.json()
                # Log response size for debugging
                result_str = json.dumps(result)
                logger.info(
                    "llm._post_once.success url={} response_chars={} total_ms={}",
                    url,
                    len(result_str),
                    elapsed_ms,
                )
                return result
        except httpx.TimeoutException:
            logger.error("llm._post_once timeout url={} timeout_seconds={}", url, timeout_seconds)
            raise LlmAdviceError(f"LLM timeout exceeded after {timeout_seconds}s") from None
        except httpx.HTTPError as exc:
            logger.error("llm._post_once HTTP error url={} error={}", url, exc)
            raise LlmAdviceError(str(exc)) from exc
        except json.JSONDecodeError as exc:
            logger.error("llm._post_once JSON decode error url={} error={}", url, exc)
            raise LlmAdviceError("LLM response did not contain valid JSON") from exc

    @staticmethod
    def _decode_response_json(response_json: dict[str, object]) -> dict[str, object]:
        """
        Extract and parse JSON from the LLM response.

        Args:
            response_json: Raw response from LLM API

        Returns:
            Parsed JSON content

        Raises:
            LlmAdviceError: If the response is invalid or missing content
        """
        try:
            choices = response_json.get("choices", [])
            if not choices:
                raise LlmAdviceError("LLM response has no choices")

            first_choice = choices[0]
            message = first_choice.get("message", {})
            content = message.get("content")
            if isinstance(content, list):
                content = "".join(
                    str(item.get("text", ""))
                    for item in content
                    if isinstance(item, dict)
                )

            if not content:
                # Check if there's tool calls
                tool_calls = message.get("tool_calls", [])
                if tool_calls:
                    first_tool_call = tool_calls[0]
                    function = first_tool_call.get("function", {})
                    arguments = function.get("arguments", "{}")
                    return json.loads(arguments)

                raise LlmAdviceError("LLM response message has no content")

            return LlmAdviceService._parse_json_from_text(str(content))

        except (IndexError, KeyError) as exc:
            raise LlmAdviceError(f"Invalid LLM response structure: {exc}") from exc

    @staticmethod
    def _extract_tool_input(response_json: dict[str, object]) -> dict[str, object]:
        """
        Extract tool input from a function call response.

        Args:
            response_json: Raw response from LLM API

        Returns:
            Tool input as a dictionary

        Raises:
            LlmAdviceError: If no tool call found in response
        """
        try:
            choices = response_json.get("choices", [])
            if not choices:
                raise LlmAdviceError("LLM response has no choices")

            first_choice = choices[0]
            message = first_choice.get("message", {})
            tool_calls = message.get("tool_calls", [])

            if not tool_calls:
                content = message.get("content")
                if isinstance(content, str) and content.strip():
                    return LlmAdviceService._parse_json_from_text(content)
                raise LlmAdviceError("LLM response has no tool calls")

            first_tool_call = tool_calls[0]
            function = first_tool_call.get("function", {})
            arguments = function.get("arguments", "{}")

            return json.loads(arguments)

        except (IndexError, KeyError) as exc:
            raise LlmAdviceError(f"Invalid tool call response structure: {exc}") from exc

    @staticmethod
    def _parse_json_from_text(content: str) -> dict[str, object]:
        stripped = content.strip()
        if not stripped:
            raise LlmAdviceError("LLM response content is empty")

        try:
            parsed = json.loads(stripped)
            if isinstance(parsed, dict):
                return parsed
            raise LlmAdviceError("LLM response JSON must be an object")
        except json.JSONDecodeError:
            pass

        without_think = re.sub(r"<think>.*?</think>", "", stripped, flags=re.DOTALL | re.IGNORECASE).strip()
        if without_think != stripped:
            try:
                parsed = json.loads(without_think)
                if isinstance(parsed, dict):
                    return parsed
            except json.JSONDecodeError:
                pass

        fenced_match = re.search(
            r"```(?:json)?\s*(\{.*?\})\s*```",
            without_think,
            flags=re.DOTALL | re.IGNORECASE,
        )
        if fenced_match:
            candidate = fenced_match.group(1).strip()
            try:
                parsed = json.loads(candidate)
                if isinstance(parsed, dict):
                    return parsed
            except json.JSONDecodeError:
                pass

        balanced_candidate = LlmAdviceService._extract_balanced_json_object(without_think)
        if balanced_candidate:
            try:
                parsed = json.loads(balanced_candidate)
                if isinstance(parsed, dict):
                    return parsed
            except json.JSONDecodeError:
                pass

        raise LlmAdviceError("LLM response did not contain a valid JSON object")

    @staticmethod
    def _extract_balanced_json_object(text: str) -> str:
        start = text.find("{")
        if start < 0:
            return ""

        depth = 0
        in_string = False
        escape_next = False
        for index in range(start, len(text)):
            char = text[index]
            if in_string:
                if escape_next:
                    escape_next = False
                elif char == "\\":
                    escape_next = True
                elif char == "\"":
                    in_string = False
                continue

            if char == "\"":
                in_string = True
            elif char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    return text[start : index + 1]

        return ""
