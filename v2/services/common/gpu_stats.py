"""Shared GPU/NVML helpers for K80 services."""
from __future__ import annotations

from typing import Dict, List

try:
    import pynvml  # nvidia-ml-py provides this for backward compat

    pynvml.nvmlInit()
    _NVML_AVAILABLE = True
except Exception:  # pragma: no cover - best effort
    _NVML_AVAILABLE = False


def nvml_available() -> bool:
    """Return True if NVML initialised successfully."""
    return _NVML_AVAILABLE


def snapshot_gpus() -> List[Dict[str, float]]:
    """Return a list of GPUs with utilisation + memory stats.

    Each element is `{"index": int, "util": float, "mem_free_gb": float, "mem_total_gb": float}`.
    Returns an empty list if NVML is unavailable.
    """
    if not _NVML_AVAILABLE:
        return []

    gpus: List[Dict[str, float]] = []
    try:
        count = pynvml.nvmlDeviceGetCount()
        for index in range(count):
            handle = pynvml.nvmlDeviceGetHandleByIndex(index)
            util = pynvml.nvmlDeviceGetUtilizationRates(handle).gpu
            mem = pynvml.nvmlDeviceGetMemoryInfo(handle)
            gpus.append(
                {
                    "index": index,
                    "util": float(util),
                    "mem_free_gb": round(mem.free / (1024 ** 3), 2),
                    "mem_total_gb": round(mem.total / (1024 ** 3), 2),
                }
            )
    except Exception:  # pragma: no cover - NVML hiccup
        return []

    return gpus
