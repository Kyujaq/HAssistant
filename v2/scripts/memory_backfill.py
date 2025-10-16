#!/usr/bin/env python3
"""Memory backfill utility.

Scans historical notes/logs, generates embeddings in batches, and upserts them into Postgres.
"""

import argparse
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Sequence, Tuple
from uuid import NAMESPACE_URL, uuid5

import httpx
import psycopg
from psycopg.types.json import Json

DEFAULT_BATCH_SIZE = 256
EMBED_BATCH_SIZE = 128
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://glados:glados@localhost:5432/glados")
MEMORY_URL = os.getenv("MEMORY_URL", "http://127.0.0.1:8001")


@dataclass
class MemoryItem:
    identifier: str
    text: str
    source: str
    kind: str = "note"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Backfill historical memories into the vector store.")
    parser.add_argument("--batch", type=int, default=DEFAULT_BATCH_SIZE, help="Number of memories per write batch.")
    parser.add_argument("--resume", type=Path, default=Path("v2/state/backfill.json"), help="Path to resume state file.")
    parser.add_argument("--dry-run", action="store_true", help="Run without writing to the database.")
    return parser.parse_args()


def collect_sources(root: Path) -> List[MemoryItem]:
    def candidate_files(path: Path) -> Iterable[Path]:
        for ext in (".md", ".txt", ".log"):
            yield from path.rglob(f"*{ext}")

    items: List[MemoryItem] = []
    if not root.exists():
        return items

    for file_path in candidate_files(root):
        try:
            contents = file_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        text = contents.strip()
        if not text:
            continue
        identifier = str(uuid5(NAMESPACE_URL, f"{file_path.relative_to(root)}"))
        items.append(
            MemoryItem(
                identifier=identifier,
                text=text,
                source=str(file_path),
            )
        )
    return items


def load_seed_sources(path: Path) -> List[MemoryItem]:
    if not path.exists():
        return []

    items: List[MemoryItem] = []
    try:
        raw_lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return items

    for idx, line in enumerate(raw_lines):
        line = line.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        text = str(payload.get("text", "")).strip()
        if not text:
            continue
        kind = str(payload.get("kind", "note") or "note")
        source = str(payload.get("source", "seed") or "seed")
        identifier = str(uuid5(NAMESPACE_URL, f"seed::{idx}::{text}"))
        items.append(MemoryItem(identifier=identifier, text=text, source=source, kind=kind))
    return items


def load_resume_state(path: Path) -> int:
    if not path.exists():
        return 0
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return 0
    return int(data.get("cursor", 0))


def save_resume_state(path: Path, cursor: int, total: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"cursor": cursor, "total": total}
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


async def embed_batch(client: httpx.AsyncClient, texts: Sequence[str]) -> List[List[float]]:
    response = await client.post(f"{MEMORY_URL}/embed", json={"texts": list(texts)})
    response.raise_for_status()
    return response.json()["vectors"]


async def upsert_batch(conn: psycopg.AsyncConnection, items: Sequence[MemoryItem], vectors: Sequence[Sequence[float]]) -> None:
    async with conn.transaction():
        for item, vector in zip(items, vectors, strict=True):
            await conn.execute(
                "INSERT INTO memories(id, kind, source, text, meta) "
                "VALUES(%s, %s, %s, %s, %s) "
                "ON CONFLICT (id) DO UPDATE SET source = EXCLUDED.source, text = EXCLUDED.text",
                (item.identifier, item.kind, "import", item.text, Json({"source": item.source})),
            )
            await conn.execute(
                "INSERT INTO embeddings(memory_id, vec) VALUES(%s, %s) "
                "ON CONFLICT (memory_id) DO UPDATE SET vec = EXCLUDED.vec",
                (item.identifier, vector),
            )


async def process_batch(
    conn: psycopg.AsyncConnection,
    client: httpx.AsyncClient,
    items: Sequence[MemoryItem],
    dry_run: bool,
) -> None:
    if dry_run:
        print(f"[DRY-RUN] Would embed and upsert {len(items)} items")
        return

    for start in range(0, len(items), EMBED_BATCH_SIZE):
        chunk = items[start : start + EMBED_BATCH_SIZE]
        vectors = await embed_batch(client, [item.text for item in chunk])
        await upsert_batch(conn, chunk, vectors)


async def run_backfill(args: argparse.Namespace) -> None:
    sources = collect_sources(Path("v1"))
    total = len(sources)
    if not sources:
        seed_path = Path("sample_data/memory_seed.jsonl")
        print(f"No sources discovered under v1/ - checking seed dataset at {seed_path}")
        sources = load_seed_sources(seed_path)
        total = len(sources)
        if not sources:
            print("No sample seed data found; exiting without backfill.")
            return
        print(f"Loaded {total} seed memories from sample_data/memory_seed.jsonl")

    cursor = load_resume_state(args.resume)
    print(f"Starting backfill from cursor {cursor} of {total} items (batch={args.batch})")

    async with await psycopg.AsyncConnection.connect(DATABASE_URL) as conn:
        timeout = httpx.Timeout(60.0, read=60.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            while cursor < total:
                batch_items = sources[cursor : cursor + args.batch]
                print(f"Processing items {cursor}..{cursor + len(batch_items) - 1}")
                await process_batch(conn, client, batch_items, args.dry_run)
                cursor += len(batch_items)
                save_resume_state(args.resume, cursor, total)

    print("Backfill complete.")


def main() -> None:
    args = parse_args()
    try:
        import asyncio

        asyncio.run(run_backfill(args))
    except KeyboardInterrupt:
        print("Backfill interrupted.", file=sys.stderr)
        sys.exit(1)
    except Exception as exc:  # pragma: no cover
        print(f"Backfill failed: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
