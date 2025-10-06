"""
Context extraction for meeting invite UI.
Extracts text from specific zones relative to detected buttons.
"""
import os
from typing import Dict, Any, List, Tuple
import numpy as np
from paddleocr import PaddleOCR

# Zone configuration (multipliers relative to button size)
# For meeting invites: button is typically on the left, details on the right
# Format: offset/size as multipliers of button dimensions
ZONE_CONFIG = {
    "title": {
        "x_offset": 1.2,    # Start 1.2x button width to the right
        "y_offset": -4.0,   # Start 4x button height above (top of invite)
        "width": 8.0,       # Wide area for title text
        "height": 1.5       # Height for title line
    },
    "time_start": {
        "x_offset": 1.2,    # Aligned with title
        "y_offset": -2.0,   # 2x button height above (middle area)
        "width": 6.0,       # Capture start time
        "height": 1.0       # Single line
    },
    "time_end": {
        "x_offset": 1.2,    # Aligned with title
        "y_offset": -0.8,   # Just above button level
        "width": 6.0,       # Capture end time
        "height": 1.0       # Single line
    },
    "location": {
        "x_offset": 1.2,    # Aligned with title
        "y_offset": 0.3,    # Just below button
        "width": 6.0,       # Capture location
        "height": 1.0       # Single line
    },
    "attendees": {
        "x_offset": 1.2,    # Aligned with title
        "y_offset": 1.5,    # Below location
        "width": 8.0,       # Wide for attendee list
        "height": 2.0       # Taller for multiple attendees
    }
}

CONTEXT_ZONES_ENABLED = os.getenv("CONTEXT_ZONES_ENABLED", "true").lower() == "true"

# Shared OCR instance from main module
_shared_ocr = None

def set_shared_ocr(ocr_instance):
    """Set shared OCR instance from main module"""
    global _shared_ocr
    _shared_ocr = ocr_instance

def calculate_zone_bbox(button_bbox: List[int], zone_name: str, frame_shape: Tuple[int, int]) -> List[int]:
    """
    Calculate absolute zone bounding box based on button position

    Args:
        button_bbox: [x, y, w, h] of detected button
        zone_name: Name of zone from ZONE_CONFIG
        frame_shape: (height, width) of frame

    Returns:
        [x, y, w, h] of zone, clipped to frame bounds
    """
    if zone_name not in ZONE_CONFIG:
        return [0, 0, 0, 0]

    btn_x, btn_y, btn_w, btn_h = button_bbox
    config = ZONE_CONFIG[zone_name]

    # Calculate zone position relative to button
    zone_x = int(btn_x + (btn_w * config["x_offset"]))
    zone_y = int(btn_y + (btn_h * config["y_offset"]))
    zone_w = int(btn_w * config["width"])
    zone_h = int(btn_h * config["height"])

    # Clip to frame boundaries
    frame_h, frame_w = frame_shape[:2]
    zone_x = max(0, min(zone_x, frame_w - 1))
    zone_y = max(0, min(zone_y, frame_h - 1))
    zone_w = max(1, min(zone_w, frame_w - zone_x))
    zone_h = max(1, min(zone_h, frame_h - zone_y))

    return [zone_x, zone_y, zone_w, zone_h]

def extract_text_from_zone(frame: np.ndarray, zone_bbox: List[int]) -> str:
    """
    Extract text from a specific zone using OCR

    Args:
        frame: Full frame image
        zone_bbox: [x, y, w, h] of zone to extract

    Returns:
        Extracted text as string
    """
    if _shared_ocr is None:
        return ""

    x, y, w, h = zone_bbox

    if w <= 0 or h <= 0:
        return ""

    # Crop zone
    zone_crop = frame[y:y+h, x:x+w]

    if zone_crop.size == 0:
        return ""

    # Run OCR on crop
    result = _shared_ocr.ocr(zone_crop, cls=False)

    if not result or not result[0]:
        return ""

    # Concatenate all detected text
    text_lines = []
    for line in result[0]:
        text, conf = line[1]
        if conf > 0.5:  # Filter low confidence
            text_lines.append(text)

    return " ".join(text_lines)

def extract_meeting_context(frame: np.ndarray, button_bbox: List[int]) -> Dict[str, Any]:
    """
    Extract meeting context from zones around a detected button

    Args:
        frame: Full frame image (BGR)
        button_bbox: [x, y, w, h] of detected button

    Returns:
        {
            "title_text": str,
            "time_start_text": str,
            "time_end_text": str,
            "location_text": str,
            "attendees_text": str,
            "zones": {
                "title": [x, y, w, h],
                "time_start": [x, y, w, h],
                "time_end": [x, y, w, h],
                "location": [x, y, w, h],
                "attendees": [x, y, w, h]
            }
        }
    """
    if not CONTEXT_ZONES_ENABLED:
        return {
            "title_text": "",
            "time_start_text": "",
            "time_end_text": "",
            "location_text": "",
            "attendees_text": "",
            "zones": {}
        }

    frame_shape = frame.shape

    # Calculate zone bounding boxes
    title_zone = calculate_zone_bbox(button_bbox, "title", frame_shape)
    time_start_zone = calculate_zone_bbox(button_bbox, "time_start", frame_shape)
    time_end_zone = calculate_zone_bbox(button_bbox, "time_end", frame_shape)
    location_zone = calculate_zone_bbox(button_bbox, "location", frame_shape)
    attendees_zone = calculate_zone_bbox(button_bbox, "attendees", frame_shape)

    # Extract text from each zone
    title_text = extract_text_from_zone(frame, title_zone)
    time_start_text = extract_text_from_zone(frame, time_start_zone)
    time_end_text = extract_text_from_zone(frame, time_end_zone)
    location_text = extract_text_from_zone(frame, location_zone)
    attendees_text = extract_text_from_zone(frame, attendees_zone)

    return {
        "title_text": title_text,
        "time_start_text": time_start_text,
        "time_end_text": time_end_text,
        "location_text": location_text,
        "attendees_text": attendees_text,
        "zones": {
            "title": title_zone,
            "time_start": time_start_zone,
            "time_end": time_end_zone,
            "location": location_zone,
            "attendees": attendees_zone
        }
    }
