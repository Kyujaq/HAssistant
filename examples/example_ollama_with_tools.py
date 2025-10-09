#!/usr/bin/env python3
"""
Example: Using GLaDOS Orchestrator Tools with Ollama

This script demonstrates how to call Ollama with tool definitions
from the GLaDOS Orchestrator, enabling function calling capabilities.

Usage:
    python3 example_ollama_with_tools.py "What time is it?"
"""

import sys
import json
import requests
from typing import List, Dict, Any


# Configuration
OLLAMA_URL = "http://ollama-chat:11434"
ORCHESTRATOR_URL = "http://hassistant-glados-orchestrator:8082"
MODEL = "hermes3"


def get_tool_definitions() -> List[Dict[str, Any]]:
    """Fetch tool definitions from the Orchestrator"""
    response = requests.get(f"{ORCHESTRATOR_URL}/tool/list", timeout=5)
    response.raise_for_status()
    return response.json()["tools"]


def call_tool(tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Call a specific tool on the Orchestrator"""
    url = f"{ORCHESTRATOR_URL}/tool/{tool_name}"
    
    # get_time doesn't need arguments
    if tool_name == "get_time":
        response = requests.get(url, timeout=10)
    else:
        response = requests.post(url, json=arguments, timeout=10)
    
    response.raise_for_status()
    return response.json()


def chat_with_tools(user_message: str, model: str = MODEL) -> str:
    """
    Send a message to Ollama with tool support and handle any tool calls.
    
    Args:
        user_message: The user's question or message
        model: The Ollama model to use
        
    Returns:
        The final response from the LLM
    """
    # Get tool definitions
    tools = get_tool_definitions()
    
    print(f"🔧 Loaded {len(tools)} tools from Orchestrator")
    print(f"📝 User: {user_message}\n")
    
    # Initial chat request with tools
    messages = [{"role": "user", "content": user_message}]
    
    chat_payload = {
        "model": model,
        "messages": messages,
        "tools": tools,
        "stream": False
    }
    
    print(f"🤖 Calling Ollama ({model})...")
    response = requests.post(
        f"{OLLAMA_URL}/api/chat",
        json=chat_payload,
        timeout=30
    )
    response.raise_for_status()
    result = response.json()
    
    message = result.get("message", {})
    
    # Check if LLM wants to call tools
    if "tool_calls" in message:
        print(f"🛠️  LLM requested {len(message['tool_calls'])} tool call(s)\n")
        
        tool_messages = []
        
        # Execute each tool call
        for i, tool_call in enumerate(message["tool_calls"], 1):
            function_name = tool_call["function"]["name"]
            arguments = tool_call["function"].get("arguments", {})
            
            print(f"   {i}. Calling {function_name}")
            if arguments:
                print(f"      Arguments: {json.dumps(arguments, indent=6)}")
            
            # Call the tool
            tool_result = call_tool(function_name, arguments)
            
            print(f"      Result: {json.dumps(tool_result, indent=6)}\n")
            
            # Store tool result for next LLM call
            tool_messages.append({
                "role": "tool",
                "content": json.dumps(tool_result)
            })
        
        # Send tool results back to LLM for final response
        print("🤖 Sending tool results back to LLM for final response...")
        
        messages = [
            {"role": "user", "content": user_message},
            {"role": "assistant", "content": "", "tool_calls": message["tool_calls"]},
            *tool_messages
        ]
        
        chat_payload = {
            "model": model,
            "messages": messages,
            "stream": False
        }
        
        response = requests.post(
            f"{OLLAMA_URL}/api/chat",
            json=chat_payload,
            timeout=30
        )
        response.raise_for_status()
        result = response.json()
        message = result.get("message", {})
    
    # Return final response
    final_response = message.get("content", "")
    print(f"✨ GLaDOS: {final_response}\n")
    return final_response


def main():
    """Main function"""
    if len(sys.argv) < 2:
        print("Usage: python3 example_ollama_with_tools.py \"Your question here\"")
        print("\nExamples:")
        print("  python3 example_ollama_with_tools.py \"What time is it?\"")
        print("  python3 example_ollama_with_tools.py \"What do you remember about my preferences?\"")
        sys.exit(1)
    
    user_message = " ".join(sys.argv[1:])
    
    print("="*70)
    print("GLaDOS Orchestrator - Tool Calling Example")
    print("="*70 + "\n")
    
    try:
        response = chat_with_tools(user_message)
        print("="*70)
        print("Success! ✓")
        print("="*70)
        
    except requests.exceptions.ConnectionError as e:
        print(f"❌ Connection Error: {e}")
        print("\nMake sure services are running:")
        print("  - docker ps | grep ollama-chat")
        print("  - docker ps | grep orchestrator")
        sys.exit(1)
        
    except requests.exceptions.HTTPError as e:
        print(f"❌ HTTP Error: {e}")
        print(f"\nResponse: {e.response.text}")
        sys.exit(1)
        
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
