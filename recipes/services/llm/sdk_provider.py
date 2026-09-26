"""Shared SDK transport; endpoint and credentials are selected by subclasses."""

import openai
from pydantic import ValidationError

from .base import LLMError, LLMProvider
from .config import LLMConfig
from .prompts import build_messages
from .schemas import Confirmation, RecipeRefineResponse


class SDKProvider(LLMProvider):
    def __init__(self, config: LLMConfig, *, api_key: str, base_url: str) -> None:
        self.config = config
        self.api_key = api_key
        self.base_url = base_url

    def _generate(self, client: openai.OpenAI, messages: list[dict[str, str]]) -> str:
        endpoint = self.config.endpoint
        kwargs = {"model": endpoint.model}
        if endpoint.send_temperature and self.config.generation.temperature is not None:
            kwargs["temperature"] = self.config.generation.temperature
        fmt = None
        if endpoint.structured_output == "json_schema":
            fmt = {
                "type": "json_schema",
                "name": "recipe_refine_response",
                "strict": True,
                "schema": RecipeRefineResponse.model_json_schema(),
            }
        elif endpoint.structured_output == "json_object":
            fmt = {"type": "json_object"}
        if endpoint.api_style == "responses":
            if fmt:
                kwargs["text"] = {"format": fmt}
            response = client.responses.create(input=messages, store=False, **kwargs)
            if response.status != "completed":
                return ""
            return response.output_text or ""
        if fmt:
            kwargs["response_format"] = (
                {
                    "type": "json_schema",
                    "json_schema": {k: v for k, v in fmt.items() if k != "type"},
                }
                if fmt["type"] == "json_schema"
                else fmt
            )
        response = client.chat.completions.create(messages=messages, **kwargs)
        if not response.choices or response.choices[0].finish_reason != "stop":
            return ""
        return response.choices[0].message.content or ""

    def refine_recipe(
        self,
        original_text: str,
        request_text: str,
        confirmation: Confirmation | None = None,
    ) -> RecipeRefineResponse:
        messages = build_messages(original_text, request_text, confirmation)
        try:
            with openai.OpenAI(
                api_key=self.api_key,
                base_url=self.base_url,
                timeout=self.config.generation.timeout_seconds,
                max_retries=0,
            ) as client:
                for attempt in range(self.config.retry.invalid_response_max_retries + 1):
                    raw = self._generate(client, messages)
                    try:
                        return RecipeRefineResponse.model_validate_json(raw)
                    except ValidationError:
                        if attempt < self.config.retry.invalid_response_max_retries:
                            messages.append(
                                {
                                    "role": "user",
                                    "content": (
                                        "前の出力は空またはschemaに不適合でした。"
                                        "全項目を含む正しいJSONを再生成してください。"
                                    ),
                                }
                            )
        except openai.APITimeoutError as exc:
            raise LLMError(
                "LLMの応答がタイムアウトしました。時間をおいてもう一度お試しください。"
            ) from exc
        except openai.APIConnectionError as exc:
            raise LLMError(
                "LLMへ接続できません。接続先とサーバーの起動状態を確認してください。"
            ) from exc
        except openai.AuthenticationError as exc:
            raise LLMError("LLMの認証に失敗しました。.env のAPIキーを確認してください。") from exc
        except openai.RateLimitError as exc:
            raise LLMError(
                "LLMの利用上限に達しました。利用枠を確認し、時間をおいてお試しください。"
            ) from exc
        except openai.APIError as exc:
            raise LLMError(
                "LLM APIでエラーが発生しました。"
                "モデル名・対応パラメーター・接続設定を確認してください。"
            ) from exc
        raise LLMError("レシピの生成結果を正しく解析できませんでした。もう一度お試しください。")
