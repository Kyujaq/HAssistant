"""
Tesla K80 Vision Worker
Headless GPU worker for vision preprocessing and detection
"""
import os
import sys
import time
import json
import logging
from typing import Dict, Any, Optional
from contextlib import asynccontextmanager

import numpy as np
import cv2
import torch
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='{"timestamp":"%(asctime)s","level":"%(levelname)s","service":"vision-worker","role":"%(name)s","message":"%(message)s"}',
    datefmt='%Y-%m-%dT%H:%M:%S'
)
logger = logging.getLogger(__name__)

# ============================================================================
# Configuration
# ============================================================================
VISION_ROLE = os.getenv("VISION_ROLE", "unknown")  # screen or room
VISION_CUDA_DEVICE = os.getenv("VISION_CUDA_DEVICE", "cpu")
PORT = int(os.getenv("PORT", "8089"))

# GPU globals
GPU_AVAILABLE = False
GPU_NAME = "CPU"
GPU_INDEX = None
DEVICE = "cpu"

# Model placeholders
detector_model = None
ocr_engine = None

# Metrics
metrics = {
    "warmup_completed": False,
    "fps_preproc": 0.0,
    "fps_detector": 0.0,
    "ocr_ms": 0.0,
    "gpu_temp": 0.0,
    "gpu_util": 0.0,
    "vram_used_mb": 0.0,
    "vram_total_mb": 0.0,
}


# ============================================================================
# GPU Setup & Detection
# ============================================================================
def setup_gpu():
    """Setup GPU device and validate availability"""
    global GPU_AVAILABLE, GPU_NAME, GPU_INDEX, DEVICE
    
    # Check if CUDA is available
    if not torch.cuda.is_available():
        logger.warning("⚠️  CUDA not available. Running in CPU-only mode.")
        return
    
    # Get device specification
    dev = VISION_CUDA_DEVICE.strip().lower()
    
    if dev == "cpu":
        logger.info("🖥️  CPU-only mode configured via VISION_CUDA_DEVICE=cpu")
        return
    
    # Try to parse device index
    try:
        device_idx = int(dev)
    except ValueError:
        logger.warning(f"⚠️  Invalid VISION_CUDA_DEVICE='{dev}'. Using CPU.")
        return
    
    # Validate device index
    if device_idx < 0 or device_idx >= torch.cuda.device_count():
        logger.warning(
            f"⚠️  GPU device {device_idx} not found. "
            f"Available devices: {torch.cuda.device_count()}. Using CPU."
        )
        return
    
    # Set device
    try:
        torch.cuda.set_device(device_idx)
        GPU_INDEX = device_idx
        GPU_NAME = torch.cuda.get_device_name(device_idx)
        DEVICE = f"cuda:{device_idx}"
        GPU_AVAILABLE = True
        
        # Get GPU properties
        props = torch.cuda.get_device_properties(device_idx)
        total_mem_gb = props.total_memory / (1024**3)
        
        logger.info(
            f"✅ GPU {device_idx} initialized: {GPU_NAME}",
            extra={
                "gpu_index": device_idx,
                "gpu_name": GPU_NAME,
                "vram_gb": f"{total_mem_gb:.2f}",
                "compute_capability": f"{props.major}.{props.minor}"
            }
        )
        
        # Verify it's a K80 or warn
        if "K80" not in GPU_NAME and "Tesla" not in GPU_NAME:
            logger.warning(
                f"⚠️  Expected Tesla K80, got {GPU_NAME}. "
                "Ensure correct GPU assignment."
            )
            
    except Exception as e:
        logger.error(f"❌ Failed to initialize GPU {device_idx}: {e}")
        GPU_AVAILABLE = False
        DEVICE = "cpu"


def get_gpu_stats() -> Dict[str, float]:
    """Get current GPU statistics"""
    if not GPU_AVAILABLE:
        return {"temp_c": 0.0, "util_pct": 0.0, "vram_used_mb": 0.0, "vram_free_mb": 0.0}
    
    try:
        import py3nvml.py3nvml as nvml
        nvml.nvmlInit()
        handle = nvml.nvmlDeviceGetHandleByIndex(GPU_INDEX)
        
        # Temperature
        temp = nvml.nvmlDeviceGetTemperature(handle, nvml.NVML_TEMPERATURE_GPU)
        
        # Utilization
        util = nvml.nvmlDeviceGetUtilizationRates(handle)
        
        # Memory
        mem_info = nvml.nvmlDeviceGetMemoryInfo(handle)
        vram_used = mem_info.used / (1024**2)  # MB
        vram_free = mem_info.free / (1024**2)  # MB
        
        nvml.nvmlShutdown()
        
        return {
            "temp_c": float(temp),
            "util_pct": float(util.gpu),
            "vram_used_mb": float(vram_used),
            "vram_free_mb": float(vram_free),
        }
    except Exception as e:
        logger.warning(f"Failed to get GPU stats: {e}")
        return {"temp_c": 0.0, "util_pct": 0.0, "vram_used_mb": 0.0, "vram_free_mb": 0.0}


