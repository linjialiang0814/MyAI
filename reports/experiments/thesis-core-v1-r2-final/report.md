# MyAI Thesis Core Experiment - PUBLISHABLE THESIS EVIDENCE

- Run: `thesis-core-v1-r2-20260810T144148Z`
- Evidence class: **PUBLISHABLE THESIS EVIDENCE**
- Dataset: `myai-thesis-core-v1-r2` / `5e72f76c1a610427affab3354c117c08e60e101c4cf1a800102241c520754ea3`
- Publishable: `true`
- Planned/actual attempts: `432` / `432`
- Requested max cases per suite: `None`
- Samples: `memory`: 18 unique cases x 3 technical repeats x 3 arms = 162 attempts; `rag`: 30 unique cases x 3 technical repeats x 3 arms = 270 attempts
- Git: `63f884ed2233814ff7830872a40a5625a2c5f3e3` on `codex/phase2-thesis-evidence`
- LLM: `qwen2.5:1.5b-instruct-q4_K_M`
- Embedding: `bge-m3:latest`

## Results

| Suite | Variant | n (unique) | Rubric accuracy | Evidence Recall@K (n) | Support Hit@K (n) | Gold-source citation hit (n) | Grounded answer + citation | Forbidden-evidence exposure (n) | Failure | Retrieval mean ms | Generation mean ms | End-to-end P95 ms |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| memory | none | 54 (18) | 33.33% | 0.00% (36) | N/A (0) | N/A (0) | N/A | 0.00% (54) | 0.00% | 0.00 | 390.51 | 409.93 |
| memory | basic | 54 (18) | 50.00% | 100.00% (36) | N/A (0) | N/A (0) | N/A | 50.00% (54) | 0.00% | 281.43 | 479.17 | 1618.95 |
| memory | governed | 54 (18) | 61.11% | 100.00% (36) | N/A (0) | N/A (0) | N/A | 5.56% (54) | 0.00% | 278.11 | 428.05 | 1657.30 |
| rag | vector | 90 (30) | 76.67% | 100.00% (78) | 100.00% (78) | 29.49% (78) | 25.64% | N/A (0) | 0.00% | 293.47 | 1603.71 | 3171.84 |
| rag | hybrid | 90 (30) | 70.00% | 100.00% (78) | 100.00% (78) | 24.36% (78) | 20.51% | N/A (0) | 0.00% | 297.19 | 1379.36 | 2607.04 |
| rag | hybrid_rerank | 90 (30) | 70.00% | 100.00% (78) | 100.00% (78) | 30.77% (78) | 30.77% | N/A (0) | 0.00% | 297.34 | 1477.03 | 2497.36 |

## Paired Rubric Accuracy Deltas

| Suite | Comparison | Paired unique n | Mean delta | Bootstrap 95% CI | Wins / ties / losses |
| --- | --- | ---: | ---: | ---: | ---: |
| memory | basic_vs_none | 18 | +16.67% | [-11.11%, +44.44%] | 5 / 11 / 2 |
| memory | governed_vs_none | 18 | +27.78% | [+11.11%, +50.00%] | 5 / 13 / 0 |
| memory | governed_vs_basic | 18 | +11.11% | [+0.00%, +27.78%] | 2 / 16 / 0 |
| rag | hybrid_vs_vector | 30 | -6.67% | [-20.00%, +6.67%] | 1 / 26 / 3 |
| rag | hybrid_rerank_vs_vector | 30 | -6.67% | [-20.00%, +6.67%] | 1 / 26 / 3 |
| rag | hybrid_rerank_vs_hybrid | 30 | +0.00% | [-13.33%, +13.33%] | 2 / 26 / 2 |

## Interpretation Guardrails

- The memory comparison is governed full-stack memory versus a naive vector baseline; it does not attribute gains to one governance mechanism.
- Support Hit@K measures retrieved answer-bearing evidence; generated citation hit separately requires the model to cite such evidence.
- Gold-source citation hit alone does not imply a correct answer; grounded answer + citation requires both the answer rubric and a gold-bearing citation.
- Forbidden-evidence exposure is the historical `leakage_rate` field. It covers every case-declared forbidden context item (for example stale, sensitive, scoped, revoked, or irrelevant evidence) and must not be read as privacy disclosure alone.
- `N/A` means the metric is outside that suite/case contract; it is never converted to a zero. Parenthesized `n` is the metric denominator.
- Rubric accuracy uses deterministic accepted-answer/required-term rules. Raw outputs require manual audit before thesis interpretation.
- Repetitions are technical repeats and never expand the unique-case statistical sample size.
- `hybrid_rerank` uses the project's deterministic lightweight rule reranker, not a cross-encoder.
- Provider validation/warm-up requests are excluded from measured case latency and recorded in `manifest.json`; shared corpus indexing is reported separately.
- The verified compute placement is CPU-only; detected GPU utilization is observational and is not attributed to model inference. The launcher requests `cpu_avx2`, but Ollama does not expose the selected CPU library through `/api/ps`.
- A non-publishable run is diagnostic evidence only and must not be quoted as the final thesis result.

