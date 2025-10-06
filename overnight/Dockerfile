# overnight/Dockerfile
FROM python:3.11-slim

ENV PIP_NO_CACHE_DIR=1 PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install -U pip && pip install -r requirements.txt

# Copy overnight module
COPY . /app/overnight/

# Create data directory for artifacts
RUN mkdir -p /data/artifacts

WORKDIR /app

# Run orchestrator
CMD ["python", "-m", "overnight.orchestrator"]
