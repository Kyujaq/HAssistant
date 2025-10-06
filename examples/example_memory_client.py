#!/usr/bin/env python3
"""
Example script demonstrating how to interact with the Letta Bridge Memory API.

This script shows how to:
- Add memories
- Search memories
- Pin/unpin memories
- Run maintenance
- Get daily brief

Usage:
    python3 example_memory_client.py
    
Environment:
    LETTA_BRIDGE_URL: URL of the Letta Bridge API (default: http://localhost:8081)
    LETTA_BRIDGE_API_KEY: API key for authentication (default: dev-key)
"""

import os
import sys
import json
import requests
from typing import Dict, List, Optional

# Configuration
LETTA_BRIDGE_URL = os.getenv("LETTA_BRIDGE_URL", "http://localhost:8081")
LETTA_BRIDGE_API_KEY = os.getenv("LETTA_BRIDGE_API_KEY", "dev-key")

class LettaMemoryClient:
    """Client for interacting with Letta Bridge Memory API."""
    
    def __init__(self, base_url: str = LETTA_BRIDGE_URL, api_key: str = LETTA_BRIDGE_API_KEY):
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.headers = {
            "x-api-key": api_key,
            "Content-Type": "application/json"
        }
    
    def add_memory(
        self,
        title: str,
        content: str,
        type: str = "event",
        tier: str = "short",
        tags: List[str] = None,
        source: List[str] = None,
        confidence: float = 0.7,
        pin: bool = False,
        generate_embedding: bool = True,
        meta: Dict = None
    ) -> Dict:
        """Add a new memory to the system."""
        payload = {
            "title": title,
            "content": content,
            "type": type,
            "tier": tier,
            "tags": tags or [],
            "source": source or [],
            "confidence": confidence,
            "pin": pin,
            "generate_embedding": generate_embedding,
            "meta": meta or {}
        }
        
        response = requests.post(
            f"{self.base_url}/memory/add",
            headers=self.headers,
            json=payload
        )
        response.raise_for_status()
        return response.json()
    
    def search_memories(
        self,
        query: str,
        k: int = 8,
        tiers: Optional[List[str]] = None,
        types: Optional[List[str]] = None
    ) -> List[Dict]:
        """Search memories using semantic similarity."""
        params = {"q": query, "k": k}
        if tiers:
            params["tiers"] = ",".join(tiers)
        if types:
            params["types"] = ",".join(types)
        
        response = requests.get(
            f"{self.base_url}/memory/search",
            headers=self.headers,
            params=params
        )
        response.raise_for_status()
        return response.json()
    
    def pin_memory(self, memory_id: str, pin: bool = True) -> Dict:
        """Pin or unpin a memory to prevent auto-eviction."""
        payload = {"id": memory_id, "pin": pin}
        
        response = requests.post(
            f"{self.base_url}/memory/pin",
            headers=self.headers,
            json=payload
        )
        response.raise_for_status()
        return response.json()
    
    def forget_memory(self, memory_id: str, reason: Optional[str] = None) -> Dict:
        """Mark a memory for forgetting (demotes to short-term, unpins)."""
        payload = {"id": memory_id}
        if reason:
            payload["reason"] = reason
        
        response = requests.post(
            f"{self.base_url}/memory/forget",
            headers=self.headers,
            json=payload
        )
        response.raise_for_status()
        return response.json()
    
    def get_daily_brief(self) -> Dict:
        """Get a brief of recent important memories."""
        response = requests.get(
            f"{self.base_url}/daily_brief",
            headers=self.headers
        )
        response.raise_for_status()
        return response.json()
    
    def run_maintenance(self) -> Dict:
        """Run memory maintenance to clean up old memories."""
        response = requests.post(
            f"{self.base_url}/memory/maintenance",
            headers=self.headers
        )
        response.raise_for_status()
        return response.json()
    
    def healthcheck(self) -> Dict:
        """Check if the API is healthy."""
        response = requests.get(f"{self.base_url}/healthz")
        response.raise_for_status()
        return response.json()


