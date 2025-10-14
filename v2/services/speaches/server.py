import os
import io
import time
import wave
import struct
import math
from pathlib import Path

from fastapi import FastAPI, UploadFile, Body, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse, PlainTextResponse
from faster_whisper import WhisperModel
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST

# Configuration from environment
USE_CUDA = os.getenv("USE_CUDA", "0") == "1"
WHISPER_MODEL = os.getenv("WHISPER_MODEL", "base.en")
SAMPLE_RATE = int(os.getenv("SAMPLE_RATE", "22050"))

# Prometheus metrics
REQUESTS = Counter("speaches_requests_total", "Total requests", ["route"])
LATENCY = Histogram("speaches_latency_seconds", "Request latency", ["route"])

# Initialize Whisper model
print(f"🔧 Initializing Whisper model: {WHISPER_MODEL} (CUDA: {USE_CUDA})")
whisper_model = WhisperModel(
    WHISPER_MODEL,
    device="cuda" if USE_CUDA else "cpu",
    compute_type="int8",  # int8 works on both CPU and GPU (GTX 1070 doesn't support FP16)
)

app = FastAPI(title="Speaches - OpenAI-Compatible STT/TTS", version="2.0.0")


@app.get("/health")
def health():
    """Health check endpoint"""
    return {
        "ok": True,
        "device": "cuda" if USE_CUDA else "cpu",
        "whisper_model": WHISPER_MODEL,
        "sample_rate": SAMPLE_RATE,
        "tts_status": "stub",  # TTS is a placeholder for now
    }


@app.get("/metrics")
def metrics():
    """Prometheus metrics endpoint for HA monitoring"""
    return PlainTextResponse(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.post("/v1/audio/transcriptions")
async def transcribe(file: UploadFile):
    """
    OpenAI-compatible STT endpoint
    Accepts audio file, returns transcription with metadata
    """
    REQUESTS.labels(route="stt").inc()
    start_time = time.time()

    try:
        audio_bytes = await file.read()

        # Transcribe with faster-whisper
        segments, info = whisper_model.transcribe(
            io.BytesIO(audio_bytes),
            beam_size=5,
            vad_filter=True,  # Voice activity detection reduces hallucinations
        )

        # Collect all segments
        text = " ".join([seg.text.strip() for seg in segments])

        return JSONResponse({
            "text": text,
            "language": info.language,
            "duration": info.duration,
        })

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Transcription error: {str(e)}")

    finally:
        LATENCY.labels(route="stt").observe(time.time() - start_time)


def generate_sine_wave(duration_ms: int, frequency: int = 440) -> bytes:
    """Generate a simple sine wave PCM audio (for testing/placeholder)"""
    num_samples = int(SAMPLE_RATE * duration_ms / 1000)
    samples = []
    for i in range(num_samples):
        # Generate sine wave
        value = int(32767.0 * math.sin(2.0 * math.pi * frequency * i / SAMPLE_RATE))
        samples.append(struct.pack('<h', value))  # 16-bit PCM
    return b''.join(samples)


@app.post("/v1/audio/speech")
async def text_to_speech(payload: dict = Body(...)):
    """
    OpenAI-compatible TTS endpoint

    NOTE: This is currently a placeholder that returns a test tone.
    For production, integrate with Piper TTS or use the wyoming-piper fallback.

    To integrate Piper TTS:
    1. Install piper binary in Dockerfile
    2. Shell out to: piper --model <voice.onnx> --output_raw | yield chunks
    3. Or keep this as stub and rely on wyoming-piper for actual TTS
    """
    REQUESTS.labels(route="tts").inc()
    start_time = time.time()

    # Support both OpenAI format ("input") and simple format ("text")
    text = payload.get("input") or payload.get("text") or ""
    if not text:
        raise HTTPException(status_code=400, detail="Missing 'input' or 'text' field")

    try:
        # Generate placeholder audio (sine wave beep)
        # In production: replace with actual Piper TTS
        duration = min(len(text) * 100, 5000)  # ~100ms per char, max 5s
        audio_data = generate_sine_wave(duration)

        # Record latency (measure time to first chunk)
        LATENCY.labels(route="tts").observe(time.time() - start_time)

        # Stream raw L16 PCM (true streaming - no WAV header buffering)
        async def stream_audio():
            # Yield audio in chunks for immediate playback
            chunk_size = 4096
            for i in range(0, len(audio_data), chunk_size):
                yield audio_data[i:i+chunk_size]

        return StreamingResponse(
            stream_audio(),
            media_type="audio/L16",
            headers={
                "Content-Type": f"audio/L16; rate={SAMPLE_RATE}; channels=1",
                "X-Sample-Rate": str(SAMPLE_RATE),
                "X-Channels": "1",
                "X-TTS-Status": "stub",  # Indicates placeholder TTS
            },
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"TTS error: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
