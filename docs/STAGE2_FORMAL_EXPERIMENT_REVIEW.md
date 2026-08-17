# Stage 2 Formal Experiment Review

Date: 2026-08-10

Status: reviewed and accepted as the Stage 2 thesis-evidence checkpoint.

## Evidence Identity

- Run ID: `thesis-core-v1-r2-20260810T144148Z`
- Experiment: `thesis-core-v1-r2`
- Git baseline: `63f884ed2233814ff7830872a40a5625a2c5f3e3`
- Dataset: `myai-thesis-core-v1-r2`
- Dataset SHA-256: `5e72f76c1a610427affab3354c117c08e60e101c4cf1a800102241c520754ea3`
- Spec SHA-256: `6e461f4a61e30bdd67ff4a1c721fc92a8493ba44688c3c79138493f4bd08e5e5`
- Evidence directory: `reports/experiments/thesis-core-v1-r2-final`

The run used Ollama `0.32.6`, `qwen2.5:1.5b-instruct-q4_K_M`, and `bge-m3:latest` with complete model digests recorded in `manifest.json`. Both models were verified through Ollama as CPU-only (`size_vram=0`) with a 4096-token context; the embedding probe returned 1024 dimensions.

## Protocol

- Memory: 18 unique cases × 3 arms (`none`, `basic`, `governed`) × 3 technical repeats = 162 attempts.
- RAG: 30 unique cases × 3 arms (`vector`, `hybrid`, `hybrid_rerank`) × 3 technical repeats = 270 attempts.
- Total: 432/432 successful attempts; failure rate 0%.
- Ordering: seed-42 balanced cyclic arm order, concurrency 1.
- Storage: fresh in-memory memory stores and one immutable shared ephemeral RAG index.
- Runtime: loopback-only OpenAI-compatible endpoint, temperature 0, seed 42, no retries, no Stub fallback.
- Statistical unit: unique case; technical repeats do not enlarge `n`.

The first strict run passed its engineering gate but was rejected by mandatory raw-output review. Revision 2 corrected a declared `CS` alias, alternate answer-bearing overlap chunks, and a Phoenix relation contradiction. It also applied a systematic scorer audit without changing any query, observation, document, prompt, case order, model, or retrieval arm. The r1 and r2 runs produced identical answers, selected evidence, and citation labels for all 432 attempts; only the registered rubric/gold corrections changed the affected scores.

## Headline Results

### Memory Ablation

| Variant | Overall rubric accuracy | Answerable accuracy | Abstention accuracy | Evidence Recall@3 | Forbidden-evidence exposure |
| --- | ---: | ---: | ---: | ---: | ---: |
| none | 33.33% | 0.00% | 100.00% | 0.00% | 0.00% |
| basic | 50.00% | 41.67% | 66.67% | 100.00% | 50.00% |
| governed | 61.11% | 41.67% | 100.00% | 100.00% | 5.56% |

Paired unique-case rubric deltas:

- basic vs none: +16.67 percentage points, bootstrap 95% CI `[-11.11, +44.44]`.
- governed vs none: +27.78 percentage points, bootstrap 95% CI `[+11.11, +50.00]`.
- governed vs basic: +11.11 percentage points, bootstrap 95% CI `[0.00, +27.78]`.

The answerable subset is tied at 5/12 unique cases for basic and governed. The governed arm's net gain comes from the six abstention/safety cases: basic answers 4/6 correctly, while governed answers 6/6 correctly. Basic exposes forbidden evidence in all six abstention cases and directly outputs a cross-conversation code and a pending sensitive identifier. Governed leaves one irrelevant-context exposure (`mem_no_relevant_fact`) but no answer-level sensitive disclosure.

`Forbidden-evidence exposure` is intentionally broader than privacy leakage. It includes case-declared stale, sensitive, scoped, revoked, or irrelevant evidence.

### RAG Ablation

| Variant | Overall rubric accuracy | Answerable accuracy | Support Hit@3 | Gold-source citation hit | Grounded answer + citation |
| --- | ---: | ---: | ---: | ---: | ---: |
| vector | 76.67% | 73.08% | 100.00% | 29.49% | 25.64% |
| hybrid | 70.00% | 65.38% | 100.00% | 24.36% | 20.51% |
| hybrid + rerank | 70.00% | 65.38% | 100.00% | 30.77% | 30.77% |

Paired unique-case rubric deltas:

- hybrid vs vector: -6.67 percentage points, bootstrap 95% CI `[-20.00, +6.67]`.
- hybrid + rerank vs vector: -6.67 percentage points, bootstrap 95% CI `[-20.00, +6.67]`.
- hybrid + rerank vs hybrid: 0.00 percentage points, bootstrap 95% CI `[-13.33, +13.33]`.

