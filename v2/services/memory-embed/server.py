import os
import time
from typing import List

from fastapi import Body, FastAPI, HTTPException
from fastapi.responses import JSONResponse, PlainTextResponse
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from sentence_transformers import SentenceTransformer
from psycopg.types.json import Json

try:
    from . import db
except ImportError:  # pragma: no cover
    import importlib

    db = importlib.import_module("db")

MODEL_NAME = os.getenv("EMBED_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
DEFAULT_TOP_K = int(os.getenv("TOP_K", "8"))

model = SentenceTransformer(MODEL_NAME)

REQS = Counter("memembed_requests_total", "requests", ["route"])
LAT = Histogram("memembed_latency_seconds", "latency", ["route"])

app = FastAPI(title="memory-embed")


@app.get("/health")
async def health() -> JSONResponse:
    return JSONResponse({"ok": True, "model": MODEL_NAME})


@app.get("/metrics")
def metrics() -> PlainTextResponse:
    return PlainTextResponse(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.post("/embed")
async def embed(payload: dict = Body(...)) -> JSONResponse:
    REQS.labels("embed").inc()
    start = time.time()

    texts: List[str] = payload.get("texts") or []
    if not texts:
        raise HTTPException(status_code=400, detail="texts[] required")

    vectors = model.encode(texts, normalize_embeddings=True).tolist()
    LAT.labels("embed").observe(time.time() - start)
    return JSONResponse({"vectors": vectors})


@app.post("/upsert")
async def upsert(payload: dict = Body(...)) -> JSONResponse:
    REQS.labels("upsert").inc()
    start = time.time()

    from uuid import UUID, uuid4

    raw_id = payload.get("id")
    text = payload.get("text", "")
    if not text:
        raise HTTPException(status_code=400, detail="text required")

    kind = payload.get("kind", "note")
    source = payload.get("source", "api")
    meta = payload.get("meta", {})

    memory_id = UUID(raw_id) if raw_id else uuid4()

    vector = model.encode([text], normalize_embeddings=True)[0].tolist()

    async with db.get_conn() as conn:
        await conn.execute(
            "INSERT INTO memories(id, kind, source, text, meta) "
            "VALUES(%s, %s, %s, %s, %s) "
            "ON CONFLICT (id) DO UPDATE SET "
            "kind = EXCLUDED.kind, "
            "source = EXCLUDED.source, "
            "text = EXCLUDED.text, "
            "meta = EXCLUDED.meta",
            (str(memory_id), kind, source, text, Json(meta)),
        )
        await conn.execute(
            "INSERT INTO embeddings(memory_id, vec) VALUES(%s, %s) "
            "ON CONFLICT (memory_id) DO UPDATE SET vec = EXCLUDED.vec",
            (str(memory_id), vector),
        )
        await conn.commit()

    LAT.labels("upsert").observe(time.time() - start)
    return JSONResponse({"id": str(memory_id)})


@app.post("/search")
async def search(payload: dict = Body(...)) -> JSONResponse:
    REQS.labels("search").inc()
    start = time.time()

    query_text = payload.get("q", "")
    if not query_text:
        raise HTTPException(status_code=400, detail="q required")
    top_k = int(payload.get("top_k", DEFAULT_TOP_K))

    query_vector = model.encode([query_text], normalize_embeddings=True)[0].tolist()

    async with db.get_conn() as conn:
        cursor = await conn.execute(
            "SELECT m.id, m.text, m.meta, 1 - (e.vec <=> %s::vector) AS score "
            "FROM embeddings e "
            "JOIN memories m ON m.id = e.memory_id "
            "ORDER BY e.vec <=> %s::vector ASC "
            "LIMIT %s",
            (query_vector, query_vector, top_k),
        )
        rows = await cursor.fetchall()

    LAT.labels("search").observe(time.time() - start)

    return JSONResponse(
        {
            "results": [
                {
                    "id": str(row[0]),
                    "text": row[1],
                    "meta": row[2],
                    "score": float(row[3]),
                }
                for row in rows
            ]
        }
    )
