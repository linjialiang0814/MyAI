from typing import Any, Dict, List

from app.memory.retrieval.retriever import RetrievedMemory


class PromptBuilder:
    @staticmethod
    def build_prompt(
        message: str,
        context: str,
        memories: List[RetrievedMemory],
        task_result: Dict[str, Any],
        knowledge_snippets: List[str] | None = None,
    ) -> str:
        long_term_memory = "\n".join(f"-{m.content}" for m in memories)
        knowledge_block = "\n".join(f"-{snippet}" for snippet in (knowledge_snippets or []))
        conversation = context if context else "(empty)"
        memory_block = long_term_memory if long_term_memory else "(none)"
        knowledge_text = knowledge_block if knowledge_block else "(none)"

        prompt = f"""
            You are a personal AI assistant.
            [Task Result]
            {task_result}
            [Conversation]
            {conversation}
            [Long-term Memory]
            {memory_block}
            [Knowledge Base]
            {knowledge_text}
            [User]
            {message}
        """.strip()

        return prompt
