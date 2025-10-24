#!/usr/bin/env python3
import os
import json
import time
import asyncio
import uuid
from typing import Dict, Any, Optional, List

import uvicorn
from fastapi import FastAPI, Body
from fastapi.responses import JSONResponse, PlainTextResponse
import httpx
import requests

# --- Env / Config ---
PORT = int(os.getenv("ORCH_PORT", "8082"))

HA_BASE_URL   = os.getenv("HA_BASE_URL", "http://192.168.2.13:8123")
HA_TOKEN      = os.getenv("HA_TOKEN", "")
S2P_URL       = os.getenv("S2P_URL", "http://s2p-gate:8083")
LETTA_SERVER_URL = os.getenv("LETTA_SERVER_URL", "http://letta-server:8283")
LETTA_API_KEY = os.getenv("LETTA_API_KEY", "")
LETTA_AGENT_ID = os.getenv("LETTA_AGENT_ID", "")  # MUST be set; we do not auto-create anymore
ORCH_BASE_URL = os.getenv("ORCH_BASE_URL", f"http://glados-orchestrator:{PORT}")

ACK_MODEL        = os.getenv("ACK_MODEL", "hermes3:latest")
ACK_MAX_TOKENS   = int(os.getenv("ACK_MAX_TOKENS", "64"))
ACK_TIMEOUT_MS   = int(os.getenv("ACK_TIMEOUT_MS", "3000"))

BARGE_IN_ENABLED = os.getenv("BARGE_IN_ENABLED", "true").lower() == "true"
BARGE_IN_DEBOUNCE_MS = int(os.getenv("BARGE_IN_DEBOUNCE_MS", "150"))
REALTIME_FLUSH_MARKERS = os.getenv("REALTIME_FLUSH_MARKERS", ".?!\n")

# --- Helper imports (yours) ---
# All of these are your existing files from Iteration 1 polish
try:
    from s2p_client import s2p_match
except Exception as e:
    async def s2p_match(*args, **kwargs):
        return {"matched": False, "raw_text": kwargs.get("text", ""), "turn_id": kwargs.get("turn_id")}
try:
    from ack_generator import generate_ack
except Exception:
    async def generate_ack(intent: str, slots: Dict[str, Any]) -> str:
        room = slots.get("room", "")
        if intent == "light_control" and slots.get("action") == "on":
            return f"Lights on{(' in ' + room) if room else ''}."
        return "Okay."

try:
    from tts_streamer import stream_to_piper, cancel_tts_session
except Exception:
    async def stream_to_piper(text: str, session_id: str, voice: str = "glados"):
        return {"ok": True, "bytes_sent": len(text.encode())}
    async def cancel_tts_session(session_id: str, reason: str = "cancel"):
        return {"ok": True, "reason": reason}

try:
    from ha_entity_mapper import resolve_entities
except Exception:
    async def resolve_entities(intent: str, slots: Dict[str, Any]) -> List[str]:
        # Fallback if your mapper module isn't present yet
        room = slots.get("room", "kitchen")
        target = slots.get("target", "lights")
        domain = "light" if "light" in target else "switch"
        eid = f"{domain}.{room}_{target}".replace(" ", "_")
        return [eid]

try:
    from redis_client import turn_id_claim, set_fact, get_fact
except Exception:
    async def turn_id_claim(turn_id: str, ttl_sec: int = 300) -> bool:
        # optimistic: allow every time if redis not present
        return True
    async def set_fact(key: str, value: str, ttl: Optional[int] = None, partition: str = "global"):
        return True
    async def get_fact(key: str, partition: str = "global") -> Optional[str]:
        return None

# --- FastAPI ---
app = FastAPI(title="GLaDOS Orchestrator", version="2.0")

