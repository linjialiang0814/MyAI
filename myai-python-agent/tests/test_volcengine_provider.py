import unittest
from unittest.mock import MagicMock, patch

from app.memory.embedding.volc_embedding import EmbeddingClient
from app.model.volc_llm import VolcengineLLM


class VolcengineProviderLifecycleTest(unittest.TestCase):
    def test_owned_clients_are_closed_exactly_once(self):
        with patch("app.model.volc_llm.httpx.Client"), patch(
            "app.model.volc_llm.OpenAI"
        ) as llm_client_type:
            llm = VolcengineLLM(model_id="ark-chat", api_key="secret")
            llm.close()
            llm.close()

        llm_client_type.return_value.close.assert_called_once_with()

        with patch("app.memory.embedding.volc_embedding.httpx.Client"), patch(
            "app.memory.embedding.volc_embedding.Ark"
        ) as embedding_client_type:
            embedding = EmbeddingClient(model="ark-embedding", api_key="secret")
            embedding.close()
            embedding.close()

        embedding_client_type.return_value.close.assert_called_once_with()

    def test_injected_clients_are_not_owned(self):
        llm_client = MagicMock()
        embedding_client = MagicMock()

        VolcengineLLM(
            model_id="ark-chat",
            api_key="secret",
            client=llm_client,
        ).close()
        EmbeddingClient(
            model="ark-embedding",
            api_key="secret",
            client=embedding_client,
        ).close()

        llm_client.close.assert_not_called()
        embedding_client.close.assert_not_called()

    def test_constructor_failure_closes_http_client(self):
        with patch("app.model.volc_llm.httpx.Client") as http_client_type, patch(
            "app.model.volc_llm.OpenAI",
            side_effect=RuntimeError("sdk init failed"),
        ):
            with self.assertRaisesRegex(RuntimeError, "sdk init failed"):
                VolcengineLLM(model_id="ark-chat", api_key="secret")

        http_client_type.return_value.close.assert_called_once_with()

        with patch(
            "app.memory.embedding.volc_embedding.httpx.Client"
        ) as embedding_http_client_type, patch(
            "app.memory.embedding.volc_embedding.Ark",
            side_effect=RuntimeError("sdk init failed"),
        ):
            with self.assertRaisesRegex(RuntimeError, "sdk init failed"):
                EmbeddingClient(model="ark-embedding", api_key="secret")

        embedding_http_client_type.return_value.close.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
