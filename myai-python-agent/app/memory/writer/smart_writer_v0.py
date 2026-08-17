from typing import Optional, Tuple
import re
from enum import Enum

#importance 可以在验证准确之后删去

class MemoryType(Enum):
    PREFERENCE = "preference"
    FACT = "fact"
    DECISION = "decision"
    GENERAL = "general"

class MemoryImportance(Enum):
    LOW = 1
    MEDIUM = 2
    HIGH = 3

class MemoryToWrite:
    def __init__(self, content: str, mem_type: str, importance: int = 1):
        self.content = content
        self.mem_type = mem_type
        self.importance = importance

class SmartMemoryWriter:
    def __init__(self):
        # 配置
        self.min_words = 3
        self.max_words = 50
        self.importance_threshold = 2  # 重要性阈值

        # 规则配置
        self.rules = [
            self._check_preference,
            self._check_fact,
            self._check_decision,
        ]

        # 关键词权重
        self.keyword_weights = {
            "love": 3, "hate": 3, "prefer": 2, "favorite": 2,
            "always": 2, "never": 2, "important": 3, "significant": 3,
            "plan": 2, "goal": 2, "decision": 2, "change": 2,
        }

    def should_write(self, user_input: str) -> Optional[MemoryToWrite]:
        """
        智能判断是否写入记忆，返回带重要性的记忆对象
        """
        # 基础过滤
        if not self._is_valid_input(user_input):
            return None

        text = user_input.strip().lower()

        # 检查否定
        if self._contains_negation(text):
            # 否定句可能表达重要的不喜欢/不同意，但需要特殊处理
            result = self._handle_negation(text)
            return MemoryToWrite(content=user_input, mem_type=result[0], importance=result[1])

        # 应用所有规则
        results = []
        for rule in self.rules:
            result = rule(text)
            if result:
                results.append(result)

        if not results:
            return None

        # 选择最匹配的结果（最高重要性）
        best_result = max(results, key=lambda x: x[1])  # (mem_type, importance)

        # 计算最终重要性
        final_importance = self._calculate_importance(text, best_result[1])

        # 低于阈值不存储
        if final_importance < self.importance_threshold:
            return None

        return MemoryToWrite(
            content=user_input,
            mem_type=best_result[0],
            importance=final_importance
        )

    def _is_valid_input(self, text: str) -> bool:
        """检查输入是否有效"""
        words = text.strip().split()

        # 长度检查
        if len(words) < self.min_words or len(words) > self.max_words:
            return False

        # 内容检查（排除问候语、简单回应等）
        common_phrases = [
            "hello", "hi", "hey", "good morning", "good afternoon",
            "thanks", "thank you", "ok", "okay", "yes", "no",
            "how are you", "what's up",
        ]

        return True

    @staticmethod
    def _contains_negation(text: str) -> bool:
        """检查文本中是否包含否定"""
        negation_patterns = [
            r"\b(do|does|did) not\b",
            r"\b(don't|doesn't|didn't)\b",
            r"\bnever\b",
            r"\bno\b",
            r"\bnot\b",
        ]

        return any(re.search(pattern, text) for pattern in negation_patterns)

    @staticmethod
    def _handle_negation(text: str) -> Optional[Tuple[str, int]]:
        """处理否定句"""
        # 否定句可能表达重要信息（如不喜欢、不同意）
        # 但通常重要性较低

        # 检查是否是重要的否定
        important_negations = [
            (r"i (don't|do not) like", "preference", 2),
            (r"i (don't|do not) want", "preference", 2),
            (r"i never", "preference", 2),
            (r"i (don't|do not) believe", "opinion", 2),
            (r"i (am|'m) not", "fact", 1),
        ]

        for pattern, mem_type, importance in important_negations:
            if re.search(pattern, text):
                return mem_type, importance

        return None

    @staticmethod
    def _check_preference(text: str) -> Optional[Tuple[str, int]]:
        """检查是否为偏好"""
        patterns = [
            (r"^(i|we) (like|love|enjoy|prefer|adore) ", 3),
            (r"^(i|we) (dislike|hate|can't stand) ", 3),
            (r"(my|our) favorite (is|are) ", 3),
            (r"i (am|'m) (really|very) (into|fond of) ", 2)
        ]

        for pattern, importance in patterns:
            if re.search(pattern, text):
                return "preference", importance

        return None

    @staticmethod
    def _check_fact(text: str) -> Optional[Tuple[str, int]]:
        """检查是否为事实"""
        patterns = [
            (r"^(i|we) (am|are|'m|'re) (a |an )?", 2),
            (r"^(my|our) (name|age|birthday|job|profession) (is|are) ", 3),
            (r"^(i|we) (study|work|live) (at|in) ", 2),
            (r"^(i|we) (have|'ve) (a |an )?", 1),
        ]

        for pattern, importance in patterns:
            if re.search(pattern, text):
                return "fact", importance

        return None

    @staticmethod
    def _check_decision(text: str) -> Optional[Tuple[str, int]]:
        """检查是否为决策"""
        patterns = [
            (r"^(i|we) (will|plan to|intend to|decided to) ", 3),
            (r"^(i|we) ('ll|'m going to|'re going to) ", 3),
            (r"^(my|our) (decision|choice) (is|was) ", 3),
        ]

        for pattern, importance in patterns:
            if re.search(pattern, text):
                return "decision", importance

        return None

    def _calculate_importance(self, text: str, base_importance: int) -> int:
        """计算最终重要性分数"""
        importance = base_importance

        # 根据关键词增加重要性
        for keyword, weight in self.keyword_weights.items():
            if keyword in text:
                importance += weight

        # 根据长度调整
        words = text.split()
        if len(words) > 10:
            importance += 1

        # 限制在合理范围
        return min(max(importance, 1), 10)

# 使用示例
if __name__ == "__main__":
    writer = SmartMemoryWriter()

    test_inputs = [
        "hello I like programming and machine learning",
        "I don't like spicy food",
        "Hi, how are you?",
        "My name is John and I'm a software engineer",
        "I plan to visit Japan next year",
        "Okay",
        "I think AI will change the world",
        "I never want to go there again",
        "The weather is nice today",
    ]

    for input_text in test_inputs:
        res = writer.should_write(input_text)
        if res:
            print(f"✅ 存储: '{input_text}'")
            print(f"   类型: {res.mem_type}, 重要性: {res.importance}")
        else:
            print(f"❌ 不存储: '{input_text}'")
        print()