# --- Helper: Wrap text as send_message tool call for Letta ---
def wrap_as_send_message_tool(text: str, model: str = "hermes-3") -> dict:
    """
    Wraps plain text into a send_message tool call format that Letta expects.
    This is required because Letta always expects tool_calls in the response.
    """
    return {
        "id": f"chatcmpl_{uuid.uuid4().hex[:12]}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": model,
        "choices": [{
            "index": 0,
            "message": {
                "role": "assistant",
                "tool_calls": [{
                    "id": f"call_{uuid.uuid4().hex[:8]}",
                    "type": "function",
                    "function": {
                        "name": "send_message",
                        "arguments": json.dumps({"text": text})
                    }
                }]
            },
            "finish_reason": "tool_calls"
        }]
    }

# --- Metrics (very lightweight placeholders; wire to Prometheus if desired) ---
_metrics = {
    "turn_id_dedupe_hits_total": 0,
    "ha_call_ms": 0,
    "ack_generate_ms": 0,
    "tts_first_chunk_ms": 0,
    "tts_cancelled_total": 0,
    "barge_in_latency_ms": 0,
    "s2p_latency_ms": 0,
}

@app.get("/health")
async def health():
    return {
        "ok": True,
        "services": {
            "letta": bool(LETTA_SERVER_URL),
            "ha": bool(HA_BASE_URL),
            "s2p": bool(S2P_URL),
        },
        "agent_id": LETTA_AGENT_ID or "<unset>",
    }

@app.get("/metrics")
async def metrics():
    # minimal prometheus-ish plaintext
    lines = []
    for k, v in _metrics.items():
        lines.append(f"# TYPE {k} counter")
        lines.append(f"{k} {v}")
    return PlainTextResponse("\n".join(lines))

# --- Letta tool runner (v1) using /v1/tools/run; no auto-create, no OpenAI ---
_LETTA_HDRS = {"Authorization": f"Bearer {LETTA_API_KEY}"}
_TOOL_ID_CACHE: Dict[str, str] = {}

def _get_tool_id_by_name(tool_name: str) -> Optional[str]:
    tid = _TOOL_ID_CACHE.get(tool_name)
    if tid:
        return tid
    r = requests.get(f"{LETTA_SERVER_URL}/v1/tools/", headers=_LETTA_HDRS, timeout=10)
    r.raise_for_status()
    for t in r.json():
        if t.get("name") == tool_name or tool_name in (t.get("tags") or []):
            _TOOL_ID_CACHE[tool_name] = t["id"]
            return t["id"]
    return None

def letta_tool(tool_name: str, payload: dict) -> dict:
    """Deterministic tool execution via /v1/tools/run; passes HA/Orch env to tool runtime."""
    try:
        tool_id = _get_tool_id_by_name(tool_name)
        if not tool_id:
            return {"ok": False, "error": f"Tool '{tool_name}' not found"}

        r = requests.get(f"{LETTA_SERVER_URL}/v1/tools/{tool_id}", headers=_LETTA_HDRS, timeout=10)
        r.raise_for_status()
        source_code = r.json().get("source_code")
        if not source_code:
            return {"ok": False, "error": f"Tool '{tool_name}' missing source_code"}

        run_body = {
            "name": tool_name,
            "source_code": source_code,
            "args": payload,
            "env_vars": {
                "HA_BASE_URL": HA_BASE_URL,
                "HA_TOKEN": HA_TOKEN,
                "ORCH_BASE_URL": ORCH_BASE_URL,
                "LETTA_AGENT_ID": LETTA_AGENT_ID,
                "LETTA_PUBLIC_BASE": LETTA_SERVER_URL,
            },
        }
        r = requests.post(
            f"{LETTA_SERVER_URL}/v1/tools/run",
            headers={**_LETTA_HDRS, "Content-Type": "application/json"},
            data=json.dumps(run_body),
            timeout=30,
        )
        r.raise_for_status()
        data = r.json()
        if data.get("status") == "error":
            return {"ok": False, "error": data.get("tool_return")}
        return {"ok": True, "result": data.get("tool_return")}
    except requests.HTTPError as e:
        return {"ok": False, "error": f"HTTP {e.response.status_code}: {e.response.text[:400]}"}
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}

