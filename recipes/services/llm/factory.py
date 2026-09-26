from .base import LLMProvider
from .config import LLMConfig, LLMConfigError
from .openai_compatible_provider import OpenAICompatibleProvider
from .openai_provider import OpenAIProvider


def create_llm_provider(config: LLMConfig) -> LLMProvider:
    if config.provider == "openai":
        return OpenAIProvider(config)
    if config.provider == "local":
        return OpenAICompatibleProvider(config)
    raise LLMConfigError("provider は openai または local を指定してください。")
