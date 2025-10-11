#!/bin/bash
# Simple wrapper to send Windows voice commands using Wyoming Piper and ALSA

set -euo pipefail

COMMAND="${1:-}"
PIPER_HOST="${PIPER_HOST:-hassistant-piper-glados}"
PIPER_PORT="${PIPER_PORT:-10200}"
AUDIO_DEVICE="${USB_AUDIO_DEVICE:-hw:5,0}"

if [ -z "$COMMAND" ]; then
    echo "Usage: $0 <command>"
    echo "Example: $0 'Open Notepad'"
    exit 1
fi

echo "🎤 Sending command: '$COMMAND'"
echo "🔊 Output device: $AUDIO_DEVICE"

# Temporary file for audio
TEMP_WAV="/tmp/command_$(date +%s).wav"

# Use Wyoming client to synthesize speech
python3 << EOF
import socket
import wave
import sys
import asyncio
from wyoming.client import AsyncTcpClient
from wyoming.tts import Synthesize
from wyoming.audio import AudioChunk, AudioStop

async def tts(text, output_file):
    try:
        async with AsyncTcpClient("${PIPER_HOST}", ${PIPER_PORT}) as client:
            # Send TTS request
            await client.write_event(Synthesize(text=text).event())

            audio_data = bytearray()
            sample_rate = 22050
            sample_width = 2
            channels = 1

            # Read audio response
            while True:
                event = await client.read_event()

                if event is None:
                    break

                if AudioChunk.is_type(event.type):
                    chunk = AudioChunk.from_event(event)
                    audio_data.extend(chunk.audio)
                    sample_rate = chunk.rate
                    sample_width = chunk.width
                    channels = chunk.channels
                elif AudioStop.is_type(event.type):
                    break

            # Write WAV file
            with wave.open(output_file, 'wb') as wav_file:
                wav_file.setnchannels(channels)
                wav_file.setsampwidth(sample_width)
                wav_file.setframerate(sample_rate)
                wav_file.writeframes(bytes(audio_data))
            return True
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return False

success = asyncio.run(tts("$COMMAND", "$TEMP_WAV"))
sys.exit(0 if success else 1)
EOF

if [ $? -ne 0 ]; then
    echo "❌ TTS synthesis failed"
    exit 1
fi

echo "✅ Audio synthesized"

# Play audio through USB audio device
aplay -D "$AUDIO_DEVICE" -q "$TEMP_WAV"

if [ $? -eq 0 ]; then
    echo "✅ Command sent successfully"
    rm -f "$TEMP_WAV"
    exit 0
else
    echo "❌ Audio playback failed"
    echo "Debug: Audio file kept at $TEMP_WAV"
    exit 1
fi