# --- Orchestrator endpoints ---

@app.post("/s2p/process")
async def s2p_process(payload: Dict = Body(...)) -> JSONResponse:
    """
    Tee point:
      - If S2P match: HA call + parallel ack → no LLM
      - Else: route to agent (messages) for full reasoning
    """
    turn_id = payload.get("turn_id")
    text = payload.get("text", "")
    locale = payload.get("locale", "en")

    t0 = time.time()
    s2p = await s2p_match(turn_id=turn_id, text=text, locale=locale, s2p_url=S2P_URL)
    _metrics["s2p_latency_ms"] = int((time.time() - t0) * 1000)

    # Idempotency (if your redis_client implements it)
    if not await turn_id_claim(turn_id, ttl_sec=300):
        _metrics["turn_id_dedupe_hits_total"] += 1
        return JSONResponse({"duplicate": True, "message": "Turn ID already processed"})

    if s2p.get("matched"):
        # Resolve to HA entities
        slots = s2p.get("slots", {})
        entities = await resolve_entities(s2p.get("intent", ""), slots)

        # Call HA
        ha_t0 = time.time()
        ok = await _ha_call_from_slots(s2p.get("intent", ""), slots, entities)
        _metrics["ha_call_ms"] = int((time.time() - ha_t0) * 1000)

        # Parallel ack to TTS
        asyncio.create_task(_send_ack(slots, s2p.get("intent", "")))
        return JSONResponse({"s2p_matched": True, "ha_executed": ok, "ack_queued": True, "confidence": s2p.get("confidence", 1.0)})

    # No S2P match → send to Letta agent message loop (v1)
    if not LETTA_AGENT_ID:
        return JSONResponse({"s2p_matched": False, "error": "LETTA_AGENT_ID unset"}, status_code=500)

    msg_body = {"messages": [{"role": "user", "content": text}]}
    try:
        r = requests.post(
            f"{LETTA_SERVER_URL}/v1/agents/{LETTA_AGENT_ID}/messages",
            headers={**_LETTA_HDRS, "Content-Type": "application/json"},
            data=json.dumps(msg_body),
            timeout=60,
        )
        r.raise_for_status()
        out = r.json()
        return JSONResponse({"s2p_matched": False, "agent": out})
    except requests.HTTPError as e:
        return JSONResponse({"s2p_matched": False, "error": f"HTTP {e.response.status_code}: {e.response.text[:400]}"},
                            status_code=502)

async def _ha_call_from_slots(intent: str, slots: Dict[str, Any], entities: List[str]) -> bool:
    # Very small, explicit map for demo; your ha_entity_mapper should do the heavy lifting
    action = slots.get("action", "on")
    domain = "light" if "light" in slots.get("target", "lights") else "switch"
    service = "turn_on" if action in ("on", "enable", "start") else "turn_off" if action in ("off", "disable", "stop") else "toggle"
    try:
        headers = {"Authorization": f"Bearer {HA_TOKEN}", "Content-Type": "application/json"}
        payload = {"entity_id": entities}
        with requests.post(f"{HA_BASE_URL}/api/services/{domain}/{service}",
                           headers=headers, data=json.dumps(payload), timeout=5) as r:
            r.raise_for_status()
        return True
    except Exception:
        return False

async def _send_ack(slots: Dict[str, Any], intent: str):
    t0 = time.time()
    text = await generate_ack(intent=intent, slots=slots)
    _metrics["ack_generate_ms"] = int((time.time() - t0) * 1000)
    # Stream to Piper (your tts_streamer handles chunking & debounce)
    session_id = slots.get("turn_id") or str(time.time())
    await stream_to_piper(text, session_id=session_id, voice="glados")

