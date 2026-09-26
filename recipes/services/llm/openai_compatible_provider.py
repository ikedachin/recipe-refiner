import os

from .config import LLMConfig
from .sdk_provider import SDKProvider


class OpenAICompatibleProvider(SDKProvider):
    def __init__(self, config: LLMConfig) -> None:
        super().__init__(
            config,
            api_key=os.getenv("LOCAL_LLM_API_KEY", "").strip() or "dummy",
            base_url=config.local.base_url,
        )
