# Multi-stage build: Python 3.9 + CUDA 11.4 runtime
FROM python:3.9-slim as builder

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python packages (pin NumPy < 2 for ONNX Runtime compatibility)
COPY requirements.txt ./
RUN pip install --no-cache-dir --user "numpy<2" \
    && pip install --no-cache-dir --user -r requirements.txt \
    && pip install --no-cache-dir --user onnxruntime==1.16.3

# Final stage: CUDA runtime + Python packages
FROM nvidia/cuda:11.4.3-cudnn8-runtime-ubuntu20.04

ENV DEBIAN_FRONTEND=noninteractive

# Install Python 3.9 and runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3.9 \
    python3.9-distutils \
    python3-pip \
    ffmpeg \
    libsndfile1 \
    libespeak-ng1 \
    curl \
    tini \
    && rm -rf /var/lib/apt/lists/*

# Copy Python packages from builder
COPY --from=builder /root/.local /root/.local

# Set PATH
ENV PATH=/root/.local/bin:$PATH \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY . .

EXPOSE 8000

ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["python3.9", "-m", "uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000"]
