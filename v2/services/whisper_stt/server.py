import asyncio
import io
import logging
import os
import time
from typing import Tuple

from fastapi import FastAPI, HTTPException, UploadFile
from fastapi.responses import JSONResponse, PlainTextResponse
from faster_whisper import WhisperModel

try:
    import ctranslate2
except ImportError:  # pragma: no cover
    ctranslate2 = None
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest

logger = logging.getLogger("whisper_stt")
logging.basicConfig(level=logging.INFO)

# Environment configuration
USE_CUDA = os.getenv("USE_CUDA", "1") == "1"
WHISPER_MODEL = os.getenv("WHISPER_MODEL", "base.en")
REQUESTED_COMPUTE_TYPE = os.getenv(
    "WHISPER_COMPUTE_TYPE", "int8_float16" if USE_CUDA else "int8"
)
WHISPER_DEVICE = "cuda" if USE_CUDA else "cpu"
WHISPER_BEAM_SIZE = int(os.getenv("WHISPER_BEAM_SIZE", "5"))
WHISPER_VAD = os.getenv("WHISPER_VAD_FILTER", "1") == "1"

# Prometheus metrics
REQUESTS = Counter("whisper_stt_requests_total", "STT requests served")
LATENCY = Histogram("whisper_stt_latency_seconds", "STT request latency")


def _supported_compute_types(device: str) -> list[str]:
    if ctranslate2 is None:
        return []
    try:
        return list(ctranslate2.get_supported_compute_types(device))
    except Exception:  # pragma: no cover
        return []


def _select_compute_type() -> str:
    requested = REQUESTED_COMPUTE_TYPE
    supported = _supported_compute_types(WHISPER_DEVICE)
    if not supported:
        return requested

    if requested in supported:
        return requested

    fallback_order = ["int8_float16", "float16", "int8"] if USE_CUDA else ["int8", "float32"]
    for candidate in fallback_order:
        if candidate in supported:
            logger.warning(
                "Requested compute type %s not supported on %s; falling back to %s",
                requested,
                WHISPER_DEVICE,
                candidate,
            )
            return candidate

    # Last resort: pick first supported
    logger.warning(
        "Requested compute type %s not supported on %s; using %s",
        requested,
        WHISPER_DEVICE,
        supported[0],
    )
    return supported[0]


WHISPER_COMPUTE_TYPE = _select_compute_type()


def _load_model() -> WhisperModel:
    candidates = [WHISPER_COMPUTE_TYPE]
    if USE_CUDA:
        candidates.extend([c for c in ("float16", "int8_float16", "int8") if c not in candidates])
    else:
        candidates.extend([c for c in ("int8", "float32") if c not in candidates])

    last_exc: Exception | None = None
    for compute_type in candidates:
        try:
            logger.info(
                "Loading Whisper model %s (device=%s compute_type=%s)",
                WHISPER_MODEL,
                WHISPER_DEVICE,
                compute_type,
            )
            return WhisperModel(
                WHISPER_MODEL,
                device=WHISPER_DEVICE,
                compute_type=compute_type,
            )
        except ValueError as exc:
            last_exc = exc
            logger.warning(
                "Failed to load Whisper model with compute_type=%s: %s",
                compute_type,
                exc,
            )
            continue

    # If we reach here, all attempts failed
    raise RuntimeError(
        f"Unable to initialize Whisper model {WHISPER_MODEL} on {WHISPER_DEVICE}: {last_exc}"
    ) from last_exc


whisper_model = _load_model()

app = FastAPI(title="Whisper STT", version="1.0.0")


@app.get("/health")
def health() -> dict:
    return {
        "ok": True,
        "model": WHISPER_MODEL,
        "device": WHISPER_DEVICE,
        "compute_type": WHISPER_COMPUTE_TYPE,
        "vad_filter": WHISPER_VAD,
        "beam_size": WHISPER_BEAM_SIZE,
    }


@app.get("/metrics")
def metrics():
    return PlainTextResponse(generate_latest(), media_type=CONTENT_TYPE_LATEST)


def _run_transcription(audio_bytes: bytes) -> Tuple[list, object]:
    segment_iter, info = whisper_model.transcribe(
        io.BytesIO(audio_bytes),
        beam_size=WHISPER_BEAM_SIZE,
        vad_filter=WHISPER_VAD,
    )
    segments = list(segment_iter)
    return segments, info


@app.post("/v1/audio/transcriptions")
async def transcribe(file: UploadFile):
    REQUESTS.inc()
    start_time = time.time()

    try:
        audio_bytes = await file.read()
        if not audio_bytes:
            raise HTTPException(status_code=400, detail="Empty audio payload")

        loop = asyncio.get_running_loop()
        segments, info = await loop.run_in_executor(None, _run_transcription, audio_bytes)

        text = " ".join(seg.text.strip() for seg in segments if seg.text)
        return JSONResponse(
            {
                "text": text,
                "language": getattr(info, "language", None),
                "duration": getattr(info, "duration", None),
            }
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Transcription error: %s", exc)
        raise HTTPException(status_code=500, detail=f"Transcription error: {exc}") from exc
    finally:
        LATENCY.observe(time.time() - start_time)
