# Upgrade Stage 2: Reproducible Thesis Evidence

## Status

Completed on 2026-08-10. Checkpoint 1 (`7db4069`) established the implementation baseline, revision-2 checkpoint `63f884e` froze the reviewed scoring contract, and the accepted 432-attempt evidence is stored under `reports/experiments/thesis-core-v1-r2-final/`.

This stage turns the existing local-first agent MVP into a controlled experimental system that can support the core claims of the graduation thesis.

## Research Questions

1. Does governed long-term memory improve answer correctness over no memory and naive vector memory?
2. Does hybrid retrieval improve evidence recall over pure vector retrieval?
3. Does the current lightweight reranker improve final evidence quality over hybrid retrieval alone?
4. What latency, resource, and failure-rate costs are introduced by each capability?

## Frozen Experimental Contract

### Runtime and models

- Runtime: Ollama `0.32.6` on Windows, accessed through the dedicated OpenAI-compatible loopback endpoint at `127.0.0.1:11435`.
- Verified compute placement: CPU-only. The canonical launcher requests Ollama's `cpu_avx2` library, but the native runtime API proves only `size_vram=0`; the report therefore records CPU-only as verified and treats AVX2 as a launcher request, not an independently observed fact. The installed GPU remains part of the recorded hardware because the current Ollama/CUDA/driver combination failed its kernel probe.
- LLM: `qwen2.5:1.5b-instruct-q4_K_M` (Apache-2.0).
- LLM upstream digest: `65ec06548149` (verified again from the installed runtime at execution time).
- Embedding: `bge-m3:latest`.
- Embedding upstream digest: `790764642607` (verified again from the installed runtime at execution time).
- Temperature: `0`.
- Seed: `42`.
- Context budget: `4096` tokens.
- Maximum generated tokens: `128` for the thesis benchmark.
- Provider retries: `0`.
- Stub fallback: disabled for generation; real embedding providers are fail-closed by design and never substitute Stub vectors.
- Warm-up: one request per model before measured cases. The strict embedding validation probe doubles as the embedding warm-up; the LLM receives one dedicated warm-up. Both latencies and their sources are recorded in the manifest and excluded from case latency.
- Repetitions: three for the final report; a one-repeat pilot is allowed only for development.

The manifest must record the actual runtime version and full model digests. A tag alone is not sufficient evidence because tags may move.

An exploratory A/B also screened `qwen2.5:3b-instruct-q4_K_M`. It recovered one cross-language memory answer but regressed on the balanced RAG sample and uses the Qwen Research License. The frozen model therefore remains the smaller Apache-2.0 1.5B release; model screening results are not thesis comparison evidence.

### Hardware baseline

- OS: Windows 11, build `10.0.26200` at planning time.
- CPU: 12th Gen Intel Core i7-12700H, 14 physical cores / 20 logical processors.
- RAM: 15.8 GiB visible to the operating system.
- GPU: NVIDIA GeForce RTX 3050 Laptop GPU, 4096 MiB VRAM.
- NVIDIA driver: `546.30` at planning time.
- Python: `3.12.6` in the project virtual environment.

The runner must fail its reproducibility preflight when a configured required field does not match the observed environment, unless the operator explicitly selects a non-baseline exploratory run.

### Data and isolation

- Dataset source is a committed UTF-8 JSON fixture with a schema version and SHA-256 recorded in every run.
- All facts are synthetic and use uncommon identifiers so the no-context arm cannot answer from model pretraining.
- Memory and RAG arms use the same observations, corpus, embedding model, insertion order, query order, `top_k`, and generation prompt.
- Every memory case/arm/repeat gets a fresh in-memory store and isolated settings directory. RAG uses the shared immutable ephemeral index described below; neither suite touches product storage.
- Experiments never read or modify personal `chroma_db`, `knowledge_data`, or `memory_settings`.
- Query order is fixed by the committed seed. Across the three technical repeats, each suite uses a committed cyclic Latin-square arm order so every arm occupies every order position once.
- All RAG arms query one shared immutable ephemeral Chroma index. This avoids index-build randomness between arms while remaining isolated from personal/product storage.
- The v1 dataset contains 18 memory cases, 10 documents, and 30 RAG cases. Six documents produce multiple chunks and include near duplicates, obsolete-value hard negatives, cross-file evidence, and four no-answer cases.

