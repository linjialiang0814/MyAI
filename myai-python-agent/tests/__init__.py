"""Shared, process-local isolation for the Python test suite."""

from __future__ import annotations

import atexit
import os
from pathlib import Path
import shutil
from uuid import uuid4


_configured_root = os.getenv("MYAI_TEST_DATA_ROOT", "").strip()
if _configured_root:
    TEST_DATA_ROOT = Path(_configured_root).resolve()
    _owns_test_root = False
else:
    _test_temp_parent = Path(__file__).resolve().parent.parent / ".tmp" / "tests"
    _test_temp_parent.mkdir(parents=True, exist_ok=True)
    TEST_DATA_ROOT = (_test_temp_parent / f"run-{uuid4()}").resolve()
    _owns_test_root = True

TEST_DATA_ROOT.mkdir(parents=True, exist_ok=True)

# Lifespan creates application services, but tests still configure deterministic
# providers and isolated persistence before importing the application factory.
os.environ["MYAI_LLM_PROVIDER"] = "stub"
os.environ["MYAI_CHAT_PROVIDER"] = "stub"
os.environ["MYAI_TASK_PROVIDER"] = "stub"
os.environ["MYAI_MEMORY_PROVIDER"] = "stub"
os.environ["MYAI_EMBEDDING_PROVIDER"] = "stub"
os.environ["MYAI_MEMORY_LLM_EXTRACTOR_ENABLED"] = "false"
os.environ["MYAI_CHROMA_MODE"] = "ephemeral"
os.environ["MYAI_CHROMA_DIR"] = str(TEST_DATA_ROOT / "chroma_db")
os.environ["MYAI_KNOWLEDGE_DATA_DIR"] = str(TEST_DATA_ROOT / "knowledge_data")
os.environ["MYAI_MEMORY_SETTINGS_DIR"] = str(TEST_DATA_ROOT / "memory_settings")
os.environ["MYAI_RUNTIME_DB_PATH"] = str(TEST_DATA_ROOT / "runtime" / "runtime.db")
os.environ["MYAI_MEMORY_MAINTENANCE_DEBOUNCE_SECONDS"] = "0.01"


if _owns_test_root:
    atexit.register(shutil.rmtree, TEST_DATA_ROOT, ignore_errors=True)
