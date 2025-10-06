#!/usr/bin/env python3
"""
Windows Voice Control Bridge
Sends commands to Windows laptop via audio cable and Piper TTS

This script allows you to control a Windows laptop using Windows Voice Assistant
by routing TTS audio through a USB audio dongle connected via 3.5mm aux cable.

Usage:
    python3 windows_voice_control.py "Open Notepad"
    python3 windows_voice_control.py "Type Hello World"
    python3 windows_voice_control.py "Press Enter"
"""

import os
import sys
import time
import logging
import subprocess
import requests
from typing import Optional

# Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger('windows_voice_control')

# Configuration from environment or defaults
TTS_URL = os.getenv('TTS_URL', 'http://localhost:10200')
PIPER_HOST = os.getenv('PIPER_HOST', 'piper-glados')
PIPER_PORT = os.getenv('PIPER_PORT', '10200')
USB_AUDIO_DEVICE = os.getenv('USB_AUDIO_DEVICE', 'hw:1,0')  # ALSA device for USB dongle
USE_PULSEAUDIO = os.getenv('USE_PULSEAUDIO', 'false').lower() == 'true'
PULSEAUDIO_SINK = os.getenv('PULSEAUDIO_SINK', 'alsa_output.usb-default')

# Wyoming protocol for Piper TTS (if using direct TCP connection)
WYOMING_ENABLED = os.getenv('WYOMING_ENABLED', 'false').lower() == 'true'

# Direct Piper TTS configuration (for Windows voice commands - clearer voice)
USE_DIRECT_PIPER = os.getenv('USE_DIRECT_PIPER', 'false').lower() == 'true'
PIPER_EXECUTABLE = os.getenv('PIPER_EXECUTABLE', '/usr/bin/piper')
PIPER_VOICE_MODEL = os.getenv('PIPER_VOICE_MODEL', 'en_US-kathleen-high')  # Clearer voice for Windows
PIPER_MODEL_PATH = os.getenv('PIPER_MODEL_PATH', '/usr/share/piper-voices')
PIPER_LENGTH_SCALE = float(os.getenv('PIPER_LENGTH_SCALE', '1.1'))  # Slower speech for clarity
PIPER_VOLUME_BOOST = float(os.getenv('PIPER_VOLUME_BOOST', '1.0'))  # Volume multiplier


def synthesize_with_piper(text: str, output_file: str) -> bool:
    """
    Synthesize speech using direct Piper command for maximum clarity
    
    Args:
        text: Text to synthesize
        output_file: Output WAV file path
        
    Returns:
        True if successful, False otherwise
    """
    try:
        # Build Piper command
        model_file = f"{PIPER_MODEL_PATH}/{PIPER_VOICE_MODEL}.onnx"
        config_file = f"{PIPER_MODEL_PATH}/{PIPER_VOICE_MODEL}.onnx.json"
        
        cmd = [
            PIPER_EXECUTABLE,
            '--model', model_file,
            '--config', config_file,
            '--output_file', output_file,
            '--length_scale', str(PIPER_LENGTH_SCALE)
        ]
        
        # Run Piper with text input via stdin
        result = subprocess.run(
            cmd,
            input=text.encode('utf-8'),
            capture_output=True,
            check=False
        )
        
        if result.returncode != 0:
            logger.error(f"Piper synthesis failed: {result.stderr.decode()}")
            return False
        
        logger.info(f"✅ Synthesized with Piper (voice: {PIPER_VOICE_MODEL}, length_scale: {PIPER_LENGTH_SCALE})")
        return True
        
    except FileNotFoundError:
        logger.error(f"Piper executable not found at {PIPER_EXECUTABLE}")
        return False
    except Exception as e:
        logger.error(f"Error synthesizing with Piper: {e}")
        return False


