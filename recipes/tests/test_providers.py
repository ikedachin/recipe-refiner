import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import httpx
import openai

from recipes.services.llm.base import LLMError
from recipes.services.llm.factory import create_llm_provider

from .helpers import OK, OfflineSimpleTestCase, config


def responses_output(text):
    return SimpleNamespace(output_text=text, status="completed")


def chat_output(text):
    return SimpleNamespace(
        choices=[
            SimpleNamespace(
                finish_reason="stop",
                message=SimpleNamespace(content=text),
            )
        ]
    )


@patch.dict("os.environ", {"OPENAI_API_KEY": "secret-test-key", "LOCAL_LLM_API_KEY": "local-test"})
class ProviderTests(OfflineSimpleTestCase):
    def setUp(self):
        super().setUp()
        patcher = patch("recipes.services.llm.sdk_provider.openai.OpenAI")
        self.client_class = patcher.start()
        self.addCleanup(patcher.stop)
        self.client = MagicMock()
        self.client_class.return_value.__enter__.return_value = self.client
        self.client.responses.create.return_value = responses_output(json.dumps(OK))
        self.client.chat.completions.create.return_value = chat_output(json.dumps(OK))

    def test_responses_success_and_configuration(self):
        result = create_llm_provider(config()).refine_recipe("元レシピ", "豚肉へ")
        self.assertEqual(result.status, "ok")
        self.client_class.assert_called_once_with(
            api_key="secret-test-key",
            base_url="https://api.openai.com/v1",
            timeout=7.0,
            max_retries=0,
        )
        params = self.client.responses.create.call_args.kwargs
        self.assertEqual(params["model"], "test-openai")
        self.assertEqual(params["text"]["format"]["type"], "json_schema")
        self.assertFalse(params["store"])
        self.assertNotIn("temperature", params)
        self.assertIn("元レシピ", params["input"][1]["content"])
        self.assertNotIn("secret-test-key", json.dumps(params))

    def test_local_chat_success(self):
        result = create_llm_provider(config("local")).refine_recipe("元", "変更")
        self.assertEqual(result.status, "ok")
        params = self.client.chat.completions.create.call_args.kwargs
        self.assertEqual(params["temperature"], 0.2)
        self.assertEqual(params["response_format"]["json_schema"]["name"], "recipe_refine_response")
        self.assertEqual(self.client_class.call_args.kwargs["base_url"], "http://localhost:8001/v1")

    def test_both_api_styles_for_both_providers(self):
        for provider in ["openai", "local"]:
            for style in ["responses", "chat_completions"]:
                with self.subTest(provider=provider, style=style):
                    result = create_llm_provider(config(provider, api_style=style)).refine_recipe(
                        "元", "変更"
                    )
                    self.assertEqual(result.status, "ok")

    def test_format_options(self):
        for style in ["responses", "chat_completions"]:
            for fmt in ["json_object", "prompt"]:
                with self.subTest(style=style, fmt=fmt):
                    create_llm_provider(
                        config("local", api_style=style, structured_output=fmt)
                    ).refine_recipe("元", "変更")
                    method = (
                        self.client.responses.create
                        if style == "responses"
                        else self.client.chat.completions.create
                    )
                    key = "text" if style == "responses" else "response_format"
                    if fmt == "prompt":
                        self.assertNotIn(key, method.call_args.kwargs)
                    else:
                        self.assertIn("json_object", json.dumps(method.call_args.kwargs[key]))

    def test_invalid_response_retries_then_succeeds(self):
        self.client.responses.create.side_effect = [
            responses_output("invalid"),
            responses_output(json.dumps(OK)),
        ]
        self.assertEqual(create_llm_provider(config()).refine_recipe("元", "変更").status, "ok")
        self.assertEqual(self.client.responses.create.call_count, 2)

    def test_invalid_response_retry_limit(self):
        for bad in ["", "not-json", '{"status":"ok"}']:
            with self.subTest(bad=bad):
                self.client.responses.create.reset_mock()
                self.client.responses.create.return_value = responses_output(bad)
                with self.assertRaisesMessage(LLMError, "解析"):
                    create_llm_provider(config()).refine_recipe("元", "変更")
                self.assertEqual(self.client.responses.create.call_count, 2)

    def test_retry_zero(self):
        settings = config().model_copy(
            update={"retry": config().retry.model_copy(update={"invalid_response_max_retries": 0})}
        )
        self.client.responses.create.return_value = responses_output("")
        with self.assertRaises(LLMError):
            create_llm_provider(settings).refine_recipe("元", "変更")
        self.assertEqual(self.client.responses.create.call_count, 1)

    def test_incomplete_output_is_rejected(self):
        self.client.responses.create.return_value = SimpleNamespace(
            status="incomplete", output_text=json.dumps(OK)
        )
        with self.assertRaises(LLMError):
            create_llm_provider(config()).refine_recipe("元", "変更")

    def test_chat_empty_and_truncated(self):
        for response in [
            SimpleNamespace(choices=[]),
            SimpleNamespace(choices=[SimpleNamespace(finish_reason="length")]),
        ]:
            self.client.chat.completions.create.return_value = response
            with self.assertRaises(LLMError):
                create_llm_provider(config("local")).refine_recipe("元", "変更")

    def test_transport_errors_are_sanitized_and_not_retried(self):
        request = httpx.Request("POST", "http://localhost/v1")
        response = httpx.Response(500, request=request)
        cases = [
            (openai.APITimeoutError(request=request), "タイムアウト"),
            (openai.APIConnectionError(request=request), "接続できません"),
            (openai.AuthenticationError("secret-test-key", response=response, body=None), "認証"),
            (openai.RateLimitError("secret-test-key", response=response, body=None), "利用上限"),
            (openai.APIStatusError("secret-test-key", response=response, body=None), "APIでエラー"),
        ]
        for error, message in cases:
            with self.subTest(error=type(error).__name__):
                self.client.responses.create.reset_mock()
                self.client.responses.create.side_effect = error
                with self.assertRaisesMessage(LLMError, message) as ctx:
                    create_llm_provider(config()).refine_recipe("元", "変更")
                self.assertNotIn("secret-test-key", str(ctx.exception))
                self.assertEqual(self.client.responses.create.call_count, 1)
