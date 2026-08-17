# MyAI App Demo Data

This directory contains synthetic, redistributable inputs for the portable Windows
App Demo. It must never contain a real user document, credential, database, model, or
runtime log.

## Knowledge demo

Upload `sample-knowledge.txt`, then try:

- `Aurora Lantern 的发布编号是什么？`
- `计划演示时间是什么时候？`
- `RBK-119 是发布编号吗？`
- `文档是否说明了移动端发布日期？`

Expected behavior:

- factual answers use the synthetic document and expose citations;
- `RBK-119` is identified as the rollback identifier, not the release identifier;
- the mobile-release question is answered as unknown rather than invented.

The other guided workflows are available from the application's `演示` workspace.
Stub mode verifies packaging, startup, UI, persistence, and API wiring only. Use the
explicit local Ollama profile when demonstrating model quality.
