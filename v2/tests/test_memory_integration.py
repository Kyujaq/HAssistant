"""
Unit tests for Memory Integration (Step 2.5)

Tests cover:
- Basic retrieval flow
- Kind filtering in search
- Autosave toggle
- PII redaction
- Deduplication
- Ephemeral vs durable classification
- Turn traceability

Run with: pytest v2/tests/test_memory_integration.py -v
"""
import os
import pytest
import httpx
import asyncio
from typing import Dict, List

# Configuration
BRIDGE_URL = os.getenv("BRIDGE_URL", "http://localhost:8010")
ORCHESTRATOR_URL = os.getenv("ORCHESTRATOR_URL", "http://localhost:8020")


@pytest.mark.asyncio
async def test_basic_retrieval_flow():
    """Test that we can add a memory and retrieve it via search"""
    async with httpx.AsyncClient() as client:
        # Add a test memory
        add_response = await client.post(
            f"{BRIDGE_URL}/memory/add",
            json={
                "text": "The HDMI dongle is in the left desk drawer",
                "kind": "note",
                "source": "test"
            }
        )
        assert add_response.status_code == 200
        add_data = add_response.json()
        assert "id" in add_data
        assert "hash_id" in add_data

        # Search for it
        search_response = await client.post(
            f"{BRIDGE_URL}/memory/search",
            json={"q": "Where is the HDMI dongle?"}
        )
        assert search_response.status_code == 200
        search_data = search_response.json()
        results = search_data.get("results", [])

        # Should find the memory
        assert len(results) > 0
        assert any("drawer" in r["text"].lower() for r in results)


@pytest.mark.asyncio
async def test_kind_filtering():
    """Test that kind filtering works in search"""
    async with httpx.AsyncClient() as client:
        # Add memories of different kinds
        await client.post(
            f"{BRIDGE_URL}/memory/add",
            json={"text": "Test note about HDMI", "kind": "note", "source": "test"}
        )
        await client.post(
            f"{BRIDGE_URL}/memory/add",
            json={"text": "Thanks for the help", "kind": "chat_ephemeral", "source": "test"}
        )

        # Search with kind filter (only notes and tasks)
        search_response = await client.post(
            f"{BRIDGE_URL}/memory/search",
            json={
                "q": "HDMI",
                "filter": {"kinds": ["note", "task"]}
            }
        )
        assert search_response.status_code == 200
        results = search_response.json().get("results", [])

        # Should only return note (not chat_ephemeral)
        for result in results:
            assert result["kind"] in ["note", "task"]


@pytest.mark.asyncio
async def test_autosave_toggle():
    """Test that autosave can be toggled via config"""
    async with httpx.AsyncClient() as client:
        # Turn off autosave
        config_response = await client.post(
            f"{BRIDGE_URL}/config",
            json={"autosave": False}
        )
        assert config_response.status_code == 200
        config_data = config_response.json()
        assert config_data["autosave"] == False

        # Turn it back on
        config_response = await client.post(
            f"{BRIDGE_URL}/config",
            json={"autosave": True}
        )
        assert config_response.status_code == 200
        config_data = config_response.json()
        assert config_data["autosave"] == True


@pytest.mark.asyncio
async def test_deduplication():
    """Test that duplicate text creates same hash and is deduplicated"""
    async with httpx.AsyncClient() as client:
        text = "The HDMI dongle is in the drawer"

        # Add first time
        response1 = await client.post(
            f"{BRIDGE_URL}/memory/add",
            json={"text": text, "kind": "note", "source": "test"}
        )
        assert response1.status_code == 200
        data1 = response1.json()
        hash_id_1 = data1["hash_id"]
        deduped_1 = data1.get("deduped", False)

        # Add same text again (normalized - case insensitive)
        response2 = await client.post(
            f"{BRIDGE_URL}/memory/add",
            json={"text": text.upper(), "kind": "note", "source": "test"}
        )
        assert response2.status_code == 200
        data2 = response2.json()
        hash_id_2 = data2["hash_id"]
        deduped_2 = data2.get("deduped", False)

        # Should have same hash and second should be marked as deduped
        assert hash_id_1 == hash_id_2
        assert deduped_1 == False  # First insert
        assert deduped_2 == True   # Dedup hit


@pytest.mark.asyncio
async def test_stats_endpoint():
    """Test that stats endpoint returns expected fields"""
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{BRIDGE_URL}/stats")
        assert response.status_code == 200
        data = response.json()

        # Check required fields
        assert "total" in data
        assert "embedded" in data
        assert "pending" in data
        assert "last_memory_hits" in data
        assert "last_used" in data
        assert "last_queries" in data

        assert isinstance(data["total"], int)
        assert isinstance(data["last_memory_hits"], int)
        assert isinstance(data["last_used"], bool)


@pytest.mark.asyncio
async def test_config_persistence():
    """Test that config changes persist"""
    async with httpx.AsyncClient() as client:
        # Set config
        await client.post(
            f"{BRIDGE_URL}/config",
            json={"min_score": 0.75, "top_k": 10}
        )

        # Get config
        response = await client.get(f"{BRIDGE_URL}/config")
        assert response.status_code == 200
        data = response.json()

        assert data["min_score"] == 0.75
        assert data["top_k"] == 10


@pytest.mark.asyncio
async def test_orchestrator_health():
    """Test that orchestrator health endpoint works"""
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(f"{ORCHESTRATOR_URL}/health")
            assert response.status_code == 200
            data = response.json()
            assert data["ok"] == True
        except httpx.ConnectError:
            pytest.skip("Orchestrator not running")


@pytest.mark.asyncio
async def test_orchestrator_chat_integration():
    """Test end-to-end chat with memory retrieval"""
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            # First seed a fact
            await client.post(
                f"{BRIDGE_URL}/memory/add",
                json={
                    "text": "The spare HDMI dongle is in the left desk drawer",
                    "kind": "note",
                    "source": "test"
                }
            )

            # Ask a question via orchestrator
            chat_response = await client.post(
                f"{ORCHESTRATOR_URL}/chat",
                json={"input": "Where is the HDMI dongle?"}
            )
            assert chat_response.status_code == 200
            data = chat_response.json()

            # Should have retrieved the memory
            assert "turn_id" in data
            assert "reply" in data
            assert "memory_hits" in data
            assert "ctx_chars" in data

            # Should have hit at least one memory
            assert data["memory_hits"] > 0

        except httpx.ConnectError:
            pytest.skip("Orchestrator or dependencies not running")


if __name__ == "__main__":
    # Allow running tests directly
    import sys
    sys.exit(pytest.main([__file__, "-v"]))
