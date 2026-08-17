# MyAI Thesis Experiments

This directory contains the committed experimental contract and synthetic data used to support the graduation-thesis comparison.

## Frozen baseline

- LLM: `qwen2.5:1.5b-instruct-q4_K_M` (Apache-2.0)
- Embedding: `bge-m3:latest`
- Runtime: Ollama `0.32.6` through `http://127.0.0.1:11435/v1`
- Verified compute placement: `cpu_only` with a runtime context length of `4096`; strict runs verify both loaded models through native `/api/ps` after warm-up (`size_vram=0`, `context_length=4096`). The canonical launcher requests Ollama's `cpu_avx2` library, but `/api/ps` does not expose that internal choice, so reports do not claim AVX2 as independently verified.
- Memory arms: `none`, `basic`, `governed`
- RAG arms: `vector`, `hybrid`, `hybrid_rerank`
- Final repetitions: 3
- Frozen contract revision: `thesis-core-v1-r2` / dataset `myai-thesis-core-v1-r2`
- Dataset SHA-256: `5e72f76c1a610427affab3354c117c08e60e101c4cf1a800102241c520754ea3`

The model tags are accompanied by expected digest prefixes in the spec. The runner reads the installed Ollama digests and rejects a mismatch. The GPU is recorded as installed hardware, but its utilization is observational only for this CPU inference baseline.

The Apache-2.0 1.5B model remains the frozen baseline. A local Qwen2.5 3B candidate was screened after the first prompt diagnostic, but it did not improve the balanced memory/RAG sample and uses the more restrictive Qwen Research License. Candidate-model screening is diagnostic only and is not mixed into the final comparison.

Start the dedicated CPU Ollama service from the repository root in the first PowerShell window:

```powershell
.\scripts\start-thesis-ollama-cpu.ps1
```

The launcher resolves `ollama.exe` from the current process PATH, the persisted user or
machine PATH, and then the standard per-user install location. This also supports a
custom installation directory that has been added to the user PATH even when the
current PowerShell session has not inherited the updated PATH yet. It explicitly
prefers the user-scoped `OLLAMA_MODELS` value, then falls back to the process or
machine value and finally the standard per-user model directory. Check the resolved
paths without starting a server with:

```powershell
.\scripts\start-thesis-ollama-cpu.ps1 -ValidateOnly
```

The script owns the remaining frozen `OLLAMA_*`/CPU environment for that server
process. Leave the window open; the experiment process does not need a duplicate
operator-attested backend variable because strict validation verifies the loaded
backend through Ollama `/api/ps`.

## Commands

In a second PowerShell window, from `myai-python-agent`:

```powershell
.\.venv\Scripts\python.exe -m app.experiments.cli validate
.\.venv\Scripts\python.exe -m app.experiments.cli validate --live
.\.venv\Scripts\python.exe -m app.experiments.cli run --suite all --output-dir "..\reports\experiments\thesis-core-v1-r2-final"
```

For a non-publishable development pilot:

```powershell
.\.venv\Scripts\python.exe -m app.experiments.cli run --suite all --repeats 1 --max-cases 3 --exploratory
```

Publishable evidence requires the exact hardware/model/runtime/dependency contract, native CPU/context verification, a clean Git tree observed before output creation, the complete dataset, three balanced-order technical repetitions, no Stub fallback, both suites, a complete attempt count, and no infrastructure failures. Three consecutive provider failures abort the run.

The multilingual answer rubric is frozen with the dataset SHA. Answerable memory cases use explicit exact short-answer aliases; RAG `required_term_groups` use OR within a declared equivalence group and AND across facts. No synonym may be added after inspecting the formal output. Legal citation labels are removed only for answer scoring, while citation quality remains a separate metric.

The checkpoint-1 strict run passed its engineering gate but was rejected by mandatory raw-output review because of three objective gold-annotation defects (the declared `CS` alias, a second authoritative reranker-weight chunk, and a Phoenix relation contradiction). Revision 2 records those corrections before a new clean run. The rejected artifacts remain diagnostic only and must not be quoted or merged with revision-2 metrics.

The dataset contains 18 memory cases and 30 RAG cases over 10 documents; six documents are multi-chunk and the set includes near duplicates, obsolete-value hard negatives, cross-file evidence, and no-answer cases. RAG arms share one immutable ephemeral index so they compare the same indexed state without reading product or personal storage.

Use two checkpoints:

1. Review and commit the implementation baseline so Git is clean.
2. Run the strict three-repeat experiment directly into a new `reports/experiments/<run>/` directory, review the LF-stable checksummed artifacts, then commit the evidence and closeout documentation.

Default runtime artifacts still go under ignored `.runtime/experiments/`; pilots are diagnostic and must not be copied into thesis evidence.
