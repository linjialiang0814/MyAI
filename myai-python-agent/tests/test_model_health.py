import unittest
from unittest.mock import patch

from app.model.config import LLMSettings
from app.model.health import probe_model_health


def settings(**overrides):
    values = {
        "default_provider": "stub",
        "chat_provider": "stub",
        "task_provider": "stub",
        "memory_provider": "stub",
        "embedding_provider": "stub",
        "memory_llm_extractor_enabled": False,
        "fallback_to_stub": True,
        "temperature": 0.7,
        "ark_api_key": "",
        "ark_base_url": "https://example.test",
        "default_model_id": "",
        "chat_model_id": "",
        "task_model_id": "",
        "memory_model_id": "",
        "embedding_model_id": "",
        "memory_collection_name": "memory_stub_default",
        "knowledge_collection_name": "knowledge_stub_default",
    }
    values.update(overrides)
    return LLMSettings(**values)


class ModelHealthTest(unittest.TestCase):
    def test_stub_only_probe_does_not_call_external_provider(self):
        payload = probe_model_health(settings())

        self.assertEqual(payload["status"], "stub_only")
        self.assertEqual(payload["summary"]["real_roles"], 0)
        self.assertTrue(payload["roles"]["chat"]["ok"])
        self.assertEqual(payload["roles"]["chat"]["status"], "stub")

    def test_missing_real_provider_config_is_reported(self):
        payload = probe_model_health(
            settings(chat_provider="volcengine", chat_model_id="", ark_api_key="")
        )

        self.assertEqual(payload["status"], "degraded")
        self.assertFalse(payload["roles"]["chat"]["ok"])
        self.assertEqual(payload["roles"]["chat"]["status"], "misconfigured")
        self.assertIn("model_id", payload["roles"]["chat"]["missing"])
        self.assertIn("provider_auth", payload["roles"]["chat"]["missing"])

    def test_openai_compatible_probe_does_not_require_an_api_key(self):
        configured = settings(
            chat_provider="openai_compatible",
            chat_model_id="local-chat",
            fallback_to_stub=False,
        )
        with patch("app.model.health.OpenAICompatibleLLM") as client_type:
            client_type.return_value.generate.return_value = "OK"
            payload = probe_model_health(configured)

        self.assertEqual(payload["status"], "healthy")
        self.assertTrue(payload["roles"]["chat"]["ok"])
        self.assertEqual(payload["roles"]["chat"]["provider"], "openai_compatible")
        self.assertNotIn("provider_auth", payload["roles"]["chat"].get("missing", []))
        client_type.return_value.close.assert_called_once_with()

    def test_openai_compatible_embedding_probe_closes_client(self):
        configured = settings(
            embedding_provider="openai_compatible",
            embedding_model_id="local-embedding",
            embedding_expected_dimensions=3,
        )
        with patch("app.model.health.OpenAICompatibleEmbedding") as client_type:
            client_type.return_value.embed.return_value = [0.1, 0.2, 0.3]
            payload = probe_model_health(configured)

        self.assertTrue(payload["roles"]["embedding"]["ok"])
        self.assertEqual(payload["roles"]["embedding"]["dimensions"], 3)
        self.assertEqual(
            payload["roles"]["embedding"]["effective_mode"],
            "real_fail_closed",
        )
        self.assertFalse(payload["roles"]["embedding"]["fallback_to_stub"])
        client_type.return_value.close.assert_called_once_with()

    def test_volcengine_probes_close_llm_and_embedding_clients(self):
        configured = settings(
            chat_provider="volcengine",
            chat_model_id="ark-chat",
            embedding_provider="volcengine",
            embedding_model_id="ark-embedding",
            embedding_expected_dimensions=3,
            ark_api_key="secret",
            fallback_to_stub=False,
        )
        with patch("app.model.health.VolcengineLLM") as llm_type, patch(
            "app.model.health.EmbeddingClient"
        ) as embedding_type:
            llm_type.return_value.generate.return_value = "OK"
            embedding_type.return_value.embed.return_value = [0.1, 0.2, 0.3]
            payload = probe_model_health(configured)

        self.assertTrue(payload["roles"]["chat"]["ok"])
        self.assertTrue(payload["roles"]["embedding"]["ok"])
        llm_type.return_value.close.assert_called_once_with()
        embedding_type.return_value.close.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
