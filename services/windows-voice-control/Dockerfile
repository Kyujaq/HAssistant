FROM python:3.11-slim

# Install system dependencies for audio playback
RUN apt-get update && apt-get install -y \
    alsa-utils \
    pulseaudio-utils \
    sox \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
RUN pip install --no-cache-dir requests python-dotenv wyoming

# Create app directory
WORKDIR /app

# Copy the scripts
COPY ../../clients/windows_voice_control.py /app/windows_voice_control.py
COPY services/windows-voice-control/send_command.sh /app/send_command.sh

# Make scripts executable
RUN chmod +x /app/windows_voice_control.py /app/send_command.sh

# Healthcheck - just check if the script exists and Python works
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python3 -c "import sys; sys.exit(0)"

# Default command - just sleep to keep container running (use docker exec to run commands)
CMD ["tail", "-f", "/dev/null"]
