import json
import threading
import unittest
from pathlib import Path
from uuid import uuid4

from app.memory.settings import MemorySettingsStore


class MemorySettingsAtomicTest(unittest.TestCase):
    def setUp(self):
        root = Path(__file__).resolve().parents[1] / ".tmp" / "memory-settings-tests"
        root.mkdir(parents=True, exist_ok=True)
        self.directory = root / f"case-{uuid4()}"
        self.directory.mkdir(parents=True, exist_ok=False)

    def tearDown(self):
        if not self.directory.exists():
            return
        for path in sorted(self.directory.rglob("*"), key=lambda item: len(item.parts), reverse=True):
            if path.is_file():
                path.unlink(missing_ok=True)
            elif path.is_dir():
                path.rmdir()
        self.directory.rmdir()

    def test_corrupt_existing_settings_fail_closed_without_reenabling_memory(self):
        store = MemorySettingsStore(self.directory)
        disabled = store.update(
            "owner",
            {"memory_enabled": False, "auto_write_enabled": False},
        )
        self.assertFalse(disabled.memory_enabled)
        path = self.directory / "owner" / "settings.json"
        path.write_text("{broken", encoding="utf-8")

        cached = store.get("owner")
        restarted = MemorySettingsStore(self.directory).get("owner")

        self.assertFalse(cached.memory_enabled)
        self.assertFalse(cached.auto_write_enabled)
        self.assertFalse(restarted.memory_enabled)
        self.assertFalse(restarted.auto_write_enabled)

    def test_concurrent_patches_are_serialized_and_file_is_atomically_valid(self):
        store = MemorySettingsStore(self.directory)
        barrier = threading.Barrier(3)

        def update(patch):
            barrier.wait()
            store.update("owner", patch)

        first = threading.Thread(target=update, args=({"memory_enabled": False},))
        second = threading.Thread(target=update, args=({"auto_write_enabled": False},))
        first.start()
        second.start()
        barrier.wait()
        first.join(timeout=2)
        second.join(timeout=2)

        final = store.get("owner")
        self.assertFalse(final.memory_enabled)
        self.assertFalse(final.auto_write_enabled)
        payload = json.loads(
            (self.directory / "owner" / "settings.json").read_text(encoding="utf-8")
        )
        self.assertFalse(payload["memory_enabled"])
        self.assertFalse(payload["auto_write_enabled"])
        self.assertEqual(list(self.directory.rglob("*.tmp")), [])


if __name__ == "__main__":
    unittest.main()
