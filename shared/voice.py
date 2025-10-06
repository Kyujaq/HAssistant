"""Windows Voice Control integration helpers."""

from __future__ import annotations

import os
import sys
import subprocess
import logging
from pathlib import Path
from typing import Callable, Dict, Optional, Tuple

import requests

LOGGER = logging.getLogger("shared.voice")

# Ensure repository root is on the import path so we can reuse client modules
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

try:  # pragma: no cover - exercised indirectly
    from clients import windows_voice_control as _windows_voice_control
except Exception:  # pragma: no cover - optional dependency in some environments
    _windows_voice_control = None

_DEFAULT_URL = os.getenv("WINDOWS_VOICE_CONTROL_URL", "http://localhost:8085").rstrip("/")
_DEFAULT_TIMEOUT = float(os.getenv("WINDOWS_VOICE_CONTROL_TIMEOUT", "10"))
_DEFAULT_SCRIPT = os.getenv(
    "WINDOWS_VOICE_CONTROL_SCRIPT",
    str(REPO_ROOT / "clients" / "windows_voice_control.py"),
)


class WindowsVoiceExecutor:
    """Executes Windows voice commands via HTTP service or local script."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        timeout: float = _DEFAULT_TIMEOUT,
        script_path: Optional[str] = _DEFAULT_SCRIPT,
    ) -> None:
        self.base_url = (base_url or _DEFAULT_URL).rstrip("/")
        self.timeout = timeout
        self.script_path = Path(script_path) if script_path else None
        self._session = requests.Session()

    @property
    def has_http_backend(self) -> bool:
        return bool(self.base_url)

    @property
    def has_module_backend(self) -> bool:
        return _windows_voice_control is not None

    @property
    def has_script_backend(self) -> bool:
        return bool(self.script_path and self.script_path.exists())

    @property
    def is_available(self) -> bool:
        return self.has_http_backend or self.has_module_backend or self.has_script_backend

    def speak(self, command: str) -> Tuple[bool, str]:
        """Execute a voice command and return success + message."""
        command = (command or "").strip()
        if not command:
            return False, "Voice command cannot be empty"

        # Try HTTP backend first for low latency interactions
        if self.has_http_backend:
            message = self._send_via_http(command)
            if message is not None:
                return True, message

        # Fallback: reuse local Python module implementation
        if self.has_module_backend:
            try:
                success = _windows_voice_control.speak_command(command)
                if success:
                    return True, f"Voice command executed via local module: '{command}'"
            except Exception as exc:  # pragma: no cover - defensive
                LOGGER.warning("Local windows_voice_control module failed: %s", exc)

        # Last resort: shell out to the helper script directly
        if self.has_script_backend:
            success, message = self._send_via_script(command)
            if success:
                return True, message

        return False, f"Failed to execute voice command: '{command}'"

    # Internal helpers -------------------------------------------------
    def _send_via_http(self, command: str) -> Optional[str]:
        try:
            response = self._session.post(
                f"{self.base_url}/speak",
                json={"text": command},
                timeout=self.timeout,
            )
            if response.status_code == 200:
                # Response may be JSON or plain text depending on implementation
                try:
                    data = response.json()
                except ValueError:
                    data = {"message": response.text.strip()}
                message = data.get("message") or data.get("detail") or data.get("status")
                if not message:
                    message = f"Voice command executed successfully: '{command}'"
                return message
            LOGGER.warning(
                "Windows voice control HTTP error %s: %s",
                response.status_code,
                response.text[:200],
            )
        except requests.RequestException as exc:
            LOGGER.debug("Windows voice control HTTP backend unavailable: %s", exc)
        return None

    def _send_via_script(self, command: str) -> Tuple[bool, str]:
        assert self.script_path is not None
        try:
            result = subprocess.run(
                [sys.executable, str(self.script_path), command],
                capture_output=True,
                text=True,
                timeout=self.timeout,
                check=False,
            )
            if result.returncode == 0:
                stdout = result.stdout.strip()
                message = stdout or f"Voice command executed via script: '{command}'"
                return True, message
            LOGGER.warning(
                "windows_voice_control script failed (code %s): %s",
                result.returncode,
                result.stderr.strip()[:200],
            )
        except (OSError, subprocess.SubprocessError) as exc:
            LOGGER.warning("Unable to execute windows_voice_control script: %s", exc)
        return False, f"windows_voice_control script failed for command '{command}'"

    # Convenience wrappers --------------------------------------------
    def speak_bool(self, command: str) -> bool:
        success, _ = self.speak(command)
        return success

    def type_text(self, text: str) -> bool:
        return self.speak_bool(f"Type {text}")

    def send_keystroke(self, key: str) -> bool:
        return self.speak_bool(f"Press {key}")

    def open_application(self, app: str) -> bool:
        return self.speak_bool(f"Open {app}")


DEFAULT_EXECUTOR = WindowsVoiceExecutor()


def execute_voice_command(
    command: str,
    executor: Optional[WindowsVoiceExecutor] = None,
) -> str:
    """Public helper used by services to execute a voice command."""
    exec_instance = executor or DEFAULT_EXECUTOR
    success, message = exec_instance.speak(command)
    if success:
        return message
    return f"Error: {message}"


def get_windows_voice_bridge(executor: Optional[WindowsVoiceExecutor] = None) -> Optional[Dict[str, Callable]]:
    """Return callables compatible with ComputerControlAgent expectations."""
    exec_instance = executor or DEFAULT_EXECUTOR
    if not exec_instance.is_available:
        return None

    return {
        "speak_command": exec_instance.speak_bool,
        "type_text": exec_instance.type_text,
        "send_keystroke": exec_instance.send_keystroke,
        "open_application": exec_instance.open_application,
    }


__all__ = [
    "DEFAULT_EXECUTOR",
    "WindowsVoiceExecutor",
    "execute_voice_command",
    "get_windows_voice_bridge",
]
