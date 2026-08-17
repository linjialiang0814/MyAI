from __future__ import annotations

import json
import logging
import re
from typing import Any, Optional

from app.memory.model.mem_types import MemoryType
from app.memory.model.slot_registry import normalize_slot, normalize_value
from app.memory.writer.extractor import MemoryToWrite
from app.model.base import BaseLLM


ALLOWED_MEMORY_TYPES = {memory_type.value for memory_type in MemoryType}
ALLOWED_SCOPES = {"global", "conversation", "topic", "task"}
ALLOWED_SENSITIVITIES = {"normal", "personal", "sensitive"}
logger = logging.getLogger(__name__)


class LLMMemoryExtractor:
    def __init__(self, llm_client: BaseLLM, *, min_confidence: float = 0.45):
        self.llm_client = llm_client
        self.min_confidence = min_confidence

    def extract(self, user_input: str) -> Optional[MemoryToWrite]:
        candidates = self.extract_many(user_input)
        return candidates[0] if candidates else None

    def extract_many(self, user_input: str) -> list[MemoryToWrite]:
        try:
            response = self.llm_client.generate(self._build_prompt(user_input))
        except Exception as exc:
            logger.warning("LLM memory extraction failed; skipping candidate: %s", exc)
            return []
        payloads = self._parse_payloads(response)
        candidates: list[MemoryToWrite] = []
        seen: set[tuple[str, str, str]] = set()
        for payload in payloads:
            candidate = self._candidate_from_payload(payload, user_input)
            if not candidate:
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

    def _candidate_from_payload(self, payload: dict[str, Any], raw: str) -> Optional[MemoryToWrite]:
        if payload.get("should_write") is not True:
            return None

        mem_type = str(payload.get("mem_type", "")).strip().lower()
        if mem_type not in ALLOWED_MEMORY_TYPES or mem_type == MemoryType.GENERAL.value:
            return None

        content = str(payload.get("content", "") or raw).strip()
        slot = normalize_slot(mem_type, str(payload.get("slot", "") or mem_type))
        value = normalize_value(str(payload.get("value", "") or ""))
        if not content or not slot or not value:
            return None

        confidence = self._as_float(payload.get("confidence"), default=0.0)
        if confidence < self.min_confidence:
            return None

        importance = int(round(self._as_float(payload.get("importance"), default=3.0)))
        importance = max(1, min(10, importance))
        reason = str(payload.get("reason", "") or "llm structured memory extraction").strip()
        sensitivity = str(payload.get("sensitivity", "personal") or "personal").strip().lower()
        if sensitivity not in ALLOWED_SENSITIVITIES:
            sensitivity = "personal"
        scope = str(payload.get("scope", "global") or "global").strip().lower()
        if scope not in ALLOWED_SCOPES:
            scope = "global"

        return MemoryToWrite(
            content=content,
            mem_type=mem_type,
            importance=importance,
            confidence=max(0.0, min(1.0, confidence)),
            canonical_key=slot,
            canonical_value=value,
            metadata={
                "slot": slot,
                "value": value,
                "extraction_method": "llm",
                "extraction_reason": reason,
                "sensitivity": sensitivity,
                "scope": scope,
                "update_intent": str(payload.get("update_intent", "") or "").strip().lower(),
            },
        )

    def _parse_payloads(self, text: str) -> list[dict[str, Any]]:
        parsed = self._parse_json(text)
        if isinstance(parsed, list):
            return [item for item in parsed if isinstance(item, dict)]
        if not isinstance(parsed, dict):
            return []
        if parsed.get("should_write") is False:
            return [parsed]
        memories = parsed.get("memories")
        if isinstance(memories, list):
            return [item for item in memories if isinstance(item, dict)]
        return [parsed]

    @staticmethod
    def _parse_json(text: str) -> Any | None:
        cleaned = text.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
            cleaned = re.sub(r"\s*```$", "", cleaned)
        try:
            parsed = json.loads(cleaned)
        except json.JSONDecodeError:
            match = re.search(r"(\{.*\}|\[.*\])", cleaned, flags=re.DOTALL)
            if not match:
                return None
            try:
                parsed = json.loads(match.group(0))
            except json.JSONDecodeError:
                return None
        return parsed

    @staticmethod
    def _as_float(value: Any, *, default: float) -> float:
        try:
            if value in (None, ""):
                return default
            return float(value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _build_prompt(user_input: str) -> str:
        return f"""
You are the memory extraction layer of a personal assistant.
Extract zero or more durable user memories from the user message.

Return pure JSON only. No markdown.

Allowed mem_type values:
- fact: stable personal facts, such as name, major, school, location, job
- preference: likes, dislikes, favorite things, interaction preferences
- decision: plans, goals, commitments
- opinion: stable viewpoints

Use these rules:
- should_write=false for questions, greetings, jokes, temporary chat, or commands not to remember.
- Do not extract secrets, passwords, tokens, bank card numbers, or API keys as accepted facts.
- Use a concise content field that preserves each memory's user meaning.
- Calibrate confidence instead of defaulting to 1.0:
  - 0.85-0.95 for direct, explicit, durable statements
  - 0.65-0.84 for implicit preferences, habits, or inferred durable meaning
  - below 0.65 when the meaning or durability is uncertain
  - use 1.0 only when there is effectively no extraction uncertainty
- Use importance from 1 to 10.
- Use sensitivity normal, personal, or sensitive.
- Use scope global unless the memory is clearly limited to the current conversation, topic, or task.
- Set update_intent to "correction" when the user says actually, correction, moved to, now lives in, 更正一下, 其实, 我搬到, or similar wording.
- Set update_intent to "negation" when the user explicitly withdraws a multi-value memory, such as "I no longer like Python" or "I don't like Python anymore".
- Otherwise set update_intent to an empty string.
- Prefer common slots like name, major, school, location, job, preference, favorite, decision, opinion.

JSON schema for one memory:
{{
  "should_write": true,
  "content": "original or concise memory text",
  "mem_type": "fact|preference|decision|opinion",
  "slot": "major",
  "value": "computer science",
  "confidence": 0.82,
  "importance": 4,
  "sensitivity": "personal",
  "scope": "global",
  "update_intent": "",
  "reason": "brief reason"
}}

When the message contains multiple durable memories, return:
{{
  "should_write": true,
  "memories": [
    {{
      "should_write": true,
      "content": "my major is computer science",
      "mem_type": "fact",
      "slot": "major",
      "value": "computer science",
      "confidence": 0.9,
      "importance": 5,
      "sensitivity": "personal",
      "scope": "global",
      "update_intent": "",
      "reason": "user stated major"
    }}
  ]
}}

If no durable memory should be written:
{{"should_write": false, "reason": "brief reason"}}

User message:
{user_input}
""".strip()
