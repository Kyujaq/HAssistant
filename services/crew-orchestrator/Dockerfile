FROM python:3.11-slim

# Security and optimization environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=8084

WORKDIR /app

# Install dependencies (better layer caching)
COPY requirements.txt /app/requirements.txt
RUN pip install --upgrade pip && \
    pip install -r /app/requirements.txt

# Copy application code
COPY crew_tools.py /app/crew_tools.py
COPY main.py /app/main.py

# Copy shared modules from project root
# Will be mounted via volume in docker-compose
RUN mkdir -p /shared

# Add shared to Python path
ENV PYTHONPATH="/shared:${PYTHONPATH}"

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
  CMD python -c "import requests; requests.get('http://localhost:8084/healthz', timeout=5).raise_for_status()" || exit 1

# Run as non-root user for security
RUN useradd -m -u 1000 crewuser && chown -R crewuser:crewuser /app
USER crewuser

EXPOSE ${PORT}

CMD sh -c "uvicorn main:app --host 0.0.0.0 --port ${PORT} --log-level info"
