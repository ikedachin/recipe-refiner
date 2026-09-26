from abc import ABC, abstractmethod

from .schemas import Confirmation, RecipeRefineResponse


class LLMError(Exception):
    """A sanitized error safe to show in the browser."""


class LLMProvider(ABC):
    @abstractmethod
    def refine_recipe(
        self,
        original_text: str,
        request_text: str,
        confirmation: Confirmation | None = None,
    ) -> RecipeRefineResponse:
        """Return a validated result, or raise a user-facing LLMError."""
