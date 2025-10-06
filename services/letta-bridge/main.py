import os
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Literal
import uuid
import json

import asyncpg
import redis.asyncio as aioredis
import uvicorn
from fastapi import FastAPI, HTTPException, Depends, Header, Query
from pydantic import BaseModel, Field
import numpy as np

# --------------------
# ENV & CONFIG
# --------------------
PG_DSN = os.getenv("LETTA_PG_URI", "postgresql://hassistant:CHANGE_ME_STRONG_PASSWORD_REQUIRED@hassistant-postgres:5432/hassistant")
REDIS_URL = os.getenv("LETTA_REDIS_URL", "redis://:CHANGE_ME_STRONG_PASSWORD_REQUIRED@hassistant-redis:6379/0")
API_KEY = os.getenv("BRIDGE_API_KEY", "dev-key")  # SECURITY: Change in production! Set BRIDGE_API_KEY in .env
EMBED_DIM = int(os.getenv("EMBED_DIM", "1536"))    # match your pgvector dim (1536 for ada-002)
DAILY_BRIEF_WINDOW_HOURS = int(os.getenv("DAILY_BRIEF_WINDOW_HOURS", "24"))

# Tier mapping: API tier names → Database tier names
TIER_MAP = {
    "short": "short_term",
    "medium": "medium_term",
    "long": "long_term",
    "permanent": "permanent",
    "session": "session"
}

# --------------------
# FastAPI
# --------------------
app = FastAPI(title="Letta Bridge", version="0.1.0")

async def get_pg():
    pool = await asyncpg.create_pool(PG_DSN, min_size=1, max_size=5)
    try:
        yield pool
    finally:
        await pool.close()

async def get_redis():
    redis = await aioredis.from_url(REDIS_URL, decode_responses=True)
    try:
        yield redis
    finally:
        await redis.close()

async def auth(x_api_key: Optional[str] = Header(default=None)):
    if API_KEY and x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return True

# --------------------
# Schemas
# --------------------
Tier = Literal["short", "medium", "long", "permanent", "session"]
MemType = Literal["fact", "event", "task", "preference", "insight", "entity", "note", "conversation", "knowledge"]

class MemoryIn(BaseModel):
    type: MemType = "event"
    title: str
    content: str
    tags: List[str] = Field(default_factory=list)
    source: List[str] = Field(default_factory=list)
    confidence: float = 0.7
    tier: Tier = "short"
    pin: bool = False
    meta: dict = Field(default_factory=dict)
    generate_embedding: bool = True

class PinIn(BaseModel):
    id: str
    pin: bool = True

class ForgetIn(BaseModel):
    id: str
    reason: Optional[str] = None

class SearchOutItem(BaseModel):
    id: str
    title: str
    preview: str
    type: str
    tier: str
    confidence: float
    score: float
    created_at: str
    tags: List[str] = []
    source: List[str] = []

# --------------------
# Embeddings (placeholder)
# ⚠️  PRODUCTION WARNING: Replace fake_embed() with real embedding model!
# --------------------
def fake_embed(text: str, dim: int = EMBED_DIM) -> List[float]:
    """
    ⚠️  WARNING: DO NOT use in production!
    
    This is a deterministic pseudo-embedding for development/testing only.
    
    Replace with a real embedding model before deploying to production:
    - sentence-transformers (all-MiniLM-L6-v2, all-mpnet-base-v2)
    - OpenAI ada-002
    - Ollama embeddings (via API or local model)
    - Hugging Face embeddings
    
    Example replacement with sentence-transformers:
        from sentence_transformers import SentenceTransformer
        model = SentenceTransformer('all-MiniLM-L6-v2')
        def real_embed(text: str) -> List[float]:
            return model.encode(text).tolist()
    """
    rng = np.random.default_rng(abs(hash(text)) % (2**32))
    v = rng.standard_normal(dim)
    v = v / (np.linalg.norm(v) + 1e-9)
    return v.astype(np.float32).tolist()

