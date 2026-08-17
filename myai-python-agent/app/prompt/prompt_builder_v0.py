from typing import List, Dict, Any
from app.memory.retrieval.retriever import RetrievedMemory
from app.task.stats.record import DecisionRecord

#如何编写prompt还需要更加详细的考虑。

class PromptBuilder:

    @staticmethod
    def build_prompt(message: str, context: str, memories: List[RetrievedMemory])->str:
        long_term_memory = "\n".join(
            f"-{m.content}" for m in memories
        )

        prompt = f"""
            You are a personal AI assistant.
            [Conversation]
            {context}
            [Long-term Memory]
            {long_term_memory} 
            [User]
            {message}
        """.strip()

        return prompt

    @staticmethod
    def build_task_prompt(decision: DecisionRecord)->str:
        return f"""
            User message: {decision.content}
            Action taken:
            Plan: {decision.plan}
            Tool Name: {decision.plan["tool_name"]}
            Tool Input: {decision.plan["tool_args"]}
            Observation: {decision.result}
        """
    #比build_prompt多加相关于tool的参数即可