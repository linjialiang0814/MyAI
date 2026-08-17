import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np

from app.memory.embedding.factory import create_embedding_client
from app.memory.embedding.openai_compatible_embedding import OpenAICompatibleEmbedding
from app.model.config import LLMSettings, load_llm_settings
from app.model.factory import create_llm
from app.model.openai_compatible_llm import OpenAICompatibleLLM


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


class _FakeChatCompletions:
    def __init__(self):
        self.request = None

    def create(self, **request):
        self.request = request
        message = SimpleNamespace(content="  local response  ")
        return SimpleNamespace(choices=[SimpleNamespace(message=message)])


class _FakeChatClient:
    def __init__(self):
        self.completions = _FakeChatCompletions()
        self.chat = SimpleNamespace(completions=self.completions)


class _FakeEmbeddingClient:
    def __init__(self, vector):
        self.vector = vector
        self.request = None
        self.embeddings = self

    def create(self, **request):
        self.request = request
        return SimpleNamespace(data=[SimpleNamespace(embedding=self.vector)])


class _FlakyEmbedding:
    def __init__(self):
        self.calls = 0

    def embed(self, text: str):
        self.calls += 1
        if self.calls == 1:
            return np.array([0.1, 0.2, 0.3], dtype=np.float32)
        raise RuntimeError("embedding server unavailable")


