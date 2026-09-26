"""The single YAML reader. Never include validation input values in public errors."""

from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

import yaml
from django.conf import settings
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator


class LLMConfigError(Exception):
    pass


class ConfigModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)


class EndpointConfig(ConfigModel):
    model: str = Field(min_length=1, max_length=200)
    api_style: Literal["responses", "chat_completions"]
    send_temperature: bool = False
    structured_output: Literal["json_schema", "json_object", "prompt"] = "json_schema"


class LocalConfig(EndpointConfig):
    base_url: str

    @field_validator("base_url")
    @classmethod
    def validate_url(cls, value: str) -> str:
        url = urlsplit(value)
        if (
            url.scheme not in {"http", "https"}
            or not url.hostname
            or url.username
            or url.password
            or url.query
            or url.fragment
        ):
            raise ValueError("認証情報を含まない http(s) URL を指定してください")
        return value.rstrip("/")


class GenerationConfig(ConfigModel):
    timeout_seconds: float = Field(default=120, gt=0, le=600)
    temperature: float | None = Field(default=0.2, ge=0, le=2)


class RetryConfig(ConfigModel):
    invalid_response_max_retries: int = Field(default=1, ge=0, le=3)


class LLMConfig(ConfigModel):
    provider: Literal["openai", "local"]
    openai: EndpointConfig
    local: LocalConfig
    generation: GenerationConfig = Field(default_factory=GenerationConfig)
    retry: RetryConfig = Field(default_factory=RetryConfig)

    @property
    def endpoint(self) -> EndpointConfig:
        return self.openai if self.provider == "openai" else self.local

    @property
    def display_name(self) -> str:
        return f"{'OpenAI' if self.provider == 'openai' else 'Local'} / {self.endpoint.model}"


def load_llm_config(path: Path | None = None) -> LLMConfig:
    """Read once per operation so settings displayed and used share one snapshot."""
    source = path or settings.LLM_CONFIG_PATH
    try:
        raw = yaml.safe_load(Path(source).read_text(encoding="utf-8"))
    except OSError as exc:
        raise LLMConfigError(
            "settings/llm.yaml を読み込めません。ファイルを確認してください。"
        ) from exc
    except (yaml.YAMLError, UnicodeError) as exc:
        raise LLMConfigError("settings/llm.yaml のYAML構文または文字コードが不正です。") from exc
    try:
        return LLMConfig.model_validate(raw)
    except ValidationError as exc:
        locations = ", ".join(".".join(map(str, err["loc"])) for err in exc.errors())
        raise LLMConfigError(f"LLM設定が不正です。設定項目を確認してください: {locations}") from exc
