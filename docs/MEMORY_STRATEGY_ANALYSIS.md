# Memory Strategy Analysis

## Current Shape

The current memory pipeline is intentionally simple:

- Recognition is rule-based in `SmartMemoryWriter`.
- Extracted memories carry a type, confidence, importance, slot, and value.
- Deduplication first checks same type plus same slot/value, then falls back to semantic vector similarity.
- Conflict handling checks same type plus same slot but different value for selected types.
- Governance now adds source, confidence, sensitivity, scope, review status, and confirmation queue behavior.

This is a solid local-first baseline. Its main weakness is that memory quality depends heavily on whether a sentence matches a known pattern and whether the rule extracts a good slot/value pair.

## Improvement Areas

### 1. Memory Recognition

Current issue: rules have high precision for known phrasings but low recall for natural language.

Examples:

- "I have been using Python for most side projects lately" may be a useful preference or skill signal, but it is not a direct "I like X" pattern.
- "Don't remember this" and "just joking" should suppress writing.
- Chinese patterns need cleanup and expansion because parts of the current source show mojibake text.

Recommended upgrade:

- Keep rules as a fast high-precision layer.
- Add a structured LLM extractor behind the rules for uncertain cases.
- Require the extractor to return JSON with:
  - `should_write`
  - `content`
  - `mem_type`
  - `slot`
  - `value`
  - `confidence`
  - `importance`
  - `sensitivity`
  - `scope`
  - `reason`
- Send low-confidence LLM results to pending instead of accepting automatically.

Near-term task:

- Status: baseline implemented.
- Current rule patterns have been cleaned into UTF-8 Chinese and English patterns.
- Negative-memory commands now short-circuit memory writing before extraction.
- `SmartMemoryWriter` now uses a pluggable structured extractor interface.

Next task:

- Status: baseline implemented.
- A feature-flagged structured LLM extractor now runs behind the rule extractor.
- Invalid JSON, unsupported memory types, missing slot/value, and very low confidence candidates are rejected.
- Low-confidence but usable LLM results flow into the existing pending review policy.

Next task:

- Status: initial live calibration implemented and run against the configured real model.
- The current 12-case English and Chinese calibration baseline passes 12/12.
- Confidence saturation discovered during the first run was corrected with an explicit confidence rubric.
- Continue expanding the eval fixture with misses discovered in actual local conversations.
- Add multi-candidate extraction when a single message contains several durable memories.

### 2. Slot And Value Modeling

Current issue: dedup and conflict depend on string slot/value equality.

This works for simple facts like `major=computer science`, but struggles with:

- aliases: `CS`, `computer science`, `计算机科学`
- broad vs specific values: `AI` vs `machine learning`
- time changes: `I live in Chengdu` vs `I moved to Shanghai`
- multi-valued preferences: liking both Python and JavaScript should not conflict

Recommended upgrade:

- Introduce a memory schema registry per memory type.
- Define whether a slot is single-value or multi-value.
- Normalize slot aliases before storage.
- Normalize common value aliases before conflict checks.
- Add `valid_from`, `valid_to`, and `observed_at` for time-sensitive facts.

Status:

- Baseline slot registry implemented for `fact`, `preference`, `decision`, and `opinion`.
- The first version includes:
  - `slot`
  - `aliases`
  - `cardinality`
  - `conflict_policy`
- New memory metadata is enriched with normalized slot/value and policy fields.
- Deduplication and conflict handling now use normalized slot/value policy.

Next task:

- Status: baseline implemented.
- New governed memories now receive temporal fields:
  - `observed_at`
  - `valid_from`
  - `valid_to`
  - `is_current`
- Single-value fact conflicts now preserve the old memory as historical and mark the new memory as current.
- Historical memories stay visible in the memory list but are excluded from normal chat retrieval through the existing `superseded` status.

Next task:

- Status: baseline implemented.
- Explicit correction detection now marks candidates with `update_intent=correction`.
- Correction-aware conflict handling records corrected historical reasons.
- The memory profile UI can filter all, current, and historical memories.

