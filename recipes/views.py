import json
import logging
from functools import wraps

from django.core.exceptions import RequestDataTooBig
from django.core.paginator import Paginator
from django.db import DatabaseError
from django.db.models import Count, F
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET

from .models import Recipe, RecipeRevision
from .services.llm.base import LLMError
from .services.llm.config import LLMConfigError
from .services.refinement import InputError, confirm_refinement, refine

logger = logging.getLogger(__name__)


def api_endpoint(method):
    """Keep API errors JSON and avoid exposing provider errors or request contents."""

    def decorator(view):
        @wraps(view)
        def wrapped(request, *args, **kwargs):
            if request.method != method:
                response = JsonResponse({"error": "この操作は対応していません。"}, status=405)
                response["Allow"] = method
                return response
            try:
                return view(request, *args, **kwargs)
            except (Recipe.DoesNotExist, RecipeRevision.DoesNotExist):
                return JsonResponse(
                    {"error": "指定されたレシピまたは履歴が見つかりません。"}, status=404
                )
            except (InputError, RequestDataTooBig) as exc:
                message = str(exc) if isinstance(exc, InputError) else "入力サイズが大きすぎます。"
                return JsonResponse({"error": message}, status=400)
            except LLMConfigError as exc:
                return JsonResponse({"error": str(exc)}, status=503)
            except LLMError as exc:
                return JsonResponse({"error": str(exc)}, status=502)
            except DatabaseError:
                return JsonResponse(
                    {
                        "error": (
                            "履歴データを保存・取得できませんでした。"
                            "データベースを確認してください。"
                        )
                    },
                    status=503,
                )
            except Exception as exc:
                # Log only the class, never SDK payloads, credentials or recipe contents.
                logger.error("Unexpected API failure (%s)", type(exc).__name__)
                return JsonResponse(
                    {"error": "処理を完了できませんでした。もう一度お試しください。"}, status=500
                )

        return wrapped

    return decorator


def read_json(request) -> dict:
    if request.content_type != "application/json":
        raise InputError("JSON形式で送信してください。")
    try:
        data = json.loads(request.body)
    except (ValueError, UnicodeError) as exc:
        raise InputError("送信内容を読み取れませんでした。") from exc
    if not isinstance(data, dict):
        raise InputError("送信内容はJSONオブジェクトにしてください。")
    return data


@ensure_csrf_cookie
@require_GET
def index(request):
    return render(request, "recipes/editor.html", {"nav": "editor", "bootstrap": {}})


@ensure_csrf_cookie
@require_GET
def recipe_list(request, favorites=False):
    recipes = Recipe.objects.annotate(revision_count=Count("revisions")).order_by(
        "-updated_at", "-pk"
    )
    if favorites:
        recipes = recipes.filter(is_favorite=True)
    try:
        page = Paginator(recipes, 24).get_page(request.GET.get("page"))
        return render(
            request,
            "recipes/list.html",
            {
                "page_obj": page,
                "favorites": favorites,
                "nav": "favorites" if favorites else "history",
            },
        )
    except DatabaseError:
        return render(
            request,
            "recipes/error.html",
            {
                "message": "履歴を読み込めません。データベースを確認してください。",
            },
            status=503,
        )


@ensure_csrf_cookie
@require_GET
def recipe_detail(request, recipe_id):
    try:
        recipe = get_object_or_404(Recipe, pk=recipe_id)
        revisions = list(recipe.revisions.all())
        selected_id = request.GET.get("revision")
        selected = None
        if selected_id != "original" and revisions:
            if selected_id is None:
                selected = revisions[-1]
            else:
                selected = next((r for r in revisions if str(r.pk) == selected_id), None)
                if selected is None:
                    return not_found(request)
        elif selected_id not in {None, "original"}:
            return not_found(request)
        numbered = {r.pk: i for i, r in enumerate(revisions, 1)}
        timeline = [
            {
                "revision": r,
                "number": numbered[r.pk],
                "parent_number": numbered.get(r.parent_revision_id),
            }
            for r in revisions
        ]
        bootstrap = {
            "recipe_id": recipe.pk,
            "revision_id": selected.pk if selected else None,
            "result": selected.result_json if selected else None,
            "result_text": selected.result_text if selected else recipe.original_text,
            "llm": f"{selected.provider} / {selected.model_name}" if selected else None,
        }
        return render(
            request,
            "recipes/editor.html",
            {
                "nav": "history",
                "recipe": recipe,
                "selected": selected,
                "timeline": timeline,
                "bootstrap": bootstrap,
                "source_text": selected.result_text if selected else recipe.original_text,
            },
        )
    except DatabaseError:
        return render(
            request,
            "recipes/error.html",
            {
                "message": "履歴を読み込めません。データベースを確認してください。",
            },
            status=503,
        )


@api_endpoint("POST")
def refine_api(request, revision_id=None, recipe_id=None):
    return JsonResponse(refine(read_json(request), revision_id=revision_id, recipe_id=recipe_id))


@api_endpoint("POST")
def confirm_api(request):
    data = read_json(request)
    token = data.get("confirmation_token")
    if not isinstance(token, str) or not token or len(token) > 200000:
        raise InputError("確認内容がありません。もう一度リファインしてください。")
    return JsonResponse(confirm_refinement(token))


@api_endpoint("POST")
def favorite_api(request, recipe_id):
    # Single SQL update avoids a lost toggle when requests overlap.
    if not Recipe.objects.filter(pk=recipe_id).update(is_favorite=~F("is_favorite")):
        raise Recipe.DoesNotExist
    return JsonResponse({"is_favorite": Recipe.objects.get(pk=recipe_id).is_favorite})


@api_endpoint("GET")
def history_api(request, recipe_id):
    recipe = Recipe.objects.get(pk=recipe_id)
    revisions = [
        {
            "id": r.pk,
            "parent_revision_id": r.parent_revision_id,
            "request_text": r.request_text,
            "provider": r.provider,
            "model_name": r.model_name,
            "api_style": r.api_style,
            "result_json": r.result_json,
            "result_text": r.result_text,
            "created_at": r.created_at.isoformat(),
        }
        for r in recipe.revisions.all()
    ]
    return JsonResponse(
        {
            "id": recipe.pk,
            "title": recipe.title,
            "original_text": recipe.original_text,
            "is_favorite": recipe.is_favorite,
            "revisions": revisions,
        }
    )


def error_response(request, message, status):
    if request.path.startswith("/api/"):
        return JsonResponse({"error": message}, status=status)
    return render(request, "recipes/error.html", {"message": message}, status=status)


def csrf_failure(request, reason=""):
    return error_response(
        request, "ページの有効期限が切れました。再読み込みしてお試しください。", 403
    )


def bad_request(request, exception=None):
    return error_response(request, "リクエストを読み取れませんでした。", 400)


def not_found(request, exception=None):
    return error_response(request, "指定されたページまたはレシピが見つかりません。", 404)


def server_error(request):
    return error_response(request, "処理を完了できませんでした。もう一度お試しください。", 500)
