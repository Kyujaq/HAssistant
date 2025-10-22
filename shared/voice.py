"""
Windows Voice Control Executor

Bridges crew orchestrator with windows_voice_control.py
"""

import os
import sys
import logging
from pathlib import Path
from typing import Tuple

logger = logging.getLogger(__name__)

# Add clients directory to path
REPO_ROOT = Path(__file__).resolve().parents[1]
CLIENTS_DIR = REPO_ROOT / "clients"
if str(CLIENTS_DIR) not in sys.path:
    sys.path.append(str(CLIENTS_DIR))


class WindowsVoiceExecutor:
    """Executor for Windows Voice Control commands"""

    def __init__(self, base_url: str = None):
        """
        Initialize Windows Voice Executor

        Args:
            base_url: Optional HTTP service URL (for future HTTP bridge)
        """
        self.base_url = base_url

        try:
            # Import windows_voice_control functions
            from windows_voice_control import speak_command, type_text, send_keystroke, open_application
            self.speak_command = speak_command
            self.type_text = type_text
            self.send_keystroke = send_keystroke
            self.open_application = open_application
            logger.info("✅ Windows Voice Control bridge initialized")
        except ImportError as e:
            logger.error(f"Failed to import windows_voice_control: {e}")
            self.speak_command = None
            self.type_text = None
            self.send_keystroke = None
            self.open_application = None

    def speak(self, command: str) -> Tuple[bool, str]:
        """
        Execute a voice command

        Args:
            command: Natural language voice command

        Returns:
            (success, message) tuple
        """
        # Use bash wrapper if available (works better in Docker with Wyoming)
        import subprocess
        import shlex

        try:
            # Try using the send_command.sh wrapper (if running in Docker)
            result = subprocess.run(
                ['bash', '/app/send_command.sh', command],
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode == 0:
                return True, f"✅ Voice command executed: '{command}'"
            else:
                error = result.stderr or result.stdout
                logger.error(f"send_command.sh failed: {error}")
                return False, f"❌ Voice command failed: {error[:200]}"

        except FileNotFoundError:
            # Fallback to direct Python call (for host execution)
            if not self.speak_command:
                return False, "Windows Voice Control not available"

            try:
                success = self.speak_command(command)
                if success:
                    return True, f"✅ Voice command executed: '{command}'"
                return False, f"❌ Voice command failed: '{command}'"
            except Exception as e:
                logger.error(f"Voice command error: {e}")
                return False, f"Error executing voice command: {str(e)}"
        except Exception as e:
            logger.error(f"Voice command error: {e}")
            return False, f"Error executing voice command: {str(e)}"

    def type(self, text: str) -> Tuple[bool, str]:
        """Type text via voice command"""
        if not self.type_text:
            return False, "Windows Voice Control not available"

        try:
            success = self.type_text(text)
            if success:
                return True, f"✅ Typed text: '{text}'"
            return False, f"❌ Failed to type: '{text}'"
        except Exception as e:
            return False, f"Error typing text: {str(e)}"

    def keystroke(self, key: str) -> Tuple[bool, str]:
        """Send keystroke via voice command"""
        if not self.send_keystroke:
            return False, "Windows Voice Control not available"

        try:
            success = self.send_keystroke(key)
            if success:
                return True, f"✅ Sent keystroke: {key}"
            return False, f"❌ Failed keystroke: {key}"
        except Exception as e:
            return False, f"Error sending keystroke: {str(e)}"

    def open_app(self, app_name: str) -> Tuple[bool, str]:
        """Open application via voice command"""
        if not self.open_application:
            return False, "Windows Voice Control not available"

        try:
            success = self.open_application(app_name)
            if success:
                return True, f"✅ Opened application: {app_name}"
            return False, f"❌ Failed to open: {app_name}"
        except Exception as e:
            return False, f"Error opening application: {str(e)}"
