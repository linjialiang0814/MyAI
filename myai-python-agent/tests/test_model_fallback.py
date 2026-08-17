import unittest

from app.model.base import BaseLLM
from app.model.factory import FallbackLLM
from app.model.stub_llm import StubLLM


class BrokenLLM(BaseLLM):
    def generate(self, prompt: str) -> str:
        raise RuntimeError("provider unavailable")


class RecordingLLM(BaseLLM):
    def __init__(self, response: str):
        self.response = response
        self.calls = 0

    def generate(self, prompt: str) -> str:
        self.calls += 1
        return self.response


class ModelFallbackTest(unittest.TestCase):
    def test_generation_failure_falls_back_to_stub(self):
        llm = FallbackLLM(primary=BrokenLLM(), fallback=StubLLM(), role="chat")

        secret_prompt = "conversation history: ARK_API_KEY=super-secret-value"
        reply = llm.generate(secret_prompt)

        self.assertIn("[StubLLM Safe Fallback]", reply)
        self.assertNotIn(secret_prompt, reply)
        self.assertNotIn("super-secret-value", reply)

    def test_stub_never_echoes_prompt(self):
        secret_prompt = "memory: password=hunter2; document: private contents"

        reply = StubLLM().generate(secret_prompt)

        self.assertIn("[StubLLM Safe Fallback]", reply)
        self.assertNotIn(secret_prompt, reply)
        self.assertNotIn("hunter2", reply)

    def test_circuit_breaker_is_isolated_per_llm_instance(self):
        chat = FallbackLLM(primary=BrokenLLM(), fallback=StubLLM(), role="chat")
        memory_primary = RecordingLLM("real memory response")
        memory = FallbackLLM(primary=memory_primary, fallback=StubLLM(), role="memory")

        self.assertIn("[StubLLM Safe Fallback]", chat.generate("chat"))
        self.assertEqual(memory.generate("memory"), "real memory response")
        self.assertEqual(memory_primary.calls, 1)


if __name__ == "__main__":
    unittest.main()
