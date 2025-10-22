FROM nvidia/cuda:12.4.1-cudnn-runtime-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update && apt-get install -y --no-install-recommends \
        python3 \
        python3-distutils \
        python3-pip \
        python3-venv \
        bash \
        libsndfile1 \
        libespeak-ng1 \
        curl \
        tini \
    && rm -rf /var/lib/apt/lists/*

RUN pip3 install --upgrade pip setuptools wheel

# Install Piper stack with GPU-enabled ONNX Runtime
RUN pip3 install \
        "piper-tts>=1.3.0" \
        "wyoming-piper>=1.5.0" \
        "onnxruntime-gpu==1.18.1"

WORKDIR /app

COPY start.sh ./start.sh
RUN chmod +x ./start.sh

ENTRYPOINT ["/usr/bin/tini", "--", "/app/start.sh"]
