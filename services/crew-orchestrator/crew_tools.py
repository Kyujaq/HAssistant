"""
Crew Tools for UI Automation

These tools provide the interface between CrewAI agents and the actual
voice command and vision verification systems.
"""

import os
import sys
import logging
from pathlib import Path
from typing import Type
from crewai_tools import BaseTool
from pydantic import BaseModel, Field, validator

# Ensure repository root is available for shared helpers
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.append(str(REPO_ROOT))

from shared.voice import WindowsVoiceExecutor
from shared.vision import VisionGatewayClient

# Logging
logger = logging.getLogger("crew-orchestrator.tools")

# Configuration
WINDOWS_VOICE_CONTROL_URL = os.getenv("WINDOWS_VOICE_CONTROL_URL", "http://localhost:8085")
VISION_GATEWAY_URL = os.getenv("VISION_GATEWAY_URL", "http://vision-gateway:8088")

_voice_executor = WindowsVoiceExecutor(base_url=WINDOWS_VOICE_CONTROL_URL)
_vision_client = VisionGatewayClient(base_url=VISION_GATEWAY_URL)


class VoiceCommandInput(BaseModel):
    """Input schema for VoiceCommandTool."""
    command: str = Field(
        ..., 
        min_length=1, 
        max_length=200,
        description="The exact voice command to speak to Windows"
    )
    
    @validator('command')
    def validate_command(cls, v):
        """Validate that command is meaningful"""
        if not v or not v.strip():
            raise ValueError("Command cannot be empty or whitespace only")
        return v.strip()


class VoiceCommandTool(BaseTool):
    name: str = "Windows Voice Command Tool"
    description: str = (
        "Executes a single voice command on Windows. "
        "Takes a natural language command and speaks it to the system. "
        "Example commands: 'Open Excel', 'Click cell A1', 'Type hello world'"
    )
    args_schema: Type[BaseModel] = VoiceCommandInput

    def _run(self, command: str) -> str:
        """
        Execute a voice command.
        
        Args:
            command: The voice command to execute
            
        Returns:
            Status message indicating the command was executed
        """
        try:
            if not command or not command.strip():
                error_msg = "Voice command cannot be empty"
                logger.error(error_msg)
                return f"Error: {error_msg}"

            command = command.strip()
            logger.info(f"[VOICE TOOL] Executing voice command: '{command}'")

            success, message = _voice_executor.speak(command)
            if success:
                return message

            error_msg = f"Voice command failed: {message}"
            logger.error(error_msg)
            return error_msg

        except Exception as e:
            error_msg = f"Voice command error: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return error_msg


class VisionVerificationInput(BaseModel):
    """Input schema for VisionVerificationTool."""
    question: str = Field(
        ..., 
        min_length=1,
        max_length=200,
        description="The yes/no question to ask about the current screen state"
    )
    
    @validator('question')
    def validate_question(cls, v):
        """Validate that question is meaningful"""
        if not v or not v.strip():
            raise ValueError("Question cannot be empty or whitespace only")
        return v.strip()


class VisionVerificationTool(BaseTool):
    name: str = "Screen State Verifier"
    description: str = (
        "Verifies the current screen state by asking a yes/no question to the vision system. "
        "Use this to confirm that a UI action was successful. "
        "Example questions: 'Is Excel open?', 'Is cell A1 selected?', 'Does the screen show a save dialog?'"
    )
    args_schema: Type[BaseModel] = VisionVerificationInput

    def _run(self, question: str) -> str:
        """
        Ask a verification question about the current screen state.
        
        Args:
            question: The yes/no question to ask
            
        Returns:
            The answer from the vision system (yes/no)
        """
        try:
            if not question or not question.strip():
                error_msg = "Verification question cannot be empty"
                logger.error(error_msg)
                return f"Error: {error_msg}"

            question = question.strip()
            logger.info(f"[VISION TOOL] Verifying screen state: '{question}'")

            result = _vision_client.answer_question(question)
            answer = result.get("answer", "Unknown")
            reason = result.get("reason", "")

            detection = result.get("detection") or {}
            detection_details = detection.get("result", {}).get("vl", {})
            extra_context = []
            if detection_details.get("title"):
                extra_context.append(f"title={detection_details['title']}")
            if detection_details.get("action_state"):
                extra_context.append(f"state={detection_details['action_state']}")
            if detection_details.get("confidence") is not None:
                extra_context.append(f"confidence={detection_details['confidence']:.2f}")

            context_str = f" ({', '.join(extra_context)})" if extra_context else ""
            return f"Vision verification: '{question}' -> {answer}. {reason}{context_str}"

        except Exception as e:
            error_msg = f"Vision verification error: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return error_msg
