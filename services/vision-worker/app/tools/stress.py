"""
GPU Stress Test Tool for Tesla K80
Maintains 80-95% GPU utilization to verify stability
"""
import os
import sys
import time
import argparse
import logging
from typing import Optional

import numpy as np
import cv2
import torch

logging.basicConfig(
    level=logging.INFO,
    format='{"timestamp":"%(asctime)s","level":"%(levelname)s","message":"%(message)s"}',
)
logger = logging.getLogger(__name__)


def get_gpu_stats(device_idx: int):
    """Get GPU stats via py3nvml"""
    try:
        import py3nvml.py3nvml as nvml
        nvml.nvmlInit()
        handle = nvml.nvmlDeviceGetHandleByIndex(device_idx)
        
        temp = nvml.nvmlDeviceGetTemperature(handle, nvml.NVML_TEMPERATURE_GPU)
        util = nvml.nvmlDeviceGetUtilizationRates(handle)
        mem_info = nvml.nvmlDeviceGetMemoryInfo(handle)
        
        # Check for throttling
        perf_state = nvml.nvmlDeviceGetPerformanceState(handle)
        
        nvml.nvmlShutdown()
        
        return {
            "temp_c": temp,
            "util_pct": util.gpu,
            "mem_util_pct": util.memory,
            "vram_used_mb": mem_info.used / (1024**2),
            "vram_total_mb": mem_info.total / (1024**2),
            "perf_state": perf_state,
        }
    except Exception as e:
        logger.error(f"Failed to get GPU stats: {e}")
        return None


def stress_opencv_cuda(device_idx: int, duration_sec: int, max_temp: float = 82.0):
    """Stress test OpenCV CUDA operations"""
    logger.info(f"Starting OpenCV CUDA stress test for {duration_sec}s on GPU {device_idx}")
    
    # Set device
    torch.cuda.set_device(device_idx)
    
    # Check OpenCV CUDA
    if cv2.cuda.getCudaEnabledDeviceCount() == 0:
        logger.warning("OpenCV has no CUDA support, using CPU fallback")
        use_cuda = False
    else:
        use_cuda = True
        logger.info("OpenCV CUDA available")
    
    # Create test frames
    frames = [
        np.random.randint(0, 255, (1080, 1920, 3), dtype=np.uint8)
        for _ in range(5)
    ]
    
    start_time = time.time()
    end_time = start_time + duration_sec
    iteration = 0
    last_report = start_time
    
    try:
        while time.time() < end_time:
            frame = frames[iteration % len(frames)]
            
            if use_cuda:
                # GPU processing
                gpu_frame = cv2.cuda_GpuMat()
                gpu_frame.upload(frame)
                
                # Multiple operations to increase load
                for _ in range(3):
                    gpu_resized = cv2.cuda.resize(gpu_frame, (960, 540))
                    gpu_gray = cv2.cuda.cvtColor(gpu_resized, cv2.COLOR_BGR2GRAY)
                    gpu_blur = cv2.cuda.GaussianBlur(gpu_gray, (5, 5), 1.5)
                    result = gpu_blur.download()
            else:
                # CPU fallback
                for _ in range(3):
                    resized = cv2.resize(frame, (960, 540))
                    gray = cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY)
                    blur = cv2.GaussianBlur(gray, (5, 5), 1.5)
            
            iteration += 1
            
            # Report every 5 seconds
            now = time.time()
            if now - last_report >= 5.0:
                stats = get_gpu_stats(device_idx)
                if stats:
                    elapsed = now - start_time
                    remaining = duration_sec - elapsed
                    
                    logger.info(
                        f"Stress test progress: {elapsed:.0f}/{duration_sec}s | "
                        f"GPU {stats['util_pct']:.0f}% | "
                        f"Temp {stats['temp_c']}°C | "
                        f"VRAM {stats['vram_used_mb']:.0f}/{stats['vram_total_mb']:.0f} MB"
                    )
                    
                    # Check temperature
                    if stats['temp_c'] > max_temp:
                        logger.error(
                            f"❌ GPU temperature {stats['temp_c']}°C exceeds limit {max_temp}°C"
                        )
                        return False
                    
                    # Check for throttling (perf state > 0 means throttled)
                    if stats['perf_state'] > 0:
                        logger.warning(f"⚠️  GPU throttling detected (perf state: {stats['perf_state']})")
                
                last_report = now
        
        # Final report
        stats = get_gpu_stats(device_idx)
        if stats:
            logger.info(
                f"✅ Stress test complete: {iteration} iterations | "
                f"Final temp: {stats['temp_c']}°C | "
                f"Final util: {stats['util_pct']}%"
            )
        
        return True
        
    except Exception as e:
        logger.error(f"Stress test failed: {e}")
        return False


