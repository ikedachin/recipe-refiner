from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import yaml
from pydantic import ValidationError

from recipes.services.llm.base import LLMError
from recipes.services.llm.config import LLMConfigError, load_llm_config
from recipes.services.llm.factory import create_llm_provider
from recipes.services.llm.openai_compatible_provider import OpenAICompatibleProvider
from recipes.services.llm.openai_provider import OpenAIProvider

from .helpers import CONFIG, OfflineSimpleTestCase, config


class ConfigTests(OfflineSimpleTestCase):
    def setUp(self):
        super().setUp()
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.path = Path(directory.name) / "llm.yaml"

    def load(self, data):
        self.path.write_text(yaml.safe_dump(data), encoding="utf-8")
        return load_llm_config(self.path)

    def test_openai_yaml(self):
        parsed = self.load(CONFIG)
        self.assertEqual(parsed.provider, "openai")
        self.assertEqual(parsed.endpoint.model, "test-openai")
        self.assertEqual(parsed.display_name, "OpenAI / test-openai")

    def test_local_yaml(self):
        data = deepcopy(CONFIG)
        data["provider"] = "local"
        parsed = self.load(data)
        self.assertEqual(parsed.endpoint.model, "test-local")
        self.assertEqual(parsed.endpoint.api_style, "chat_completions")

    def test_invalid_fields(self):
        for path, value in [
            (("provider",), "other"),
            (("openai", "model"), " "),
            (("local", "base_url"), ""),
            (("local", "base_url"), "file:///etc/passwd"),
            (("local", "base_url"), "http://user:secret@localhost/v1"),
            (("openai", "api_style"), "unsupported"),
            (("generation", "timeout_seconds"), 0),
            (("generation", "timeout_seconds"), -1),
            (("generation", "temperature"), 3),
            (("generation", "temperature"), -1),
            (("retry", "invalid_response_max_retries"), -1),
        ]:
            with self.subTest(path=path, value=value):
                data = deepcopy(CONFIG)
                target = data
                for key in path[:-1]:
                    target = target[key]
                target[path[-1]] = value
                with self.assertRaises(LLMConfigError):
                    self.load(data)

    def test_missing_model_and_base_url(self):
        for parent, key in [("openai", "model"), ("local", "model"), ("local", "base_url")]:
            data = deepcopy(CONFIG)
            del data[parent][key]
            with self.subTest(parent=parent, key=key), self.assertRaises(LLMConfigError):
                self.load(data)

    def test_missing_file(self):
        with self.assertRaisesMessage(LLMConfigError, "読み込めません"):
            load_llm_config(self.path)

    def test_invalid_yaml(self):
        self.path.write_text("provider: [openai", encoding="utf-8")
        with self.assertRaisesMessage(LLMConfigError, "構文"):
            load_llm_config(self.path)

    def test_empty_yaml(self):
        self.path.write_text("", encoding="utf-8")
        with self.assertRaises(LLMConfigError):
            load_llm_config(self.path)

    def test_secrets_are_rejected_without_echoing_values(self):
        data = deepcopy(CONFIG)
        data["openai"]["api_key"] = "never-echo-this-secret"
        with self.assertRaises(LLMConfigError) as ctx:
            self.load(data)
        self.assertNotIn("never-echo-this-secret", str(ctx.exception))

    def test_config_is_immutable(self):
        with self.assertRaises(ValidationError):
            config().provider = "local"

    def test_file_change_is_observed(self):
        self.assertEqual(self.load(CONFIG).provider, "openai")
        data = deepcopy(CONFIG)
        data["provider"] = "local"
        self.assertEqual(self.load(data).provider, "local")


class FactoryTests(OfflineSimpleTestCase):
    @patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"})
    def test_openai(self):
        self.assertIsInstance(create_llm_provider(config()), OpenAIProvider)

    @patch.dict("os.environ", {}, clear=True)
    def test_local_without_key(self):
        self.assertIsInstance(create_llm_provider(config("local")), OpenAICompatibleProvider)

    @patch.dict("os.environ", {"OPENAI_API_KEY": " "})
    def test_openai_missing_key(self):
        with self.assertRaisesMessage(LLMError, "未設定"):
            create_llm_provider(config())

    def test_bad_provider_is_rejected(self):
        invalid = config().model_copy(update={"provider": "unsupported"})
        with self.assertRaises(LLMConfigError):
            create_llm_provider(invalid)
