FROM python:3.11-slim
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*
WORKDIR /app

COPY services/memory-backfill/requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY scripts/ scripts/

ENTRYPOINT ["python", "scripts/memory_backfill.py"]
