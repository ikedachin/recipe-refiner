"""Provider-independent output contract and semantic validation."""

from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


class SchemaModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, strict=True)


class Ingredient(SchemaModel):
    name: str = Field(min_length=1)
    amount: str
    unit: str
    note: str


class RecipeStep(SchemaModel):
    order: int = Field(ge=1)
    instruction: str = Field(min_length=1)


class RefinedRecipe(SchemaModel):
    title: str = Field(min_length=1, max_length=200)
    servings: str = Field(min_length=1)
    ingredients: list[Ingredient] = Field(min_length=1)
    steps: list[RecipeStep] = Field(min_length=1)
    estimated_time_minutes: int | None = Field(ge=1)
    notes: list[str]

    @model_validator(mode="after")
    def ordered_steps(self) -> Self:
        if [s.order for s in self.steps] != list(range(1, len(self.steps) + 1)):
            raise ValueError("steps.order must be sequential, starting at 1")
        return self


class RecipeChange(SchemaModel):
    type: str = Field(min_length=1)
    before: str
    after: str
    reason: str = Field(min_length=1)


class Confirmation(SchemaModel):
    message: str = Field(min_length=1)
    concerns: list[str] = Field(min_length=1)
    required_changes: list[str] = Field(min_length=1)
    alternatives: list[str] = Field(min_length=1)


class RecipeRefineResponse(SchemaModel):
    status: Literal["ok", "needs_confirmation"]
    recipe: RefinedRecipe | None
    confirmation: Confirmation | None
    changes: list[RecipeChange]
    assumptions: list[str]
    warnings: list[str]

    @model_validator(mode="after")
    def status_matches_payload(self) -> Self:
        if self.status == "ok" and (self.recipe is None or self.confirmation is not None):
            raise ValueError("ok requires recipe and null confirmation")
        if self.status == "needs_confirmation" and (
            self.confirmation is None or self.recipe is not None
        ):
            raise ValueError("needs_confirmation requires confirmation and null recipe")
        return self
