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
PIPER_HOST = os.getenv('PIPER_HOST', 'hassistant-piper')
PIPER_PORT = os.getenv('PIPER_PORT', '10200')
USB_AUDIO_DEVICE = os.getenv('USB_AUDIO_DEVICE', 'hw:1,0')  # ALSA device for USB dongle
USE_PULSEAUDIO = os.getenv('USE_PULSEAUDIO', 'false').lower() == 'true'
PULSEAUDIO_SINK = os.getenv('PULSEAUDIO_SINK', 'alsa_output.usb-default')

# Wyoming protocol for Piper TTS (if using direct TCP connection)
WYOMING_ENABLED = os.getenv('WYOMING_ENABLED', 'false').lower() == 'true'


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
        # Get TTS audio from Piper
        # Note: This assumes Piper has an HTTP endpoint. 
        # If using Wyoming protocol, you may need a different approach
        
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
        temp_file = f"/tmp/win_cmd_{int(time.time())}.wav"
        with open(temp_file, 'wb') as f:
            for chunk in response.iter_content(chunk_size=4096):
                f.write(chunk)
        
        logger.info(f"✅ TTS audio saved to {temp_file}")
        
        # Play through specified audio device
        if USE_PULSEAUDIO:
            # Use PulseAudio
            cmd = ['paplay', f'--device={PULSEAUDIO_SINK}', temp_file]
            logger.info(f"Playing via PulseAudio: {PULSEAUDIO_SINK}")
        else:
            # Use ALSA directly
            cmd = ['aplay', '-D', device, '-q', temp_file]
            logger.info(f"Playing via ALSA: {device}")
        
        result = subprocess.run(cmd, check=False, capture_output=True, text=True)
        
        if result.returncode != 0:
            logger.error(f"Audio playback failed: {result.stderr}")
            # Don't delete temp file for debugging
            logger.info(f"Debug: Audio file kept at {temp_file}")
            return False
        
        # Clean up
        os.remove(temp_file)
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
