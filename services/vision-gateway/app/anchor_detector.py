"""
Anchor-based button detection for meeting invites.
Lightweight OCR scanner that only looks for specific keywords.
"""
import re
import os
from typing import List, Dict, Any
import numpy as np

# Keywords we're looking for in meeting UIs
ANCHOR_KEYWORDS = os.getenv("ANCHOR_KEYWORDS", "Accept,Send,Decline").split(",")
ANCHOR_KEYWORDS_LOWER = [kw.strip().lower() for kw in ANCHOR_KEYWORDS]

# We'll import the shared OCR instance from main
_shared_ocr = None

def set_shared_ocr(ocr_instance):
    """Set shared OCR instance from main module"""
    global _shared_ocr
    _shared_ocr = ocr_instance

def detect_buttons(frame: np.ndarray, ocr_boxes: List[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """
    Scan frame for button keywords (Accept, Decline, Send)

    Args:
        frame: OpenCV image (BGR)
        ocr_boxes: Pre-computed OCR results from ocr_with_boxes() to avoid redundant OCR

    Returns:
        List of detected buttons: [{"text": str, "bbox": [x, y, w, h]}, ...]
    """
    # If OCR results provided, use them; otherwise run OCR
    if ocr_boxes is None:
        if _shared_ocr is None:
            return []

        # Run OCR detection + recognition
        result = _shared_ocr.ocr(frame, cls=False)

        if not result or not result[0]:
            return []

        # Convert to our box format
        ocr_boxes = []
        for line in result[0]:
            pts = line[0]
            text, conf = line[1]
            x_coords = [p[0] for p in pts]
            y_coords = [p[1] for p in pts]
            x = int(min(x_coords))
            y = int(min(y_coords))
            w = int(max(x_coords) - min(x_coords))
            h = int(max(y_coords) - min(y_coords))
            ocr_boxes.append({"bbox": [x, y, w, h], "text": text, "conf": float(conf)})

    detected_buttons = []

    for box in ocr_boxes:
        text = box["text"]
        text_lower = text.lower()

        # Check if text contains any of our keywords (exact match or word boundary)
        matched_keyword = None
        for keyword in ANCHOR_KEYWORDS_LOWER:
            # Use word boundary regex for better matching
            if re.search(r'\b' + re.escape(keyword) + r'\b', text_lower):
                matched_keyword = keyword
                break

        if not matched_keyword:
            continue

        detected_buttons.append({
            "text": text,
            "keyword": matched_keyword,
            "bbox": box["bbox"],
            "confidence": box["conf"]
        })

    return detected_buttons