class OpenAICompatibleProviderTest(unittest.TestCase):
    def test_default_endpoint_is_loopback_and_experiment_controls_are_stable(self):
        with patch.dict(os.environ, {}, clear=True):
            loaded = load_llm_settings()

        self.assertEqual(loaded.openai_compatible_base_url, "http://127.0.0.1:11434/v1")
        self.assertEqual(
            loaded.openai_compatible_embedding_base_url,
            "http://127.0.0.1:11434/v1",
        )
        self.assertEqual(loaded.llm_seed, 42)
        self.assertEqual(loaded.llm_max_tokens, 512)
        self.assertEqual(loaded.llm_max_retries, 0)

    def test_embedding_key_is_inherited_only_for_the_same_endpoint(self):
        shared = {
            "MYAI_OPENAI_COMPATIBLE_BASE_URL": "https://chat.example/v1/",
            "MYAI_OPENAI_COMPATIBLE_API_KEY": "chat-secret",
        }
        with patch.dict(os.environ, shared, clear=True):
            loaded = load_llm_settings()
        self.assertEqual(loaded.openai_compatible_embedding_api_key, "chat-secret")

        separate = {
            **shared,
            "MYAI_OPENAI_COMPATIBLE_EMBEDDING_BASE_URL": "http://127.0.0.1:11434/v1",
            "MYAI_OPENAI_COMPATIBLE_EMBEDDING_API_KEY": "",
        }
        with patch.dict(os.environ, separate, clear=True):
            loaded = load_llm_settings()
        self.assertEqual(loaded.openai_compatible_embedding_api_key, "")

    def test_config_rejects_non_finite_float_values(self):
        for name in (
            "MYAI_LLM_TEMPERATURE",
            "MYAI_LLM_REQUEST_TIMEOUT_SECONDS",
            "MYAI_EMBEDDING_REQUEST_TIMEOUT_SECONDS",
        ):
            for value in ("nan", "inf", "+inf", "-inf"):
                with self.subTest(name=name, value=value), patch.dict(
                    os.environ,
                    {name: value},
                    clear=True,
                ):
                    with self.assertRaisesRegex(ValueError, "must be finite"):
                        load_llm_settings()

    def test_config_limits_temperature_to_openai_supported_range(self):
        for value in ("-0.01", "2.01"):
            with self.subTest(value=value), patch.dict(
                os.environ,
                {"MYAI_LLM_TEMPERATURE": value},
                clear=True,
            ):
                with self.assertRaises(ValueError):
                    load_llm_settings()

        for value in ("0", "2"):
            with self.subTest(value=value), patch.dict(
                os.environ,
                {"MYAI_LLM_TEMPERATURE": value},
                clear=True,
            ):
                self.assertEqual(load_llm_settings().temperature, float(value))

    def test_chat_client_forwards_seed_max_tokens_and_generation_settings(self):
        client = _FakeChatClient()
        llm = OpenAICompatibleLLM(
            model_id="local-chat",
            temperature=0.0,
            timeout_seconds=12,
            max_retries=0,
            seed=123,
            max_tokens=321,
            client=client,
        )

        reply = llm.generate("hello")

        self.assertEqual(reply, "local response")
        self.assertEqual(client.completions.request["model"], "local-chat")
        self.assertEqual(client.completions.request["temperature"], 0.0)
        self.assertEqual(client.completions.request["seed"], 123)
        self.assertEqual(client.completions.request["max_tokens"], 321)
        self.assertEqual(client.completions.request["messages"][-1]["content"], "hello")

    def test_chat_client_rejects_missing_choices(self):
        client = _FakeChatClient()
        with patch.object(
            client.completions,
            "create",
            return_value=SimpleNamespace(choices=[]),
        ):
            llm = OpenAICompatibleLLM(model_id="local-chat", client=client)
            with self.assertRaisesRegex(RuntimeError, "no completion choices"):
                llm.generate("hello")

    def test_chat_client_rejects_empty_content(self):
        for content in (None, "", "   "):
            with self.subTest(content=content):
                client = _FakeChatClient()
                response = SimpleNamespace(
                    choices=[SimpleNamespace(message=SimpleNamespace(content=content))]
                )
                with patch.object(client.completions, "create", return_value=response):
                    llm = OpenAICompatibleLLM(model_id="local-chat", client=client)
                    with self.assertRaisesRegex(RuntimeError, "empty text content"):
                        llm.generate("hello")

    def test_factory_does_not_hide_initialization_failure_when_fallback_is_disabled(self):
        configured = settings(
            chat_provider="openai_compatible",
            chat_model_id="local-chat",
            fallback_to_stub=False,
        )
        with patch(
            "app.model.factory.OpenAICompatibleLLM",
            side_effect=RuntimeError("local server unavailable"),
        ):
            with self.assertRaisesRegex(RuntimeError, "local server unavailable"):
                create_llm("chat", configured)

    def test_embedding_accepts_only_finite_vector_with_expected_dimensions(self):
        client = _FakeEmbeddingClient([0.1, 0.2, 0.3])
        embedding = OpenAICompatibleEmbedding(
            model="local-embedding",
            expected_dimensions=3,
            client=client,
        )

        vector = embedding.embed("knowledge")

        self.assertEqual(vector.dtype, np.float32)
        self.assertEqual(vector.tolist(), np.array([0.1, 0.2, 0.3], dtype=np.float32).tolist())
        self.assertEqual(client.request, {"model": "local-embedding", "input": "knowledge"})

    def test_embedding_rejects_non_finite_and_wrong_dimension_responses(self):
        for vector, message in [
            ([0.1, float("nan")], "non-finite"),
            ([0.1, 0.2], "dimension mismatch"),
        ]:
            with self.subTest(vector=vector):
                embedding = OpenAICompatibleEmbedding(
                    model="local-embedding",
                    expected_dimensions=3,
                    client=_FakeEmbeddingClient(vector),
                )
                with self.assertRaisesRegex(ValueError, message):
                    embedding.embed("knowledge")

    def test_embedding_factory_does_not_hide_failure_when_fallback_is_disabled(self):
        configured = settings(
            embedding_provider="openai_compatible",
            embedding_model_id="local-embedding",
            fallback_to_stub=False,
        )
        with patch(
            "app.memory.embedding.factory.OpenAICompatibleEmbedding",
            side_effect=RuntimeError("embedding server unavailable"),
        ):
            with self.assertRaisesRegex(RuntimeError, "embedding server unavailable"):
                create_embedding_client(configured)

    def test_embedding_factory_is_fail_closed_even_when_llm_fallback_is_enabled(self):
        configured = settings(
            embedding_provider="openai_compatible",
            embedding_model_id="local-embedding",
            fallback_to_stub=True,
        )
        with patch(
            "app.memory.embedding.factory.OpenAICompatibleEmbedding",
            side_effect=RuntimeError("embedding server unavailable"),
        ):
            with self.assertRaisesRegex(RuntimeError, "embedding server unavailable"):
                create_embedding_client(configured)

    def test_embedding_runtime_failure_never_switches_to_stub_vector(self):
        primary = _FlakyEmbedding()
        configured = settings(
            embedding_provider="openai_compatible",
            embedding_model_id="local-embedding",
            embedding_expected_dimensions=3,
            fallback_to_stub=True,
        )
        with patch(
            "app.memory.embedding.factory.OpenAICompatibleEmbedding",
            return_value=primary,
        ):
            embedding = create_embedding_client(configured)

        self.assertEqual(embedding.embed("first").shape, (3,))
        with self.assertRaisesRegex(RuntimeError, "embedding server unavailable"):
            embedding.embed("second")

    def test_unknown_embedding_provider_never_falls_back_to_stub(self):
        configured = settings(embedding_provider="typo", fallback_to_stub=True)

        with self.assertRaisesRegex(ValueError, "Unsupported embedding provider"):
            create_embedding_client(configured)

    def test_owned_sdk_clients_are_closed_exactly_once(self):
        with patch("app.model.openai_compatible_llm.httpx.Client"), patch(
            "app.model.openai_compatible_llm.OpenAI"
        ) as llm_client_type:
            llm = OpenAICompatibleLLM(model_id="local-chat")
            llm.close()
            llm.close()

        llm_client_type.return_value.close.assert_called_once_with()

        with patch("app.memory.embedding.openai_compatible_embedding.httpx.Client"), patch(
            "app.memory.embedding.openai_compatible_embedding.OpenAI"
        ) as embedding_client_type:
            embedding = OpenAICompatibleEmbedding(model="local-embedding")
            embedding.close()
            embedding.close()

        embedding_client_type.return_value.close.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
