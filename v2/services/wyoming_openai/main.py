import asyncio
import io
import json
import logging
import os
import struct
import wave
from contextlib import asynccontextmanager
from typing import Optional, Union

import httpx
from fastapi import Body, FastAPI, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from wyoming.asr import Transcript
from wyoming.audio import AudioChunk, AudioStart, AudioStop
from wyoming.event import Event
from wyoming.info import AsrModel, AsrProgram, Attribution, Describe, Info, TtsProgram, TtsVoice
from wyoming.tts import Synthesize, SynthesizeVoice
from wyoming.server import AsyncEventHandler, AsyncServer
from wyoming.client import AsyncTcpClient
from wyoming.error import Error

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
ASR_URL = os.getenv("ASR_URL", "")
PRIMARY_TTS_HOST = os.getenv("PRIMARY_TTS_HOST", os.getenv("PIPER_HOST", "piper-main"))
PRIMARY_TTS_PORT = int(os.getenv("PRIMARY_TTS_PORT", "10200"))
FALLBACK_TTS_HOST = os.getenv("FALLBACK_TTS_HOST", "wyoming-piper")
FALLBACK_TTS_PORT = int(os.getenv("FALLBACK_TTS_PORT", "10200"))
FALLBACK_TTS_URL = os.getenv("FALLBACK_TTS_URL", "")
SAMPLE_RATE = 22050
CHUNK_SIZE = 8192  # 8KB chunks for streaming

_fallback_lock = asyncio.Lock()
tts_fallback_enabled = False  # guarded by _fallback_lock

# Servers
stt_server: Optional[AsyncServer] = None
tts_server: Optional[AsyncServer] = None


