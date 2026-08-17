from collections import OrderedDict
from threading import RLock
from typing import List


class ConversationContext:
    """In-memory short-term conversation context manager."""

    def __init__(self, max_turns: int = 6, max_conversations: int = 1_000):
        self.max_turns = max_turns
        self.max_conversations = max(1, int(max_conversations))
        self.memory: OrderedDict[str, List[dict[str, str]]] = OrderedDict()
        self._lock = RLock()

    def add_user_message(self, user_id: str, message: str) -> None:
        self._add_message(user_id, "user", message)

    def add_assistant_message(self, user_id: str, message: str) -> None:
        self._add_message(user_id, "assistant", message)

    def _add_message(self, user_id: str, role: str, message: str) -> None:
        with self._lock:
            if user_id not in self.memory:
                self._ensure_capacity()
                self.memory[user_id] = []

            self.memory[user_id].append({"role": role, "content": message})
            self.memory.move_to_end(user_id)

            max_messages = self.max_turns * 2
            if len(self.memory[user_id]) > max_messages:
                self.memory[user_id] = self.memory[user_id][-max_messages:]

    def get_context(self, user_id: str) -> str:
        with self._lock:
            if user_id not in self.memory:
                return ""
            self.memory.move_to_end(user_id)
            items = list(self.memory[user_id])

        lines: List[str] = []
        for item in items:
            role = item.get("role", "user")
            content = item.get("content", "")
            prefix = "User" if role == "user" else "Assistant"
            lines.append(f"{prefix}: {content}")
        return "\n".join(lines)

    def load_history(self, user_id: str, history: List[dict[str, str]] | None) -> str:
        if not history:
            return self.get_context(user_id)

        normalized: List[dict[str, str]] = []
        for item in history:
            role = item.get("role", "user")
            content = item.get("content", "")
            normalized.append({"role": role, "content": content})
        with self._lock:
            if user_id not in self.memory:
                self._ensure_capacity()
            self.memory[user_id] = normalized[-self.max_turns * 2:]
            self.memory.move_to_end(user_id)
        return self.get_context(user_id)

    def _ensure_capacity(self) -> None:
        while len(self.memory) >= self.max_conversations:
            self.memory.popitem(last=False)