All three arms retrieved answer-bearing evidence for all 78 answerable attempts. Exact-anchor precision was 41.03%, 42.31%, and 37.18%; MRR was 98.08%, 100%, and 100%. The dataset is therefore saturated at Support Hit@3 and cannot support a claim that hybrid retrieval or reranking improves recall.

Across 234 answerable RAG attempts, the model generated 66 citations (28.21%). All 66 labels were valid and pointed to supporting evidence, but only 60 attempts combined a correct answer with a valid citation (25.64%). All 36 no-answer attempts correctly returned `UNKNOWN` without citation hallucination, yet every one still retrieved three irrelevant chunks. Rejection therefore came from the generator, not a retrieval relevance gate.

## Latency, Resources, And Stability

| Suite / arm | Retrieval mean | Generation mean | End-to-end P95 |
| --- | ---: | ---: | ---: |
| memory none | 0.00 ms | 390.51 ms | 409.93 ms |
| memory basic | 281.43 ms | 479.17 ms | 1618.95 ms |
| memory governed | 278.11 ms | 428.05 ms | 1657.30 ms |
| RAG vector | 293.47 ms | 1603.71 ms | 3171.84 ms |
| RAG hybrid | 297.19 ms | 1379.36 ms | 2607.04 ms |
| RAG hybrid + rerank | 297.34 ms | 1477.03 ms | 2497.36 ms |

- Shared corpus indexing: 9756.649 ms, excluded from per-query latency.
- Total run duration: 644.494 seconds.
- System CPU mean/peak: 65.46% / 85.9%.
- System RAM mean/peak: 14002.56 / 14445.15 MiB.
- Python RSS peak: 145.61 MiB.
- Dedicated Ollama PID-tree RSS peak: 2886.16 MiB.
- RAG Ollama RSS peaks (vector/hybrid/rerank): 2882.40 / 2886.16 / 2874.13 MiB.
- Model/infrastructure failures: 0/432.

The 966 resource samples all reference the dedicated port-11435 server PID, contain no synthetic first CPU-zero sample, and reproduce the published aggregates. System CPU/RAM and NVIDIA metrics are host-global observations; only Python and Ollama PID-tree RSS are process-attributed. Small latency differences must not be interpreted causally because repeat-one warm-state effects remain visible despite balanced arm order.

Repeat consistency across 144 unique case-arm groups was 144/144 for correctness and selected evidence, 138/144 for exact answer text, and 141/144 for citation behavior. Temperature zero and seed 42 therefore stabilized decisions but did not guarantee byte-identical formatting within a run.

## Review And Integrity Gates

Three independent read-only reviews passed with no P0/P1 blocker:

- Artifact integrity: exact eight-file set, no residual `work/`, strict UTF-8/LF, and 7/7 independent checksum verification.
- Metric integrity: cases → metrics → CSV/report, paired bootstrap, latency, and resource aggregates independently recomputed with zero mismatch.
- Semantic integrity: all 432 raw outputs and 66 generated citations reviewed; no remaining clear rubric false positive/negative.

The only semantic P2 note is a governed-memory answer that says a secret is “never retrieved without explicit permission.” This is an unnecessary qualification, but it does not assert that permission bypasses the permanent block. Results should be described as deterministic core-proposition rubric accuracy, not unrestricted whole-answer factual accuracy.

## Claims Supported

- Under this frozen synthetic benchmark, governed memory improves overall accuracy relative to no memory, with the paired bootstrap interval excluding zero.
- Governance substantially reduces forbidden-evidence exposure and improves safe abstention compared with naive memory.
- All three RAG strategies achieve complete Support Hit@3 on this dataset.
- The end-to-end local CPU-only pipeline completed 432 attempts with no model or infrastructure failure in this controlled run.
- The small model's main RAG bottlenecks are evidence use and citation generation rather than Top-3 support recall.

## Claims Not Supported

- Governed memory does not improve answerable factual QA over basic memory in this benchmark; both score 41.67%.
- Hybrid retrieval and reranking do not improve RAG accuracy or recall over vector retrieval here.
- The rerank arm's higher observed citation/grounded rate is descriptive; no paired confidence interval was preregistered for that metric.
- Aggregate latency differences do not establish one retrieval strategy as faster.
- Zero failures in one controlled run do not establish production reliability.
- The 18/30 unique synthetic cases and technical repeats do not represent real-user distributions or enlarge the independent sample size.

## Evidence Files

- `reports/experiments/thesis-core-v1-r2-final/manifest.json`
- `reports/experiments/thesis-core-v1-r2-final/cases.jsonl`
- `reports/experiments/thesis-core-v1-r2-final/metrics.json`
- `reports/experiments/thesis-core-v1-r2-final/comparison.csv`
- `reports/experiments/thesis-core-v1-r2-final/resource_samples.jsonl`
- `reports/experiments/thesis-core-v1-r2-final/report.md`
- `reports/experiments/thesis-core-v1-r2-final/status.json`
- `reports/experiments/thesis-core-v1-r2-final/CHECKSUMS.sha256`
