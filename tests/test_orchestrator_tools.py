#!/usr/bin/env python3
"""
Test suite for GLaDOS Orchestrator tool endpoints

Tests the refactored orchestrator's tool API endpoints
"""

import sys
import json
import asyncio
from datetime import datetime

# Add the service directory to path
sys.path.insert(0, '/home/runner/work/HAssistant/HAssistant/services/glados-orchestrator')

from main import app, list_tools, get_time, letta_query, LettaQueryRequest
from fastapi.testclient import TestClient

client = TestClient(app)


def test_root_endpoint():
    """Test the root endpoint returns service info"""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["service"] == "GLaDOS Orchestrator"
    assert data["version"] == "2.0.0"
    assert data["mode"] == "tool-provider"
    assert "endpoints" in data
    print("✓ Root endpoint test passed")


def test_health_check():
    """Test the health check endpoint"""
    response = client.get("/healthz")
    assert response.status_code == 200
    data = response.json()
    assert data["service"] == "glados-orchestrator"
    assert data["version"] == "2.0.0"
    assert data["mode"] == "tool-provider"
    assert "tools_available" in data
    print("✓ Health check test passed")


def test_list_tools():
    """Test the tool list endpoint"""
    response = client.get("/tool/list")
    assert response.status_code == 200
    data = response.json()
    assert "tools" in data
    assert len(data["tools"]) >= 3  # At least 3 tools defined
    
    # Verify tool structure
    tool_names = [tool["function"]["name"] for tool in data["tools"]]
    assert "get_time" in tool_names
    assert "letta_query" in tool_names
    assert "execute_ha_skill" in tool_names
    print("✓ List tools test passed")


def test_get_time_tool():
    """Test the get_time tool endpoint"""
    response = client.get("/tool/get_time")
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "data" in data
    assert "datetime" in data["data"]
    assert "formatted" in data["data"]
    assert "day_of_week" in data["data"]
    
    # Verify datetime is recent
    result_date = datetime.fromisoformat(data["data"]["datetime"])
    now = datetime.now()
    time_diff = abs((now - result_date).total_seconds())
    assert time_diff < 5  # Should be within 5 seconds
    print("✓ Get time tool test passed")


def test_letta_query_tool():
    """Test the letta_query tool endpoint (may fail if Letta Bridge is not running)"""
    response = client.post(
        "/tool/letta_query",
        json={"query": "test query", "limit": 5}
    )
    assert response.status_code == 200
    data = response.json()
    
    # Should return success even if no memories found
    if data.get("success"):
        assert "data" in data
        assert "query" in data["data"]
        assert "count" in data["data"]
        assert "memories" in data["data"]
        print("✓ Letta query tool test passed")
    else:
        # Acceptable if Letta Bridge is not available
        assert "error" in data
        print("⚠ Letta query tool test skipped (Letta Bridge not available)")


def test_execute_ha_skill_tool():
    """Test the execute_ha_skill tool endpoint"""
    response = client.post(
        "/tool/execute_ha_skill",
        json={"skill_name": "test_skill", "parameters": {"param1": "value1"}}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "data" in data
    assert data["data"]["skill_name"] == "test_skill"
    print("✓ Execute HA skill tool test passed")


def test_tool_definitions_format():
    """Test that tool definitions match Ollama function calling format"""
    response = client.get("/tool/list")
    data = response.json()
    tools = data["tools"]
    
    for tool in tools:
        # Each tool should have type and function
        assert tool["type"] == "function"
        assert "function" in tool
        
        func = tool["function"]
        # Function should have name, description, and parameters
        assert "name" in func
        assert "description" in func
        assert "parameters" in func
        
        params = func["parameters"]
        # Parameters should follow JSON Schema
        assert params["type"] == "object"
        assert "properties" in params
        
    print("✓ Tool definitions format test passed")


def run_all_tests():
    """Run all tests"""
    print("\n" + "="*60)
    print("Testing GLaDOS Orchestrator Tool Endpoints")
    print("="*60 + "\n")
    
    test_root_endpoint()
    test_health_check()
    test_list_tools()
    test_get_time_tool()
    test_letta_query_tool()
    test_execute_ha_skill_tool()
    test_tool_definitions_format()
    
    print("\n" + "="*60)
    print("All tests completed successfully!")
    print("="*60 + "\n")


if __name__ == "__main__":
    run_all_tests()
