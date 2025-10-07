# qwen-agent/Dockerfile
FROM python:3.11-slim

ENV PIP_NO_CACHE_DIR=1 PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
RUN apt-get update && apt-get install -y --no-install-recommends \
      git build-essential portaudio19-dev alsa-utils \
      gnome-screenshot xdg-utils procps && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app
# Clone as a build step so image is reproducible
RUN git clone https://github.com/QwenLM/Qwen-Agent.git /app/Qwen-Agent
WORKDIR /app/Qwen-Agent

# Install with extras you need. Trim extras if you don't need them.
RUN pip install -U pip \
 && pip install -e ".[gui,rag,code_interpreter,mcp]"

# Install PC control agent dependencies
COPY requirements.txt /app/requirements.txt
RUN pip install -r /app/requirements.txt

# Copy PC control agent
COPY pc_control_agent.py /app/pc_control_agent.py

# Default working dir; we'll exec into the container to run examples or your script
WORKDIR /app
CMD ["python3", "pc_control_agent.py"]