## Ablation Definitions

### Memory

| Arm | Write path | Retrieval path | Governance |
| --- | --- | --- | --- |
| `none` | skipped | empty context | none |
| `basic` | the same frozen structured candidates are stored as flat memories | pure vector Top-K | no review, sensitivity filter, deduplication, conflict resolution, temporal state, weighted rerank, touch, consolidation, or decay |
| `governed` | the same candidates go through current `MemoryService` | current vector + lexical recall and `MemoryPolicy` | confidence calibration, review status, sensitivity, deduplication, conflict/temporal state, weighted selection |

Candidate extraction is intentionally frozen by the dataset adapter. This isolates the governed memory stack from extractor variability. Extractor quality remains covered by its separate evaluation suite.

This is a system-level comparison of governed full-stack memory against a naive vector baseline. It does not attribute an observed gain to one individual governance mechanism.

### RAG

| Arm | Candidate source | First-stage score | Final selection |
| --- | --- | --- | --- |
| `vector` | vector only | cosine similarity | score order with the same hard context budget |
| `hybrid` | vector + keyword | current vector/lexical/metadata fusion | fusion-score order with the same hard context budget |
| `hybrid_rerank` | vector + keyword | current fusion | current lightweight rule rerank, duplicate penalty, and file-diversity policy |

The existing reranker is a deterministic lightweight/rule reranker, not a cross-encoder or LLM reranker. Reports and thesis text must use that exact term.

## Metrics

### Quality

- Deterministic rubric accuracy using normalized accepted-answer or required/forbidden-term rules. `answer_accuracy` remains a compatibility alias; raw outputs require manual review before thesis interpretation.
- Abstention accuracy for unanswerable or disallowed cases.
- Memory evidence Recall@K, Precision@K, MRR, stale-fact leakage, and sensitive/pending leakage.
- RAG answer-bearing support Hit@K, evidence Recall@K, Precision@K, and MRR.
- Generated citation hit/precision, invalid citation rate, and no-answer citation hallucination rate. Retrieval support is never reported as generated citation correctness.
- Citation completeness remains a structural metric and is never presented as citation correctness.

### Reliability and efficiency

- Successful retrieval, generation, and end-to-end latency: mean, P50, and P95. Failed attempts retain their real elapsed time in separate all-attempt/failure summaries and never inject synthetic zero latency.
- Failure rate with error category; empty response and fallback count as failures.
- Python and Ollama RSS, system RAM, system CPU, and NVIDIA VRAM/utilization peaks where available.
- Ollama RSS is restricted to the dedicated loopback server PID and its recursive child runners; unrelated default Ollama/App processes are excluded.
- Candidate count, selected-context count, memory write latency, and per-repeat/category/language/answerability breakdowns.
- Paired unique-case rubric deltas with deterministic bootstrap intervals. Technical repeats measure consistency and latency variation; they do not increase the statistical sample size.

## Deliverables

- Generic `openai_compatible` LLM and embedding providers with loopback-safe defaults.
- Provider health/status and startup diagnostics that understand local providers.
- Frozen experiment config and UTF-8 dataset.
- Memory and RAG ablation runner using current production services.
- Machine-readable manifest, per-case JSONL, summary CSV, aggregate JSON, and Markdown report.
- Unit tests for provider selection, strict fail-closed behavior, experiment modes, metrics, and manifest hashing.
- A real-model checkpoint report created on the frozen hardware when Ollama and both models are available.

## Execution Order

