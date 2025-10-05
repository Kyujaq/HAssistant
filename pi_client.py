#!/usr/bin/env python3
"""
Clean Pi Client for Home Assistant Assist Integration
Replaces custom brain service with HA's native Assist API
"""

import os
import sys
import time
import logging
import asyncio
import subprocess
from pathlib import Path
from typing import Optional
import uuid
from datetime import datetime, timedelta

import numpy as np
import pvporcupine
import sounddevice as sd
import requests
import pyaudio
import wave

# Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger('glados.pi')

# Configuration from environment
PV_ACCESS_KEY = os.getenv('PV_ACCESS_KEY')  # Porcupine wake word key
HA_URL = os.getenv('HA_URL', 'http://assistant-ha:8123')
HA_TOKEN = os.getenv('HA_TOKEN')
TTS_URL = os.getenv('TTS_URL', 'http://hassistant-tts:8004')
WAKE_WORD_MODEL = os.getenv('WAKE_WORD_MODEL', 'computer')  # or path to .ppn file

# Audio settings
SAMPLE_RATE = 16000
CHUNK_SIZE = 512
SILENCE_THRESHOLD = 0.02
SILENCE_DURATION = 1.5  # seconds
MAX_RECORDING_DURATION = 10  # seconds

class GLaDOSPiClient:
    """Raspberry Pi voice client for Home Assistant + GLaDOS"""

    def __init__(self):
        self.porcupine = None
        self.audio_stream = None
        self.is_listening = False

        if not PV_ACCESS_KEY:
            logger.error("PV_ACCESS_KEY not set! Cannot initialize wake word detection.")
            sys.exit(1)

        if not HA_TOKEN:
            logger.error("HA_TOKEN not set! Cannot communicate with Home Assistant.")
            sys.exit(1)

    def initialize_wake_word(self):
        """Initialize Porcupine wake word detection"""
        try:
            # Use built-in keyword or custom model
            if WAKE_WORD_MODEL.endswith('.ppn'):
                keyword_paths = [WAKE_WORD_MODEL]
                logger.info(f"Using custom wake word model: {WAKE_WORD_MODEL}")
            else:
                # Built-in keywords: computer, jarvis, alexa, etc.
                keywords = [WAKE_WORD_MODEL]
                keyword_paths = None
                logger.info(f"Using built-in wake word: {WAKE_WORD_MODEL}")

            self.porcupine = pvporcupine.create(
                access_key=PV_ACCESS_KEY,
                keywords=keywords if not keyword_paths else None,
                keyword_paths=keyword_paths
            )
            logger.info(f"✅ Wake word detection initialized (sample rate: {self.porcupine.sample_rate})")
        except Exception as e:
            logger.error(f"Failed to initialize wake word: {e}")
            sys.exit(1)

    def play_acknowledgment(self):
        """Play quick acknowledgment beep"""
        # Simple beep to confirm wake word detected
        try:
            subprocess.run(['aplay', '-q', '/usr/share/sounds/alsa/Front_Center.wav'],
                          check=False, timeout=1)
        except (subprocess.TimeoutExpired, FileNotFoundError):
            # Ignore if sound file not found or timeout
            pass

    def listen_for_wake_word(self):
        """Listen continuously for wake word"""
        logger.info(f"👂 Listening for wake word: '{WAKE_WORD_MODEL}'...")

        pa = pyaudio.PyAudio()
        audio_stream = pa.open(
            rate=self.porcupine.sample_rate,
            channels=1,
            format=pyaudio.paInt16,
            input=True,
            frames_per_buffer=self.porcupine.frame_length
        )

        try:
            while True:
                pcm = audio_stream.read(self.porcupine.frame_length)
                pcm_array = np.frombuffer(pcm, dtype=np.int16)

                keyword_index = self.porcupine.process(pcm_array)

                if keyword_index >= 0:
                    logger.info("🎤 Wake word detected!")
                    self.play_acknowledgment()
                    audio_stream.stop_stream()

                    # Record user speech
                    audio_file = self.record_speech(pa)

                    if audio_file:
                        # Send to HA Assist
                        self.process_with_ha_assist(audio_file)
                        os.remove(audio_file)  # Clean up

                    # Resume wake word listening
                    audio_stream.start_stream()
                    logger.info("👂 Listening for wake word...")

        except KeyboardInterrupt:
            logger.info("Shutting down...")
        finally:
            audio_stream.close()
            pa.terminate()

    def record_speech(self, pa) -> Optional[str]:
        """Record user speech after wake word"""
        logger.info("🎙️ Recording speech...")

        audio_stream = pa.open(
            rate=SAMPLE_RATE,
            channels=1,
            format=pyaudio.paInt16,
            input=True,
            frames_per_buffer=CHUNK_SIZE
        )

        frames = []
        silence_chunks = 0
        max_chunks = int(MAX_RECORDING_DURATION * SAMPLE_RATE / CHUNK_SIZE)

        for i in range(max_chunks):
            data = audio_stream.read(CHUNK_SIZE)
            frames.append(data)

            # Detect silence
            audio_data = np.frombuffer(data, dtype=np.int16)
            volume = np.abs(audio_data).mean()

            if volume < SILENCE_THRESHOLD * 32768:
                silence_chunks += 1
            else:
                silence_chunks = 0

            # Stop on silence
            if silence_chunks > int(SILENCE_DURATION * SAMPLE_RATE / CHUNK_SIZE):
                logger.info("Silence detected, stopping recording")
                break

        audio_stream.close()

        if not frames:
            logger.warning("No audio recorded")
            return None

        # Save to temporary WAV file
        temp_file = f"/tmp/glados_recording_{int(time.time())}.wav"
        wf = wave.open(temp_file, 'wb')
        wf.setnchannels(1)
        wf.setsampwidth(pa.get_sample_size(pyaudio.paInt16))
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(b''.join(frames))
        wf.close()

        logger.info(f"✅ Recorded {len(frames)} chunks to {temp_file}")
        return temp_file

    def process_with_ha_assist(self, audio_file: str):
        """Send audio to Home Assistant Assist API"""
        logger.info("🧠 Processing with Home Assistant Assist...")

        try:
            # HA Assist STT endpoint
            url = f"{HA_URL}/api/stt/stt.whisper"
            headers = {
                "Authorization": f"Bearer {HA_TOKEN}",
                "Content-Type": "audio/wav"
            }

            with open(audio_file, 'rb') as f:
                audio_data = f.read()

            # Send to STT
            response = requests.post(url, headers=headers, data=audio_data, timeout=10)

            if response.status_code != 200:
                logger.error(f"STT failed: {response.status_code} - {response.text}")
                return

            stt_result = response.json()
            text = stt_result.get('text', '')

            if not text:
                logger.warning("No speech detected")
                return

            logger.info(f"📝 Transcribed: {text}")

            # Send to Conversation (Ollama)
            self.send_to_conversation(text)

        except Exception as e:
            logger.error(f"Error processing with HA: {e}")

    def send_to_conversation(self, text: str):
        """Send text to HA Conversation (Ollama) and get response"""
        logger.info("💭 Sending to GLaDOS (Ollama)...")

        try:
            url = f"{HA_URL}/api/conversation/process"
            headers = {
                "Authorization": f"Bearer {HA_TOKEN}",
                "Content-Type": "application/json"
            }
            payload = {
                "text": text,
                "language": "en",
                "conversation_id": str(uuid.uuid4())
            }

            response = requests.post(url, headers=headers, json=payload, timeout=30)

            if response.status_code != 200:
                logger.error(f"Conversation failed: {response.status_code}")
                return

            result = response.json()
            response_text = result.get('response', {}).get('speech', {}).get('plain', {}).get('speech', '')

            if not response_text:
                logger.warning("No response from GLaDOS")
                return

            logger.info(f"🗣️ GLaDOS says: {response_text}")

            # Convert to speech and play
            self.speak(response_text)

        except Exception as e:
            logger.error(f"Error in conversation: {e}")

    def speak(self, text: str):
        """Convert text to GLaDOS voice and play"""
        logger.info("🔊 Speaking with GLaDOS voice...")

        try:
            # Call Piper TTS service
            url = f"{TTS_URL}/synthesize"
            params = {"text": text}

            response = requests.get(url, params=params, stream=True, timeout=10)

            if response.status_code != 200:
                logger.error(f"TTS failed: {response.status_code}")
                return

            # Save audio temporarily
            temp_audio = f"/tmp/glados_tts_{int(time.time())}.wav"
            with open(temp_audio, 'wb') as f:
                for chunk in response.iter_content(chunk_size=4096):
                    f.write(chunk)

            # Play audio
            subprocess.run(['aplay', '-q', temp_audio], check=False)
            os.remove(temp_audio)

        except Exception as e:
            logger.error(f"Error in TTS: {e}")

    def run(self):
        """Main run loop"""
        logger.info("🚀 GLaDOS Pi Client Starting...")
        logger.info(f"   HA URL: {HA_URL}")
        logger.info(f"   TTS URL: {TTS_URL}")

        self.initialize_wake_word()
        self.listen_for_wake_word()


if __name__ == "__main__":
    client = GLaDOSPiClient()
    client.run()
