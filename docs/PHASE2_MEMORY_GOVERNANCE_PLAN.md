# Phase 2 Plan: Memory Governance 2.0

## Goal

Move MyAI from "can store memories" to "can manage memories responsibly".

The system already has useful pieces: memory extraction, confidence, source, deduplication, conflict handling, decay, listing, deletion, and trace visibility. Phase 2 should organize these pieces into a clearer governance layer before adding heavier features.

## Current Baseline

- Memories are stored as `MemoryItem` with:
  - `memory_id`
  - `user_id`
  - `content`
  - `mem_type`
  - `score`
  - `importance`
  - timestamps
  - `status`
  - free-form `metadata`
- The writer already produces:
  - `confidence`
  - `canonical_key`
  - `canonical_value`
  - `slot`
  - `value`
- The API already exposes part of the governance surface:
  - `source`
  - `confidence`
- Existing maintenance already includes:
  - decay
  - deduplication
  - conflict superseding

## Phase 2 Increments

### 2.1 Memory Metadata Contract

Purpose: make every stored memory explainable.

Status: implemented.

Add a normalized governance metadata shape:

- `source`: where the memory came from, such as `user_explicit`, `chat_extraction`, or `manual`.
- `source_ref`: structured reference to the source, including conversation id and message id when available.
- `extraction_reason`: why the system decided this was worth remembering.
- `confidence`: writer confidence.
- `scope`: `global`, `conversation`, `topic`, or `task`.
- `sensitivity`: `normal`, `personal`, or `sensitive`.
- `review_status`: `accepted`, `pending`, or `rejected`.

First implementation should be backward compatible by keeping these fields in `metadata`.

### 2.2 Memory List Visibility

Purpose: let the user inspect memory quality.

Status: implemented.

Expose the new governance fields through:

- Python memory list response.
- Java memory DTO.
- Memory profile cards on the frontend.

The first UI should stay compact: source, confidence, scope, review status, and reason are enough.

### 2.3 Retrieval Governance

Purpose: avoid low-quality or unapproved memories influencing answers.

Status: implemented.

Update memory retrieval policy so it can consider:

- `review_status`
- `confidence`
- `scope`
- `sensitivity`
- existing score and importance

Initial rule:

- retrieve only active memories
- exclude `review_status=rejected`
- exclude `review_status=pending` from normal chat context
- down-rank low-confidence memories
- exclude sensitive memories from normal chat context unless explicitly requested
- allow conversation-scoped memories only when the conversation id matches
- reinforce memory access only after governance filtering accepts the memory into context

### 2.4 Confirmation Queue

Purpose: prevent uncertain or sensitive memories from silently entering context.

Status: implemented.

Add a queue-like view over memories with `review_status=pending`.

Initial endpoints:

- list pending memories
- accept memory
- reject memory

This can be implemented without a relational migration because Chroma metadata already stores status-like fields.

Automatic pending classification is now implemented for sensitive memories, low-confidence memories, and low-importance opinion or decision memories.

### 2.5 Memory Citations

Purpose: make memory influence visible in answers.

Status: implemented.

Add retrieved memory references to the agent trace first. Later, surface them in answer UI when a response uses memory strongly.

Current implementation exposes citations in the `memory.retrieve` trace step and renders them in the collapsible execution trace panel.

### 2.6 Slot Registry

Purpose: make deduplication and conflict handling schema-aware instead of relying only on raw string equality.

Status: baseline implemented.

The first registry version defines:

- normalized slot names and aliases
- normalized value aliases for common cases
- slot cardinality: `single` or `multi`
- conflict policy: `supersede`, `coexist`, `append`, or `pending`

Current implementation uses the registry in:

- memory governance metadata enrichment
- exact slot/value deduplication
- conflict handling for single-value and multi-value slots

This gives the memory module a stable policy layer before adding LLM-based extraction or heavier consolidation.

### 2.7 Temporal Memory Modeling

Purpose: preserve changing facts as history instead of only replacing old values.

Status: baseline implemented.

Current implementation:

- New memories receive `observed_at`, `valid_from`, `valid_to`, and `is_current`.
- Single-value fact changes mark the old memory historical with `valid_to` and `is_current=false`.
- The new memory remains current and stores `previous_memory_id`.
- Historical memories remain visible in the memory list but do not enter normal chat retrieval.