# --------------------
# Routes
# --------------------
@app.get("/healthz")
async def healthz():
    return {"status": "ok", "time": datetime.now(timezone.utc).isoformat()}

@app.post("/memory/add")
async def add_memory(
    body: MemoryIn,
    _=Depends(auth),
    pg=Depends(get_pg),
    redis=Depends(get_redis),
):
    now = datetime.now(timezone.utc)
    db_tier = TIER_MAP.get(body.tier, "short_term")

    async with pg.acquire() as conn:
        async with conn.transaction():
            mem_id = await conn.fetchval(
                """
                INSERT INTO memory_blocks
                  (id, type, title, content, tags, source, confidence, created_at, last_used_at, tier, pin, meta)
                VALUES
                  ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12::jsonb)
                RETURNING id
                """,
                uuid.uuid4(), body.type, body.title, body.content, body.tags, body.source,
                body.confidence, now, now, db_tier, body.pin, json.dumps(body.meta)
            )

            if body.generate_embedding:
                emb = fake_embed(body.title + "\n" + body.content, EMBED_DIM)
                # Convert list to pgvector format string
                emb_str = '[' + ','.join(map(str, emb)) + ']'
                await conn.execute(
                    """
                    INSERT INTO memory_embeddings (memory_id, embedding)
                    VALUES ($1, $2::vector)
                    ON CONFLICT (memory_id) DO UPDATE SET embedding = EXCLUDED.embedding
                    """,
                    mem_id, emb_str
                )

    # small ephemeral marker in Redis (optional)
    await redis.setex(f"cooldown:mem_add:{mem_id}", 60, "1")
    return {"status": "ok", "id": str(mem_id)}

@app.post("/memory/pin")
async def memory_pin(body: PinIn, _=Depends(auth), pg=Depends(get_pg)):
    async with pg.acquire() as conn:
        rec = await conn.fetchrow("SELECT id FROM memory_blocks WHERE id=$1", uuid.UUID(body.id))
        if not rec:
            raise HTTPException(404, "Memory not found")
        await conn.execute("UPDATE memory_blocks SET pin=$1 WHERE id=$2", body.pin, uuid.UUID(body.id))
    return {"status":"ok","id":body.id,"pinned":body.pin}

@app.post("/memory/forget")
async def memory_forget(body: ForgetIn, _=Depends(auth), pg=Depends(get_pg)):
    async with pg.acquire() as conn:
        rec = await conn.fetchrow("SELECT id FROM memory_blocks WHERE id=$1", uuid.UUID(body.id))
        if not rec:
            raise HTTPException(404, "Memory not found")
        await conn.execute(
            "UPDATE memory_blocks SET tier='short_term', pin=false WHERE id=$1",
            uuid.UUID(body.id)
        )
    return {"status":"ok","id":body.id,"tier":"short_term"}

@app.get("/memory/search", response_model=List[SearchOutItem])
async def memory_search(
    q: str = Query(..., description="Text query"),
    k: int = 8,
    tiers: Optional[str] = Query(None, description="comma list e.g. short,medium,long,permanent"),
    types: Optional[str] = Query(None, description="comma list e.g. event,fact,insight"),
    _=Depends(auth),
    pg=Depends(get_pg)
):
    # Map API tier names to database tier names
    tiers_list = None
    if tiers:
        api_tiers = [t.strip() for t in tiers.split(",")]
        tiers_list = [TIER_MAP.get(t, t) for t in api_tiers]

    types_list = [t.strip() for t in types.split(",")] if types else None

    # text match + optional vector
    async with pg.acquire() as conn:
        # vector part
        emb = fake_embed(q, EMBED_DIM)
        # Convert list to pgvector format string
        emb_str = '[' + ','.join(map(str, emb)) + ']'
        filters = []
        params = [emb_str]
        if tiers_list:
            filters.append(f"tier = ANY(${len(params)+1})")
            params.append(tiers_list)
        if types_list:
            filters.append(f"type = ANY(${len(params)+1})")
            params.append(types_list)
        where = ("WHERE " + " AND ".join(filters)) if filters else ""

        rows = await conn.fetch(
            f"""
            SELECT mb.id, mb.title, left(mb.content, 200) AS preview, mb.type, mb.tier,
                   mb.confidence, mb.created_at, mb.tags, mb.source,
                   1 - (me.embedding <=> $1::vector) AS score
            FROM memory_embeddings me
            JOIN memory_blocks mb ON mb.id = me.memory_id
            {where}
            ORDER BY score DESC
            LIMIT {k}
            """,
            *params
        )
    return [
        SearchOutItem(
            id=str(r["id"]), title=r["title"], preview=r["preview"], type=r["type"],
            tier=r["tier"], confidence=r["confidence"],
            score=float(r["score"]), created_at=r["created_at"].isoformat(),
            tags=r["tags"] or [], source=r["source"] or []
        )
        for r in rows
    ]