1. Add and test the local provider boundary.
2. Add explicit memory and RAG strategies while preserving product defaults.
3. Add the frozen dataset, runner, metrics, resource sampler, and report renderers.
4. Run deterministic unit and release suites.
5. Install/probe Ollama, pull exact models, and run the non-publishable pilot.
6. Review security, attribution validity, state isolation, metric definitions, and result reproducibility; run Python/Java/release gates.
7. Create checkpoint 1: commit the reviewed implementation baseline so the formal run starts from a clean Git commit.
8. Run the three-repeat strict experiment directly into a new `reports/experiments/` directory. The manifest records checkpoint 1's commit before creating the output directory.
9. Review generated cases, metrics, checksums, citation outputs, and limitations; update roadmap, configuration, release notes, version, and execution log.
10. Create checkpoint 2: commit the reviewed evidence and closeout documentation.

## Review Gate

- Default product behavior is unchanged when no experimental strategy is supplied.
- `none` performs no memory write, embedding, retrieval, touch, or maintenance.
- `basic` and `governed` consume identical structured candidates.
- `vector` results have no keyword candidates and no rerank.
- `hybrid` final order follows first-stage fusion order.
- `hybrid_rerank` retains the current production selection behavior.
- Real experiments fail closed on provider failure; no Stub output or Stub vector may enter a result.
- Every result contains provider/model, runtime and native `/api/ps` CPU/context verification, dependency versions, dataset hash, Git commit/dirty state, balanced order, mode, timing, and error metadata.
- Three consecutive provider/timeout failures open a circuit and fail the run instead of producing a partial completed artifact. Planned and actual attempts must match; infrastructure failures cannot be publishable.
- Retrieval evidence is scored immediately after retrieval and remains in the case record when later generation fails, so model reliability cannot silently depress retrieval quality.
- Final checksums include `status.json`, use LF-stable text artifacts, reject unexpected files/directories, and are verified before success is returned.
- Gold citation matching uses stable file aliases and content anchors, not runtime UUIDs.
- Personal runtime data and credentials remain outside the repository and experiment artifacts.

## Diagnostic Review Before Checkpoint 1

All pilot runs are development diagnostics and remain under the ignored `.runtime/` tree; none is thesis evidence.

- The first balanced pilot exposed a prompt-template defect: the 1.5B model copied an `UNKNOWN` fallback instead of using available RAG evidence. Sources are now presented before the instruction, and citation labels must be copied from actual evidence rather than a placeholder.
- A 3B candidate recovered one cross-language memory response but did not improve the balanced RAG diagnostic and carries the Qwen Research License. The Apache-2.0 1.5B model therefore remains frozen.
- A multilingual rubric audit found that semantically correct Chinese answers could be scored as wrong. The checkpoint-1 dataset declared bilingual equivalence groups, unioned Chinese abstention aliases, and was frozen at SHA-256 `c22d3fa6fc58fefdc4983dbecdd764182b581bb66371e876878f57f492c8ba62`.
- The one-repeat full diagnostic showed a useful governed-memory signal but mixed RAG outcomes: hybrid retrieval improved some ranks, while the lightweight reranker improved grounded citations but lost one support hit. The formal report must preserve this result honestly; no post-result tuning is allowed.
- Review also separated retrieved support from generated citation correctness, excluded no-gold cases from evidence denominators, preserved retrieval scores across generation failure, added all pre-registered pairwise deltas, and made non-applicable metrics render as `N/A` rather than zero.

Checkpoint 1 is permitted only after the complete Python/Java/release gates pass and the reviewed implementation is committed. The formal three-repeat run must then start from that clean commit.

## Checkpoint 1 Verification

The reviewed implementation baseline passed the following gates on 2026-08-10:

- Python: 228 unit/integration tests, zero failures.
- Java: 19 tests executed, zero failures/errors, one intentionally skipped.
- Release smoke: startup diagnostics, documentation links, dependency pins, sensitive-default scan, and frontend script syntax all passed.
- Experiment contract: 18 memory cases, 10 RAG documents, and 30 RAG cases; spec SHA-256 `2447c9f95bd08a9833dc8773548060b66594c19b9f947fc57a68d049f329051c` and dataset SHA-256 `c22d3fa6fc58fefdc4983dbecdd764182b581bb66371e876878f57f492c8ba62`.
- Environment: all 95 pinned Python distributions matched, Python compileall passed, both PowerShell launchers parsed successfully, and `git diff --check` reported no whitespace errors.

