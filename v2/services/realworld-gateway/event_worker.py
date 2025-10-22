import json
import logging
import os
from typing import Dict, Optional

import httpx

ROUTER_URL = os.getenv("VISION_ROUTER_URL", "http://vision-router:8050")
FRIGATE_BASE = os.getenv("FRIGATE_BASE", "http://127.0.0.1:5000")

log = logging.getLogger("event-worker")


async def fetch_snapshot(event_id: str) -> Optional[bytes]:
    """
    Fetch the Frigate event snapshot for the given event ID.
    Returns JPEG bytes or None if unavailable.
    """
    if not event_id:
        return None

    url = f"{FRIGATE_BASE.rstrip('/')}/api/events/{event_id}/snapshot.jpg"
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(5.0, read=5.0)) as client:
            response = await client.get(url)
            response.raise_for_status()
            return response.content
    except Exception as exc:
        log.warning("Failed to fetch snapshot for event %s: %s", event_id, exc)
        return None


async def post_event_to_router(event: Dict[str, object], snapshot: Optional[bytes]) -> None:
    """
    Forward the enriched event payload to the vision router.
    Sends multipart form data so the router can consume the snapshot bytes
    alongside the JSON payload.
    """
    data = {"json": json.dumps(event, ensure_ascii=False)}
    files = None
    if snapshot:
        files = {"snapshot": ("snapshot.jpg", snapshot, "image/jpeg")}

    async with httpx.AsyncClient(timeout=httpx.Timeout(10.0, read=10.0)) as client:
        response = await client.post(f"{ROUTER_URL.rstrip('/')}/events", data=data, files=files)
        response.raise_for_status()