@app.post("/ack")
async def ack_endpoint(payload: Dict = Body(...)) -> JSONResponse:
    text = await generate_ack(payload.get("intent", ""), payload.get("slots", {}))
    # Not auto-sending; just returning for debugging
    return JSONResponse({"ack_text": text})

@app.post("/tts/cancel")
async def tts_cancel(payload: Dict = Body(...)) -> JSONResponse:
    sid = payload.get("session_id", "")
    t0 = time.time()
    res = await cancel_tts_session(sid, reason=payload.get("reason", "cancel"))
    lat = int((time.time() - t0) * 1000)
    _metrics["tts_cancelled_total"] += 1
    _metrics["barge_in_latency_ms"] = lat
    return JSONResponse({"cancelled": bool(res.get("ok", True)), "latency_ms": lat})

@app.post("/ollama/route")
async def ollama_route(payload: Dict = Body(...)) -> JSONResponse:
    """
    Thin wrapper around your existing model routing rules (Hermes/Qwen/VL).
    Adjust the call inside if your router lives elsewhere.
    """
    prompt = payload.get("prompt", "")
    mode = payload.get("mode", "auto")
    max_tokens = int(payload.get("max_tokens", 256))

    model = "hermes3:latest"
    if mode == "deep":
        model = "qwen3:4b"
    elif mode == "vision":
        model = "qwen2.5-vl:7b"

    # Call Ollama directly here, or route through your existing router if you have one as a service.
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await client.post(
                "http://ollama-text:11434/api/generate",
                json={"model": model, "prompt": prompt, "stream": False, "options": {"num_predict": max_tokens}},
            )
        txt = r.json().get("response", "")
        return JSONResponse({"text": txt, "model": model})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=502)

# ---------- HA dashboard memory proxies (direct archival memory API) ----------

@app.post("/memory/ha_search")
async def ha_memory_search(payload: Dict = Body(...)) -> JSONResponse:
    """Search Letta agent archival memory from HA dashboard"""
    if not LETTA_AGENT_ID:
        return JSONResponse({"ok": False, "error": "LETTA_AGENT_ID unset"}, status_code=500)

    q = (payload.get("q") or "").strip()
    limit = payload.get("limit", 10)
    if not q:
        return JSONResponse({"ok": True, "results": []})

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await client.get(
                f"{LETTA_SERVER_URL}/v1/agents/{LETTA_AGENT_ID}/archival-memory/search",
                headers=_LETTA_HDRS,
                params={"query": q, "limit": limit}
            )
            r.raise_for_status()
            data = r.json()

            # Transform Letta's response format to match HA dashboard expectations
            results = []
            for item in data.get("results", []):
                results.append({
                    "id": item.get("id", ""),
                    "score": 1.0,  # Letta doesn't return scores in archival search
                    "tags": item.get("tags", []) or [],
                    "snippet": item.get("content", "")[:200]
                })
            return JSONResponse({"ok": True, "results": results})
    except httpx.HTTPStatusError as e:
        return JSONResponse({"ok": False, "error": f"HTTP {e.response.status_code}"}, status_code=502)
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=502)

@app.post("/memory/ha_fix")
async def ha_memory_fix(payload: Dict = Body(...)) -> JSONResponse:
    """Add corrective memory note to Letta archival memory"""
    if not LETTA_AGENT_ID:
        return JSONResponse({"ok": False, "error": "LETTA_AGENT_ID unset"}, status_code=500)

    mid = payload.get("id")
    corr = (payload.get("correction") or "").strip()
    if not mid or not corr:
        return JSONResponse({"ok": False, "error": "missing id/correction"}, status_code=400)

    # Add correction as a new archival memory entry
    correction_text = f"CORRECTION for {mid}: {corr}"
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await client.post(
                f"{LETTA_SERVER_URL}/v1/agents/{LETTA_AGENT_ID}/archival-memory",
                headers={**_LETTA_HDRS, "Content-Type": "application/json"},
                json={"text": correction_text}
            )
            r.raise_for_status()
            return JSONResponse({"ok": True, "id": r.json()[0]["id"]})
    except httpx.HTTPStatusError as e:
        return JSONResponse({"ok": False, "error": f"HTTP {e.response.status_code}"}, status_code=502)
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=502)

