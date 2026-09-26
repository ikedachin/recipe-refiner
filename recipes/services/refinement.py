"""Application workflow: validate inputs, confirm, generate, and atomically save."""

from dataclasses import dataclass

from django.core import signing
from django.db import transaction
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from recipes.models import Recipe, RecipeRevision

from .llm.config import LLMConfig, load_llm_config
from .llm.factory import create_llm_provider
from .llm.schemas import Confirmation, RecipeRefineResponse, RefinedRecipe

CONFIRMATION_SALT = "recipes.refinement.confirm.v1"
CONFIRMATION_MAX_AGE = 1800


class InputError(Exception):
    pass


class RefineInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, strict=True)
    original_text: str = Field(default="", max_length=30000)
    request_text: str = Field(min_length=1, max_length=6000)


@dataclass(frozen=True)
class RecipeSource:
    text: str
    recipe: Recipe | None = None
    parent: RecipeRevision | None = None


def recipe_to_text(recipe: RefinedRecipe) -> str:
    lines = [recipe.title, recipe.servings, "", "材料"]
    for item in recipe.ingredients:
        note = f"（{item.note}）" if item.note else ""
        lines.append(f"{item.name} {item.amount}{item.unit}{note}")
    lines.extend(["", "作り方"])
    lines.extend(f"{s.order}. {s.instruction}" for s in recipe.steps)
    if recipe.estimated_time_minutes:
        lines.extend(["", f"調理時間の目安: {recipe.estimated_time_minutes}分"])
    if recipe.notes:
        lines.extend(["", "補足", *recipe.notes])
    return "\n".join(lines)


def resolve_source(
    original_text: str,
    *,
    recipe_id: int | None = None,
    revision_id: int | None = None,
) -> RecipeSource:
    if revision_id is not None:
        parent = RecipeRevision.objects.select_related("recipe").get(pk=revision_id)
        return RecipeSource(parent.result_text, parent.recipe, parent)
    if recipe_id is not None:
        recipe = Recipe.objects.get(pk=recipe_id)
        return RecipeSource(recipe.original_text, recipe)
    if not original_text:
        raise InputError("元レシピを入力してください。")
    return RecipeSource(original_text)


def refine(
    data: dict,
    *,
    recipe_id: int | None = None,
    revision_id: int | None = None,
    confirmation: Confirmation | None = None,
) -> dict:
    try:
        inputs = RefineInput.model_validate(data)
    except ValidationError as exc:
        raise InputError(
            "元レシピは30,000文字以内、変更希望は1〜6,000文字で入力してください。"
        ) from exc
    source = resolve_source(inputs.original_text, recipe_id=recipe_id, revision_id=revision_id)
    config = load_llm_config()
    result = create_llm_provider(config).refine_recipe(
        source.text, inputs.request_text, confirmation
    )
    if result.status == "needs_confirmation":
        token = signing.dumps(
            {
                "original_text": source.text if source.recipe is None else "",
                "request_text": inputs.request_text,
                "recipe_id": source.recipe.pk if source.recipe else None,
                "revision_id": source.parent.pk if source.parent else None,
                "confirmation": result.confirmation.model_dump(),
            },
            salt=CONFIRMATION_SALT,
            compress=True,
        )
        return {**result.model_dump(), "confirmation_token": token}
    revision = save_result(source, inputs.request_text, result, config, confirmation)
    return {
        **result.model_dump(),
        "recipe_id": revision.recipe_id,
        "revision_id": revision.pk,
        "result_text": revision.result_text,
        "history_url": f"/recipes/{revision.recipe_id}/?revision={revision.pk}",
        "llm": config.display_name,
    }


def confirm_refinement(token: str) -> dict:
    try:
        payload = signing.loads(token, salt=CONFIRMATION_SALT, max_age=CONFIRMATION_MAX_AGE)
        confirmation = Confirmation.model_validate(payload["confirmation"])
    except (signing.BadSignature, ValidationError, KeyError, TypeError) as exc:
        raise InputError(
            "確認の有効期限が切れたか、内容が不正です。もう一度リファインしてください。"
        ) from exc
    return refine(
        {"original_text": payload["original_text"], "request_text": payload["request_text"]},
        recipe_id=payload["recipe_id"],
        revision_id=payload["revision_id"],
        confirmation=confirmation,
    )


@transaction.atomic
def save_result(
    source: RecipeSource,
    request_text: str,
    result: RecipeRefineResponse,
    config: LLMConfig,
    confirmation: Confirmation | None,
) -> RecipeRevision:
    """Only successful generations become revisions; rollback both inserts on failure."""
    recipe = source.recipe or Recipe.objects.create(
        title=result.recipe.title,
        original_text=source.text,
    )
    revision = RecipeRevision.objects.create(
        recipe=recipe,
        parent_revision=source.parent,
        request_text=request_text,
        provider=config.provider,
        model_name=config.endpoint.model,
        api_style=config.endpoint.api_style,
        result_json=result.model_dump(),
        result_text=recipe_to_text(result.recipe),
        confirmation_json=confirmation.model_dump() if confirmation else None,
    )
    recipe.save(update_fields=["updated_at"])
    return revision