### 2.8 Correction-Aware Updates

Purpose: distinguish explicit user corrections from ordinary same-slot conflicts.

Status: baseline implemented.

Current implementation:

- Correction phrases and move/live-now expressions add `update_intent=correction`.
- LLM extraction can emit the same `update_intent` field.
- Conflict handling records correction-specific history metadata.
- The memory profile UI can filter all, current, and historical memories.

### 2.9 Sensitive Memory Policy Refinement

Purpose: prevent credentials and high-risk identifiers from entering retrievable memory as LLM extraction becomes more capable.

Status: baseline implemented.

Current implementation:

- Adds `sensitive_category` to memory governance metadata and API responses.
- Classifies explicit credential-shaped content as `secret`.
- Forces `secret` memories to `review_status=rejected`.
- Keeps ID card, bank card, credit card, passport, and similar personal-sensitive facts as `pending`.
- Avoids false positives for ordinary facts such as `password manager`.

Recommended next follow-up:

- Add edit-before-accept so users can correct pending memories before accepting them.
- Then add negation-aware multi-value updates for preferences and identities.

### 2.10 Edit-Before-Accept

Purpose: turn the confirmation queue into a real governance workflow instead of a binary accept/reject queue.

Status: baseline implemented.

Current implementation:

- Pending memories can be edited before acceptance.
- Edits support content, memory type, scope, sensitivity, and importance.
- Content edits recompute embeddings.
- Edit metadata preserves `original_content`, `last_edited_at`, and `edited_before_accept`.
- Secret-like edited content is forced to rejected and cannot be accepted.
- The frontend pending panel exposes save, save-and-accept, and reject actions.

Recommended next follow-up:

- Add negation-aware multi-value updates for preferences and identities.
- Then add dedup merge audit metadata.

### 2.11 Negation-Aware Multi-Value Updates

Purpose: allow users to withdraw one value from a multi-value memory without erasing unrelated values.

Status: baseline implemented.

Current implementation:

- Rule extraction detects explicit preference negation.
- LLM extraction prompt can emit `update_intent=negation`.
- Dedup bypasses negation candidates.
- Conflict handling processes negation before multi-value `coexist` or `append` policies.
- Matching active values are marked historical instead of creating a new duplicate.
- Negations without a matching current value become pending review items.

Recommended next follow-up:

- Add dedup merge audit metadata.
- Then add retrieval explanation for why a memory was selected or filtered.

### 2.12 Dedup Merge Audit

Purpose: make memory deduplication traceable instead of silently absorbing new observations into an old memory.

Status: baseline implemented.

Current implementation:

- Exact and semantic merges record merge audit metadata.
- `merged_count` and `last_merged_at` make repeated consolidation visible.
- `last_merge_reason` and `last_merge_type` explain the latest merge decision.
- `merged_from` preserves recent merged memory ids.
- `merge_events` preserves bounded event details as JSON for Chroma compatibility.
- Memory API and Java DTO expose the audit fields.
- Frontend memory cards show a compact merge summary.

Recommended next follow-up:

- Add memory retrieval explanation for selected and filtered memories.
- Later, add a richer merge detail panel that expands `merge_events`.

### 2.13 Memory Retrieval Explanation

Purpose: make memory context construction inspectable, including both selected memories and filtered candidates.

Status: baseline implemented.

Current implementation:

- Retrieval policy can produce per-candidate decisions.
- Selected memories include final score and scoring factors.
- Filtered memories include governance or scoring threshold reasons.
- Chat trace `memory.retrieve` metadata includes `retrieval_explanations`.
- The frontend trace panel renders a readable retrieval explanation section.

Recommended next follow-up:

- Add a richer memory detail UI for merge events and retrieval decisions.
- Then consider multi-candidate extraction with confidence-aware pending behavior.

### 2.14 Multi-Candidate Extraction

Purpose: let one user message create multiple governed memory candidates instead of forcing extraction into one best guess.

Status: baseline implemented.

Current implementation:

- Writer interface supports multi-candidate extraction while preserving single-candidate compatibility.
- Rule-based extraction handles simple compound messages.
- LLM extraction can parse either a single memory object or a `memories` array.
- Each candidate independently goes through governance, deduplication, conflict handling, and pending/rejected policy.
- Write responses expose aggregate `candidate_count`, `written_count`, and per-candidate `results`.

Recommended next follow-up:

- Add richer confidence-aware pending behavior for multi-candidate extraction.
- Add a memory detail UI for merge events and retrieval decisions.

### 2.15 Confidence-Aware Multi-Candidate Pending Behavior

Purpose: reduce false-positive memory writes when one message produces several candidates, especially from LLM extraction where secondary candidates may be inferred rather than explicitly stated.

Status: baseline implemented.

Current implementation:

- Multi-candidate memory writes carry shared batch metadata and per-candidate position.
- Governance metadata includes `extraction_batch_id`, `candidate_index`, `candidate_count`, and `multi_candidate`.
- Multi-candidate candidates below confidence `0.85` are routed to pending.
- Existing single-candidate confidence threshold remains `0.70`.
- The pending reason explicitly states that the candidate was held because of multi-candidate confidence.
- API, Java DTO, and frontend memory cards expose the candidate metadata.

Recommended next follow-up:

- Add memory detail UI for merge events and retrieval decisions.
- Consider LLM extraction calibration that tunes confidence by slot, source, and extraction reason.

### 2.16 Memory Observability UI

Purpose: make the upgraded memory governance behavior visible enough to debug and trust without forcing raw JSON inspection.

Status: baseline implemented.

Current implementation:

- Memory cards include a collapsible governance and audit detail panel.
- The panel surfaces review status, reasons, confidence, sensitivity, source/citation refs, lifecycle timestamps, current/history state, candidate batch metadata, and merge audit metadata.
- Merge event JSON is parsed into readable event cards when available.
- Chat trace retrieval explanations are rendered as selected/filtered cards with score factors and filter reasons.
- The compact memory card summary remains unchanged for everyday use.

Recommended next follow-up:

- Add slot/source confidence calibration and show calibrated confidence provenance in the same observability panel.
- Add bulk review actions once pending queues become large.

### 2.17 Confidence Calibration Baseline

Purpose: make memory confidence usable as a governance signal instead of trusting raw extractor scores directly.

Status: baseline implemented.

Current implementation:

- Raw extractor confidence is preserved in `confidence` and `raw_confidence`.
- Governance produces `calibrated_confidence` plus human-readable calibration reason and factor details.
- Calibration uses slot, source, extraction method, multi-candidate context, weak/inferred wording, and sensitivity.
- Pending classification and retrieval ranking now use calibrated confidence.
- Retrieval explanations include both calibrated confidence and raw confidence.
- Memory observability UI exposes raw, calibrated, reason, and factors.

Recommended next follow-up:

- Move calibration weights into slot/source policy configuration.
- Expand eval fixtures with confidence calibration expectations.
- Add calibration reporting so changes to weights can be evaluated before rollout.

### 2.18 Calibration Policy Configuration And Eval Expansion

Purpose: make confidence calibration tunable and regression-testable instead of burying weights in governance code.

Status: baseline implemented.

Current implementation:

- Slot-level confidence adjustment is now part of `SlotDefinition`.
- Source, extraction method, unknown fallback, multi-candidate, weak-signal, and sensitive-memory adjustments live in `ConfidenceCalibrationPolicy`.
- Governance reads calibration weights from policy configuration.
- Slot enrichment includes `slot_confidence_adjustment` for auditability.
- The memory governance eval fixture includes explicit calibration cases and write-case confidence expectations.
- Eval tests now verify calibrated confidence ranges and calibration factor provenance.

Recommended next follow-up:

- Add a calibration report command that prints per-case expected/actual deltas.
- Add more fixture cases for ambiguous facts, inferred preferences, sensitive facts, and multi-candidate LLM extraction.
- Consider moving policy configuration to JSON/YAML only after the policy surface stabilizes.

### 2.19 Calibration Report

Purpose: make calibration changes reviewable before rollout by showing expected/actual confidence deltas instead of only pass/fail.

Status: baseline implemented.

Current implementation:

- Added `app.memory.evaluation.governance_report`.
- The report consumes `memory_governance_eval.json`.
- Markdown output shows case id, section, pass/fail, raw confidence, actual calibrated confidence, expected range, delta/margin, review status, and calibration factors.
- JSON output is available for automation.
- `--strict` exits non-zero when any case fails.
- `--output` saves the rendered report.
- Unit tests cover report summary, delta calculation, and Markdown rendering.

Recommended next follow-up:

- Add more calibration fixture cases for ambiguous facts, inferred preferences, sensitive facts, and multi-candidate LLM extraction.
- Add a small script or docs command that writes reports under `docs/reports/`.

### 2.20 Memory Governance Eval Expansion

Purpose: broaden the memory governance safety net before further slot policy, retrieval, and consolidation changes.

Status: baseline implemented.

Current implementation:

- Governance fixture now covers write/no-write boundaries, sensitive cases, multi-candidate extraction, dedup, conflict, temporal history, citation, and confidence calibration.
- Multi-candidate LLM-like behavior is tested through a fixture-backed structured extractor.
- Eval assertions cover candidate counts, slot/value/status, calibrated confidence, pending reasons, sensitive category, and temporal history links.
- Calibration report now shows fixture coverage by section.

Recommended next follow-up:

- Continue with slot policy refinement: move more thresholds and review behavior into slot policy.
- Then upgrade retrieval policy with slot-aware and freshness-aware ranking.

### 2.21 Slot Policy Refinement

Purpose: make slot policy the source of truth for memory review and retrieval behavior, instead of scattering thresholds across governance and retrieval code.

Status: baseline implemented.

Current implementation:

- Slot definitions now include review confidence threshold, multi-candidate confidence threshold, retrieval weight, and optional low-importance review threshold.
- Governance metadata exposes those policy values for auditability.
- Pending classification reads slot-specific confidence and low-importance thresholds.
- Retrieval scoring applies `slot_retrieval_weight` and includes slot factors in retrieval explanations.
- Eval fixtures cover slot retrieval weights and low-importance decision review behavior.

Recommended next follow-up:

- Upgrade retrieval policy with freshness-aware ranking and clearer source weighting.
- Add memory consolidation once retrieval scoring can distinguish current facts, stable preferences, and stale observations.

### 2.22 Retrieval Policy Advancement

Purpose: make retrieved memory context reflect not only semantic similarity, but also memory freshness, source quality, and current/history state.

Status: baseline implemented.

Current implementation:

- Retrieval candidates now carry temporal metadata:
  - `created_at`
  - `last_accessed_at`
  - `observed_at`
  - `valid_from`
  - `valid_to`
  - `is_current`
- Retrieval scoring now includes:
  - source weight
  - freshness weight
  - current/history weight
- Freshness uses type-specific half-life and floors:
  - decisions and opinions decay faster
  - stable facts and preferences decay gently
  - very recent memories can receive a small boost
- User-explicit memories are slightly preferred over unknown or lower-quality sources.
- Non-current memories are strongly down-ranked if they remain eligible.
- Retrieval explanations expose source, temporal fields, freshness age, half-life, and each new weight factor.
- Governance eval fixtures now include retrieval policy cases for freshness, source weighting, and current/history ranking.

Recommended next follow-up:

- Begin memory consolidation on top of the richer retrieval signals.
- Consider moving retrieval weights into policy configuration once the shape stabilizes.

### 2.23 Memory Consolidation Baseline

Purpose: reduce long-term memory clutter while preserving evidence and making summary memories auditable.

Status: baseline implemented.

Current implementation:

- Added a `MemoryConsolidator` maintenance component.
- Consolidation currently handles:
  - repeated observations with the same type/slot/value
  - long-term multi-value preferences
  - historical fact chains with previous/current states
- Consolidation creates active summary memories with audit metadata:
  - `consolidation_summary`
  - `consolidation_kind`
  - `consolidated_at`
  - `consolidated_count`
  - `consolidated_from`
  - `consolidation_events`
