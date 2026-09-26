import json
from copy import deepcopy

from pydantic import ValidationError

from recipes.services.llm.schemas import RecipeRefineResponse
from recipes.services.refinement import recipe_to_text

from .helpers import CONFIRM, OK, OfflineSimpleTestCase, ok_response


class SchemaTests(OfflineSimpleTestCase):
    def test_valid_json(self):
        result = RecipeRefineResponse.model_validate_json(json.dumps(OK))
        self.assertEqual(result.recipe.servings, "2人前")

    def test_missing_field(self):
        data = deepcopy(OK)
        del data["recipe"]["title"]
        with self.assertRaises(ValidationError):
            RecipeRefineResponse.model_validate(data)

    def test_invalid_json(self):
        for value in ["", "plain text", "```json\n{}\n```", '{"status":']:
            with self.subTest(value=value), self.assertRaises(ValidationError):
                RecipeRefineResponse.model_validate_json(value)

    def test_confirmation(self):
        result = RecipeRefineResponse.model_validate(CONFIRM)
        self.assertEqual(result.status, "needs_confirmation")
        self.assertIsNone(result.recipe)

    def test_semantic_status_validation(self):
        for source in [OK, CONFIRM]:
            data = deepcopy(source)
            data["status"] = "needs_confirmation" if source is OK else "ok"
            with self.assertRaises(ValidationError):
                RecipeRefineResponse.model_validate(data)

    def test_empty_recipe_and_unordered_steps(self):
        for field, value in [
            ("ingredients", []),
            ("steps", []),
            ("title", "  "),
            ("steps", [{"order": 2, "instruction": "切る"}]),
            ("estimated_time_minutes", -1),
        ]:
            data = deepcopy(OK)
            data["recipe"][field] = value
            with self.subTest(field=field), self.assertRaises(ValidationError):
                RecipeRefineResponse.model_validate(data)

    def test_unknown_fields_rejected(self):
        with self.assertRaises(ValidationError):
            RecipeRefineResponse.model_validate({**OK, "unexpected": "value"})

    def test_text_keeps_complete_recipe(self):
        text = recipe_to_text(ok_response().recipe)
        for expected in ["ポークカレー", "2人前", "豚肉 150g（薄切り）", "1.", "30分", "弱火"]:
            self.assertIn(expected, text)