Next task:

- Add negation-aware updates for multi-value memories, such as "I no longer like X".
- Add edit-before-accept for pending memories.

### 3. Deduplication

Current issue: semantic dedup uses a single threshold and merges by updating the old metadata with the new metadata.

Risks:

- False merge: similar but distinct memories become one.
- Metadata overwrite: a lower-quality new memory can overwrite useful old metadata.
- No audit trail: merged sources are not preserved clearly.

Recommended upgrade:

- Use a two-stage dedup:
  - exact canonical key/value
  - semantic candidate plus entailment or structured comparison
- Preserve `merged_from` source ids and source refs.
- Merge confidence and importance using explicit rules, not blind metadata update.
- Send uncertain dedup decisions to pending.

Near-term task:

- Change merge metadata to keep `merged_from`, `merged_count`, and `last_merged_at`.

### 4. Conflict Handling

Current issue: conflict means same type and slot, different value.

This is good for simple single-value facts but not enough for:

- preferences that can coexist
- historical changes
- uncertain corrections
- contradictory opinions

Recommended upgrade:

- Conflict policy should depend on slot cardinality.
- Single-value slots should supersede old memories.
- Multi-value slots should append unless the user explicitly negates a prior value.
- Temporal facts should preserve history and mark current value.
- Uncertain conflicts should enter confirmation queue.

Near-term task:

- Expand conflict handling to preserve historical facts instead of only superseding them.
- Route uncertain single-value conflicts to pending when confidence is low or source quality is weak.

### 5. Review And User Control

Current issue: confirmation queue exists, but only the system decides review status.

Recommended upgrade:

- Add "why pending" and "what will happen if accepted" copy in the UI.
- Allow editing memory content before accepting.
- Allow changing memory type, scope, and sensitivity from the UI.
- Add bulk accept/reject for low-risk queues.

Near-term task:

- Add edit-before-accept for pending memories.

### 6. Evaluation

Current issue: memory behavior is hard to improve safely without examples.

Recommended upgrade:

- Add a small local evaluation dataset with cases for:
  - should write
  - should not write
  - type classification
  - slot/value extraction
  - duplicate merge
  - conflict supersede
  - pending classification
- Run it with stub and real model modes.

Near-term task:

- Status: baseline fixture implemented in `tests/fixtures/memory_governance_eval.json`.
- Keep expanding the fixture whenever memory behavior changes.
- Add negative-memory commands and temporal fact cases before introducing LLM extraction.

## Recommended Next Step

The slot registry baseline, governance eval fixture, negative-memory commands, structured extractor interface, feature-flagged LLM extractor, initial live calibration, temporal memory baseline, and correction-aware updates are now in place.

Priority update: sensitive memory policy refinement should come before negation-aware multi-value updates. Once LLM extraction and richer retrieval are enabled, the highest-risk failure mode is persisting credentials or sensitive identifiers into normal memory. The policy should distinguish explicit secrets from ordinary facts that merely contain sensitive-looking words.

Current sensitive policy target:

- Reject explicit credentials such as passwords, tokens, API keys, private keys, and secret assignments.
- Keep personal-sensitive facts such as ID cards or bank cards in the confirmation queue.
- Avoid false positives for ordinary facts such as `password manager`.

Edit-before-accept, negation-aware multi-value updates, dedup merge audit metadata, retrieval explanation, baseline multi-candidate extraction, confidence-aware multi-candidate pending behavior, memory observability UI, baseline confidence calibration, calibration policy/eval expansion, calibration reporting, broader governance eval coverage, slot policy refinement, retrieval policy advancement, deterministic memory consolidation, consolidation observability UI, consolidation policy tuning, User Memory Control MVP, baseline Python Agent memory management, persistent user-level memory settings, and Java frontend memory settings are now implemented. The best next engineering step is deciding whether settings should move from JSON files to SQLite for auditability/sync, while keeping Python Agent workflows for advanced maintenance and reporting.