- Repeated observations and long-term preference evidence are marked historical/superseded and linked with `consolidated_into`.
- Historical fact chain summaries preserve the current fact while summarizing prior states.
- Memory decay now preserves non-deleted historical evidence instead of dropping all non-active memories.
- `memory.maintenance` trace metadata now includes the consolidation report.
- Python schema and Java DTO expose consolidation audit fields.

Recommended next follow-up:

- Add frontend visibility for consolidation summaries and evidence events.
- Add policy tuning for when preference summaries should replace individual values versus coexist with them.
- Consider LLM-assisted summary wording after deterministic consolidation behavior is stable.

### 2.24 Consolidation Observability UI

Purpose: make consolidation summaries and evidence chains visible in the memory profile so users can understand where a summary memory came from.

Status: baseline implemented.

Current implementation:

- Memory card metadata now shows consolidation summary kind/count for summary memories.
- Evidence memories show `consolidated_into` so users can see which summary absorbed them.
- The memory governance detail panel now includes consolidation audit fields:
  - `consolidation_summary`
  - `consolidation_kind`
  - `consolidated_at`
  - `consolidated_count`
  - `consolidated_from`
  - `consolidated_into`
- `consolidation_events` are rendered as readable evidence cards with memory id, source, current/history state, observed time, valid range, and original content.
- Existing merge audit visibility is preserved in the same detail panel.

Recommended next follow-up:

- Add a dedicated filter or badge for summary memories and evidence memories.
- Tune whether summaries replace original memories or coexist with them per slot/type.
- Consider LLM-assisted summary wording once deterministic consolidation policy is stable.

### 2.25 Consolidation Policy Tuning

Purpose: make consolidation behavior explicit per slot/type so summary memories can either replace evidence or coexist with it.

Status: baseline implemented.

Current implementation:

- Slot policy now includes `consolidation_policy`.
- Supported consolidation policies:
  - `replace_evidence`: summary becomes the current memory and evidence is marked historical/superseded.
  - `coexist_with_evidence`: summary is linked to evidence while original memories remain current/active.
- Current policy choices:
  - repeated single-slot facts use `replace_evidence` by default.
  - long-term preferences use `coexist_with_evidence` so individual preferences remain inspectable and retrievable.
  - historical fact chains use `coexist_with_evidence` to preserve the current fact while summarizing prior states.
- Summary and evidence metadata now expose:
  - `consolidation_policy`
  - `consolidation_evidence_action`
- Maintenance trace reports now include slot, policy, evidence action, linked evidence count, and replaced evidence count.
- The memory profile UI exposes consolidation policy in cards/details and adds a filter for summary, evidence, and raw memories.

Recommended next follow-up:

- Move consolidation thresholds and policies to external config after more runtime observation.
- Add a small maintenance report view that groups consolidation actions by slot and policy.
- Consider LLM-assisted summary wording once policy behavior is stable.

### 2.26 User Memory Control MVP

Purpose: reduce memory governance complexity for normal users and give users direct control over whether individual memories are visible, retrievable, pinned, or historical.

Status: baseline implemented.

Current implementation:

- Memory API edit requests now support user-control fields:
  - `retrieval_enabled`
  - `pinned`
  - `user_hidden`
  - `user_locked`
  - `is_current`
  - `user_control_reason`
- Memory list responses expose the same user-control metadata.
- Retrieval policy filters memories when:
  - `retrieval_enabled=false`
  - `user_hidden=true`
- Control-only updates do not trigger edit-before-accept recalibration or pending review.
- The memory profile defaults to a simplified view.
- Users can switch to audit view when they need governance details, merge audit, consolidation evidence, or trace-style metadata.
- The memory profile now supports visibility filtering:
  - visible memories
  - hidden memories
  - all visibility states
- Memory cards expose direct controls:
  - enable or disable retrieval
  - hide or unhide
  - pin or unpin
  - mark historical or restore current
  - delete

Recommended next follow-up:

- Add user-level memory settings for default write/review behavior.
- Add export/delete-by-category controls.
- Move advanced governance panels behind an explicit "advanced" affordance if the UI still feels busy.
- Then begin Python Agent management for memory maintenance, eval, and policy report workflows.

### 2.27 Python Agent Memory Management

Purpose: make memory maintenance, eval/reporting, policy inspection, and future user-level settings available as explicit Python Agent workflows instead of scattered manual scripts and implicit endpoints.

