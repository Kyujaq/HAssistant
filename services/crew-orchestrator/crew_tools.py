"""
Crew Tools for UI Automation

These tools provide the interface between CrewAI agents and the actual
voice command and vision verification systems.
"""

import os
import time
import logging
from typing import Type, Optional
from crewai_tools import BaseTool
from pydantic import BaseModel, Field, validator
import requests

# Logging
logger = logging.getLogger("crew-orchestrator.tools")

# Configuration
WINDOWS_VOICE_CONTROL_URL = os.getenv("WINDOWS_VOICE_CONTROL_URL", "http://localhost:8085")
VISION_GATEWAY_URL = os.getenv("VISION_GATEWAY_URL", "http://vision-gateway:8088")


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
            # Validate command
            if not command or not command.strip():
                error_msg = "Voice command cannot be empty"
                logger.error(error_msg)
                return f"Error: {error_msg}"
            
            command = command.strip()
            logger.info(f"[VOICE TOOL] Speaking: '{command}'")
            
            # TODO: Implement actual integration with windows_voice_control service
            # Uncomment and test when service is available:
            # try:
            #     response = requests.post(
            #         f"{WINDOWS_VOICE_CONTROL_URL}/speak",
            #         json={"text": command},
            #         timeout=10
            #     )
            #     if response.status_code == 200:
            #         return f"Voice command executed successfully: '{command}'"
            #     else:
            #         error_msg = f"Voice command failed: {response.text}"
            #         logger.error(error_msg)
            #         return error_msg
            # except requests.RequestException as e:
            #     error_msg = f"Voice command connection error: {str(e)}"
            #     logger.error(error_msg)
            #     return error_msg
            
            # Placeholder implementation for now
            return f"Voice command executed: '{command}'"
            
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
            # Validate question
            if not question or not question.strip():
                error_msg = "Verification question cannot be empty"
                logger.error(error_msg)
                return f"Error: {error_msg}"
            
            question = question.strip()
            logger.info(f"[VISION TOOL] Verifying: '{question}'")
            
            # TODO: Implement actual integration with vision-gateway service
            # Uncomment and test when service is available:
            # try:
            #     response = requests.post(
            #         f"{VISION_GATEWAY_URL}/query",
            #         json={"question": question},
            #         timeout=30
            #     )
            #     if response.status_code == 200:
            #         result = response.json()
            #         answer = result.get("answer", "Unknown")
            #         return f"Vision verification: '{question}' - {answer}"
            #     else:
            #         error_msg = f"Vision verification failed: {response.text}"
            #         logger.error(error_msg)
            #         return error_msg
            # except requests.RequestException as e:
            #     error_msg = f"Vision verification connection error: {str(e)}"
            #     logger.error(error_msg)
            #     return error_msg
            
            # Placeholder implementation - simulate verification delay
            time.sleep(2)
            return f"Vision verification: '{question}' - Yes (placeholder)"
            
        except Exception as e:
            error_msg = f"Vision verification error: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return error_msg
