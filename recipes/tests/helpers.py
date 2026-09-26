from copy import deepcopy
from unittest.mock import patch

import httpx
from django.test import SimpleTestCase, TestCase

from recipes.services.llm.config import LLMConfig
from recipes.services.llm.schemas import RecipeRefineResponse

CONFIG = {
    "provider": "openai",
    "openai": {"model": "test-openai", "api_style": "responses"},
    "local": {
        "model": "test-local",
        "api_style": "chat_completions",
        "base_url": "http://localhost:8001/v1",
        "send_temperature": True,
    },
    "generation": {"timeout_seconds": 7, "temperature": 0.2},
    "retry": {"invalid_response_max_retries": 1},
}
OK = {
    "status": "ok",
    "recipe": {
        "title": "ポークカレー",
        "servings": "2人前",
        "ingredients": [{"name": "豚肉", "amount": "150", "unit": "g", "note": "薄切り"}],
        "steps": [{"order": 1, "instruction": "豚肉を十分に加熱する。"}],
        "estimated_time_minutes": 30,
        "notes": ["弱火で仕上げる"],
    },
    "confirmation": None,
    "changes": [
        {
            "type": "ingredient_substitution",
            "before": "牛肉300g",
            "after": "豚肉150g",
            "reason": "2人前への変更に合わせ、火入れも調整",
        }
    ],
    "assumptions": ["豚肉は薄切りと仮定"],
    "warnings": [],
}
CONFIRM = {
    "status": "needs_confirmation",
    "recipe": None,
    "confirmation": {
        "message": "この変更では元のレシピを維持することが難しい可能性があります。",
        "concerns": ["粉を使わずにパンの生地を作れません"],
        "required_changes": ["卵を中心とした別の生地へ変える必要があります"],
        "alternatives": ["パンに似た卵料理として作る"],
    },
    "changes": [],
    "assumptions": [],
    "warnings": [],
}


def config(provider="openai", **endpoint_overrides):
    data = deepcopy(CONFIG)
    data["provider"] = provider
    data[provider].update(endpoint_overrides)
    return LLMConfig.model_validate(data)


def ok_response():
    return RecipeRefineResponse.model_validate(deepcopy(OK))


def confirmation_response():
    return RecipeRefineResponse.model_validate(deepcopy(CONFIRM))


class NoNetworkMixin:
    """Fail loudly if any test accidentally reaches an external SDK transport."""

    def setUp(self):
        super().setUp()
        self.network_guard = patch.object(
            httpx.Client,
            "send",
            side_effect=AssertionError("Tests must never call an external API"),
        )
        self.network_guard.start()
        self.addCleanup(self.network_guard.stop)


class OfflineSimpleTestCase(NoNetworkMixin, SimpleTestCase):
    pass


class OfflineTestCase(NoNetworkMixin, TestCase):
    pass
