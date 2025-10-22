import asyncio
import hashlib
import json
import os
import time
from collections import deque
from typing import Any, Deque, Dict, List, Optional

import httpx
from fastapi import Body, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, PlainTextResponse
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest

try:
    from . import db
except ImportError:  # pragma: no cover
    import importlib

    db = importlib.import_module("db")

MEMORY_URL = os.getenv("MEMORY_URL", "http://memory-embed:8001")
QUERY_HISTORY_SIZE = 10

# Enhanced metrics for Step 2.5
memory_additions_total = Counter("memory_additions_total", "Total memory additions", ["role", "kind"])
memory_search_total = Counter("memory_search_total", "Total memory search requests")
memory_search_used_total = Counter("memory_search_used_total", "Searches where memory was used")
memory_dedup_hits_total = Counter("memory_dedup_hits_total", "Memory upserts that hit existing hash")
search_latency_ms = Histogram("letta_search_latency_ms", "Search latency in milliseconds")
add_latency_ms = Histogram("letta_add_latency_ms", "Add latency in milliseconds")

# Global state for stats
_last_hits = 0
_last_used = False
_config = {"autosave": True, "min_score": 0.62, "top_k": 6, "ingest": True}


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
    """
    Add a memory with deduplication support.

    Step 2.5: Enhanced to support hash-based deduplication using hash_id.
    """
    t0 = time.time()

    text = payload.get("text", "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="text required")

    kind = payload.get("kind", "note")
    source = payload.get("source", "api")
    meta = payload.get("meta") or {}
    hash_id = payload.get("hash_id")

    # Compute hash if not provided
    if not hash_id:
        normalized = text.lower().strip()
        hash_id = hashlib.sha256(normalized.encode('utf-8')).hexdigest()[:16]

    role = meta.get("role", "unknown")

    # Upsert memory with dedup detection
    async with db.get_conn() as conn:
        query = """
        INSERT INTO memories (id, hash_id, kind, source, text, meta, created_at, updated_at)
        VALUES (gen_random_uuid(), %(hash)s, %(kind)s, %(source)s, %(text)s, %(meta)s::jsonb, NOW(), NOW())
        ON CONFLICT (hash_id) DO UPDATE
          SET meta = memories.meta || EXCLUDED.meta,
              text = EXCLUDED.text,
              updated_at = NOW()
        RETURNING id, (xmax != 0) AS was_update
        """

        cur = await conn.execute(
            query,
            {
                "hash": hash_id,
                "kind": kind,
                "source": source,
                "text": text,
                "meta": json.dumps(meta)
            }
        )
        row = await cur.fetchone()
        memory_id, was_update = str(row[0]), bool(row[1])

    # Update metrics
    if was_update:
        memory_dedup_hits_total.inc()
    else:
        memory_additions_total.labels(role=role, kind=kind).inc()

    # Ensure embedding exists (delegate to mem-embed)
    http: httpx.AsyncClient = app.state.http
    try:
        await http.post(
            f"{MEMORY_URL}/upsert",
            json={"id": memory_id, "text": text, "kind": kind, "source": source, "meta": meta}
        )
    except httpx.HTTPError:
        pass  # Non-blocking - embedding will be created by backfill

    add_latency_ms.observe((time.time() - t0) * 1000)

    return JSONResponse({"id": memory_id, "hash_id": hash_id, "deduped": was_update})


@app.post("/memory/search")
async def memory_search(payload: dict = Body(...)) -> JSONResponse:
    """
    Search memories with kind filtering support.

    Step 2.5: Enhanced to support filtering by memory kind via SQL.
    """
    global _last_hits

    t0 = time.time()
    memory_search_total.inc()

    query = payload.get("q", "").strip()
    if not query:
        raise HTTPException(status_code=400, detail="q (query) required")

    top_k = int(payload.get("top_k", _config["top_k"]))
    turn_id = payload.get("turn_id")
    filter_dict = payload.get("filter") or {}
    kinds = filter_dict.get("kinds")

    # Get embedding from mem-embed
    http: httpx.AsyncClient = app.state.http
    try:
        embed_response = await http.post(
            f"{MEMORY_URL}/embed",
            json={"texts": [query]}
        )
        embed_response.raise_for_status()
        vectors = embed_response.json().get("vectors", [])
        if not vectors:
            raise HTTPException(status_code=502, detail="Failed to get embedding")
        vector = vectors[0]
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"Embedding service error: {exc}") from exc

    # Search with optional kind filter
    async with db.get_conn() as conn:
        if kinds:
            cur = await conn.execute(
                """
                SELECT m.id, m.text, m.kind, m.meta, m.created_at,
                       1 - (e.vec <=> %s::vector) AS score
                FROM embeddings e
                JOIN memories m ON m.id = e.memory_id
                WHERE m.kind = ANY(%s)
                ORDER BY e.vec <=> %s::vector ASC
                LIMIT %s
                """,
                (vector, kinds, vector, top_k)
            )
        else:
            cur = await conn.execute(
                """
                SELECT m.id, m.text, m.kind, m.meta, m.created_at,
                       1 - (e.vec <=> %s::vector) AS score
                FROM embeddings e
                JOIN memories m ON m.id = e.memory_id
                ORDER BY e.vec <=> %s::vector ASC
                LIMIT %s
                """,
                (vector, vector, top_k)
            )

        rows = await cur.fetchall()

    results = [
        {
            "id": str(row[0]),
            "text": row[1],
            "kind": row[2],
            "meta": row[3],
            "created_at": row[4].isoformat() if row[4] else None,
            "score": float(row[5])
        }
        for row in rows
    ]

    _last_hits = len(results)
    await query_history.add(query=query, count=len(results))
    search_latency_ms.observe((time.time() - t0) * 1000)

    return JSONResponse({"results": results, "turn_id": turn_id})


