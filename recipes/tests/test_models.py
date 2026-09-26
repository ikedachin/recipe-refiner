from django.core.exceptions import ValidationError

from recipes.models import Recipe, RecipeRevision

from .helpers import OK, OfflineTestCase


class ModelTests(OfflineTestCase):
    def make_revision(self, recipe, parent=None):
        return RecipeRevision.objects.create(
            recipe=recipe,
            parent_revision=parent,
            request_text="2人前に",
            provider="local",
            model_name="test",
            api_style="chat_completions",
            result_json=OK,
            result_text="2人前のレシピ",
        )

    def test_recipe_and_revisions(self):
        recipe = Recipe.objects.create(title="カレー", original_text="カレー4人前")
        first = self.make_revision(recipe)
        second = self.make_revision(recipe, first)
        second.full_clean()
        self.assertFalse(recipe.is_favorite)
        self.assertEqual(recipe.revisions.count(), 2)
        self.assertEqual(second.parent_revision, first)
        self.assertIsNone(first.parent_revision)
        self.assertEqual(str(recipe), "カレー")

    def test_cross_recipe_parent_rejected(self):
        one = Recipe.objects.create(title="一", original_text="一")
        two = Recipe.objects.create(title="二", original_text="二")
        revision = self.make_revision(one)
        wrong = RecipeRevision(recipe=two, parent_revision=revision)
        with self.assertRaises(ValidationError):
            wrong.clean()

    def test_self_parent_rejected(self):
        recipe = Recipe.objects.create(title="一", original_text="一")
        revision = self.make_revision(recipe)
        revision.parent_revision = revision
        with self.assertRaises(ValidationError):
            revision.clean()

    def test_favorite_toggle(self):
        recipe = Recipe.objects.create(title="カレー", original_text="元")
        for expected in (True, False):
            response = self.client.post(f"/api/recipes/{recipe.pk}/favorite/")
            recipe.refresh_from_db()
            self.assertEqual(response.json()["is_favorite"], expected)
            self.assertEqual(recipe.is_favorite, expected)
