from typing import Any, Dict, List


def ocr_density(frame: Dict[str, Any]) -> float:
    text = (frame.get("ocr") or {}).get("text") or ""
    area = max(1, frame.get("width", 1280) * frame.get("height", 720))
    return min(1.0, len(text) / 3000)


def slide_like(tags: List[str], text: str) -> bool:
    lowered = text.lower()
    keys = ("slide", "agenda", "summary", "meeting", "q&a", "action items")
    tag_set = set(tag.lower() for tag in tags)
    if any(key in lowered for key in keys):
        return True
    return "meeting" in tag_set or "slide_candidate" in tag_set


def diagram_like(frame: Dict[str, Any], text: str) -> bool:
    confidence = (frame.get("ocr") or {}).get("conf") or 0.0
    short_tokens = sum(1 for token in text.split() if 1 <= len(token) <= 3)
    return confidence < 0.88 and short_tokens > 12


def compute_usefulness(event: Dict[str, Any]) -> float:
    frames = event.get("frames") or []
    tags = list(event.get("tags") or [])
    base_score = 0.0
    for frame in frames:
        density = ocr_density(frame)
        text = (frame.get("ocr") or {}).get("text") or ""
        score = density
        if slide_like(tags, text):
            score += 0.25
        if diagram_like(frame, text):
            score += 0.25
        base_score = max(base_score, score)
    return min(base_score, 1.0)
