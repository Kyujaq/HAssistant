import sys
import types
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from typing import Any, Dict, List, Optional

import pytest
from fastapi.testclient import TestClient

MODULE_DIR = Path(__file__).resolve().parents[1] / "services" / "memory-embed"
PACKAGE_NAME = "memory_embed_pkg"
PACKAGE = types.ModuleType(PACKAGE_NAME)
PACKAGE.__path__ = [str(MODULE_DIR)]
spec = spec_from_file_location(f"{PACKAGE_NAME}.server", MODULE_DIR / "server.py", submodule_search_locations=[str(MODULE_DIR)])
mem_server = module_from_spec(spec)
sys.modules.setdefault(PACKAGE_NAME, PACKAGE)
sys.modules[f"{PACKAGE_NAME}.server"] = mem_server
spec.loader.exec_module(mem_server)


class FakeCursor:
    def __init__(self, rows: Optional[List[Any]] = None) -> None:
        self._rows = rows or []

    async def fetchall(self) -> List[Any]:
        return self._rows


class FakeConnection:
    def __init__(self) -> None:
        self.memories: Dict[str, Dict[str, Any]] = {}
        self.embeddings: Dict[str, Dict[str, Any]] = {}
        self.search_term: str = ""

    async def execute(self, query: str, params: Any) -> FakeCursor:
        if query.startswith("INSERT INTO memories"):
            memory_id = params[0]
            self.memories[memory_id] = {
                "kind": params[1],
                "source": params[2],
                "text": params[3],
                "meta": params[4],
            }
            return FakeCursor()

        if query.startswith("INSERT INTO embeddings"):
            memory_id = params[0]
            self.embeddings[memory_id] = {"vec": params[1]}
            return FakeCursor()

        if query.startswith("SELECT m.id"):
            term = (self.search_term or "keyword").lower()
            results = []
            for memory_id, data in self.memories.items():
                text = data["text"]
                if term in text.lower():
                    score = 1.0
                    results.append((memory_id, text, data["meta"], score))
            return FakeCursor(results)

        raise AssertionError(f"Unexpected query: {query}")

    async def commit(self) -> None:
        return None


class FakeConnManager:
    def __init__(self, conn: FakeConnection) -> None:
        self._conn = conn

    async def __aenter__(self) -> FakeConnection:
        return self._conn

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None


class StubModel:
    def encode(self, texts, normalize_embeddings=True):
        return [[1.0, 0.0, 0.0] for _ in texts]


def test_upsert_and_search(monkeypatch):
    fake_conn = FakeConnection()
    monkeypatch.setattr(mem_server, "model", StubModel())
    monkeypatch.setattr(mem_server.db, "get_conn", lambda: FakeConnManager(fake_conn))

    client = TestClient(mem_server.app)

    for idx in range(20):
        text = f"Memory {idx} keyword" if idx % 2 == 0 else f"Memory {idx}"
        response = client.post(
            "/upsert",
            json={
                "id": f"00000000-0000-0000-0000-{idx:012d}",
                "text": text,
                "kind": "note",
                "source": "pytest",
            },
        )
        assert response.status_code == 200

    fake_conn.search_term = "keyword"
    search_response = client.post("/search", json={"q": "keyword", "top_k": 5})
    assert search_response.status_code == 200
    data = search_response.json()
    assert data["results"], "Expected search results for keyword"