# ---------- OpenAI-compatible endpoint for HA Voice Assist ----------

@app.post("/v1/chat/completions")
async def chat_completions(payload: Dict = Body(...)) -> JSONResponse:
    """
    OpenAI-compatible endpoint for Home Assistant Voice Assist integration.
    Routes through existing S2P → Letta flow and returns OpenAI-formatted responses.

    If the request includes a 'tools' array with 'send_message', wraps plain text
    responses as tool calls (required by Letta).
    """
    messages = payload.get("messages", [])
    tools = payload.get("tools", [])
    last_msg = messages[-1].get("content", "") if messages else ""
    turn_id = f"ha_{int(time.time() * 1000)}"
    text = last_msg
    locale = "en"

    # Check if Letta is calling us with tools (send_message present)
    has_send_message_tool = any(
        t.get("function", {}).get("name") == "send_message"
        for t in tools
    )

    # Inline S2P → Letta logic (same as s2p_process but returns dict instead of JSONResponse)
    t0 = time.time()
    s2p = await s2p_match(turn_id=turn_id, text=text, locale=locale, s2p_url=S2P_URL)
    _metrics["s2p_latency_ms"] = int((time.time() - t0) * 1000)

    # Idempotency check
    if not await turn_id_claim(turn_id, ttl_sec=300):
        _metrics["turn_id_dedupe_hits_total"] += 1
        reply_text = "I already processed that request."
    elif s2p.get("matched"):
        # S2P matched - resolve entities, call HA, generate ack
        slots = s2p.get("slots", {})
        intent = s2p.get("intent", "")
        entities = await resolve_entities(intent, slots)

        # Call HA
        ha_t0 = time.time()
        ok = await _ha_call_from_slots(intent, slots, entities)
        _metrics["ha_call_ms"] = int((time.time() - ha_t0) * 1000)

        # Generate ack text for response
        reply_text = await generate_ack(intent=intent, slots=slots)

        # Also send to TTS in background
        asyncio.create_task(_send_ack(slots, intent))
    else:
        # No S2P match → send to Letta agent
        if not LETTA_AGENT_ID:
            reply_text = "I'm sorry, my memory system is not configured."
        else:
            msg_body = {"messages": [{"role": "user", "content": text}]}
            try:
                r = requests.post(
                    f"{LETTA_SERVER_URL}/v1/agents/{LETTA_AGENT_ID}/messages",
                    headers={**_LETTA_HDRS, "Content-Type": "application/json"},
                    data=json.dumps(msg_body),
                    timeout=60,
                )
                r.raise_for_status()
                out = r.json()

                # Extract last assistant message
                agent_messages = out.get("messages", [])
                reply_text = "I'm processing that."
                for msg in reversed(agent_messages):
                    if msg.get("role") == "assistant":
                        reply_text = msg.get("content", reply_text)
                        break
            except requests.HTTPError as e:
                reply_text = "I encountered an error processing your request."

    # If Letta sent us tools array with send_message, wrap as tool call
    if has_send_message_tool:
        return JSONResponse(wrap_as_send_message_tool(reply_text, model="glados"))

    # Otherwise return standard OpenAI format (for HA Voice Assist)
    return JSONResponse({
        "id": f"chatcmpl-{turn_id}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": "glados",
        "choices": [{
            "index": 0,
            "message": {
                "role": "assistant",
                "content": reply_text
            },
            "finish_reason": "stop"
        }],
        "usage": {
            "prompt_tokens": len(last_msg.split()),
            "completion_tokens": len(reply_text.split()),
            "total_tokens": len(last_msg.split()) + len(reply_text.split())
        }
    })

# ---------- Run ----------
if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=PORT, reload=False)