def adjust_audio_volume(input_file: str, output_file: str, volume: float) -> bool:
    """
    Adjust audio volume using sox/ffmpeg if available
    
    Args:
        input_file: Input WAV file
        output_file: Output WAV file
        volume: Volume multiplier (e.g., 1.5 for 150%)
        
    Returns:
        True if successful, False otherwise
    """
    if volume == 1.0:
        # No adjustment needed
        if input_file != output_file:
            subprocess.run(['cp', input_file, output_file], check=True)
        return True
    
    try:
        # Try sox first (preferred for audio processing)
        cmd = ['sox', input_file, output_file, 'vol', str(volume)]
        result = subprocess.run(cmd, capture_output=True, check=False)
        
        if result.returncode == 0:
            logger.info(f"✅ Volume adjusted to {volume}x using sox")
            return True
        
        # Fallback to ffmpeg
        cmd = [
            'ffmpeg', '-i', input_file, '-af', f'volume={volume}',
            '-y', output_file
        ]
        result = subprocess.run(cmd, capture_output=True, check=False)
        
        if result.returncode == 0:
            logger.info(f"✅ Volume adjusted to {volume}x using ffmpeg")
            return True
        
        logger.warning("Could not adjust volume (sox/ffmpeg not available)")
        # Copy original file if volume adjustment fails
        if input_file != output_file:
            subprocess.run(['cp', input_file, output_file], check=True)
        return True
        
    except Exception as e:
        logger.warning(f"Volume adjustment failed: {e}, using original audio")
        if input_file != output_file:
            subprocess.run(['cp', input_file, output_file], check=True)
        return True


def speak_command(command: str, device: Optional[str] = None) -> bool:
    """
    Send voice command to Windows via Piper TTS + audio cable
    
    Args:
        command: Voice command text (e.g., "Open Notepad")
        device: Audio device to use (defaults to USB_AUDIO_DEVICE)
        
    Returns:
        True if successful, False otherwise
    """
    if device is None:
        device = USB_AUDIO_DEVICE
    
    logger.info(f"🎤 Sending command: '{command}'")
    logger.info(f"🔊 Output device: {device}")
    
    try:
        # Save audio temporarily
        temp_audio = f"/tmp/win_cmd_{int(time.time())}.wav"
        temp_adjusted = f"/tmp/win_cmd_adj_{int(time.time())}.wav"
        
        # Choose synthesis method
        if USE_DIRECT_PIPER:
            # Use direct Piper command for clearer voice (kathleen-high)
            logger.info(f"Using direct Piper (voice: {PIPER_VOICE_MODEL})")
            success = synthesize_with_piper(command, temp_audio)
            if not success:
                logger.error("Direct Piper synthesis failed")
                return False
        else:
            # Use HTTP endpoint (default GLaDOS voice via Wyoming)
            if WYOMING_ENABLED:
                logger.warning("Wyoming protocol mode not yet implemented. Use HTTP mode.")
                return False
            
            # HTTP request to Piper (if you have an HTTP wrapper around Wyoming)
            response = requests.get(
                f"{TTS_URL}/synthesize",
                params={"text": command},
                stream=True,
                timeout=10
            )
            
            if response.status_code != 200:
                logger.error(f"TTS request failed: {response.status_code}")
                return False
            
            # Save audio temporarily
            with open(temp_audio, 'wb') as f:
                for chunk in response.iter_content(chunk_size=4096):
                    f.write(chunk)
        
        logger.info(f"✅ TTS audio saved to {temp_audio}")
        
        # Apply volume adjustment if needed
        if PIPER_VOLUME_BOOST != 1.0:
            adjust_audio_volume(temp_audio, temp_adjusted, PIPER_VOLUME_BOOST)
            playback_file = temp_adjusted
        else:
            playback_file = temp_audio
        
        # Play through specified audio device
        if USE_PULSEAUDIO:
            # Use PulseAudio
            cmd = ['paplay', f'--device={PULSEAUDIO_SINK}', playback_file]
            logger.info(f"Playing via PulseAudio: {PULSEAUDIO_SINK}")
        else:
            # Use ALSA directly
            cmd = ['aplay', '-D', device, '-q', playback_file]
            logger.info(f"Playing via ALSA: {device}")
        
        result = subprocess.run(cmd, check=False, capture_output=True, text=True)
        
        if result.returncode != 0:
            logger.error(f"Audio playback failed: {result.stderr}")
            # Don't delete temp file for debugging
            logger.info(f"Debug: Audio file kept at {playback_file}")
            return False
        
        # Clean up
        if os.path.exists(temp_audio):
            os.remove(temp_audio)
        if os.path.exists(temp_adjusted) and temp_adjusted != temp_audio:
            os.remove(temp_adjusted)
        logger.info("✅ Command sent successfully")
        return True
        
    except requests.exceptions.RequestException as e:
        logger.error(f"TTS request error: {e}")
        return False
    except Exception as e:
        logger.error(f"Error sending command: {e}")
        return False


