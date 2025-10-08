# Tesla K80 Vision Worker - CUDA 11.4 compatible base
# Kepler architecture (compute capability 3.7) support
FROM nvidia/cuda:11.4.3-cudnn8-runtime-ubuntu20.04

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_PREFER_BINARY=1 \
    CUDA_MODULE_LOADING=LAZY

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3.10 python3.10-dev python3-pip python3.10-distutils \
    ffmpeg libsm6 libxext6 libxrender-dev libgomp1 \
    libglib2.0-0 libgl1-mesa-glx \
    tesseract-ocr tesseract-ocr-eng \
    curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Update alternatives to use python3.10 as default
RUN update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.10 1 \
    && update-alternatives --install /usr/bin/python python /usr/bin/python3.10 1

# Upgrade pip
RUN python3 -m pip install --upgrade pip setuptools wheel

WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt /app/requirements.txt

# Install Python packages
# PyTorch 1.13.1 is the last version with full Kepler (sm_37) support
RUN pip install --no-cache-dir -r /app/requirements.txt

# Copy application code
COPY app /app/app

# Expose health check port
EXPOSE 8089

# Default command (can be overridden in docker-compose)
CMD ["python3", "-m", "app.main"]
