import os

from .base import LLMError
from .config import LLMConfig
from .sdk_provider import SDKProvider


class OpenAIProvider(SDKProvider):
    def __init__(self, config: LLMConfig) -> None:
        key = os.getenv("OPENAI_API_KEY", "").strip()
        if not key:
            raise LLMError("OPENAI_API_KEY が未設定です。.env に設定して再起動してください。")
        super().__init__(config, api_key=key, base_url="https://api.openai.com/v1")