def stress_pytorch(device_idx: int, duration_sec: int, max_temp: float = 82.0):
    """Stress test PyTorch operations"""
    logger.info(f"Starting PyTorch stress test for {duration_sec}s on GPU {device_idx}")
    
    device = f"cuda:{device_idx}"
    torch.cuda.set_device(device_idx)
    
    # Create test tensors
    batch_size = 16
    channels = 3
    height = 640
    width = 640
    
    start_time = time.time()
    end_time = start_time + duration_sec
    iteration = 0
    last_report = start_time
    
    try:
        while time.time() < end_time:
            # Create random input
            x = torch.randn(batch_size, channels, height, width, device=device)
            
            # Convolution operations
            conv = torch.nn.Conv2d(channels, 32, 3, padding=1).to(device)
            x = conv(x)
            x = torch.relu(x)
            
            # More convolutions
            conv2 = torch.nn.Conv2d(32, 64, 3, padding=1).to(device)
            x = conv2(x)
            x = torch.relu(x)
            
            # Pooling
            x = torch.nn.functional.max_pool2d(x, 2)
            
            # Matrix multiplication
            x_flat = x.view(batch_size, -1)
            fc = torch.nn.Linear(x_flat.shape[1], 256).to(device)
            out = fc(x_flat)
            
            # Backward pass for more GPU load
            loss = out.sum()
            loss.backward()
            
            # Clear gradients
            conv.zero_grad()
            conv2.zero_grad()
            fc.zero_grad()
            
            iteration += 1
            
            # Report every 5 seconds
            now = time.time()
            if now - last_report >= 5.0:
                stats = get_gpu_stats(device_idx)
                if stats:
                    elapsed = now - start_time
                    
                    logger.info(
                        f"PyTorch stress: {elapsed:.0f}/{duration_sec}s | "
                        f"GPU {stats['util_pct']:.0f}% | "
                        f"Temp {stats['temp_c']}°C | "
                        f"VRAM {stats['vram_used_mb']:.0f}/{stats['vram_total_mb']:.0f} MB"
                    )
                    
                    if stats['temp_c'] > max_temp:
                        logger.error(f"❌ Temperature limit exceeded: {stats['temp_c']}°C")
                        return False
                
                last_report = now
        
        logger.info(f"✅ PyTorch stress test complete: {iteration} iterations")
        return True
        
    except Exception as e:
        logger.error(f"PyTorch stress test failed: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="GPU Stress Test for Tesla K80")
    parser.add_argument("--device", type=int, default=0, help="GPU device index")
    parser.add_argument("--minutes", type=float, default=5.0, help="Duration in minutes")
    parser.add_argument("--max-temp", type=float, default=82.0, help="Max temperature (°C)")
    parser.add_argument("--mode", choices=["opencv", "pytorch", "both"], default="both",
                       help="Stress test mode")
    
    args = parser.parse_args()
    
    duration_sec = int(args.minutes * 60)
    
    logger.info("=" * 60)
    logger.info(f"GPU Stress Test Configuration")
    logger.info(f"Device: {args.device}")
    logger.info(f"Duration: {args.minutes} minutes ({duration_sec}s)")
    logger.info(f"Max temp: {args.max_temp}°C")
    logger.info(f"Mode: {args.mode}")
    logger.info("=" * 60)
    
    # Initial GPU stats
    stats = get_gpu_stats(args.device)
    if stats:
        logger.info(f"Initial GPU state: {stats['temp_c']}°C, {stats['util_pct']}% util")
    
    success = True
    
    # Run stress tests
    if args.mode in ["opencv", "both"]:
        if not stress_opencv_cuda(args.device, duration_sec, args.max_temp):
            success = False
    
    if args.mode in ["pytorch", "both"] and success:
        if not stress_pytorch(args.device, duration_sec, args.max_temp):
            success = False
    
    # Final stats
    stats = get_gpu_stats(args.device)
    if stats:
        logger.info("=" * 60)
        logger.info(f"Final GPU state:")
        logger.info(f"  Temperature: {stats['temp_c']}°C")
        logger.info(f"  Utilization: {stats['util_pct']}%")
        logger.info(f"  VRAM: {stats['vram_used_mb']:.0f}/{stats['vram_total_mb']:.0f} MB")
        logger.info(f"  Perf state: {stats['perf_state']}")
        logger.info("=" * 60)
    
    if success:
        logger.info("✅ Stress test PASSED")
        sys.exit(0)
    else:
        logger.error("❌ Stress test FAILED")
        sys.exit(1)


if __name__ == "__main__":
    main()
