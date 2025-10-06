"""Vision Gateway integration helpers."""

from __future__ import annotations

import base64
import logging
import os
from typing import Any, Dict, List, Optional, Tuple

import requests

LOGGER = logging.getLogger("shared.vision")

_DEFAULT_URL = os.getenv("VISION_GATEWAY_URL", "http://vision-gateway:8088").rstrip("/")
_DEFAULT_TIMEOUT = float(os.getenv("VISION_GATEWAY_TIMEOUT", "10"))


class VisionGatewayClient:
    """Thin wrapper around the vision-gateway REST API."""

    def __init__(self, base_url: Optional[str] = None, timeout: float = _DEFAULT_TIMEOUT) -> None:
        self.base_url = (base_url or _DEFAULT_URL).rstrip("/")
        self.timeout = timeout
        self._session = requests.Session()

    # ------------------------------------------------------------------
    def get_recent_detections(self, limit: int = 1) -> List[Dict[str, Any]]:
        try:
            response = self._session.get(f"{self.base_url}/api/detections", timeout=self.timeout)
            response.raise_for_status()
            data = response.json()
            if isinstance(data, list):
                return data[:limit]
            LOGGER.warning("Unexpected detections payload: %s", type(data))
        except requests.RequestException as exc:
            LOGGER.debug("Vision gateway detections unavailable: %s", exc)
        return []

    def fetch_latest_frame(self, source: str) -> Tuple[Optional[Any], Optional[Dict[str, Any]]]:
        """Return numpy image array if dependencies are available."""
        try:
            response = self._session.get(
                f"{self.base_url}/api/latest_frame/{source}",
                timeout=self.timeout,
            )
            response.raise_for_status()
            payload: Dict[str, Any] = response.json()
            image_b64 = payload.get("image")
            if not image_b64:
                return None, payload

            try:
                import numpy as np  # type: ignore
                import cv2  # type: ignore
            except Exception:  # pragma: no cover - optional dependency for headless services
                LOGGER.debug("OpenCV not available; returning raw payload only")
                return None, payload

            img_bytes = base64.b64decode(image_b64)
            nparr = np.frombuffer(img_bytes, np.uint8)
            frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            return frame, payload
        except requests.RequestException as exc:
            LOGGER.debug("Vision gateway latest_frame unavailable: %s", exc)
        except Exception as exc:  # pragma: no cover - defensive
            LOGGER.warning("Failed to decode latest frame: %s", exc)
        return None, None

    def answer_question(self, question: str) -> Dict[str, Any]:
        question_norm = (question or "").strip()
        if not question_norm:
            return {
                "answer": "Error",
                "reason": "Verification question cannot be empty",
                "detection": None,
            }

        detections = self.get_recent_detections(limit=1)
        if not detections:
            return {
                "answer": "Unknown",
                "reason": "No detections available from vision-gateway",
                "detection": None,
            }

        latest = detections[0]
        result = latest.get("result", {})
        vl = result.get("vl", {})
        question_lower = question_norm.lower()

        answer = "Unknown"
        reason_parts: List[str] = []

        # Heuristics for meeting invite dialogs
        if any(keyword in question_lower for keyword in ["invite", "meeting", "calendar"]):
            invite_detected = bool(result.get("invite_detected") or vl.get("invite_detected"))
            answer = "Yes" if invite_detected else "No"
            title = vl.get("title")
            state = vl.get("action_state")
            if invite_detected:
                reason_parts.append("Meeting invite detected by vision model")
            else:
                reason_parts.append("Vision model did not detect a meeting invite")
            if title:
                reason_parts.append(f"Title: {title}")
            if state:
                reason_parts.append(f"State: {state}")

        # Button press heuristics
        elif any(keyword in question_lower for keyword in ["button", "press", "clicked", "accept", "decline"]):
            pressed = result.get("button_pressed")
            action_state = (vl.get("action_state") or "").lower()

            if "accept" in question_lower and action_state:
                answer = "Yes" if action_state == "accepted" else "No"
                reason_parts.append(f"Action state reported by model: {action_state}")
            elif "decline" in question_lower and action_state:
                answer = "Yes" if action_state == "declined" else "No"
                reason_parts.append(f"Action state reported by model: {action_state}")
            elif pressed is not None:
                answer = "Yes" if pressed else "No"
                reason_parts.append(f"Button pressed flag: {pressed}")
            else:
                reason_parts.append("No button press data in latest detection")

        # Generic fallback summary
        else:
            if vl:
                answer = "Summary"
                summary_bits = []
                if vl.get("app"):
                    summary_bits.append(f"app={vl['app']}")
                if vl.get("action_state"):
                    summary_bits.append(f"state={vl['action_state']}")
                if vl.get("confidence") is not None:
                    summary_bits.append(f"confidence={vl['confidence']:.2f}")
                reason_parts.append("; ".join(summary_bits) or "Vision model returned structured data")
            else:
                reason_parts.append("Latest detection has no vision model data")

        reason = "; ".join(reason_parts) if reason_parts else "No matching heuristics for question"
        return {
            "answer": answer,
            "reason": reason,
            "detection": latest,
        }


__all__ = [
    "VisionGatewayClient",
]
