import os
from typing import Optional

import httpx
from fastapi import FastAPI, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse


ASR_URL = os.getenv("ASR_URL", "")
TTS_URL = os.getenv("TTS_URL", "")
FALLBACK_TTS_HOST = os.getenv("FALLBACK_TTS_HOST", "wyoming-piper")
FALLBACK_TTS_PORT = int(os.getenv("FALLBACK_TTS_PORT", "10200"))

app = FastAPI()


@app.get("/healthz")
async def healthz() -> dict:
    """Expose configured backend endpoints so the orchestrator can verify wiring."""
    return {
        "ok": bool(ASR_URL and TTS_URL),
        "asr": ASR_URL,
        "tts": TTS_URL,
        "fallback_tts_host": FALLBACK_TTS_HOST,
        "fallback_tts_port": FALLBACK_TTS_PORT,
    }


@app.post("/wyoming/stt")
async def wyoming_stt(
    audio: UploadFile,
    model: Optional[str] = Form(default=None),
    language: Optional[str] = Form(default=None),
) -> dict:
    if not ASR_URL:
        raise HTTPException(status_code=500, detail="ASR_URL not configured")

    payload = {}
    if model:
        payload["model"] = model
    if language:
        payload["language"] = language

    contents = await audio.read()
    files = {
        "file": (
            audio.filename or "audio.wav",
            contents,
            audio.content_type or "application/octet-stream",
        )
    }

    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(60.0)) as client:
            response = await client.post(ASR_URL, data=payload, files=files)
            response.raise_for_status()
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"ASR backend error: {exc}") from exc

    return response.json()


@app.post("/wyoming/tts")
async def wyoming_tts(
    text: str = Form(...),
    voice: Optional[str] = Form(default=None),
    model: Optional[str] = Form(default=None),
    format_hint: Optional[str] = Form(default=None),
) -> StreamingResponse:
    if not TTS_URL:
        raise HTTPException(status_code=500, detail="TTS_URL not configured")

    payload = {"input": text}
    if model:
        payload["model"] = model
    if voice:
        payload["voice"] = voice
    if format_hint:
        payload["format"] = format_hint

    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(90.0)) as client:
            response = await client.post(TTS_URL, json=payload)
            response.raise_for_status()
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=502, detail=f"TTS backend error: {exc}"
        ) from exc

    media_type = response.headers.get("content-type", "audio/mpeg")

    return StreamingResponse(
        iter([response.content]),
        media_type=media_type,
        headers={"X-Source": "primary-tts"},
    )
