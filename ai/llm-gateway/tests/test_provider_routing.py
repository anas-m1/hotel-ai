"""Provider routing tests with fake keys and mocked completions; no billable calls."""

import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from fastapi import HTTPException

from src.router import chat


def configured(**overrides):
    values = {
        "openrouter_api_key": "test-only-key",
        "self_hosted_api_base": "",
        "self_hosted_api_key": "",
        "ollama_api_base": "http://ollama:11434",
    }
    values.update(overrides)
    return SimpleNamespace(**values)


class ProviderRoutingTests(unittest.TestCase):
    def test_openrouter_uses_server_key_and_endpoint(self):
        with patch.object(chat, "settings", configured()):
            options = chat.provider_options("openrouter/vendor/model")
        self.assertEqual(
            options, {"api_base": "https://openrouter.ai/api/v1", "api_key": "test-only-key"}
        )

    def test_openrouter_without_key_fails_before_provider_call(self):
        with patch.object(chat, "settings", configured(openrouter_api_key="")):
            with self.assertRaises(HTTPException) as caught:
                chat.provider_options("openrouter/vendor/model")
        self.assertEqual(caught.exception.status_code, 503)

    def test_self_hosted_endpoint_and_optional_auth(self):
        with patch.object(
            chat, "settings", configured(self_hosted_api_base="http://inference:8000/v1")
        ):
            options = chat.provider_options("hosted_vllm/test")
        self.assertEqual(options, {"api_base": "http://inference:8000/v1"})

    def test_self_hosted_missing_endpoint_fails(self):
        with patch.object(chat, "settings", configured()):
            with self.assertRaises(HTTPException):
                chat.provider_options("hosted_vllm/test")

    def test_request_cannot_supply_provider_url_or_key(self):
        request = chat.ChatRequest(
            model="hosted_vllm/test", messages=[], api_base="http://untrusted", api_key="untrusted"
        )
        self.assertNotIn("api_base", request.model_dump())
        self.assertNotIn("api_key", request.model_dump())

    def test_completion_forwards_tools_and_server_options(self):
        async def scenario():
            tools = [{"type": "function", "function": {"name": "get_hotel", "parameters": {}}}]
            response = SimpleNamespace(model_dump=lambda: {"choices": []})
            completion = AsyncMock(return_value=response)
            with (
                patch.object(chat, "settings", configured()),
                patch.object(chat.litellm, "acompletion", completion),
                patch.object(chat, "record_usage"),
            ):
                await chat.chat_completions(
                    chat.ChatRequest(
                        model="openrouter/vendor/model",
                        messages=[chat.Message(role="user", content="test")],
                        tools=tools,
                        tool_choice="auto",
                    )
                )
            self.assertEqual(completion.call_args.kwargs["tools"], tools)
            self.assertEqual(completion.call_args.kwargs["api_key"], "test-only-key")

        asyncio.run(scenario())

    def test_authentication_error_does_not_echo_provider_message(self):
        class ProviderAuthError(Exception):
            pass

        async def scenario():
            with (
                patch.object(chat, "settings", configured()),
                patch.object(chat.litellm, "AuthenticationError", ProviderAuthError),
                patch.object(
                    chat.litellm,
                    "acompletion",
                    AsyncMock(side_effect=ProviderAuthError("private detail")),
                ),
            ):
                with self.assertRaises(HTTPException) as caught:
                    await chat.chat_completions(
                        chat.ChatRequest(model="openrouter/vendor/model", messages=[])
                    )
            self.assertEqual(caught.exception.status_code, 401)
            self.assertEqual(caught.exception.detail, "Provider authentication failed")

        asyncio.run(scenario())


if __name__ == "__main__":
    unittest.main()
