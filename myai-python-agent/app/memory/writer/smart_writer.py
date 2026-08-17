import re
from typing import Optional, Sequence

from app.memory.model.mem_types import MemoryType
from app.memory.writer.extractor import MemoryToWrite, StructuredMemoryExtractor
from app.memory.writer.llm_extractor import LLMMemoryExtractor
from app.model.config import load_llm_settings
from app.model.factory import create_llm


class RuleBasedMemoryExtractor:
    def __init__(self):
        self.min_words = 3
        self.max_words = 60
        self.importance_threshold = 2
        self.common_phrases = {
            "hello", "hi", "hey", "thanks", "thank you", "ok", "okay", "yes", "no",
            "good morning", "good afternoon", "good evening", "how are you", "what's up",
            "你好", "您好", "嗨", "谢谢", "好的", "是的", "不是", "再见",
        }

    def extract(self, user_input: str) -> Optional[MemoryToWrite]:
        candidates = self.extract_many(user_input)
        return candidates[0] if candidates else None

    def extract_many(self, user_input: str) -> list[MemoryToWrite]:
        if not self._is_valid_input(user_input):
            return []

        text = user_input.strip().lower()
        segment_candidates = self._extract_segment_candidates(user_input)
        if len(segment_candidates) > 1:
            return segment_candidates

        result = (
            self._extract_preference(text, user_input)
            or self._extract_fact(text, user_input)
            or self._extract_decision(text, user_input)
            or self._extract_opinion(text, user_input)
        )
        if not result:
            return []
        if result.importance < self.importance_threshold:
            return []
        return [result]

    def _extract_segment_candidates(self, user_input: str) -> list[MemoryToWrite]:
        segments = self._split_candidate_segments(user_input)
        if len(segments) <= 1:
            return []
        candidates: list[MemoryToWrite] = []
        seen: set[tuple[str, str, str]] = set()
        for segment in segments:
            text = segment.strip().lower()
            if not self._is_valid_input(segment):
                continue
            candidate = (
                self._extract_preference(text, segment)
                or self._extract_fact(text, segment)
                or self._extract_decision(text, segment)
                or self._extract_opinion(text, segment)
            )
            if not candidate or candidate.importance < self.importance_threshold:
                continue
            key = (
                candidate.mem_type,
                str(candidate.metadata.get("slot", "")),
                str(candidate.metadata.get("value", "")),
            )
            if key in seen:
                continue
            seen.add(key)
            candidates.append(candidate)
        return candidates

    def _is_valid_input(self, text: str) -> bool:
        normalized = text.strip().lower()
        if normalized in self.common_phrases:
            return False
        if normalized.endswith("?") or normalized.endswith("？"):
            return False

        if self._contains_chinese(normalized):
            effective_length = len(re.sub(r"\s+", "", normalized))
            return 3 <= effective_length <= 80

        words = normalized.split()
        return self.min_words <= len(words) <= self.max_words

    def _extract_preference(self, text: str, raw: str) -> Optional[MemoryToWrite]:
        negation_patterns = [
            r"^i (no longer|don't|do not) (like|love|enjoy|prefer) (?P<value>.+?)( anymore)?$",
            r"^i used to (like|love|enjoy|prefer) (?P<value>.+?) but (now )?(i )?(don't|do not|no longer).*$",
            r"^\u6211\u4e0d\u518d(\u559c\u6b22|\u7231|\u504f\u597d)(?P<value>.+)$",
            r"^\u6211\u5df2\u7ecf\u4e0d(\u559c\u6b22|\u7231|\u504f\u597d)(?P<value>.+)$",
            r"^\u6211\u73b0\u5728\u4e0d(\u559c\u6b22|\u7231|\u504f\u597d)(?P<value>.+)$",
        ]
        for pattern in negation_patterns:
            m = re.search(pattern, text)
            if not m:
                continue
            value = self._clean_value(m.groupdict().get("value", ""))
            return MemoryToWrite(
                content=raw,
                mem_type=MemoryType.PREFERENCE.value,
                importance=4,
                confidence=0.9,
                canonical_key="preference",
                canonical_value=value,
                metadata={
                    "slot": "preference",
                    "value": value,
                    "update_intent": "negation",
                    "negation_signal": "explicit",
                },
            )

        patterns = [
            (r"^我最喜欢的(?P<key>[^是]+)是(?P<value>.+)$", 5, None),
            (r"^i (like|love|enjoy|prefer|hate|dislike) (?P<value>.+)$", 4, "preference"),
            (r"^my favorite (?P<key>[a-z ]{1,25}) is (?P<value>.+)$", 5, None),
            (r"^i don't like (?P<value>.+)$", 4, "preference"),
            (r"^我喜欢(?P<value>.+)$", 4, "preference"),
            (r"^我很喜欢(?P<value>.+)$", 4, "preference"),
            (r"^我最喜欢(?P<value>.+)$", 5, "favorite"),
            (r"^我不喜欢(?P<value>.+)$", 4, "preference"),
            (r"^我讨厌(?P<value>.+)$", 4, "preference"),
            (r"^我比较喜欢(?P<value>.+)$", 4, "preference"),
            (r"^我更喜欢(?P<value>.+)$", 4, "preference"),
        ]
        for pattern, importance, default_key in patterns:
            m = re.search(pattern, text)
            if not m:
                continue
            key = (m.groupdict().get("key") or default_key or "preference").strip()
            key = self._normalize_slot(key)
            value = self._clean_value(m.groupdict().get("value", ""))
            return MemoryToWrite(
                content=raw,
                mem_type=MemoryType.PREFERENCE.value,
                importance=importance,
                confidence=0.9,
                canonical_key=key,
                canonical_value=value,
                metadata={"slot": key, "value": value},
            )
        return None

    def _extract_fact(self, text: str, raw: str) -> Optional[MemoryToWrite]:
        patterns = [
            (r"^my (?P<key>name|major|birthday|job|profession|occupation) is (?P<value>.+)$", 5, None),
            (r"^i (am|study|work|live) (?P<value>.+)$", 3, None),
            (r"^i moved to (?P<value>.+)$", 5, "location"),
            (r"^i now live in (?P<value>.+)$", 5, "location"),
            (r"^i currently live in (?P<value>.+)$", 5, "location"),
            (r"^我搬到(?P<value>.+)$", 5, "location"),
            (r"^我现在住在(?P<value>.+)$", 5, "location"),
            (r"^我目前住在(?P<value>.+)$", 5, "location"),
            (r"^i am a[n]? (?P<value>.+)$", 4, "identity"),
            (r"^我叫(?P<value>.+)$", 5, "name"),
            (r"^我的名字是(?P<value>.+)$", 5, "name"),
            (r"^我的专业是(?P<value>.+)$", 5, "major"),
            (r"^我是(?P<value>.+)专业的?$", 5, "major"),
            (r"^我在(?P<value>.+)上学$", 4, "school"),
            (r"^我在(?P<value>.+)读书$", 4, "school"),
            (r"^我住在(?P<value>.+)$", 4, "location"),
            (r"^我家在(?P<value>.+)$", 4, "hometown"),
            (r"^我是(?P<value>.+)$", 3, "identity"),
            (r"^我的职业是(?P<value>.+)$", 5, "job"),
            (r"^我的工作是(?P<value>.+)$", 5, "job"),
            (r"^我在(?P<value>.+)工作$", 4, "work"),
            (r"^我的生日是(?P<value>.+)$", 5, "birthday"),
        ]
        for pattern, importance, default_key in patterns:
            m = re.search(pattern, text)
            if not m:
                continue
            key = m.groupdict().get("key")
            if not key:
                key = self._infer_fact_key(text, default_key)
            key = self._normalize_slot(key)
            value = self._clean_value(m.groupdict().get("value", ""))
            return MemoryToWrite(
                content=raw,
                mem_type=MemoryType.FACT.value,
                importance=importance,
                confidence=0.85,
                canonical_key=key,
                canonical_value=value,
                metadata={"slot": key, "value": value},
            )
        return None

    def _extract_decision(self, text: str, raw: str) -> Optional[MemoryToWrite]:
        patterns = [
            (r"^i (will|plan to|intend to|decided to|am going to) (?P<value>.+)$", 5),
            (r"^my (plan|decision|goal) is to (?P<value>.+)$", 5),
            (r"^我打算(?P<value>.+)$", 5),
            (r"^我准备(?P<value>.+)$", 5),
            (r"^我计划(?P<value>.+)$", 5),
            (r"^我决定(?P<value>.+)$", 5),
            (r"^我的计划是(?P<value>.+)$", 5),
            (r"^我的目标是(?P<value>.+)$", 5),
            (r"^我想要(?P<value>.+)$", 4),
            (r"^我今年想(?P<value>.+)$", 5),
        ]
        for pattern, importance in patterns:
            m = re.search(pattern, text)
            if not m:
                continue
            value = self._clean_value(m.groupdict().get("value", ""))
            return MemoryToWrite(
                content=raw,
                mem_type=MemoryType.DECISION.value,
                importance=importance,
                confidence=0.88,
                canonical_key="decision",
                canonical_value=value,
                metadata={"slot": "decision", "value": value},
            )
        return None

    def _extract_opinion(self, text: str, raw: str) -> Optional[MemoryToWrite]:
        patterns = [
            (r"^my opinion on (?P<value>.+)$", 4),
            (r"^i (think|believe) (?P<value>.+)$", 4),
            (r"^我觉得(?P<value>.+)$", 4),
            (r"^我认为(?P<value>.+)$", 4),
            (r"^我相信(?P<value>.+)$", 4),
            (r"^在我看来(?P<value>.+)$", 4),
            (r"^我的看法是(?P<value>.+)$", 4),
            (r"^我感觉(?P<value>.+)$", 3),
        ]
        for pattern, importance in patterns:
            m = re.search(pattern, text)
            if not m:
                continue
            value = self._clean_value(m.groupdict().get("value", ""))
            return MemoryToWrite(
                content=raw,
                mem_type=MemoryType.OPINION.value,
                importance=importance,
                confidence=0.88,
                canonical_key="opinion",
                canonical_value=value,
                metadata={"slot": "opinion", "value": value},
            )
        return None

    @staticmethod
    def _contains_chinese(text: str) -> bool:
        return re.search(r"[\u4e00-\u9fff]", text) is not None

    @staticmethod
    def _split_candidate_segments(user_input: str) -> list[str]:
        normalized = re.sub(r"\s+", " ", user_input.strip())
        if not normalized:
            return []
        parts = re.split(r"\s*(?:;|；|。|，|,|\band\b|\balso\b)\s+", normalized, flags=re.IGNORECASE)
        return [part.strip() for part in parts if part.strip()]

    @staticmethod
    def _clean_value(value: str) -> str:
        return value.strip().strip("。！？；，,.!?;: ")

    @staticmethod
    def _normalize_slot(slot: str) -> str:
        slot = slot.strip().replace(" ", "_")
        mapping = {
            "名字": "name",
            "姓名": "name",
            "专业": "major",
            "学校": "school",
            "住址": "location",
            "城市": "location",
            "家乡": "hometown",
            "职业": "job",
            "工作": "work",
            "生日": "birthday",
            "favorite": "favorite",
            "preference": "preference",
        }
        return mapping.get(slot, slot)

    @staticmethod
    def _infer_fact_key(text: str, default_key: Optional[str]) -> str:
        if default_key:
            return default_key
        if text.startswith("i live"):
            return "location"
        if text.startswith("i study"):
            return "study"
        if text.startswith("i work"):
            return "work"
        return "identity"


