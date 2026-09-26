from django.conf import settings

from .services.llm.config import LLMConfigError, load_llm_config


def app_context(request):
    try:
        label = load_llm_config().display_name
        error = ""
    except LLMConfigError as exc:
        label, error = "設定を確認してください", str(exc)
    return {"app_name": settings.APP_DISPLAY_NAME, "llm_label": label, "config_error": error}
