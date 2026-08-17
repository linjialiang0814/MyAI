from typing import Optional
from dataclasses import dataclass
import re

#step 10 长期记忆写入策略
#重要：在这一步判断mem type并写入
#关键词：记住 不要忘 重要。。。0

@dataclass
class MemoryToWrite:
    content: str
    mem_type: str  # preference / fact / decision


class MemoryWritePolicy:
    """
    长期记忆写入策略（Step 10）
    """
    def should_write_v1(self, content: str) -> Optional[MemoryToWrite]:
        """
        判断一条用户输入是否值得写入长期记忆
        返回 MemoryToWrite 或 None
        """
        text = content.lower()

        # ---------- 规则 1：偏好类 ----------
        if any(kw in text for kw in ["i like", "i prefer", "i love", "i hate"]):
            return MemoryToWrite(
                content=content,
                mem_type="preference"
            )

        # ---------- 规则 2：事实类（自我描述） ----------
        if any(kw in text for kw in ["i am a", "i'm a", "my major is", "i study"]):
            return MemoryToWrite(
                content=content,
                mem_type="fact"
            )

        # ---------- 规则 3：长期决策 ----------
        if any(kw in text for kw in ["i will", "i plan to", "i decided to"]):
            return MemoryToWrite(
                content=content,
                mem_type="decision"
            )

        # ---------- 默认：general ----------
        return MemoryToWrite(
            content = content,
            mem_type = "general"
        )

    #如何分类应更详细考虑
    #可以替换为NLP?

    def should_write_v2(self, content: str) -> Optional[MemoryToWrite]:
        """
        判断一条用户输入是否值得写入长期记忆
        返回 MemoryToWrite 或 None（如果不值得写入）
        """
        text = content.strip().lower()

        # 过滤掉太短或无效的输入
        if len(text.split()) < 3:  # 少于3个词
            return None

        # ---------- 规则 1：偏好类 ----------
        # 使用正则表达式更精确匹配
        preference_patterns = [
            r"^(i|we) (like|love|enjoy|prefer|adore|dislike|hate) ",
            r"(my|our) favorite ",
            r"(i|we) (am|are) (a )?fan of ",
        ]

        for pattern in preference_patterns:
            if re.search(pattern, text):
            # 检查是否为否定
                #if not self._contains_negation(text):
                    return MemoryToWrite(
                        content=content,
                        mem_type="preference"
                    )

        # ---------- 规则 2：事实类（自我描述） ----------
        fact_patterns = [
            r"^(i|we) (am|are|'m|'re) (a |an )?",
            r"^(my|our) (name|age|job|profession|occupation) (is|are) ",
            r"^(i|we) (study|work|live) ",
        ]

        for pattern in fact_patterns:
            if re.search(pattern, text):
                #if not self._contains_negation(text):
                    return MemoryToWrite(
                        content=content,
                        mem_type="fact"
                    )

        # ---------- 规则 3：长期决策 ----------
        decision_patterns = [
            r"^(i|we) (will|plan to|intend to|decided to|going to) ",
            r"^(i|we) ('ll|'m going to) ",
            r"^(my|our) (plan|decision|goal) (is|are) ",
        ]

        for pattern in decision_patterns:
            if re.search(pattern, text):
                #if not self._contains_negation(text):
                    return MemoryToWrite(
                        content=content,
                        mem_type="decision"
                    )

        # ---------- 规则 4：重要陈述 ----------
        # 添加其他重要类型的检测
        important_patterns = [
            r"(important|significant|crucial|essential) (to me|for me|for us)",
            r"(i|we) (think|believe|feel) that ",
            r"(i|we) (have|'ve) (always|never) ",
        ]

        for pattern in important_patterns:
            if re.search(pattern, text):
                return MemoryToWrite(
                    content=content,
                    mem_type="important"
                )

        # ---------- 默认：general ----------
        return MemoryToWrite(
            content = content,
            mem_type = "general"
        )

    #def _contains_negation(self, text: str) -> bool:
    #    """检查文本中是否包含否定词"""
    #    negations = ["don't", "do not", "doesn't", "does not",
    #                "didn't", "did not", "never", "not", "no"]
    #    return any (neg in text for neg in negations)