# ============================================================================
# Model Loading
# ============================================================================
def load_detector():
    """Load YOLO detector model"""
    global detector_model
    
    try:
        from ultralytics import YOLO
        
        # Use YOLOv8n (nano) for lightweight detection
        logger.info("Loading YOLOv8n detector...")
        detector_model = YOLO("yolov8n.pt")
        
        # Move to GPU if available
        if GPU_AVAILABLE:
            # Ultralytics will use the device set by torch.cuda.set_device
            logger.info(f"Detector loaded on {DEVICE}")
        else:
            logger.info("Detector loaded on CPU")
            
    except Exception as e:
        logger.error(f"Failed to load detector: {e}")
        detector_model = None


def load_ocr():
    """Load OCR engine"""
    global ocr_engine
    
    try:
        from paddleocr import PaddleOCR
        
        logger.info("Loading PaddleOCR...")
        # Use CPU for OCR to minimize GPU memory usage
        ocr_engine = PaddleOCR(
            use_angle_cls=False,
            lang='en',
            use_gpu=False,  # Keep OCR on CPU
            show_log=False
        )
        logger.info("OCR engine loaded (CPU)")
        
    except Exception as e:
        logger.error(f"Failed to load OCR: {e}")
        ocr_engine = None


# ============================================================================
# Warmup Pipeline
# ============================================================================
def warmup_opencv_cuda():
    """Warmup OpenCV CUDA operations"""
    if not GPU_AVAILABLE:
        logger.info("Skipping OpenCV CUDA warmup (CPU mode)")
        return 0.0
    
    try:
        # Check if OpenCV has CUDA support
        if cv2.cuda.getCudaEnabledDeviceCount() == 0:
            logger.warning("⚠️  OpenCV built without CUDA support. Using CPU fallback.")
            return 0.0
        
        logger.info("Warming up OpenCV CUDA pipeline...")
        
        # Create test frame (1920x1080)
        test_frame = np.random.randint(0, 255, (1080, 1920, 3), dtype=np.uint8)
        
        # Upload to GPU
        gpu_frame = cv2.cuda_GpuMat()
        gpu_frame.upload(test_frame)
        
        # Run operations
        iterations = 10
        start = time.time()
        
        for _ in range(iterations):
            # Resize
            gpu_resized = cv2.cuda.resize(gpu_frame, (960, 540))
            # Convert color
            gpu_gray = cv2.cuda.cvtColor(gpu_resized, cv2.COLOR_BGR2GRAY)
            # Download
            result = gpu_gray.download()
        
        elapsed = time.time() - start
        fps = iterations / elapsed
        
        logger.info(f"✅ OpenCV CUDA warmup: {fps:.2f} FPS")
        return fps
        
    except Exception as e:
        logger.warning(f"⚠️  OpenCV CUDA warmup failed: {e}. Using CPU fallback.")
        return 0.0


def warmup_detector():
    """Warmup detector model"""
    if detector_model is None:
        logger.warning("Detector not loaded, skipping warmup")
        return 0.0
    
    try:
        logger.info("Warming up detector...")
        
        # Create test frame
        test_frame = np.random.randint(0, 255, (640, 640, 3), dtype=np.uint8)
        
        # Run inference
        iterations = 5
        start = time.time()
        
        for _ in range(iterations):
            _ = detector_model(test_frame, verbose=False, device=DEVICE)
        
        elapsed = time.time() - start
        fps = iterations / elapsed
        
        logger.info(f"✅ Detector warmup: {fps:.2f} FPS")
        return fps
        
    except Exception as e:
        logger.error(f"Detector warmup failed: {e}")
        return 0.0


def warmup_ocr():
    """Warmup OCR engine"""
    if ocr_engine is None:
        logger.warning("OCR not loaded, skipping warmup")
        return 0.0
    
    try:
        logger.info("Warming up OCR...")
        
        # Create test crop with text
        test_crop = np.ones((100, 300, 3), dtype=np.uint8) * 255
        cv2.putText(test_crop, "Hello World", (10, 50), 
                   cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 0), 2)
        
        # Run OCR
        start = time.time()
        result = ocr_engine.ocr(test_crop, cls=False)
        elapsed = (time.time() - start) * 1000  # ms
        
        logger.info(f"✅ OCR warmup: {elapsed:.1f} ms")
        return elapsed
        
    except Exception as e:
        logger.error(f"OCR warmup failed: {e}")
        return 0.0