# Wyoming STT Handler
class WhisperSTTHandler(AsyncEventHandler):
    """Wyoming STT handler that bridges to the Whisper STT service"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.audio_buffer = bytearray()
        self.sample_rate = 16000  # Wyoming default
        self.channels = 1
        self._info_sent = False

    async def handle_event(self, event: Event) -> bool:
        # Send Info event on first connection
        if not self._info_sent:
            logger.info("[STT] New Wyoming STT connection")
            await self._send_info()
            self._info_sent = True

        if Describe.is_type(event.type):
            # Client requesting info
            logger.info("[STT] Client requesting info")
            await self._send_info()
            return True
        if AudioStart.is_type(event.type):
            # Start of audio stream
            audio_start = AudioStart.from_event(event)
            self.sample_rate = audio_start.rate
            self.channels = audio_start.channels
            self.audio_buffer.clear()
            logger.info(f"[STT] Audio start: {self.sample_rate}Hz, {self.channels}ch")

        elif AudioChunk.is_type(event.type):
            # Accumulate audio data
            audio_chunk = AudioChunk.from_event(event)
            self.audio_buffer.extend(audio_chunk.audio)
            logger.debug(f"[STT] Received audio chunk: {len(audio_chunk.audio)} bytes")

        elif AudioStop.is_type(event.type):
            # End of audio - transcribe
            logger.info(f"[STT] Audio stop - buffer size: {len(self.audio_buffer)} bytes")
            if not ASR_URL:
                logger.error("[STT] ASR_URL not configured")
                await self.write_event(Transcript(text="Error: ASR_URL not configured").event())
                return True

            try:
                # Convert raw PCM to WAV
                wav_bytes = self._pcm_to_wav(bytes(self.audio_buffer))
                logger.info(f"[STT] Sending {len(wav_bytes)} bytes to {ASR_URL}")

                # Send to Whisper STT service
                files = {"file": ("audio.wav", wav_bytes, "audio/wav")}
                async with httpx.AsyncClient(timeout=httpx.Timeout(60.0, connect=2.0)) as client:
                    response = await client.post(ASR_URL, files=files)
                    response.raise_for_status()
                    result = response.json()

                # Send transcript back
                text = result.get("text", "")
                logger.info(f"[STT] Transcription result: '{text}'")
                await self.write_event(Transcript(text=text).event())

            except Exception as e:
                logger.error(f"[STT] Transcription error: {e}", exc_info=True)
                await self.write_event(Transcript(text=f"Error: {str(e)}").event())

            return True

        return True

    def _pcm_to_wav(self, pcm_data: bytes) -> bytes:
        """Convert raw PCM to WAV format"""
        wav_buffer = io.BytesIO()
        with wave.open(wav_buffer, 'wb') as wav_file:
            wav_file.setnchannels(self.channels)
            wav_file.setsampwidth(2)  # 16-bit
            wav_file.setframerate(self.sample_rate)
            wav_file.writeframes(pcm_data)
        return wav_buffer.getvalue()

    async def _send_info(self):
        """Send Info event describing ASR capabilities"""
        info = Info(
            asr=[
                AsrProgram(
                    name="whisper-stt",
                    description="Faster Whisper STT (GPU)",
                    attribution=Attribution(name="Whisper STT", url=""),
                    installed=True,
                    version="1.0.0",
                    models=[
                        AsrModel(
                            name="base.en",
                            description="Faster Whisper base.en (GPU)",
                            attribution=Attribution(name="OpenAI Whisper", url=""),
                            installed=True,
                            version="1.0.0",
                            languages=["en"],
                        )
                    ],
                )
            ],
        )
        await self.write_event(info.event())


# Wyoming TTS Handler
class PiperTTSHandler(AsyncEventHandler):
    """Wyoming TTS handler that bridges to Piper streaming"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._info_sent = False

    async def handle_event(self, event: Event) -> bool:
        # Send Info event on first connection
        if not self._info_sent:
            logger.info("[TTS] New Wyoming TTS connection")
            await self._send_info()
            self._info_sent = True

        if Describe.is_type(event.type):
            # Client requesting info
            logger.info("[TTS] Client requesting info")
            await self._send_info()
            return True

        if not Synthesize.is_type(event.type):
            return True

        synthesize = Synthesize.from_event(event)
        text = synthesize.text or ""
        voice = synthesize.voice
        voice_description = self._describe_voice(voice)
        logger.info(f"[TTS] Synthesize request: '{text[:50]}...' voice={voice_description}")

        if not text:
            logger.info("[TTS] Empty text; skipping synthesis")
            return True

        # Check fallback mode
        async with _fallback_lock:
            use_fallback = tts_fallback_enabled

        try:
            if use_fallback:
                logger.info("[TTS] Fallback mode enabled")
                await self._synthesize_with_fallback(text, voice)
            else:
                await self._stream_from_wyoming(
                    PRIMARY_TTS_HOST,
                    PRIMARY_TTS_PORT,
                    text,
                    voice,
                )
            logger.info("[TTS] Synthesis complete")
        except Exception as e:
            logger.warning(f"[TTS] Primary synthesis failed: {e}")
            try:
                await self._synthesize_with_fallback(text, voice)
                logger.info("[TTS] Fallback synthesis complete")
            except Exception as fallback_exc:
                logger.error(f"[TTS] Synthesis error: {fallback_exc}", exc_info=True)

        return True

    @staticmethod
    def _describe_voice(voice: Optional[Union[str, SynthesizeVoice]]) -> str:
        if isinstance(voice, SynthesizeVoice):
            return f"SynthesizeVoice(name={voice.name!r}, language={voice.language!r}, speaker={voice.speaker!r})"
        if isinstance(voice, str):
            return voice
        if voice is None:
            return "default"
        return str(voice)

    @staticmethod
    def _voice_payload(voice: Optional[Union[str, SynthesizeVoice]]) -> dict:
        if voice is None:
            return {}
        if isinstance(voice, str):
            return {"voice": voice}
        if isinstance(voice, SynthesizeVoice):

            payload = {}
            if voice.name:
                payload["voice"] = voice.name
            if voice.language:
                payload["language"] = voice.language
            if voice.speaker:
                payload["speaker"] = voice.speaker
            return payload
        return {"voice": str(voice)}

    async def _stream_from_http_endpoint(
        self,
        url: str,
        text: str,
        voice: Optional[Union[str, SynthesizeVoice]],
    ) -> None:
        """Stream PCM audio from an HTTP TTS endpoint."""
        payload = {
            "input": text,
            "response_format": "pcm",
        }
        payload.update(self._voice_payload(voice))
        # Some providers expect a model hint; the pipeline ignores but keep for compatibility
        payload.setdefault("model", "tts-1")

        timeout = httpx.Timeout(90.0, connect=2.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            async with client.stream("POST", url, json=payload) as response:
                response.raise_for_status()

                sample_rate = SAMPLE_RATE
                header_rate = response.headers.get("X-Sample-Rate") or response.headers.get("x-sample-rate")
                if header_rate:
                    try:
                        sample_rate = int(header_rate)
                    except ValueError:
                        sample_rate = SAMPLE_RATE

                await self.write_event(
                    AudioStart(rate=sample_rate, width=2, channels=1).event()
                )

                async for chunk in response.aiter_bytes(CHUNK_SIZE):
                    if chunk:
                        await self.write_event(
                            AudioChunk(audio=chunk, rate=sample_rate, width=2, channels=1).event()
                        )

                await self.write_event(AudioStop().event())

    async def _stream_from_url(
        self,
        url: str,
        text: str,
        voice: Optional[Union[str, SynthesizeVoice]],
    ):
        """Stream from fallback URL"""
        await self._stream_from_http_endpoint(url, text, voice)

    async def _stream_from_wyoming(
        self,
        host: str,
        port: int,
        text: str,
        voice: Optional[Union[str, SynthesizeVoice]],
    ) -> None:
        synth_voice = self._to_synthesize_voice(voice)
        logger.info(f"[TTS] Streaming via Wyoming {host}:{port} (voice={synth_voice})")

        async with AsyncTcpClient(host, port) as client:
            await client.write_event(
                Synthesize(text=text, voice=synth_voice).event()
            )

            started = False

            while True:
                event = await client.read_event()
                if event is None:
                    break

                if AudioStart.is_type(event.type):
                    audio_start = AudioStart.from_event(event)
                    await self.write_event(
                        AudioStart(
                            rate=audio_start.rate,
                            width=audio_start.width,
                            channels=audio_start.channels,
                        ).event()
                    )
                    started = True
                    continue

                if AudioChunk.is_type(event.type):
                    chunk = AudioChunk.from_event(event)
                    await self.write_event(
                        AudioChunk(
                            audio=chunk.audio,
                            rate=chunk.rate,
                            width=chunk.width,
                            channels=chunk.channels,
                        ).event()
                    )
                    continue

                if AudioStop.is_type(event.type):
                    await self.write_event(AudioStop().event())
                    started = False
                    break

                if Error.is_type(event.type):
                    err = Error.from_event(event)
                    raise RuntimeError(err.text)

            if started:
                await self.write_event(AudioStop().event())

    async def _synthesize_with_fallback(
        self,
        text: str,
        voice: Optional[Union[str, SynthesizeVoice]],
    ) -> None:
        """Attempt fallback synthesis via configured Wyoming host or HTTP URL."""
        fallback_errors: list[str] = []

        if FALLBACK_TTS_HOST:
            try:
                await self._stream_from_wyoming(
                    FALLBACK_TTS_HOST,
                    FALLBACK_TTS_PORT,
                    text,
                    voice,
                )
                return
            except Exception as exc:
                logger.warning("[TTS] Wyoming fallback failed: %s", exc)
                fallback_errors.append(str(exc))

        if FALLBACK_TTS_URL:
            try:
                await self._stream_from_url(FALLBACK_TTS_URL, text, voice)
                return
            except Exception as exc:
                logger.warning("[TTS] HTTP fallback failed: %s", exc)
                fallback_errors.append(str(exc))

        raise RuntimeError(
            "All fallback synthesis attempts failed: " + "; ".join(fallback_errors)
        )

    def _to_synthesize_voice(
        self, voice: Optional[Union[str, SynthesizeVoice]]
    ) -> Optional[SynthesizeVoice]:
        if voice is None:
            return None
        if isinstance(voice, SynthesizeVoice):
            return voice
        if isinstance(voice, str):
            return SynthesizeVoice(name=voice)
        return None

    async def _send_info(self):
        """Send Info event describing TTS capabilities"""
        info = Info(
            tts=[
                TtsProgram(
                    name="piper-main",
                    description="Piper TTS via piper-main streaming",
                    attribution=Attribution(name="Piper", url=""),
                    installed=True,
                    version="1.0.0",
                    voices=[
                        TtsVoice(
                            name="en_US-glados-medium",
                            description="GLaDOS medium voice (Piper)",
                            attribution=Attribution(name="Piper TTS", url=""),
                            installed=True,
                            version="1.0.0",
                            languages=["en-US"],
                        )
                    ],
                )
            ],
        )
        await self.write_event(info.event())


# FastAPI app
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start Wyoming TCP servers on startup"""
    global stt_server, tts_server

    print("🎙️  Starting Wyoming TCP servers...", flush=True)

    try:
        # STT Server
        stt_server = AsyncServer.from_uri("tcp://0.0.0.0:10300")
        print(f"✅ Created Wyoming STT server on tcp://0.0.0.0:10300", flush=True)

        # TTS Server
        tts_server = AsyncServer.from_uri("tcp://0.0.0.0:10210")
        print(f"✅ Created Wyoming TTS server on tcp://0.0.0.0:10210", flush=True)

        # Start servers in background with handler factories
        asyncio.create_task(stt_server.run(WhisperSTTHandler))
        print(f"✅ Started Wyoming STT server task", flush=True)

        asyncio.create_task(tts_server.run(PiperTTSHandler))
        print(f"✅ Started Wyoming TTS server task", flush=True)

        print(f"🎉 Wyoming TCP servers started successfully!", flush=True)
    except Exception as e:
        print(f"❌ Failed to start Wyoming servers: {e}", flush=True)
        import traceback
        traceback.print_exc()
        raise

    yield

    # Cleanup (not reached in practice, but good form)
    print("👋 Shutting down Wyoming TCP servers...", flush=True)
    pass


app = FastAPI(lifespan=lifespan)
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
        "ok": bool(ASR_URL and PRIMARY_TTS_HOST),
        "asr": ASR_URL,
        "tts": f"tcp://{PRIMARY_TTS_HOST}:{PRIMARY_TTS_PORT}",
        "primary_tts_host": PRIMARY_TTS_HOST,
        "primary_tts_port": PRIMARY_TTS_PORT,
        "fallback_tts_host": FALLBACK_TTS_HOST,
        "fallback_tts_port": FALLBACK_TTS_PORT,
        "fallback_tts_url": FALLBACK_TTS_URL,
        "tts_fallback": fallback_enabled,
        "wyoming_stt": "tcp://0.0.0.0:10300",
        "wyoming_tts": "tcp://0.0.0.0:10210",
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


# Keep HTTP endpoints for debugging/testing
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
    async with _fallback_lock:
        use_fallback = tts_fallback_enabled

    target_host = PRIMARY_TTS_HOST
    target_port = PRIMARY_TTS_PORT
    source_tag = "primary-tts"

    if use_fallback and FALLBACK_TTS_HOST:
        target_host = FALLBACK_TTS_HOST
        target_port = FALLBACK_TTS_PORT
        source_tag = "fallback-tts"

    if use_fallback and not FALLBACK_TTS_HOST and FALLBACK_TTS_URL:
        # Legacy HTTP fallback
        payload = {"input": text}
        if model:
            payload["model"] = model
        if voice:
            payload["voice"] = voice
        if format_hint:
            payload["format"] = format_hint

        async with httpx.AsyncClient(timeout=httpx.Timeout(90.0)) as client:
            try:
                async with client.stream("POST", FALLBACK_TTS_URL, json=payload) as response:
                    response.raise_for_status()

                    passthrough_headers = {
                        "X-Source": "fallback-tts-http",
                        "X-TTS-Fallback": "true",
                    }
                    for header in ("X-Sample-Rate", "X-Channels", "X-TTS-Status"):
                        if header in response.headers:
                            passthrough_headers[header] = response.headers[header]

                    async def http_audio_iter():
                        async for chunk in response.aiter_bytes():
                            if chunk:
                                yield chunk

                    media_type = response.headers.get("content-type", "audio/L16")
                    return StreamingResponse(
                        http_audio_iter(),
                        media_type=media_type,
                        headers=passthrough_headers,
                    )
            except httpx.HTTPError as exc:
                raise HTTPException(status_code=502, detail=f"TTS fallback error: {exc}") from exc

        raise HTTPException(status_code=500, detail="Fallback TTS URL unavailable")

    synth_voice = SynthesizeVoice(name=voice) if voice else None

    headers = {
        "X-Source": source_tag,
        "X-TTS-Fallback": str(use_fallback).lower(),
        "X-Sample-Rate": str(SAMPLE_RATE),
        "X-Channels": "1",
        "X-TTS-Status": "wyoming",
    }

    async def wyoming_audio_iter():
        async with AsyncTcpClient(target_host, target_port) as client:
            await client.write_event(
                Synthesize(text=text, voice=synth_voice).event()
            )

            while True:
                event = await client.read_event()
                if event is None:
                    break

                if AudioChunk.is_type(event.type):
                    chunk = AudioChunk.from_event(event)
                    headers["X-Sample-Rate"] = str(chunk.rate)
                    headers["X-Channels"] = str(chunk.channels)
                    yield chunk.audio
                elif AudioStop.is_type(event.type):
                    break
                elif Error.is_type(event.type):
                    err = Error.from_event(event)
                    raise HTTPException(status_code=502, detail=err.text)

    return StreamingResponse(
        wyoming_audio_iter(),
        media_type="audio/L16",
        headers=headers,
    )