class SmartMemoryWriter:
    NEGATIVE_MEMORY_COMMANDS = (
        "don't remember this",
        "do not remember this",
        "dont remember this",
        "don't save this",
        "do not save this",
        "don't store this",
        "do not store this",
        "forget this",
        "please forget this",
        "不要记住",
        "别记",
        "不要保存",
        "别保存",
        "不要记录",
        "别记录",
    )

    def __init__(self, extractors: Sequence[StructuredMemoryExtractor] | None = None):
        self.extractors = list(extractors or [RuleBasedMemoryExtractor()])

    def should_write(self, user_input: str) -> Optional[MemoryToWrite]:
        candidates = self.extract_candidates(user_input)
        return candidates[0] if candidates else None

    def extract_candidates(self, user_input: str) -> list[MemoryToWrite]:
        if self._is_negative_memory_command(user_input):
            return []
        extraction_input, update_intent = self._prepare_input(user_input)
        for extractor in self.extractors:
            candidates = _extract_many(extractor, extraction_input)
            if candidates:
                if update_intent:
                    for candidate in candidates:
                        candidate.content = user_input
                        candidate.metadata["update_intent"] = update_intent
                        candidate.metadata["correction_signal"] = "explicit"
                return candidates
        return []

    @classmethod
    def _is_negative_memory_command(cls, user_input: str) -> bool:
        text = user_input.strip().lower()
        return any(command in text for command in cls.NEGATIVE_MEMORY_COMMANDS)

    @classmethod
    def _prepare_input(cls, user_input: str) -> tuple[str, str | None]:
        stripped = user_input.strip()
        correction_prefixes = (
            "actually",
            "correction",
            "correction:",
            "update:",
            "to be precise",
            "更正一下",
            "纠正一下",
            "其实",
            "准确地说",
        )
        lower = stripped.lower()
        for prefix in correction_prefixes:
            normalized_prefix = prefix.lower()
            if lower.startswith(normalized_prefix):
                remainder = stripped[len(prefix):].lstrip(" ,:：，")
                if remainder:
                    return remainder, "correction"
        if re.search(r"\b(i moved to|i now live in|i currently live in)\b", lower):
            return stripped, "correction"
        if any(signal in stripped for signal in ("我搬到", "我现在住在", "我目前住在")):
            return stripped, "correction"
        return stripped, None


def build_memory_writer(settings=None, llm_client=None) -> SmartMemoryWriter:
    settings = settings or load_llm_settings()
    extractors: list[StructuredMemoryExtractor] = [RuleBasedMemoryExtractor()]
    if settings.memory_llm_extractor_enabled:
        extractor_llm = llm_client if llm_client is not None else create_llm(role="memory", settings=settings)
        extractors.append(LLMMemoryExtractor(extractor_llm))
    return SmartMemoryWriter(extractors=extractors)


def _extract_many(extractor: StructuredMemoryExtractor, user_input: str) -> list[MemoryToWrite]:
    if hasattr(extractor, "extract_many"):
        return list(extractor.extract_many(user_input))
    candidate = extractor.extract(user_input)
    return [candidate] if candidate else []