def run_warmup():
    """Run complete warmup pipeline"""
    logger.info("🔥 Starting warmup pipeline...")
    
    # Load models
    load_detector()
    load_ocr()
    
    # Run warmup tests
    fps_opencv = warmup_opencv_cuda()
    fps_det = warmup_detector()
    ocr_ms = warmup_ocr()
    
    # Update metrics
    metrics["warmup_completed"] = True
    metrics["fps_preproc"] = fps_opencv
    metrics["fps_detector"] = fps_det
    metrics["ocr_ms"] = ocr_ms
    
    # Get GPU stats
    gpu_stats = get_gpu_stats()
    metrics["gpu_temp"] = gpu_stats["temp_c"]
    metrics["gpu_util"] = gpu_stats["util_pct"]
    metrics["vram_used_mb"] = gpu_stats["vram_used_mb"]
    
    logger.info(
        "✅ Warmup complete",
        extra={
            "role": VISION_ROLE,
            "fps_preproc": fps_opencv,
            "fps_detector": fps_det,
            "ocr_ms": ocr_ms,
            "gpu_temp": gpu_stats["temp_c"],
            "gpu_util": gpu_stats["util_pct"],
        }
    )


# ============================================================================
# FastAPI Application
# ============================================================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan - startup and shutdown"""
    # Startup
    logger.info(f"🚀 Vision Worker starting - Role: {VISION_ROLE}")
    setup_gpu()
    run_warmup()
    yield
    # Shutdown
    logger.info("🛑 Vision Worker shutting down")


app = FastAPI(
    title=f"Vision Worker ({VISION_ROLE})",
    description="Tesla K80 GPU-accelerated vision preprocessing worker",
    lifespan=lifespan
)


class HealthResponse(BaseModel):
    ok: bool
    role: str
    gpu_name: str
    gpu_index: Optional[int]
    device: str
    temp_c: float
    util_pct: float
    vram_used_mb: float
    fps_preproc: float
    fps_detector: float
    ocr_ms: float
    warmup_completed: bool


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint with GPU metrics"""
    gpu_stats = get_gpu_stats()
    
    return HealthResponse(
        ok=True,
        role=VISION_ROLE,
        gpu_name=GPU_NAME,
        gpu_index=GPU_INDEX,
        device=DEVICE,
        temp_c=gpu_stats["temp_c"],
        util_pct=gpu_stats["util_pct"],
        vram_used_mb=gpu_stats["vram_used_mb"],
        fps_preproc=metrics["fps_preproc"],
        fps_detector=metrics["fps_detector"],
        ocr_ms=metrics["ocr_ms"],
        warmup_completed=metrics["warmup_completed"],
    )


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "service": "vision-worker",
        "role": VISION_ROLE,
        "gpu": GPU_NAME,
        "status": "running"
    }


# ============================================================================
# Processing Endpoints
# ============================================================================
@app.post("/process/frame")
async def process_frame(file: UploadFile = File(...)):
    """Process uploaded frame with GPU preprocessing"""
    try:
        # Read image
        contents = await file.read()
        nparr = np.frombuffer(contents, np.uint8)
        frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        if frame is None:
            raise HTTPException(status_code=400, detail="Invalid image")
        
        # GPU preprocessing if available
        if GPU_AVAILABLE:
            try:
                if cv2.cuda.getCudaEnabledDeviceCount() > 0:
                    gpu_frame = cv2.cuda_GpuMat()
                    gpu_frame.upload(frame)
                    gpu_resized = cv2.cuda.resize(gpu_frame, (640, 640))
                    frame = gpu_resized.download()
                else:
                    frame = cv2.resize(frame, (640, 640))
            except:
                frame = cv2.resize(frame, (640, 640))
        else:
            frame = cv2.resize(frame, (640, 640))
        
        # Run detection if model available
        detections = []
        if detector_model:
            results = detector_model(frame, verbose=False, device=DEVICE)
            if results and len(results) > 0:
                for r in results[0].boxes.data:
                    detections.append({
                        "bbox": r[:4].cpu().tolist(),
                        "conf": float(r[4]),
                        "class": int(r[5])
                    })
        
        return {
            "ok": True,
            "detections": detections,
            "gpu": GPU_NAME,
            "device": DEVICE
        }
        
    except Exception as e:
        logger.error(f"Frame processing error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/ocr/crop")
async def ocr_crop(file: UploadFile = File(...)):
    """Run OCR on uploaded crop"""
    try:
        # Read image
        contents = await file.read()
        nparr = np.frombuffer(contents, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        if img is None:
            raise HTTPException(status_code=400, detail="Invalid image")
        
        if ocr_engine is None:
            return {"ok": False, "error": "OCR not available"}
        
        # Run OCR
        start = time.time()
        result = ocr_engine.ocr(img, cls=False)
        elapsed_ms = (time.time() - start) * 1000
        
        # Extract text
        text_lines = []
        if result and result[0]:
            for line in result[0]:
                text_lines.append({
                    "text": line[1][0],
                    "conf": float(line[1][1])
                })
        
        return {
            "ok": True,
            "text_lines": text_lines,
            "ocr_ms": elapsed_ms
        }
        
    except Exception as e:
        logger.error(f"OCR error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=PORT)