Two independent final read-only reviews found no remaining P0/P1 implementation blocker. Deferred production hardening is tracked separately from thesis evidence: FastAPI-wide provider shutdown ownership, broader provider-error secret redaction, and a narrower RAM identity check.

## Mandatory Raw-Output Review And Dataset Revision 2

The first strict run (`thesis-core-v1-20260810T133430Z`) completed 432/432 attempts with zero runtime failures, verified checksums, and `publishable=true` at the engineering gate. It is nevertheless rejected as final thesis evidence because the mandatory semantic audit found three objective annotation defects:

- `mem_duplicate_major` treated the observation's declared `CS` alias as wrong instead of equivalent to `computer science`.
- `rag_rerank_weights` omitted a second authoritative chunk that states the same current `0.72/0.20/0.08` weights, undercounting support and one valid citation.
- `rag_phoenix_window` checked the requested time but did not reject the contradictory relation `deployment code is ROL-119`; the source assigns `ROL-119` to rollback and `PXQ100` to deployment.

The rejected run is retained under ignored `.runtime/experiments/` for audit and is never mixed with revision-2 results. The `rag_memory_secret` output's phrase “without explicit permission” remains a disclosed manual-review boundary rather than a post-hoc automatic penalty because it is an unsupported implication, not an explicit logical contradiction.

Revision 2 fixes those observed defects, then applies one systematic rubric-consistency pass: Latin/numeric terms use token boundaries, declared numeric/hyphen aliases are consistent, multi-fact questions require every requested fact, answerable memory cases follow their short-answer contract with explicit exact aliases, abstention follows the case-declared `UNKNOWN` sentinel, and explicit polarity contradictions are rejected. The original questions and prompts remain unchanged. The resource sampler also primes CPU measurement inside its own thread and waits one interval before persisting a sample, avoiding the synthetic first zero. It does not change model, embedding, corpus text, prompts, retrieval arms, hardware, seed, or repetition count.

- Experiment ID: `thesis-core-v1-r2`
- Dataset ID: `myai-thesis-core-v1-r2`
- Dataset SHA-256: `5e72f76c1a610427affab3354c117c08e60e101c4cf1a800102241c520754ea3`
- Spec SHA-256: `6e461f4a61e30bdd67ff4a1c721fc92a8493ba44688c3c79138493f4bd08e5e5`

Revision 2 passed focused/full regression, received its own clean correction checkpoint, and completed the full 432-attempt protocol. Its artifact, metric, and raw-output reviews found no P0/P1 blocker; the accepted interpretation is recorded in `docs/STAGE2_FORMAL_EXPERIMENT_REVIEW.md`.

Pre-checkpoint verification for revision 2: static contract validation passed at 18 memory cases, 10 documents, and 30 RAG cases; 48 focused experiment tests and all 237 Python tests passed; compileall and `git diff --check` passed. An independent frozen-contract audit confirmed that revision 2 leaves all questions, observations, documents, case order, and model inputs unchanged.

## Final Formal Result

- Run: `thesis-core-v1-r2-20260810T144148Z`
- Attempts: 432/432 successful; failure rate 0%; checksums 7/7 verified.
- Memory accuracy (`none/basic/governed`): 33.33% / 50.00% / 61.11%.
- Memory forbidden-evidence exposure: 0.00% / 50.00% / 5.56%.
- RAG accuracy (`vector/hybrid/hybrid_rerank`): 76.67% / 70.00% / 70.00%.
- RAG Support Hit@3: 100% for every arm.
- RAG citation hit: 29.49% / 24.36% / 30.77%.
- RAG grounded answer + citation: 25.64% / 20.51% / 30.77%.

The evidence supports governance as a safe-abstention and forbidden-context control, not as an improvement to answerable factual QA. It does not support a claim that hybrid retrieval or the lightweight reranker improves accuracy or recall on this saturated synthetic dataset.

Final release verification passed through root `release-smoke.cmd` at version `0.9.0-local`, including documentation, dependency, sensitive-default, frontend, Python (237 tests), and Java gates.