def example_basic_usage():
    """Demonstrate basic memory operations."""
    print("=" * 60)
    print("Letta Memory Client - Basic Usage Example")
    print("=" * 60)
    
    client = LettaMemoryClient()
    
    # 1. Health check
    print("\n1. Checking API health...")
    try:
        health = client.healthcheck()
        print(f"   ✓ API is healthy: {health}")
    except Exception as e:
        print(f"   ✗ Error: {e}")
        print("\n   Make sure Letta Bridge is running:")
        print("   docker-compose up -d letta-bridge")
        return
    
    # 2. Add a memory
    print("\n2. Adding a new memory...")
    try:
        result = client.add_memory(
            title="Temperature Alert",
            content="Living room temperature reached 25°C at 3:00 PM",
            type="event",
            tier="short",
            tags=["temperature", "living_room", "alert"],
            source=["ha://sensor.living_room_temperature"],
            confidence=0.95
        )
        memory_id = result.get("id")
        print(f"   ✓ Memory added: {memory_id}")
    except Exception as e:
        print(f"   ✗ Error: {e}")
        return
    
    # 3. Search memories
    print("\n3. Searching for temperature-related memories...")
    try:
        results = client.search_memories(
            query="temperature living room",
            k=5,
            tiers=["short", "medium"]
        )
        print(f"   ✓ Found {len(results)} memories")
        for i, mem in enumerate(results[:3], 1):
            print(f"   {i}. {mem['title']} (score: {mem['score']:.3f})")
    except Exception as e:
        print(f"   ✗ Error: {e}")
    
    # 4. Pin a memory
    print("\n4. Pinning the memory...")
    try:
        result = client.pin_memory(memory_id, pin=True)
        print(f"   ✓ Memory pinned: {result}")
    except Exception as e:
        print(f"   ✗ Error: {e}")
    
    # 5. Get daily brief
    print("\n5. Getting daily brief...")
    try:
        brief = client.get_daily_brief()
        print(f"   ✓ Daily brief: {len(brief['items'])} items since {brief['since']}")
    except Exception as e:
        print(f"   ✗ Error: {e}")
    
    print("\n" + "=" * 60)
    print("Example completed!")
    print("=" * 60)


def example_conversation_logging():
    """Example: Log a conversation to memory."""
    print("\n" + "=" * 60)
    print("Example: Logging a Conversation")
    print("=" * 60)
    
    client = LettaMemoryClient()
    
    conversation = [
        ("user", "What's the weather like?"),
        ("assistant", "Currently 22°C and sunny in your area."),
        ("user", "Should I bring an umbrella?"),
        ("assistant", "No need, there's no rain forecasted for today."),
    ]
    
    print("\nLogging conversation to memory...")
    for i, (speaker, message) in enumerate(conversation):
        try:
            result = client.add_memory(
                title=f"Conversation turn {i+1}: {speaker}",
                content=message,
                type="conversation",
                tier="session",
                tags=["conversation", "weather", speaker],
                source=["conversation://example"],
                confidence=1.0,
                meta={"turn": i+1, "speaker": speaker}
            )
            print(f"   ✓ Logged: {speaker}: {message[:30]}...")
        except Exception as e:
            print(f"   ✗ Error logging message: {e}")
    
    print("\nSearching for weather-related conversations...")
    try:
        results = client.search_memories(
            query="weather umbrella rain",
            types=["conversation"]
        )
        print(f"   ✓ Found {len(results)} conversation turns")
    except Exception as e:
        print(f"   ✗ Error: {e}")


def example_user_preference():
    """Example: Store a user preference."""
    print("\n" + "=" * 60)
    print("Example: Storing User Preferences")
    print("=" * 60)
    
    client = LettaMemoryClient()
    
    preferences = [
        {
            "title": "Lighting Preference",
            "content": "User prefers warm white lighting (2700K) in the evening",
            "tags": ["lighting", "preference", "evening"],
        },
        {
            "title": "Temperature Preference",
            "content": "User likes the temperature set to 21°C during the day",
            "tags": ["temperature", "preference", "comfort"],
        },
        {
            "title": "Music Preference",
            "content": "User enjoys classical music while working",
            "tags": ["music", "preference", "work"],
        },
    ]
    
    print("\nStoring user preferences...")
    for pref in preferences:
        try:
            result = client.add_memory(
                title=pref["title"],
                content=pref["content"],
                type="preference",
                tier="long",  # Preferences are long-term
                tags=pref["tags"],
                confidence=0.85,
                pin=True,  # Pin preferences so they don't get evicted
            )
            print(f"   ✓ Stored: {pref['title']}")
        except Exception as e:
            print(f"   ✗ Error: {e}")
    
    print("\nRetrieving preferences...")
    try:
        results = client.search_memories(
            query="user preferences",
            types=["preference"],
            tiers=["long", "permanent"]
        )
        print(f"   ✓ Found {len(results)} preferences:")
        for i, mem in enumerate(results, 1):
            print(f"   {i}. {mem['title']}")
    except Exception as e:
        print(f"   ✗ Error: {e}")


def main():
    """Run all examples."""
    print("\n🧠 Letta Bridge Memory API Examples\n")
    print("This script demonstrates how to use the memory system.")
    print("Make sure Letta Bridge is running before proceeding.\n")
    
    try:
        # Run examples
        example_basic_usage()
        example_conversation_logging()
        example_user_preference()
        
        print("\n✨ All examples completed!")
        print("\nFor more information, see MEMORY_INTEGRATION.md")
        
    except KeyboardInterrupt:
        print("\n\nExamples interrupted by user.")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
