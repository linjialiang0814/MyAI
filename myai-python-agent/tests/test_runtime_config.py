import os
from pathlib import Path
import unittest
from unittest.mock import patch

from app.runtime.config import load_runtime_settings


class RuntimeConfigTest(unittest.TestCase):
    def test_defaults_are_finite_and_production_bounded(self):
        names = [name for name in os.environ if name.startswith("MYAI_RUNTIME_") or name.startswith("MYAI_RETRY_")]
        names.extend(
            name for name in os.environ if name.startswith("MYAI_MEMORY_MAINTENANCE_")
        )
        names.extend(name for name in os.environ if name.startswith("MYAI_CIRCUIT_"))
        environment = dict(os.environ)
        for name in names:
            environment.pop(name, None)

        with patch.dict(os.environ, environment, clear=True):
            settings = load_runtime_settings()

        self.assertEqual(settings.database_path, Path("./.runtime/runtime.db").resolve())
        self.assertEqual(settings.database_busy_timeout_ms, 5_000)
        self.assertTrue(settings.memory_maintenance_enabled)
        self.assertEqual(settings.memory_maintenance_worker_count, 2)
        self.assertEqual(settings.memory_maintenance_deadline_seconds, 60.0)
        self.assertEqual(settings.circuit_failure_threshold, 3)

    def test_invalid_nonfinite_and_inverted_backoff_fail_closed(self):
        with patch.dict(os.environ, {"MYAI_CIRCUIT_RECOVERY_SECONDS": "nan"}, clear=False):
            with self.assertRaisesRegex(ValueError, "finite"):
                load_runtime_settings()

        with patch.dict(
            os.environ,
            {
                "MYAI_CIRCUIT_RECOVERY_SECONDS": "30",
                "MYAI_RETRY_BASE_DELAY_SECONDS": "5",
                "MYAI_RETRY_MAX_DELAY_SECONDS": "1",
            },
            clear=False,
        ):
            with self.assertRaisesRegex(ValueError, "retry_max_delay_seconds"):
                load_runtime_settings()

        with patch.dict(
            os.environ,
            {"MYAI_MEMORY_MAINTENANCE_DEADLINE_SECONDS": "inf"},
            clear=False,
        ):
            with self.assertRaisesRegex(ValueError, "finite"):
                load_runtime_settings()


if __name__ == "__main__":
    unittest.main()
