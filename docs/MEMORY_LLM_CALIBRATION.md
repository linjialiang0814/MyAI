# Memory LLM Calibration

## Purpose

Evaluate the real memory-role LLM against durable-memory extraction cases before expanding its production responsibility.

## Command

Run from `myai-python-agent`:

```powershell
.\.venv\Scripts\python.exe -m app.memory.evaluation.calibrate --output .\calibration-report.json
```

Use `--strict` when the command should fail if any expected behavior regresses.

## Fixture

The live calibration fixture is stored at:

- `tests/fixtures/memory_llm_calibration.json`

It currently covers:

- implicit preferences and work habits
- natural-language personal facts
- durable goals and opinions
- temporary requests and questions
- jokes and non-durable claims
- negative-memory commands
- sensitive secrets
- Chinese implicit preferences and temporary states
- confidence calibration ranges

## 2026-06-05 Baseline

Configured real memory-role model:

- feature flag enabled
- provider configured through `.env`
- model id configured through `.env`

First run:

- total: 12
- passed: 12
- failed: 0
- issue found: every accepted candidate returned `confidence=1.0`

Calibration change:

- Added an explicit confidence rubric to the LLM extraction prompt.
- Added confidence range expectations to the live fixture.

Second run:

- total: 12
- passed: 12
- failed: 0
- write cases passed: 6/6
- no-write cases passed: 6/6
- confidence range checks passed: 6/6

## Next Calibration Work

- Add cases from actual local conversations.
- Add ambiguous statements that should become pending.
- Add temporal fact changes and corrections.
- Add multi-memory messages before implementing multi-candidate extraction.
