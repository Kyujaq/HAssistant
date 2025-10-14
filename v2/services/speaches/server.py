import asyncio
import io
import json
import os
import shutil
import time
from pathlib import Path
from typing import AsyncGenerator, Optional

from fastapi import Body, FastAPI, HTTPException, UploadFile
from fastapi.responses import JSONResponse, PlainTextResponse, StreamingResponse
from faster_whisper import WhisperModel
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest

# Configuration from environment
USE_CUDA = os.getenv("USE_CUDA", "0") == "1"
WHISPER_MODEL = os.getenv("WHISPER_MODEL", "base.en")
SAMPLE_RATE = int(os.getenv("SAMPLE_RATE", "22050"))

_binary_hint = os.getenv("PIPER_BINARY") or shutil.which("piper")
PIPER_BINARY = Path(_binary_hint) if _binary_hint else None
PIPER_VOICE = os.getenv("PIPER_VOICE", "")
PIPER_VOICE_DIR = Path(os.getenv("PIPER_VOICE_DIR", "/app/voices"))
PIPER_SPEAKER = os.getenv("PIPER_SPEAKER", "")
PIPER_LENGTH_SCALE = os.getenv("PIPER_LENGTH_SCALE", "")

# Prometheus metrics
REQUESTS = Counter("speaches_requests_total", "Total requests", ["route"])
LATENCY = Histogram("speaches_latency_seconds", "Request latency", ["route"])


def _resolve_voice_model() -> Optional[Path]:
    if not PIPER_VOICE:
        candidates = sorted(PIPER_VOICE_DIR.glob("*.onnx"))
        return candidates[0] if candidates else None
    candidates = sorted(PIPER_VOICE_DIR.glob(f"{PIPER_VOICE}*.onnx"))
    return candidates[0] if candidates else None


VOICE_MODEL_PATH = _resolve_voice_model()
VOICE_CONFIG_PATH: Optional[Path] = None
VOICE_SAMPLE_RATE = SAMPLE_RATE

if VOICE_MODEL_PATH:
    config_candidates = [
        VOICE_MODEL_PATH.with_suffix(".json"),
        Path(f"{VOICE_MODEL_PATH}.json"),
    ]
    for candidate in config_candidates:
        if candidate.exists():
            VOICE_CONFIG_PATH = candidate
            try:
                data = json.loads(candidate.read_text(encoding="utf-8"))
                VOICE_SAMPLE_RATE = int(
                    data.get("audio", {}).get("sample_rate", VOICE_SAMPLE_RATE)
                )
            except (json.JSONDecodeError, ValueError, OSError):
                VOICE_SAMPLE_RATE = SAMPLE_RATE
            break
else:
    VOICE_SAMPLE_RATE = SAMPLE_RATE

PIPER_AVAILABLE = (
    PIPER_BINARY is not None and PIPER_BINARY.exists() and os.access(PIPER_BINARY, os.X_OK)
)

# Initialize Whisper model
print(f"🔧 Initializing Whisper model: {WHISPER_MODEL} (CUDA: {USE_CUDA})")
whisper_model = WhisperModel(
    WHISPER_MODEL,
    device="cuda" if USE_CUDA else "cpu",
    compute_type="int8",  # int8 works on both CPU and GPU (GTX 1070 doesn't support FP16)
)

app = FastAPI(title="Speaches - OpenAI-Compatible STT/TTS", version="2.1.0")


@app.get("/health")
def health():
    """Health check endpoint."""
    return {
        "ok": True,
        "device": "cuda" if USE_CUDA else "cpu",
        "whisper_model": WHISPER_MODEL,
        "sample_rate": VOICE_SAMPLE_RATE,
        "tts_status": "piper" if (PIPER_AVAILABLE and VOICE_MODEL_PATH) else "unavailable",
        "tts_voice": str(VOICE_MODEL_PATH) if VOICE_MODEL_PATH else None,
        "piper_voice": VOICE_MODEL_PATH.stem if VOICE_MODEL_PATH else None,
    }


