"""
Vision Gateway Client

Interfaces with vision-gateway service for screen state verification.
Benefits from cache and memory features added today.
"""

import logging
import requests
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class VisionGatewayClient:
    """Client for querying vision-gateway service"""

    def __init__(self, base_url: str = "http://vision-gateway:8088"):
        """
        Initialize Vision Gateway Client

        Args:
            base_url: Vision gateway service URL
        """
        self.base_url = base_url.rstrip('/')
        logger.info(f"Vision Gateway Client initialized: {self.base_url}")

    def get_latest_frame(self, source: str = "hdmi") -> Optional[Dict[str, Any]]:
        """
        Get latest captured frame from vision gateway

        Args:
            source: Frame source (default: "hdmi")

        Returns:
            Frame data dict or None
        """
        try:
            response = requests.get(
                f"{self.base_url}/api/latest_frame/{source}",
                timeout=5
            )
            if response.status_code == 200:
                return response.json()
            logger.warning(f"Failed to get latest frame: {response.status_code}")
            return None
        except Exception as e:
            logger.error(f"Error getting latest frame: {e}")
            return None

    def get_detections(self) -> Dict[str, Any]:
        """
        Get recent detections from vision gateway

        Returns:
            Detection data (benefits from today's cache implementation)
        """
        try:
            response = requests.get(
                f"{self.base_url}/api/detections",
                timeout=5
            )
            if response.status_code == 200:
                return response.json()
            logger.warning(f"Failed to get detections: {response.status_code}")
            return {"detections": []}
        except Exception as e:
            logger.error(f"Error getting detections: {e}")
            return {"detections": []}

    def answer_question(self, question: str) -> Dict[str, Any]:
        """
        Ask a yes/no question about the current screen state

        This leverages vision-gateway's detection cache and can provide
        contextual answers based on recent screen analysis.

        Args:
            question: Yes/no question about screen state

        Returns:
            Answer dict with format:
            {
                "answer": "yes" | "no" | "unknown",
                "reason": "explanation",
                "detection": {...}  # Optional detection data
            }
        """
        try:
            # Get recent detections (uses cache from today's updates)
            detections_response = self.get_detections()
            detections = detections_response.get("detections", [])

            # Analyze question and detections
            answer, reason = self._analyze_question(question, detections)

            return {
                "answer": answer,
                "reason": reason,
                "detection": detections[0] if detections else None,
                "cached": True  # Indicates we're using cached detection data
            }

        except Exception as e:
            logger.error(f"Error answering question: {e}")
            return {
                "answer": "unknown",
                "reason": f"Error: {str(e)}",
                "detection": None
            }

    def _analyze_question(self, question: str, detections: list) -> tuple:
        """
        Analyze question against detection data

        This is a simple heuristic-based approach. Future enhancement:
        integrate with Ollama vision model for better understanding.

        Args:
            question: User's question
            detections: Recent detection data

        Returns:
            (answer, reason) tuple
        """
        question_lower = question.lower()

        # No detections available
        if not detections:
            return "unknown", "No recent screen data available"

        # Get most recent detection
        latest = detections[0]
        detection_result = latest.get("result", {})
        vl_data = detection_result.get("vl", {})

        # Extract useful info
        title = vl_data.get("title", "").lower()
        action_state = vl_data.get("action_state", "").lower()
        confidence = vl_data.get("confidence", 0.0)

        # Heuristic matching (can be improved with LLM)
        # Check for specific applications
        if "excel" in question_lower:
            if "excel" in title or "spreadsheet" in title:
                return "yes", f"Detected '{title}' on screen (confidence: {confidence:.2f})"
            return "no", "Excel not detected on screen"

        if "chrome" in question_lower or "browser" in question_lower:
            if "chrome" in title or "browser" in title or "edge" in title:
                return "yes", f"Detected browser: '{title}'"
            return "no", "Browser not detected"

        if "notepad" in question_lower:
            if "notepad" in title:
                return "yes", f"Detected Notepad on screen"
            return "no", "Notepad not detected"

        # Check for UI state questions
        if "open" in question_lower:
            if action_state == "visible" or confidence > 0.5:
                return "yes", f"Application appears to be open: '{title}'"
            return "no", "Application does not appear to be open"

        if "button" in question_lower or "click" in question_lower:
            if "button" in action_state or "send" in action_state:
                return "yes", f"Button detected: state={action_state}"
            return "no", "No clickable button detected"

        # Generic response based on confidence
        if confidence > 0.7:
            return "yes", f"High confidence detection: '{title}' (confidence: {confidence:.2f})"
        elif confidence > 0.4:
            return "maybe", f"Possible match: '{title}' (confidence: {confidence:.2f})"
        else:
            return "no", f"Low confidence in screen state (confidence: {confidence:.2f})"

    def health_check(self) -> bool:
        """Check if vision gateway is reachable"""
        try:
            response = requests.get(
                f"{self.base_url}/healthz",
                timeout=3
            )
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Vision gateway health check failed: {e}")
            return False