@app.get("/daily_brief")
async def daily_brief(
    _=Depends(auth),
    pg=Depends(get_pg),
):
    since = datetime.now(timezone.utc) - timedelta(hours=DAILY_BRIEF_WINDOW_HOURS)
    async with pg.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, title, left(content, 240) AS preview, type, tier, created_at
            FROM memory_blocks
            WHERE created_at >= $1
              AND (type = 'insight' OR tier IN ('medium_term','long_term','permanent'))
            ORDER BY created_at DESC
            LIMIT 20
            """,
            since
        )
    return {
        "since": since.isoformat(),
        "items": [
            {
                "id": str(r["id"]), "title": r["title"], "preview": r["preview"],
                "type": r["type"], "tier": r["tier"],
                "created_at": r["created_at"].isoformat()
            } for r in rows
        ]
    }

@app.post("/memory/maintenance")
async def memory_maintenance(_=Depends(auth), pg=Depends(get_pg)):
    """
    Run memory eviction based on tier age policies.
    Should be called periodically (e.g., daily) to clean up old memories.
    """
    async with pg.acquire() as conn:
        rows = await conn.fetch("SELECT * FROM evict_old_memories()")
    
    summary = {r["tier"]: r["evicted_count"] for r in rows}
    total = sum(summary.values())
    
    return {
        "status": "ok",
        "total_evicted": total,
        "by_tier": summary
    }

@app.get("/metrics")
async def metrics():
    return {"uptime": "ok"}  # stub; add real metrics later

if __name__ == "__main__":
    import sys
    import warnings
    
    # Production safety check
    print("=" * 70)
    print("🚀 Starting Letta Bridge API Server")
    print("=" * 70)
    
    # Warn about fake embedding function
    warnings.warn(
        "\n" + "!" * 70 + "\n"
        "⚠️  PRODUCTION WARNING: Using fake_embed() placeholder function!\n"
        "   This is for development/testing only.\n"
        "   Replace with a real embedding model before production deployment.\n"
        "   See letta_bridge/main.py for implementation examples.\n"
        + "!" * 70,
        UserWarning,
        stacklevel=2
    )
    
    # Warn about default API key
    if API_KEY == "dev-key":
        warnings.warn(
            "\n" + "!" * 70 + "\n"
            "⚠️  SECURITY WARNING: Using default dev-key for API authentication!\n"
            "   Set BRIDGE_API_KEY environment variable before production deployment.\n"
            + "!" * 70,
            UserWarning,
            stacklevel=2
        )
    
    print(f"Configuration:")
    print(f"  - API Key: {'dev-key (⚠️  INSECURE)' if API_KEY == 'dev-key' else '***configured***'}")
    print(f"  - Embedding Dimension: {EMBED_DIM}")
    print(f"  - Daily Brief Window: {DAILY_BRIEF_WINDOW_HOURS}h")
    print(f"  - Port: {os.getenv('PORT', '8081')}")
    print("=" * 70)
    
    uvicorn.run("main:app", host="0.0.0.0", port=int(os.getenv("PORT", "8081")), reload=False)
