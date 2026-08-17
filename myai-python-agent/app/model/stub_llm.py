from app.model.base import BaseLLM


SAFE_STUB_RESPONSE = (
    "[StubLLM Safe Fallback]\n"
    "The model response is currently unavailable. Please retry after the model service is stable."
)


class StubLLM(BaseLLM):
    """
    占位式大模型
    """
    def generate(self, prompt: str) -> str:
        # A fallback must never echo the prompt: it may contain conversation
        # history, long-term memories, retrieved documents, or tool output.
        return SAFE_STUB_RESPONSE
