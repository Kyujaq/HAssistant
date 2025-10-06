#!/usr/bin/env python3
"""
Qwen PC Control Agent - Voice-controlled PC assistant using STT and Qwen LLM

This agent uses:
- Whisper STT for voice input
- Qwen LLM for natural language understanding
- System commands for PC control
"""

import os
import sys
import json
import time
import logging
import subprocess
import platform
import pyaudio
import wave
import requests
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from pathlib import Path

# Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger('qwen.pc_control')

# Configuration
WHISPER_STT_URL = os.getenv('WHISPER_STT_URL', 'http://hassistant-whisper:10300')
OLLAMA_URL = os.getenv('OLLAMA_URL', 'http://ollama-chat:11434')
QWEN_MODEL = os.getenv('QWEN_MODEL', 'qwen2.5:7b')

# Audio settings
SAMPLE_RATE = 16000
CHUNK_SIZE = 1024
SILENCE_THRESHOLD = 0.02
SILENCE_DURATION = 2.0  # seconds
MAX_RECORDING_DURATION = 10  # seconds


@dataclass
class PCCommand:
    """Represents a PC control command"""
    action: str
    target: str
    parameters: Dict[str, Any]


class PCControlAgent:
    """Qwen-based PC control agent with STT"""
    
    def __init__(self):
        self.system_type = platform.system()
        logger.info(f"🖥️ PC Control Agent initialized on {self.system_type}")
        
        # Define available commands
        self.commands = {
            'open_app': self._open_application,
            'close_app': self._close_application,
            'volume_up': self._volume_up,
            'volume_down': self._volume_down,
            'mute': self._mute,
            'unmute': self._unmute,
            'lock_screen': self._lock_screen,
            'screenshot': self._take_screenshot,
            'open_file': self._open_file,
            'list_files': self._list_files,
            'system_info': self._get_system_info,
        }
        
    def record_audio(self) -> Optional[str]:
        """Record audio from microphone"""
        logger.info("🎤 Recording audio... Speak now!")
        
        try:
            pa = pyaudio.PyAudio()
            stream = pa.open(
                rate=SAMPLE_RATE,
                channels=1,
                format=pyaudio.paInt16,
                input=True,
                frames_per_buffer=CHUNK_SIZE
            )
            
            frames = []
            silence_chunks = 0
            max_chunks = int(MAX_RECORDING_DURATION * SAMPLE_RATE / CHUNK_SIZE)
            
            for _ in range(max_chunks):
                data = stream.read(CHUNK_SIZE)
                frames.append(data)
                
                # Detect silence
                import numpy as np
                audio_data = np.frombuffer(data, dtype=np.int16)
                volume = np.abs(audio_data).mean() / 32768
                
                if volume < SILENCE_THRESHOLD:
                    silence_chunks += 1
                else:
                    silence_chunks = 0
                
                # Stop on silence
                if silence_chunks > int(SILENCE_DURATION * SAMPLE_RATE / CHUNK_SIZE):
                    logger.info("Silence detected, stopping recording")
                    break
            
            stream.stop_stream()
            stream.close()
            pa.terminate()
            
            if not frames:
                logger.warning("No audio recorded")
                return None
            
            # Save to temporary file
            temp_file = "/tmp/qwen_pc_recording.wav"
            wf = wave.open(temp_file, 'wb')
            wf.setnchannels(1)
            wf.setsampwidth(pa.get_sample_size(pyaudio.paInt16))
            wf.setframerate(SAMPLE_RATE)
            wf.writeframes(b''.join(frames))
            wf.close()
            
            logger.info(f"✅ Audio recorded to {temp_file}")
            return temp_file
            
        except Exception as e:
            logger.error(f"Error recording audio: {e}")
            return None
    
    def transcribe_audio(self, audio_file: str) -> Optional[str]:
        """Send audio to Whisper STT for transcription"""
        logger.info("🗣️ Transcribing audio with Whisper...")
        
        try:
            # Whisper STT endpoint
            url = f"{WHISPER_STT_URL}/api/stt"
            headers = {"Content-Type": "audio/wav"}
            
            with open(audio_file, 'rb') as f:
                audio_data = f.read()
            
            response = requests.post(url, headers=headers, data=audio_data, timeout=30)
            
            if response.status_code == 200:
                result = response.json()
                text = result.get('text', '').strip()
                logger.info(f"📝 Transcribed: {text}")
                return text
            else:
                logger.error(f"STT failed: {response.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"Error in transcription: {e}")
            return None
    
    def parse_command_with_qwen(self, text: str) -> Optional[PCCommand]:
        """Use Qwen LLM to parse natural language into PC command"""
        logger.info("🧠 Analyzing command with Qwen...")
        
        try:
            # Create a structured prompt for Qwen
            prompt = f"""You are a PC control assistant. Parse the following voice command into a structured PC action.

Available actions:
- open_app: Open an application (target: app name)
- close_app: Close an application (target: app name)
- volume_up: Increase volume
- volume_down: Decrease volume
- mute: Mute audio
- unmute: Unmute audio
- lock_screen: Lock the screen
- screenshot: Take a screenshot
- open_file: Open a file (target: file path)
- list_files: List files in a directory (target: directory path)
- system_info: Get system information

User command: "{text}"

Respond with ONLY a JSON object in this format:
{{"action": "action_name", "target": "target_value", "parameters": {{}}}}

If the command is unclear or cannot be executed, respond with:
{{"action": "unknown", "target": "", "parameters": {{"error": "explanation"}}}}

JSON response:"""

            # Call Qwen via Ollama
            url = f"{OLLAMA_URL}/api/generate"
            payload = {
                "model": QWEN_MODEL,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.3,  # Low temperature for structured output
                    "num_predict": 200
                }
            }
            
            response = requests.post(url, json=payload, timeout=30)
            
            if response.status_code == 200:
                result = response.json()
                response_text = result.get('response', '').strip()
                
                # Extract JSON from response
                import re
                json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
                if json_match:
                    command_data = json.loads(json_match.group(0))
                    command = PCCommand(
                        action=command_data.get('action', 'unknown'),
                        target=command_data.get('target', ''),
                        parameters=command_data.get('parameters', {})
                    )
                    logger.info(f"📋 Parsed command: {command.action} -> {command.target}")
                    return command
                else:
                    logger.error("Could not extract JSON from Qwen response")
                    return None
            else:
                logger.error(f"Qwen API failed: {response.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"Error parsing command: {e}")
            return None
    
    def execute_command(self, command: PCCommand) -> Dict[str, Any]:
        """Execute the parsed PC command"""
        logger.info(f"⚡ Executing: {command.action}")
        
        if command.action == 'unknown':
            error = command.parameters.get('error', 'Unknown command')
            logger.warning(f"Cannot execute: {error}")
            return {"success": False, "message": error}
        
        if command.action not in self.commands:
            logger.error(f"Unsupported action: {command.action}")
            return {"success": False, "message": f"Unsupported action: {command.action}"}
        
        try:
            result = self.commands[command.action](command.target, command.parameters)
            return {"success": True, "message": result}
        except Exception as e:
            logger.error(f"Error executing command: {e}")
            return {"success": False, "message": str(e)}
    
    # Command implementations
    def _open_application(self, app_name: str, params: Dict) -> str:
        """Open an application"""
        logger.info(f"Opening application: {app_name}")
        
        if self.system_type == "Linux":
            # Try common Linux applications
            apps = {
                'browser': 'firefox',
                'firefox': 'firefox',
                'chrome': 'google-chrome',
                'terminal': 'gnome-terminal',
                'files': 'nautilus',
                'calculator': 'gnome-calculator',
                'text editor': 'gedit',
                'code': 'code',
            }
            cmd = apps.get(app_name.lower(), app_name.lower())
            subprocess.Popen([cmd], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            
        elif self.system_type == "Darwin":  # macOS
            subprocess.Popen(['open', '-a', app_name])
            
        elif self.system_type == "Windows":
            subprocess.Popen(['start', app_name], shell=True)
        
        return f"Opened {app_name}"
    
    def _close_application(self, app_name: str, params: Dict) -> str:
        """Close an application"""
        logger.info(f"Closing application: {app_name}")
        
        if self.system_type == "Linux":
            subprocess.run(['pkill', '-f', app_name])
        elif self.system_type == "Darwin":
            subprocess.run(['killall', app_name])
        elif self.system_type == "Windows":
            subprocess.run(['taskkill', '/IM', f"{app_name}.exe", '/F'])
        
        return f"Closed {app_name}"
    
    def _volume_up(self, target: str, params: Dict) -> str:
        """Increase volume"""
        if self.system_type == "Linux":
            subprocess.run(['amixer', 'set', 'Master', '5%+'])
        elif self.system_type == "Darwin":
            subprocess.run(['osascript', '-e', 'set volume output volume (output volume of (get volume settings) + 10)'])
        elif self.system_type == "Windows":
            # Windows volume control requires more complex implementation
            pass
        
        return "Volume increased"
    
    def _volume_down(self, target: str, params: Dict) -> str:
        """Decrease volume"""
        if self.system_type == "Linux":
            subprocess.run(['amixer', 'set', 'Master', '5%-'])
        elif self.system_type == "Darwin":
            subprocess.run(['osascript', '-e', 'set volume output volume (output volume of (get volume settings) - 10)'])
        
        return "Volume decreased"
    
    def _mute(self, target: str, params: Dict) -> str:
        """Mute audio"""
        if self.system_type == "Linux":
            subprocess.run(['amixer', 'set', 'Master', 'mute'])
        elif self.system_type == "Darwin":
            subprocess.run(['osascript', '-e', 'set volume with output muted'])
        
        return "Audio muted"
    
    def _unmute(self, target: str, params: Dict) -> str:
        """Unmute audio"""
        if self.system_type == "Linux":
            subprocess.run(['amixer', 'set', 'Master', 'unmute'])
        elif self.system_type == "Darwin":
            subprocess.run(['osascript', '-e', 'set volume without output muted'])
        
        return "Audio unmuted"
    
    def _lock_screen(self, target: str, params: Dict) -> str:
        """Lock the screen"""
        if self.system_type == "Linux":
            subprocess.Popen(['xdg-screensaver', 'lock'])
        elif self.system_type == "Darwin":
            subprocess.run(['pmset', 'displaysleepnow'])
        elif self.system_type == "Windows":
            subprocess.run(['rundll32.exe', 'user32.dll,LockWorkStation'])
        
        return "Screen locked"
    
    def _take_screenshot(self, target: str, params: Dict) -> str:
        """Take a screenshot"""
        screenshot_path = Path.home() / "Pictures" / f"screenshot_{int(time.time())}.png"
        
        if self.system_type == "Linux":
            subprocess.run(['gnome-screenshot', '-f', str(screenshot_path)])
        elif self.system_type == "Darwin":
            subprocess.run(['screencapture', str(screenshot_path)])
        elif self.system_type == "Windows":
            # Windows screenshot requires PIL or other library
            pass
        
        return f"Screenshot saved to {screenshot_path}"
    
    def _open_file(self, file_path: str, params: Dict) -> str:
        """Open a file"""
        if self.system_type == "Linux":
            subprocess.Popen(['xdg-open', file_path])
        elif self.system_type == "Darwin":
            subprocess.Popen(['open', file_path])
        elif self.system_type == "Windows":
            subprocess.Popen(['start', file_path], shell=True)
        
        return f"Opened {file_path}"
    
    def _list_files(self, directory: str, params: Dict) -> str:
        """List files in directory"""
        if not directory:
            directory = str(Path.home())
        
        try:
            path = Path(directory)
            if path.exists() and path.is_dir():
                files = [f.name for f in path.iterdir()][:10]  # Limit to 10
                return f"Files in {directory}: {', '.join(files)}"
            else:
                return f"Directory not found: {directory}"
        except Exception as e:
            return f"Error listing files: {e}"
    
    def _get_system_info(self, target: str, params: Dict) -> str:
        """Get system information"""
        import psutil
        
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        info = f"""System Information:
- OS: {platform.system()} {platform.release()}
- CPU Usage: {cpu_percent}%
- Memory: {memory.percent}% used ({memory.used // (1024**3)}GB / {memory.total // (1024**3)}GB)
- Disk: {disk.percent}% used ({disk.used // (1024**3)}GB / {disk.total // (1024**3)}GB)"""
        
        return info
    
    def process_voice_command(self):
        """Main loop: record -> transcribe -> parse -> execute"""
        logger.info("\n" + "="*60)
        logger.info("🎤 Ready for voice command! Speak now...")
        logger.info("="*60 + "\n")
        
        # Step 1: Record audio
        audio_file = self.record_audio()
        if not audio_file:
            logger.error("Failed to record audio")
            return
        
        # Step 2: Transcribe with Whisper
        text = self.transcribe_audio(audio_file)
        if not text:
            logger.error("Failed to transcribe audio")
            return
        
        # Step 3: Parse with Qwen
        command = self.parse_command_with_qwen(text)
        if not command:
            logger.error("Failed to parse command")
            return
        
        # Step 4: Execute
        result = self.execute_command(command)
        
        logger.info("\n" + "="*60)
        logger.info(f"✅ Result: {result['message']}")
        logger.info("="*60 + "\n")
        
        # Cleanup
        if os.path.exists(audio_file):
            os.remove(audio_file)
    
    def run_interactive(self):
        """Run in interactive mode"""
        logger.info("🚀 Qwen PC Control Agent Starting...")
        logger.info(f"   STT: {WHISPER_STT_URL}")
        logger.info(f"   LLM: {OLLAMA_URL} ({QWEN_MODEL})")
        logger.info(f"   Platform: {self.system_type}")
        logger.info("\nPress Ctrl+C to exit\n")
        
        try:
            while True:
                input("\n👉 Press Enter to start voice command (or Ctrl+C to exit)...")
                self.process_voice_command()
        except KeyboardInterrupt:
            logger.info("\n\n👋 Shutting down...")


def main():
    """Main entry point"""
    agent = PCControlAgent()
    agent.run_interactive()


if __name__ == "__main__":
    main()
