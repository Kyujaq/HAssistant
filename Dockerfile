FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    DATA_DIR=/data

WORKDIR /app

# Copy requirements files
COPY orchestrator/requirements.txt /app/orchestrator/requirements.txt

# Install Python dependencies
RUN pip install --upgrade pip && \
    pip install -r /app/orchestrator/requirements.txt

# Copy project source code
COPY orchestrator/ /app/orchestrator/
COPY db/ /app/db/
COPY paprika_bridge/ /app/paprika_bridge/
COPY deals/ /app/deals/
COPY vision/ /app/vision/

# Create data directory
RUN mkdir -p /data/artifacts

# Set the entrypoint
ENTRYPOINT ["python3", "/app/orchestrator/nightly.py"]