def test_audio_device(device: Optional[str] = None) -> bool:
    """
    Test if the audio device is working
    
    Args:
        device: Audio device to test (defaults to USB_AUDIO_DEVICE)
        
    Returns:
        True if device is working
    """
    if device is None:
        device = USB_AUDIO_DEVICE
    
    logger.info(f"Testing audio device: {device}")
    
    try:
        # Try to play a test sound
        if USE_PULSEAUDIO:
            cmd = ['pactl', 'list', 'sinks', 'short']
        else:
            cmd = ['aplay', '-l']
        
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        logger.info("Audio system status:")
        logger.info(result.stdout)
        
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"Audio device test failed: {e}")
        return False


def send_keystroke(key: str) -> bool:
    """
    Send a specific keystroke command
    
    Args:
        key: Key name (e.g., "Enter", "Tab", "Escape")
        
    Returns:
        True if successful
    """
    return speak_command(f"Press {key}")


def type_text(text: str) -> bool:
    """
    Type text on Windows
    
    Args:
        text: Text to type
        
    Returns:
        True if successful
    """
    return speak_command(f"Type {text}")


def open_application(app_name: str) -> bool:
    """
    Open an application on Windows
    
    Args:
        app_name: Application name (e.g., "Notepad", "Excel", "Chrome")
        
    Returns:
        True if successful
    """
    return speak_command(f"Open {app_name}")


def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Send voice commands to Windows via audio cable',
        epilog='''
Examples:
  %(prog)s "Open Notepad"
  %(prog)s "Type Hello World"
  %(prog)s --key Enter
  %(prog)s --type "Hello from Linux"
  %(prog)s --test
        '''
    )
    
    parser.add_argument('command', nargs='*', help='Voice command to send')
    parser.add_argument('--test', action='store_true', help='Test audio device')
    parser.add_argument('--device', type=str, help='Override audio device')
    parser.add_argument('--key', type=str, help='Send specific keystroke (e.g., Enter, Tab)')
    parser.add_argument('--type', type=str, help='Type specific text')
    parser.add_argument('--open', type=str, help='Open specific application')
    
    args = parser.parse_args()
    
    # Override device if specified
    device = args.device if args.device else None
    
    # Handle different modes
    if args.test:
        logger.info("Testing audio device...")
        success = test_audio_device(device)
        sys.exit(0 if success else 1)
    
    elif args.key:
        success = send_keystroke(args.key)
        sys.exit(0 if success else 1)
    
    elif args.type:
        success = type_text(args.type)
        sys.exit(0 if success else 1)
    
    elif args.open:
        success = open_application(args.open)
        sys.exit(0 if success else 1)
    
    elif args.command:
        command = " ".join(args.command)
        success = speak_command(command, device)
        sys.exit(0 if success else 1)
    
    else:
        parser.print_help()
        print("\n❌ No command specified")
        print("\nExamples:")
        print("  python3 windows_voice_control.py 'Open Notepad'")
        print("  python3 windows_voice_control.py --type 'Hello World'")
        print("  python3 windows_voice_control.py --key Enter")
        print("  python3 windows_voice_control.py --open Excel")
        print("  python3 windows_voice_control.py --test")
        sys.exit(1)


if __name__ == "__main__":
    main()
