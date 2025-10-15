import asyncio
import os
from typing import Optional

import httpx
from fastapi import Body, FastAPI, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware


ASR_URL = os.getenv("ASR_URL", "")
TTS_URL = os.getenv("TTS_URL", "")
FALLBACK_TTS_HOST = os.getenv("FALLBACK_TTS_HOST", "wyoming-piper")
FALLBACK_TTS_PORT = int(os.getenv("FALLBACK_TTS_PORT", "10200"))
FALLBACK_TTS_URL = os.getenv("FALLBACK_TTS_URL", "")

_fallback_lock = asyncio.Lock()
tts_fallback_enabled = False  # guarded by _fallback_lock

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=False,
)


@app.get("/healthz")
async def healthz() -> dict:
    """Expose configured backend endpoints so the orchestrator can verify wiring."""
    async with _fallback_lock:
        fallback_enabled = tts_fallback_enabled
    return {
        "ok": bool(ASR_URL and TTS_URL),
        "asr": ASR_URL,
        "tts": TTS_URL,
        "fallback_tts_host": FALLBACK_TTS_HOST,
        "fallback_tts_port": FALLBACK_TTS_PORT,
        "fallback_tts_url": FALLBACK_TTS_URL,
        "tts_fallback": fallback_enabled,
    }


@app.get("/config")
async def get_config() -> dict:
    async with _fallback_lock:
        return {"tts_fallback": tts_fallback_enabled}


@app.post("/config")
async def set_config(payload: dict = Body(...)) -> dict:
    if "tts_fallback" not in payload:
        raise HTTPException(status_code=400, detail="tts_fallback flag required")

    new_value = bool(payload["tts_fallback"])
    async with _fallback_lock:
        global tts_fallback_enabled
        tts_fallback_enabled = new_value
        current = tts_fallback_enabled

    return {"tts_fallback": current}


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

    async with _fallback_lock:
        use_fallback = tts_fallback_enabled

    payload = {"input": text}
    if model:
        payload["model"] = model
    if voice:
        payload["voice"] = voice
    if format_hint:
        payload["format"] = format_hint

    target_url = TTS_URL
    source_tag = "primary-tts"
    if use_fallback and FALLBACK_TTS_URL:
        target_url = FALLBACK_TTS_URL
        source_tag = "fallback-tts"

    try:
        client = httpx.AsyncClient(timeout=httpx.Timeout(90.0))
    except Exception as exc:  # pragma: no cover
        raise HTTPException(status_code=500, detail=f"HTTP client init failed: {exc}") from exc

    async def close_client() -> None:
        await client.aclose()

    try:
        stream = client.stream("POST", target_url, json=payload)
        response = await stream.__aenter__()
        response.raise_for_status()
    except httpx.HTTPError as exc:
        await close_client()
        raise HTTPException(status_code=502, detail=f"TTS backend error: {exc}") from exc

    media_type = response.headers.get("content-type", "audio/mpeg")
    passthrough_headers = {"X-Source": source_tag, "X-TTS-Fallback": str(use_fallback).lower()}
    for header in ("X-Sample-Rate", "X-Channels", "X-TTS-Status"):
        if header in response.headers:
            passthrough_headers[header] = response.headers[header]

    async def audio_iter():
        try:
            async for chunk in response.aiter_bytes():
                if chunk:
                    yield chunk
        finally:
            await stream.__aexit__(None, None, None)
            await close_client()

    return StreamingResponse(audio_iter(), media_type=media_type, headers=passthrough_headers)