@app.get("/stats")
async def stats() -> JSONResponse:
    """Get memory statistics including last query metrics."""
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
            "last_memory_hits": _last_hits,
            "last_used": _last_used,
            "last_queries": history,
        }
    )


@app.post("/stats/hit")
async def stats_hit(payload: dict = Body(...)) -> JSONResponse:
    """
    Record that memory was (or wasn't) used in a response.

    Step 2.5: Orchestrator signals whether retrieved memories were actually used.
    """
    global _last_used

    used = bool(payload.get("used", False))
    if used:
        memory_search_used_total.inc()

    _last_used = used
    return JSONResponse({"ok": True})


@app.post("/backfill/start")
async def backfill_start(request: Request) -> JSONResponse:
    payload = await request.json() if request.headers.get("content-type") == "application/json" else {}
    return JSONResponse({"status": "accepted", "payload": payload}, status_code=202)


@app.post("/config")
async def config(payload: dict = Body(...)) -> JSONResponse:
    """
    Update configuration (autosave, min_score, top_k, ingest).

    Step 2.5: Enhanced to support memory-specific config.
    """
    global ingest_enabled

    # Update config dict with any valid keys
    valid_keys = {"autosave", "min_score", "top_k", "ingest"}
    for key, value in payload.items():
        if key in valid_keys:
            _config[key] = value

    # Maintain backward compatibility with ingest flag
    if "ingest" in payload:
        ingest = bool(payload["ingest"])
        async with ingest_lock:
            ingest_enabled = ingest
            _config["ingest"] = ingest

    return JSONResponse(_config)


@app.get("/config")
async def get_config() -> JSONResponse:
    """Get current configuration."""
    async with ingest_lock:
        current_ingest = ingest_enabled

    return JSONResponse({**_config, "ingest": current_ingest})


@app.get("/turns/{turn_id}")
async def get_turn_debug(turn_id: str) -> JSONResponse:
    """
    Debug endpoint: show all memories for a turn_id.

    Step 2.5: Traceability endpoint for debugging memory flow.
    Gated by DEBUG_TURNS environment variable in production.
    """
    debug_enabled = os.getenv("DEBUG_TURNS", "0") == "1"
    if not debug_enabled:
        raise HTTPException(status_code=404, detail="Endpoint not available")

    async with db.get_conn() as conn:
        cur = await conn.execute(
            """
            SELECT m.id, m.text, m.kind, m.meta, m.created_at, m.updated_at,
                   e.vec IS NOT NULL as has_embedding
            FROM memories m
            LEFT JOIN embeddings e ON e.memory_id = m.id
            WHERE m.meta->>'turn_id' = %s
            ORDER BY m.created_at ASC
            """,
            (turn_id,)
        )
        rows = await cur.fetchall()

    memories = [
        {
            "id": str(row[0]),
            "text": row[1],
            "kind": row[2],
            "meta": row[3],
            "created_at": row[4].isoformat() if row[4] else None,
            "updated_at": row[5].isoformat() if row[5] else None,
            "has_embedding": bool(row[6])
        }
        for row in rows
    ]

    return JSONResponse({"turn_id": turn_id, "memories": memories, "count": len(memories)})
