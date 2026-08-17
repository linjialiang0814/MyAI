from app.memory.embedding.openai_compatible_embedding import OpenAICompatibleEmbedding
from app.memory.embedding.stub_embedding import StubEmbedding
from app.memory.embedding.volc_embedding import EmbeddingClient
from app.model.config import LLMSettings, load_llm_settings

def create_embedding_client(settings: LLMSettings | None = None):
    settings = settings or load_llm_settings()
    provider = settings.embedding_provider

    if provider == "stub":
        return StubEmbedding()

    if provider == "volcengine":
        return EmbeddingClient(
            model=settings.embedding_model_id,
            api_key=settings.ark_api_key,
            expected_dimensions=settings.embedding_expected_dimensions,
        )

    if provider == "openai_compatible":
        return OpenAICompatibleEmbedding(
            model=settings.embedding_model_id,
            base_url=settings.openai_compatible_embedding_base_url,
            api_key=settings.openai_compatible_embedding_api_key,
            timeout_seconds=settings.embedding_request_timeout_seconds,
            max_retries=settings.embedding_max_retries,
            expected_dimensions=settings.embedding_expected_dimensions,
            trust_env_proxy=settings.model_trust_env_proxy,
        )

    raise ValueError(f"Unsupported embedding provider: {provider}")