@app.get("/metrics")
def metrics():
    """Prometheus metrics endpoint for HA monitoring."""
    return PlainTextResponse(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.post("/v1/audio/transcriptions")
async def transcribe(file: UploadFile):
    """
    OpenAI-compatible STT endpoint.
    Accepts an audio file and returns a transcription with metadata.
    """
    REQUESTS.labels(route="stt").inc()
    start_time = time.time()

    try:
        audio_bytes = await file.read()
        segments, info = whisper_model.transcribe(
            io.BytesIO(audio_bytes),
            beam_size=5,
            vad_filter=True,  # Voice activity detection reduces hallucinations
        )
        text = " ".join([seg.text.strip() for seg in segments])
        return JSONResponse(
            {
                "text": text,
                "language": info.language,
                "duration": info.duration,
            }
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Transcription error: {exc}") from exc
    finally:
        LATENCY.labels(route="stt").observe(time.time() - start_time)


async def _piper_stream(text: str, start_time: float) -> AsyncGenerator[bytes, None]:
    if not PIPER_AVAILABLE:
        raise HTTPException(status_code=500, detail="Piper binary not available")
    if not VOICE_MODEL_PATH:
        raise HTTPException(status_code=500, detail="Piper voice model not found")

    args = [
        str(PIPER_BINARY),
        "--model",
        str(VOICE_MODEL_PATH),
        "--output_raw",
    ]
    if VOICE_CONFIG_PATH:
        args.extend(["--config", str(VOICE_CONFIG_PATH)])
    if PIPER_SPEAKER:
        args.extend(["--speaker", PIPER_SPEAKER])
    if PIPER_LENGTH_SCALE:
        args.extend(["--length_scale", PIPER_LENGTH_SCALE])

    process = await asyncio.create_subprocess_exec(
        *args,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    assert process.stdin is not None
    assert process.stdout is not None
    assert process.stderr is not None

    input_payload = (text.strip() or ".") + "\n"
    process.stdin.write(input_payload.encode("utf-8"))
    await process.stdin.drain()
    process.stdin.close()
    if hasattr(process.stdin, "wait_closed"):
        try:
            await process.stdin.wait_closed()
        except Exception:
            pass

    stderr_task = asyncio.create_task(process.stderr.read())
    first_chunk_at: Optional[float] = None

    try:
        while True:
            chunk = await process.stdout.read(4096)
            if not chunk:
                break
            if first_chunk_at is None:
                first_chunk_at = time.time()
                LATENCY.labels(route="tts").observe(first_chunk_at - start_time)
            yield chunk
    finally:
        returncode = await process.wait()
        stderr_data = await stderr_task
        if first_chunk_at is None:
            LATENCY.labels(route="tts").observe(time.time() - start_time)
        if returncode != 0:
            detail = stderr_data.decode("utf-8", errors="ignore").strip() or "unknown error"
            raise HTTPException(
                status_code=500, detail=f"Piper synthesis failed (exit {returncode}): {detail}"
            )


@app.post("/v1/audio/speech")
async def text_to_speech(payload: dict = Body(...)):
    """
    OpenAI-compatible TTS endpoint backed by Piper.
    Streams raw 16-bit PCM audio as Piper produces it.
    """
    REQUESTS.labels(route="tts").inc()
    start_time = time.time()

    text = payload.get("input") or payload.get("text") or ""
    if not text:
        raise HTTPException(status_code=400, detail="Missing 'input' or 'text' field")

    async def audio_stream() -> AsyncGenerator[bytes, None]:
        async for chunk in _piper_stream(text, start_time):
            yield chunk

    return StreamingResponse(
        audio_stream(),
        media_type="audio/L16",
        headers={
            "Content-Type": f"audio/L16; rate={VOICE_SAMPLE_RATE}; channels=1",
            "X-Sample-Rate": str(VOICE_SAMPLE_RATE),
            "X-Channels": "1",
            "X-TTS-Status": "piper",
        },
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
