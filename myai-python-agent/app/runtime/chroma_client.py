from __future__ import annotations

import os

import chromadb


def create_chroma_client(persist_dir: str | None = None):
    """Build a Chroma client without coupling tests to development storage."""
    settings = chromadb.config.Settings(anonymized_telemetry=False)
    mode = os.getenv("MYAI_CHROMA_MODE", "persistent").strip().lower()
    if persist_dir is None and mode == "ephemeral":
        return chromadb.EphemeralClient(settings=settings)

    resolved_persist_dir = persist_dir or os.getenv("MYAI_CHROMA_DIR", "./chroma_db")
    return chromadb.PersistentClient(path=resolved_persist_dir, settings=settings)
