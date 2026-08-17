from __future__ import annotations

import csv
import io
import shutil
import subprocess
import threading
import time
from typing import Any

import psutil


class ResourceSampler:
    def __init__(self, interval_seconds: float = 0.5, *, ollama_root_pid: int | None = None):
        self.interval_seconds = max(0.2, float(interval_seconds))
        self.ollama_root_pid = int(ollama_root_pid) if ollama_root_pid is not None else None
        self.samples: list[dict[str, Any]] = []
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> "ResourceSampler":
        if self._thread is not None:
            return self
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="experiment-resource-sampler", daemon=True)
        self._thread.start()
        return self

    def stop(self) -> dict[str, Any]:
        self._stop.set()
        if self._thread is not None:
            # On Windows, starting and terminating nvidia-smi can exceed its
            # internal two-second subprocess timeout under CPU pressure. Give
            # the in-flight sample a bounded window to unwind before treating
            # resource collection as incomplete.
            self._thread.join(timeout=max(8.0, self.interval_seconds + 7.0))
            if self._thread.is_alive():
                raise RuntimeError("resource sampler did not stop after the sampling timeout window")
            self._thread = None
        if not self.samples:
            self.samples.append(_sample_once(self.ollama_root_pid))
        return summarize_resources(self.samples)

    def __enter__(self) -> "ResourceSampler":
        return self.start()

    def __exit__(self, exc_type, exc, tb) -> None:
        self.stop()

    def _run(self) -> None:
        # psutil keeps the non-blocking CPU baseline per calling thread. Prime
        # inside the sampler thread, then wait one sampling interval before
        # persisting a value. An immediate second call can still cover an
        # effectively empty interval and report another synthetic 0.0.
        psutil.cpu_percent(interval=None)
        if self._stop.wait(self.interval_seconds):
            return
        while not self._stop.is_set():
            self.samples.append(_sample_once(self.ollama_root_pid))
            self._stop.wait(self.interval_seconds)


def summarize_resources(samples: list[dict[str, Any]]) -> dict[str, Any]:
    def stats(key: str) -> dict[str, float] | None:
        values = [float(item[key]) for item in samples if item.get(key) is not None]
        if not values:
            return None
        return {
            "mean": round(sum(values) / len(values), 3),
            "peak": round(max(values), 3),
        }

    scopes = {str(item.get("ollama_process_scope") or "") for item in samples}
    root_pids = {int(item["ollama_root_pid"]) for item in samples if item.get("ollama_root_pid") is not None}
    return {
        "sample_count": len(samples),
        "resource_scope": "system_plus_python_and_ollama_processes",
        "ollama_process_scope": next(iter(scopes)) if len(scopes) == 1 else "mixed",
        "ollama_root_pid": next(iter(root_pids)) if len(root_pids) == 1 else None,
        "system_cpu_percent": stats("system_cpu_percent"),
        "system_memory_used_mib": stats("system_memory_used_mib"),
        "python_rss_mib": stats("python_rss_mib"),
        "ollama_rss_mib": stats("ollama_rss_mib"),
        "gpu_utilization_percent": stats("gpu_utilization_percent"),
        "gpu_memory_used_mib": stats("gpu_memory_used_mib"),
        "gpu_available": any(item.get("gpu_memory_used_mib") is not None for item in samples),
    }


def _sample_once(ollama_root_pid: int | None = None) -> dict[str, Any]:
    process = psutil.Process()
    memory = psutil.virtual_memory()
    if ollama_root_pid is not None:
        ollama_rss = _process_tree_rss_bytes(ollama_root_pid)
        ollama_process_scope = "dedicated_server_pid_tree"
    else:
        ollama_rss = _all_named_ollama_rss_bytes()
        ollama_process_scope = "all_named_ollama_processes"
    gpu = _gpu_sample()
    return {
        "monotonic_seconds": round(time.perf_counter(), 6),
        "system_cpu_percent": psutil.cpu_percent(interval=None),
        "system_memory_used_mib": round(memory.used / (1024**2), 3),
        "python_rss_mib": round(process.memory_info().rss / (1024**2), 3),
        "ollama_rss_mib": round(ollama_rss / (1024**2), 3),
        "ollama_process_scope": ollama_process_scope,
        "ollama_root_pid": ollama_root_pid,
        **gpu,
    }


def _process_tree_rss_bytes(root_pid: int) -> int:
    try:
        root = psutil.Process(int(root_pid))
        processes = [root, *root.children(recursive=True)]
    except (psutil.Error, ValueError):
        return 0
    total = 0
    seen: set[int] = set()
    for candidate in processes:
        try:
            if candidate.pid in seen:
                continue
            seen.add(candidate.pid)
            total += int(candidate.memory_info().rss)
        except psutil.Error:
            continue
    return total


def _all_named_ollama_rss_bytes() -> int:
    total = 0
    for candidate in psutil.process_iter(["name", "memory_info"]):
        try:
            name = str(candidate.info.get("name") or "").lower()
            if "ollama" in name:
                total += int(candidate.info["memory_info"].rss)
        except (psutil.Error, KeyError, AttributeError):
            continue
    return total


def _gpu_sample() -> dict[str, float | None]:
    executable = shutil.which("nvidia-smi")
    if not executable:
        return {"gpu_utilization_percent": None, "gpu_memory_used_mib": None}
    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        completed = subprocess.run(
            [
                executable,
                "--query-gpu=utilization.gpu,memory.used",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=2,
            check=True,
            creationflags=creationflags,
        )
        row = next(csv.reader(io.StringIO(completed.stdout.strip())))
        return {
            "gpu_utilization_percent": float(row[0].strip()),
            "gpu_memory_used_mib": float(row[1].strip()),
        }
    except (OSError, subprocess.SubprocessError, StopIteration, ValueError, IndexError):
        return {"gpu_utilization_percent": None, "gpu_memory_used_mib": None}
