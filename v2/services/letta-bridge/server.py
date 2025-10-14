import asyncio
import os
import time
from collections import deque
from typing import Any, Deque, Dict, List

import httpx
from fastapi import Body, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, PlainTextResponse
from prometheus_client import CONTENT_TYPE_LATEST, Counter, generate_latest

from . import db

MEMORY_URL = os.getenv("MEMORY_URL", "http://memory-embed:8001")
QUERY_HISTORY_SIZE = 10

memory_additions_total = Counter("memory_additions_total", "Total memory additions")
memory_search_total = Counter("memory_search_total", "Total memory search requests")


class QueryHistory:
    def __init__(self, limit: int) -> None:
        self._limit = limit
        self._items: Deque[Dict[str, Any]] = deque(maxlen=limit)
        self._lock = asyncio.Lock()

    async def add(self, query: str, count: int) -> None:
        entry = {
            "query": query,
            "results": count,
            "ts": time.time(),
        }
        async with self._lock:
            self._items.appendleft(entry)

    async def snapshot(self) -> List[Dict[str, Any]]:
        async with self._lock:
            return list(self._items)


query_history = QueryHistory(limit=QUERY_HISTORY_SIZE)
ingest_lock = asyncio.Lock()
ingest_enabled = True

app = FastAPI(title="letta-bridge")


@app.on_event("startup")
async def startup() -> None:
    app.state.http = httpx.AsyncClient(timeout=httpx.Timeout(30.0))


@app.on_event("shutdown")
async def shutdown() -> None:
    http: httpx.AsyncClient = app.state.http
    await http.aclose()


@app.get("/health")
async def health() -> JSONResponse:
    return JSONResponse({"ok": True, "memory_url": MEMORY_URL})


@app.get("/metrics")
def metrics() -> PlainTextResponse:
    return PlainTextResponse(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.post("/memory/add")
async def memory_add(payload: dict = Body(...)) -> JSONResponse:
    memory_additions_total.inc()
    http: httpx.AsyncClient = app.state.http
    try:
        response = await http.post(f"{MEMORY_URL}/upsert", json=payload)
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"Memory service error: {exc}") from exc
    return JSONResponse(response.json(), status_code=response.status_code)


@app.post("/memory/search")
async def memory_search(payload: dict = Body(...)) -> JSONResponse:
    memory_search_total.inc()
    http: httpx.AsyncClient = app.state.http
    try:
        response = await http.post(f"{MEMORY_URL}/search", json=payload)
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"Memory service error: {exc}") from exc

    data = response.json()
    results = data.get("results", [])
    query = payload.get("q", "")
    await query_history.add(query=query, count=len(results))

    return JSONResponse(data, status_code=response.status_code)


@app.get("/stats")
async def stats() -> JSONResponse:
    async with db.get_conn() as conn:
        cur_total = await conn.execute("SELECT COUNT(*) FROM memories")
        total = (await cur_total.fetchone())[0]

        cur_embedded = await conn.execute("SELECT COUNT(*) FROM embeddings")
        embedded = (await cur_embedded.fetchone())[0]

    pending = max(total - embedded, 0)
    history = await query_history.snapshot()

    return JSONResponse(
        {
            "total": total,
            "embedded": embedded,
            "pending": pending,
            "last_queries": history,
        }
    )


@app.post("/backfill/start")
async def backfill_start(request: Request) -> JSONResponse:
    payload = await request.json() if request.headers.get("content-type") == "application/json" else {}
    return JSONResponse({"status": "accepted", "payload": payload}, status_code=202)


@app.post("/config")
async def config(payload: dict = Body(...)) -> JSONResponse:
    global ingest_enabled
    if "ingest" not in payload:
        raise HTTPException(status_code=400, detail="ingest flag required")
    ingest = bool(payload["ingest"])
    async with ingest_lock:
        ingest_enabled = ingest
    return JSONResponse({"ingest": ingest_enabled})


@app.get("/config")
async def get_config() -> JSONResponse:
    async with ingest_lock:
        current = ingest_enabled
    return JSONResponse({"ingest": current})
