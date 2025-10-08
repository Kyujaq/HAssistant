# Vision Worker Service

GPU-accelerated vision preprocessing and detection worker for Tesla K80 GPUs.

## Overview

This service provides headless GPU workers for:
- OpenCV CUDA preprocessing (resize, color conversion, filters)
- YOLOv8n object detection
- OCR preprocessing and cropping
- Frame processing offload from main vision-gateway

## Features

- ✅ **CUDA 11.4 support** for Kepler architecture (Tesla K80)
- ✅ **PyTorch 1.13.x** - Last version with full Kepler support
- ✅ **CPU fallback** - Graceful degradation if GPU unavailable
- ✅ **Health checks** with GPU metrics
- ✅ **Structured logging** (JSON format)
- ✅ **Warmup pipeline** validates GPU on startup
- ✅ **Stress testing** tool for burn-in validation

## Quick Start

### 1. Build Image

```bash
docker build -t hassistant/vision-worker:latest .
```

### 2. Run Worker

```bash
# Screen worker on GPU 2
docker run -d --name vision-screen \
  --gpus device=2 \
  -e VISION_CUDA_DEVICE=2 \
  -e VISION_ROLE=screen \
  -p 8089:8089 \
  hassistant/vision-worker:latest

# Room worker on GPU 3
docker run -d --name vision-room \
  --gpus device=3 \
  -e VISION_CUDA_DEVICE=3 \
  -e VISION_ROLE=room \
  -p 8090:8090 \
  hassistant/vision-worker:latest
```

### 3. Check Health

```bash
curl http://localhost:8089/health | jq
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `VISION_CUDA_DEVICE` | `cpu` | GPU device index (0-7) or `cpu` |
| `VISION_ROLE` | `unknown` | Worker role (`screen`, `room`, etc.) |
| `PORT` | `8089` | HTTP API port |

## API Endpoints

### GET /health

Health check with GPU metrics.

**Response:**
```json
{
  "ok": true,
  "role": "screen",
  "gpu_name": "Tesla K80",
  "gpu_index": 2,
  "device": "cuda:2",
  "temp_c": 72.0,
  "util_pct": 45.0,
  "vram_used_mb": 4096.0,
  "fps_preproc": 45.2,
  "fps_detector": 28.5,
  "ocr_ms": 125.0,
  "warmup_completed": true
}
```

### POST /process/frame

Process uploaded frame with GPU preprocessing and detection.

**Request:**
```bash
curl -X POST http://localhost:8089/process/frame \
  -F "file=@frame.jpg"
```

**Response:**
```json
{
  "ok": true,
  "detections": [
    {
      "bbox": [100, 200, 300, 400],
      "conf": 0.85,
      "class": 0
    }
  ],
  "gpu": "Tesla K80",
  "device": "cuda:2"
}
```

### POST /ocr/crop

Run OCR on uploaded image crop.

**Request:**
```bash
curl -X POST http://localhost:8089/ocr/crop \
  -F "file=@crop.jpg"
```

**Response:**
```json
{
  "ok": true,
  "text_lines": [
    {"text": "Hello World", "conf": 0.95}
  ],
  "ocr_ms": 120.0
}
```

## Testing

### Warmup Test

```bash
docker run --rm --gpus device=2 \
  -e VISION_CUDA_DEVICE=2 \
  hassistant/vision-worker:latest \
  python3 -c "from app.main import setup_gpu, run_warmup; setup_gpu(); run_warmup()"
```

### Stress Test

```bash
# 5-minute stress test
docker run --rm --gpus device=2 \
  hassistant/vision-worker:latest \
  python3 -m app.tools.stress --device 0 --minutes 5

# 10-minute burn-in with temp limit
docker run --rm --gpus device=2 \
  hassistant/vision-worker:latest \
  python3 -m app.tools.stress --device 0 --minutes 10 --max-temp 80
```

## Development

### Project Structure

```
services/vision-worker/
├── Dockerfile              # CUDA 11.4 container
├── requirements.txt        # Python dependencies
├── README.md              # This file
└── app/
    ├── __init__.py
    ├── main.py            # FastAPI application
    └── tools/
        ├── __init__.py
        └── stress.py      # GPU stress testing tool
```

### Local Development

```bash
# Install dependencies
pip install -r requirements.txt

# Run locally (requires CUDA 11.4)
VISION_CUDA_DEVICE=2 VISION_ROLE=screen python3 -m app.main
```

### Adding New Endpoints

Edit `app/main.py`:

```python
@app.post("/my-endpoint")
async def my_endpoint():
    # Your code here
    return {"ok": True}
```

## Performance

Typical performance on Tesla K80:

| Task | FPS | Notes |
|------|-----|-------|
| OpenCV CUDA ops | 40-50 | Resize, color conv, blur |
| YOLOv8n (640x640) | 25-30 | Lightweight detector |
| PaddleOCR | 8-10 imgs/s | CPU-based |

## Troubleshooting

### Worker won't start

```bash
# Check logs
docker logs vision-screen

# Test GPU access
docker run --rm --gpus device=2 nvidia/cuda:11.4.3-base nvidia-smi
```

### "CUDA not available"

- Verify host driver >= 470.x
- Check NVIDIA Container Toolkit installation
- Ensure correct GPU index in `VISION_CUDA_DEVICE`

### "OpenCV built without CUDA"

This is expected. OpenCV-Python wheels don't include CUDA support.
The worker will use PyTorch for GPU operations and fall back to CPU for OpenCV.

For full OpenCV CUDA support, you need a custom build (adds ~30min to image build).

### High temperature

```bash
# Check temps
nvidia-smi --query-gpu=temperature.gpu --format=csv

# Reduce power limit
sudo nvidia-smi -i 2 -pl 200
```

## See Also

- [Main K80 documentation](../../docs/k80.md)
- [Docker Compose integration](../../docker-compose.yml)
- [Makefile targets](../../Makefile)
