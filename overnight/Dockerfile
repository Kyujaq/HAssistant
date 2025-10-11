# overnight/Dockerfile
FROM python:3.11-slim

ENV PIP_NO_CACHE_DIR=1 PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install -U pip && pip install -r requirements.txt

# Copy overnight module
COPY . .

# Create data directory for artifacts
RUN mkdir -p /data/artifacts

# Expose the port the app runs on
EXPOSE 8000

# Set PYTHONPATH to allow absolute imports
ENV PYTHONPATH=/app

# Run the application
CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000"]
