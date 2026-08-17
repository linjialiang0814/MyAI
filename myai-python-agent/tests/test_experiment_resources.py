import unittest
import threading
from types import SimpleNamespace
from unittest.mock import patch

from app.experiments.resources import ResourceSampler, _process_tree_rss_bytes


SAMPLE = {
    "monotonic_seconds": 1.0,
    "system_cpu_percent": 1.0,
    "system_memory_used_mib": 2.0,
    "python_rss_mib": 3.0,
    "ollama_rss_mib": 4.0,
    "gpu_utilization_percent": None,
    "gpu_memory_used_mib": None,
}


class ExperimentResourceSamplerTest(unittest.TestCase):
    def test_stop_joins_and_resets_sampler_thread(self):
        sampler = ResourceSampler(interval_seconds=0.2)
        with patch("app.experiments.resources._sample_once", return_value=dict(SAMPLE)):
            sampler.start()
            summary = sampler.stop()
            sampler.start()
            sampler.stop()

        self.assertIsNone(sampler._thread)
        self.assertGreaterEqual(summary["sample_count"], 1)

    def test_stop_waits_for_an_inflight_sample_to_unwind(self):
        entered = threading.Event()
        release = threading.Event()

        def slow_sample(_ollama_root_pid=None):
            entered.set()
            release.wait(timeout=1.0)
            return dict(SAMPLE)

        sampler = ResourceSampler(interval_seconds=0.2)
        with patch("app.experiments.resources._sample_once", side_effect=slow_sample):
            sampler.start()
            self.assertTrue(entered.wait(timeout=1.0))
            timer = threading.Timer(0.05, release.set)
            timer.start()
            try:
                summary = sampler.stop()
            finally:
                timer.cancel()

        self.assertIsNone(sampler._thread)
        self.assertEqual(summary["sample_count"], 1)

    def test_dedicated_ollama_scope_sums_only_the_root_process_tree(self):
        root = SimpleNamespace(
            pid=10,
            children=lambda recursive: [child],
            memory_info=lambda: SimpleNamespace(rss=3 * 1024**2),
        )
        child = SimpleNamespace(
            pid=11,
            memory_info=lambda: SimpleNamespace(rss=5 * 1024**2),
        )

        with patch("app.experiments.resources.psutil.Process", return_value=root):
            total = _process_tree_rss_bytes(10)

        self.assertEqual(total, 8 * 1024**2)

    def test_sampler_passes_the_dedicated_ollama_root_pid_to_each_sample(self):
        sampler = ResourceSampler(interval_seconds=0.2, ollama_root_pid=4321)
        with patch("app.experiments.resources._sample_once", return_value=dict(SAMPLE)) as sample_once:
            sampler.start()
            sampler.stop()

        sample_once.assert_called_with(4321)

    def test_cpu_percent_is_primed_inside_the_sampler_thread(self):
        caller_threads = []

        def record_thread(*args, **kwargs):
            caller_threads.append(threading.current_thread().name)
            return 0.0

        sampler = ResourceSampler(interval_seconds=0.2)
        with patch("app.experiments.resources.psutil.cpu_percent", side_effect=record_thread), patch(
            "app.experiments.resources._sample_once",
            return_value=dict(SAMPLE),
        ):
            sampler.start()
            sampler.stop()

        self.assertIn("experiment-resource-sampler", caller_threads)

    def test_first_persisted_sample_waits_for_a_real_interval(self):
        sampled = threading.Event()

        def record_sample(_ollama_root_pid=None):
            sampled.set()
            return dict(SAMPLE)

        sampler = ResourceSampler(interval_seconds=0.2)
        with patch("app.experiments.resources.psutil.cpu_percent", return_value=0.0), patch(
            "app.experiments.resources._sample_once",
            side_effect=record_sample,
        ):
            sampler.start()
            self.assertFalse(sampled.wait(timeout=0.05))
            self.assertTrue(sampled.wait(timeout=0.5))
            sampler.stop()


if __name__ == "__main__":
    unittest.main()
