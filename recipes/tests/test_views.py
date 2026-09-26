from unittest.mock import patch

from django.core import signing
from django.db import DatabaseError
from django.test import Client, override_settings

from recipes.models import Recipe, RecipeRevision
from recipes.services.llm.base import LLMError
from recipes.services.llm.config import LLMConfigError

from .helpers import OfflineTestCase, config, confirmation_response, ok_response


class APITests(OfflineTestCase):
    def setUp(self):
        super().setUp()
        factory_patch = patch("recipes.services.refinement.create_llm_provider")
        self.factory = factory_patch.start()
        self.addCleanup(factory_patch.stop)
        self.provider = self.factory.return_value
        self.provider.refine_recipe.return_value = ok_response()
        config_patch = patch("recipes.services.refinement.load_llm_config", return_value=config())
        self.load_config = config_patch.start()
        self.addCleanup(config_patch.stop)
        self.inputs = {"original_text": "カレー4人前\n牛肉300g", "request_text": "豚肉で2人前"}

    def post(self, url="/api/refine/", data=None, client=None):
        return (client or self.client).post(
            url, self.inputs if data is None else data, content_type="application/json"
        )

    def create(self):
        response = self.post()
        self.assertEqual(response.status_code, 200)
        return RecipeRevision.objects.get(pk=response.json()["revision_id"])

    def test_refine_success(self):
        result = self.post()
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json()["status"], "ok")
        recipe = Recipe.objects.get()
        revision = RecipeRevision.objects.get()
        self.assertEqual(recipe.original_text, self.inputs["original_text"])
        self.assertEqual(revision.request_text, self.inputs["request_text"])
        self.assertEqual(revision.provider, "openai")
        self.assertEqual(revision.model_name, "test-openai")
        self.assertEqual(revision.api_style, "responses")
        self.assertIsNone(revision.parent_revision)
        self.assertNotIn("api_key", str(revision.result_json))

    def test_empty_inputs_and_lengths(self):
        for data in [
            {"original_text": "", "request_text": "変更"},
            {"original_text": "元", "request_text": "  "},
            {"original_text": "元"},
            {"original_text": 4, "request_text": "変更"},
            {"original_text": "a" * 30001, "request_text": "変更"},
            {"original_text": "元", "request_text": "a" * 6001},
            {**self.inputs, "confirmed": True},
        ]:
            with self.subTest(data_size=len(str(data))):
                self.assertEqual(self.post(data=data).status_code, 400)
        self.provider.refine_recipe.assert_not_called()
        self.assertFalse(Recipe.objects.exists())

    def test_invalid_json(self):
        for data in ["{broken", "[]", "null"]:
            response = self.client.post("/api/refine/", data, content_type="application/json")
            self.assertEqual(response.status_code, 400)
        self.assertEqual(self.client.post("/api/refine/", self.inputs).status_code, 400)

    def test_needs_confirmation_does_not_save(self):
        self.provider.refine_recipe.return_value = confirmation_response()
        response = self.post()
        self.assertEqual(response.json()["status"], "needs_confirmation")
        self.assertIn("confirmation_token", response.json())
        self.assertFalse(Recipe.objects.exists())
        self.assertFalse(RecipeRevision.objects.exists())

    def test_confirmation_reuses_signed_original_and_request(self):
        self.provider.refine_recipe.return_value = confirmation_response()
        token = self.post().json()["confirmation_token"]
        self.provider.refine_recipe.return_value = ok_response()
        response = self.post(
            "/api/refine/confirm/", {"confirmation_token": token, "request_text": "改ざん"}
        )
        self.assertEqual(response.status_code, 200)
        args = self.provider.refine_recipe.call_args.args
        self.assertEqual(args[:2], (self.inputs["original_text"], self.inputs["request_text"]))
        self.assertEqual(args[2], confirmation_response().confirmation)
        self.assertIsNotNone(RecipeRevision.objects.get().confirmation_json)

    def test_confirmation_for_revision_preserves_parent(self):
        first = self.create()
        self.provider.refine_recipe.return_value = confirmation_response()
        token = self.post(f"/api/refine/{first.pk}/", {"request_text": "粉を使わない"}).json()[
            "confirmation_token"
        ]
        self.provider.refine_recipe.return_value = ok_response()
        response = self.post("/api/refine/confirm/", {"confirmation_token": token})
        child = RecipeRevision.objects.get(pk=response.json()["revision_id"])
        self.assertEqual(child.parent_revision, first)
        self.assertEqual(child.recipe, first.recipe)

    def test_tampered_missing_and_expired_confirmation(self):
        self.provider.refine_recipe.return_value = confirmation_response()
        token = self.post().json()["confirmation_token"]
        for invalid in [token + "x", "", 4]:
            self.assertEqual(
                self.post("/api/refine/confirm/", {"confirmation_token": invalid}).status_code, 400
            )
        with patch(
            "recipes.services.refinement.signing.loads", side_effect=signing.SignatureExpired()
        ):
            self.assertEqual(
                self.post("/api/refine/confirm/", {"confirmation_token": token}).status_code, 400
            )
        self.assertFalse(RecipeRevision.objects.exists())

    def test_history_chain_and_branch(self):
        first = self.create()
        second_data = self.post(
            f"/api/refine/{first.pk}/", {"request_text": "3人前", "original_text": "無視すべき入力"}
        ).json()
        second = RecipeRevision.objects.get(pk=second_data["revision_id"])
        self.assertEqual(second.parent_revision, first)
        self.assertEqual(self.provider.refine_recipe.call_args.args[0], first.result_text)
        third = self.post(f"/api/refine/{second.pk}/", {"request_text": "辛く"}).json()
        self.assertEqual(
            RecipeRevision.objects.get(pk=third["revision_id"]).parent_revision, second
        )
        branch = self.post(f"/api/refine/{first.pk}/", {"request_text": "甘く"}).json()
        self.assertEqual(
            RecipeRevision.objects.get(pk=branch["revision_id"]).parent_revision, first
        )
        self.assertEqual(Recipe.objects.count(), 1)
        self.assertEqual(RecipeRevision.objects.count(), 4)

    def test_refine_from_original(self):
        first = self.create()
        data = self.post(f"/api/recipes/{first.recipe_id}/refine/", {"request_text": "変更"}).json()
        revision = RecipeRevision.objects.get(pk=data["revision_id"])
        self.assertIsNone(revision.parent_revision)
        self.assertEqual(revision.recipe, first.recipe)
        self.assertEqual(self.provider.refine_recipe.call_args.args[0], first.recipe.original_text)

    def test_history_endpoint(self):
        revision = self.create()
        response = self.client.get(f"/api/recipes/{revision.recipe_id}/history/")
        data = response.json()
        self.assertEqual(data["original_text"], self.inputs["original_text"])
        self.assertEqual(data["revisions"][0]["id"], revision.pk)
        self.assertIsNone(data["revisions"][0]["parent_revision_id"])
        self.assertEqual(data["revisions"][0]["api_style"], "responses")

    def test_provider_changes_do_not_rewrite_history(self):
        first = self.create()
        self.load_config.return_value = config("local")
        self.post(f"/api/refine/{first.pk}/", {"request_text": "3人前"})
        first.refresh_from_db()
        self.assertEqual(first.model_name, "test-openai")
        self.assertEqual(RecipeRevision.objects.last().model_name, "test-local")

    def test_invalid_ids(self):
        for url in [
            "/api/refine/9999/",
            "/api/recipes/9999/refine/",
            "/api/recipes/9999/favorite/",
        ]:
            self.assertEqual(self.post(url).status_code, 404)
        self.assertEqual(self.client.get("/api/recipes/9999/history/").status_code, 404)
        self.provider.refine_recipe.assert_not_called()

    def test_expected_errors_have_safe_messages(self):
        for error, status in [(LLMError("接続できません"), 502), (LLMConfigError("設定不正"), 503)]:
            self.provider.refine_recipe.side_effect = error
            response = self.post()
            self.assertEqual(response.status_code, status)
            self.assertEqual(response.json()["error"], str(error))
        self.assertFalse(Recipe.objects.exists())

    def test_unexpected_errors_do_not_leak_secrets(self):
        self.provider.refine_recipe.side_effect = RuntimeError("secret-private-value")
        response = self.post()
        self.assertEqual(response.status_code, 500)
        self.assertNotIn("secret-private-value", response.content.decode())
        self.assertNotIn("Traceback", response.content.decode())

    def test_database_failure_rolls_back_recipe(self):
        with patch(
            "recipes.services.refinement.RecipeRevision.objects.create",
            side_effect=DatabaseError("secret-db-details"),
        ):
            response = self.post()
        self.assertEqual(response.status_code, 503)
        self.assertFalse(Recipe.objects.exists())
        self.assertNotIn("secret-db-details", response.content.decode())

    def test_methods(self):
        self.assertEqual(self.client.get("/api/refine/").status_code, 405)
        self.assertEqual(self.post("/api/recipes/99/history/").status_code, 405)

    def test_csrf_required_and_valid_token_accepted(self):
        client = Client(enforce_csrf_checks=True)
        response = self.post(client=client)
        self.assertEqual(response.status_code, 403)
        self.assertIn("error", response.json())
        client.get("/")
        response = client.post(
            "/api/refine/",
            self.inputs,
            content_type="application/json",
            HTTP_X_CSRFTOKEN=client.cookies["csrftoken"].value,
        )
        self.assertEqual(response.status_code, 200)

    def test_pages_and_favorites(self):
        revision = self.create()
        for url in [
            "/",
            "/history/",
            "/favorites/",
            f"/recipes/{revision.recipe_id}/",
            f"/recipes/{revision.recipe_id}/?revision=original",
        ]:
            self.assertEqual(self.client.get(url).status_code, 200)
        self.assertNotContains(self.client.get("/favorites/"), revision.recipe.title)
        self.post(f"/api/recipes/{revision.recipe_id}/favorite/", {})
        self.assertContains(self.client.get("/favorites/"), revision.recipe.title)
        self.assertEqual(
            self.client.get(f"/recipes/{revision.recipe_id}/?revision=999").status_code, 404
        )
        self.assertEqual(self.client.get("/recipes/99999/").status_code, 404)

    def test_html_and_bootstrap_are_escaped(self):
        result = ok_response()
        result.recipe.title = '<script>alert("bad")</script>'
        self.provider.refine_recipe.return_value = result
        self.inputs["original_text"] = '</textarea><script>alert("bad")</script>'
        revision = self.create()
        page = self.client.get(f"/recipes/{revision.recipe_id}/?revision=original")
        self.assertNotContains(page, '<script>alert("bad")</script>')
        self.assertContains(page, "&lt;script&gt;")
        generated = self.client.get(f"/recipes/{revision.recipe_id}/")
        self.assertNotContains(generated, '<script>alert("bad")</script>')
        self.assertContains(generated, r"\u003Cscript\u003E")

    @override_settings(DEBUG=False)
    def test_debug_false_errors(self):
        page = self.client.get("/not-a-page/")
        self.assertEqual(page.status_code, 404)
        self.assertNotContains(page, "Traceback", status_code=404)
        response = self.client.get("/api/not-a-page/")
        self.assertEqual(response.status_code, 404)
        self.assertIn("error", response.json())

    def test_bad_config_page_is_readable(self):
        with patch(
            "recipes.context_processors.load_llm_config", side_effect=LLMConfigError("YAML設定不正")
        ):
            self.assertContains(self.client.get("/"), "YAML設定不正")
