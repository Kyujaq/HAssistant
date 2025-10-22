"""
NVML helper for GPU monitoring.

Provides lightweight GPU utilization and memory sampling for VL routing decisions.
Falls back safely to "idle" state if NVML is unavailable.
"""
import os
import time
from typing import Tuple

try:
    import pynvml
    pynvml.nvmlInit()
    NVML_AVAILABLE = True
except Exception as e:
    pynvml = None
    NVML_AVAILABLE = False
    print(f"Warning: NVML initialization failed: {e}", flush=True)

GPU_INDEX = int(os.getenv("VL_GPU_INDEX", "0"))

# Cache: (util_smoothed, mem_free_gb, last_sample_time)
_cache = (0.0, 99.0, time.time())


def sample_vl() -> Tuple[float, float]:
    """
    Sample VL GPU utilization and free memory.

    Returns:
        (util_5s_avg, mem_free_gb): Smoothed 5s utilization average and free VRAM in GB

    Falls back to (0.0, 99.0) if NVML unavailable (safe "idle" assumption).
    Caches samples for 1s to avoid excessive polling.
    """
    global _cache

    now = time.time()

    # Return cached value if fresh (< 1s old)
    if now - _cache[2] < 1.0:
        return (_cache[0], _cache[1])

    # Fallback if NVML unavailable
    if not NVML_AVAILABLE:
        return (0.0, 99.0)

    try:
        handle = pynvml.nvmlDeviceGetHandleByIndex(GPU_INDEX)

        # Get current utilization (0-100)
        util_pct = pynvml.nvmlDeviceGetUtilizationRates(handle).gpu
        util = util_pct / 100.0

        # Get memory info
        mem_info = pynvml.nvmlDeviceGetMemoryInfo(handle)
        mem_free_gb = mem_info.free / (1024**3)

        # Exponential smoothing for 5s average (α=0.3)
        alpha = 0.3
        util_smoothed = alpha * util + (1 - alpha) * _cache[0]

        # Update cache
        _cache = (util_smoothed, mem_free_gb, now)

        return (util_smoothed, mem_free_gb)

    except Exception:
        # Failsafe: return previous values or defaults
        return (_cache[0], _cache[1])


def get_gpu_info() -> dict:
    """
    Get detailed GPU information for debugging/monitoring.

    Returns:
        Dict with gpu_index, name, util, mem_used_mb, mem_free_mb, mem_total_mb
    """
    if not NVML_AVAILABLE:
        return {
            "available": False,
            "gpu_index": GPU_INDEX,
            "error": "NVML not available"
        }

    try:
        handle = pynvml.nvmlDeviceGetHandleByIndex(GPU_INDEX)
        name = pynvml.nvmlDeviceGetName(handle)
        util = pynvml.nvmlDeviceGetUtilizationRates(handle).gpu
        mem_info = pynvml.nvmlDeviceGetMemoryInfo(handle)

        return {
            "available": True,
            "gpu_index": GPU_INDEX,
            "name": name.decode('utf-8') if isinstance(name, bytes) else name,
            "util_pct": util,
            "mem_used_mb": mem_info.used // (1024**2),
            "mem_free_mb": mem_info.free // (1024**2),
            "mem_total_mb": mem_info.total // (1024**2)
        }
    except Exception as e:
        return {
            "available": False,
            "gpu_index": GPU_INDEX,
            "error": str(e)
        }