Status: baseline implemented.

Current implementation:

- Added a `memory_admin` task tool.
- Supported operations:
  - `maintenance`: run user-scoped memory maintenance and return consolidation/decay report metadata.
  - `eval_report`: run the memory governance eval/calibration report and return summary, JSON, or Markdown.
  - `policy_inspection`: inspect slot policy, confidence calibration policy, and supported user controls.
  - `settings_preview`: expose the user-level memory settings contract and current persisted values when a user id is available.
- `memory_admin` participates in the normal task planner and tool executor flow.
- The tool can inherit `user_id` from task runtime context for user-scoped maintenance.
- Rule triggers cover memory maintenance, memory reports, memory policy inspection, and memory settings previews.
- Tests cover direct tool workflows and `/task` rule-based policy inspection.

Recommended next follow-up:

- Split `memory_admin` into narrower tools only if planner ambiguity appears in real use.
- Continue expanding persistent user-level memory settings after the initial contract stabilizes.
- Add a frontend or chat command surface for running maintenance/report workflows intentionally.
- Add report artifact saving under `docs/reports/` for longer calibration/policy runs.

### 2.28 Persistent User Memory Settings

Purpose: turn the memory settings preview contract into durable per-user defaults that influence memory extraction, retrieval, and agent management workflows.

Status: baseline implemented.

Current implementation:

- Added `MemorySettingsStore`, backed by per-user JSON files under `memory_settings/<user_id>/settings.json`.
- Added persisted settings:
  - `memory_enabled`
  - `auto_write_enabled`
  - `sensitive_requires_confirmation`
  - `default_memory_view`
- `MemoryService` now reads settings before memory writes and retrieval:
  - `memory_enabled=false` blocks memory writes and retrieval.
  - `auto_write_enabled=false` blocks automatic memory writes.
  - `sensitive_requires_confirmation=true` keeps sensitive accepted candidates in confirmation when applicable.
- `memory_admin` now supports:
  - `get_settings`
  - `update_settings`
  - persisted `settings_preview`
- `settings_preview` now reports `status=persisted` and includes current settings when `user_id` is available.
- Runtime settings storage is ignored by git.

Recommended next follow-up:

- Expose memory settings in the Java frontend settings page.
- Add user-facing task/chat commands for changing common settings safely.
- Consider promoting settings storage to SQLite once settings need audit history or multi-device sync.

### 2.29 Java Frontend Memory Settings

Purpose: expose default memory policy controls in the Java frontend settings page so users can manage memory behavior without agent/tool instructions.

Status: baseline implemented.

Current implementation:

- Added Python API endpoints:
  - `GET /memory/settings/{user_id}`
  - `PATCH /memory/settings/{user_id}`
- Added Java memory proxy endpoints:
  - `GET /memory/settings`
  - `PATCH /memory/settings`
- Added a memory settings panel to the Java settings page.
- Users can now manage:
  - global memory enablement
  - automatic memory writes
  - sensitive-memory confirmation
  - default memory card view
- Saving settings also updates the frontend memory view mode selector.
- Added API regression coverage for persisted settings and automatic-write blocking.

Recommended next follow-up:

- Decide whether settings should move from JSON files to SQLite when audit history or sync is needed.
- Add lightweight user-facing explanations or confirmations only if real users find the current labels ambiguous.
- Keep Python Agent memory management as the advanced/reporting workflow, with the Java settings page as the default control surface.

## Recommended First Task

Completed:

- 2.1 Memory Metadata Contract
- 2.2 Memory List Visibility
- 2.3 Retrieval Governance
- 2.4 Confirmation Queue
- 2.5 Memory Citations
- 2.6 Slot Registry baseline

Recommended next task:

- Add a small memory governance evaluation fixture.
- Cover write/no-write, slot extraction, deduplication, conflict policy, pending classification, and citation visibility.
- Use the fixture to protect the current rule-based writer before introducing a structured LLM extractor.

## Non-Goals For The First Increment

- No database migration.
- No full memory rewrite.
- No LLM-based consolidation yet.
- No complicated frontend workflow yet.
- No persistent trace-memory joins yet.
