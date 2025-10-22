FROM python:3.11-slim
WORKDIR /app
COPY vision-gateway/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
RUN apt-get update && apt-get install -y curl ffmpeg && rm -rf /var/lib/apt/lists/*
COPY vision-gateway /app
COPY common /app/common
EXPOSE 8051
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8051"]
