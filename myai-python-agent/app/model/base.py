from abc import ABC, abstractmethod


class BaseLLM(ABC):
    """Common interface for model backends used by chat and planning."""

    @abstractmethod
    def generate(self, prompt: str) -> str:
        """Generate a text response for the given prompt."""

    def close(self) -> None:
        """Release provider resources when the implementation owns any."""
