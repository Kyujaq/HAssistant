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

# Install GroundingDINO and supervision
# Use git version of GroundingDINO for PyTorch 2.1 compatibility
# Pin transformers to version compatible with PyTorch 2.1
RUN pip install supervision transformers==4.36.2 && \
    pip install git+https://github.com/IDEA-Research/GroundingDINO.git

COPY app /app/app
EXPOSE 8088
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8088"]
