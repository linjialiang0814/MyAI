import unittest

from app.model.config import LLMSettings
from app.model.status import model_status


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


class ModelStatusTest(unittest.TestCase):
    def test_stub_provider_reports_stub_mode(self):
        payload = model_status(settings())

        self.assertFalse(payload["provider_auth_configured"])
        self.assertEqual(payload["roles"]["chat"]["kind"], "stub")
        self.assertEqual(payload["roles"]["chat"]["effective_mode"], "stub")
        self.assertEqual(payload["roles"]["embedding"]["effective_mode"], "stub")

    def test_real_provider_with_complete_config_reports_real_with_fallback(self):
        payload = model_status(
            settings(
                chat_provider="volcengine",
                chat_model_id="ep-chat",
                ark_api_key="secret",
                memory_llm_extractor_enabled=True,
            )
        )

        self.assertTrue(payload["provider_auth_configured"])
        self.assertTrue(payload["memory_llm_extractor_enabled"])
        self.assertEqual(payload["roles"]["chat"]["kind"], "real")
        self.assertEqual(payload["roles"]["chat"]["effective_mode"], "real_with_fallback")
        self.assertEqual(payload["roles"]["chat"]["missing"], [])

    def test_missing_real_provider_config_reports_fallback_or_misconfigured(self):
        fallback_payload = model_status(settings(chat_provider="volcengine", chat_model_id="ep-chat"))
        strict_payload = model_status(
            settings(chat_provider="volcengine", chat_model_id="ep-chat", fallback_to_stub=False)
        )

        self.assertEqual(fallback_payload["roles"]["chat"]["effective_mode"], "stub_fallback")
        self.assertIn("api_key", fallback_payload["roles"]["chat"]["missing"])
        self.assertEqual(strict_payload["roles"]["chat"]["effective_mode"], "misconfigured")

    def test_openai_compatible_local_provider_does_not_require_api_key(self):
        payload = model_status(
            settings(
                chat_provider="openai_compatible",
                chat_model_id="local-chat",
                fallback_to_stub=False,
            )
        )

        self.assertFalse(payload["provider_auth_configured"])
        self.assertEqual(payload["roles"]["chat"]["effective_mode"], "real")
        self.assertEqual(payload["roles"]["chat"]["missing"], [])

    def test_real_embedding_is_always_reported_as_fail_closed(self):
        payload = model_status(
            settings(
                embedding_provider="openai_compatible",
                embedding_model_id="local-embedding",
                fallback_to_stub=True,
            )
        )

        self.assertEqual(
            payload["roles"]["embedding"]["effective_mode"],
            "real_fail_closed",
        )
        self.assertFalse(payload["roles"]["embedding"]["fallback_to_stub"])


if __name__ == "__main__":
    unittest.main()
