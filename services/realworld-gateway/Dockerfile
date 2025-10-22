FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 UVICORN_LOG_LEVEL=info \
    PIP_PREFER_BINARY=1

# Install system dependencies (PyTorch will bring CUDA runtime via pip)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg libgl1 libglib2.0-0 curl ca-certificates \
    wget git build-essential \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt /app/requirements.txt

# Install PyTorch with CUDA 11.8 support (compatible with driver 470/480)
# PyTorch wheels include all necessary CUDA runtime libraries
RUN pip install --upgrade pip \
 && pip install torch==2.1.0 torchvision==0.16.0 --index-url https://download.pytorch.org/whl/cu118 \
 && pip install -r /app/requirements.txt

# Install YOLOv8 and face detection dependencies
RUN pip install ultralytics==8.0.196 \
    && pip install retinaface-pytorch mediapipe

COPY app /app/app
EXPOSE 8089
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8089"]
