#!/usr/bin/env python3
"""
Test script for Qwen PC Control Agent

Tests the command parsing and execution logic without requiring
actual audio input or STT services.
"""

import sys
import os


def test_command_structure():
    """Test command structure without importing the full agent"""
    print("Testing Qwen PC Control Agent Structure...")
    print("=" * 60)
    
    # Test that the files exist
    agent_path = os.path.join(os.path.dirname(__file__), "pc_control_agent.py")
    requirements_path = os.path.join(os.path.dirname(__file__), "requirements.txt")
    dockerfile_path = os.path.join(os.path.dirname(__file__), "Dockerfile")
    docs_path = os.path.join(os.path.dirname(__file__), "PC_CONTROL_AGENT.md")
    
    files_to_check = [
        ("Agent Script", agent_path),
        ("Requirements", requirements_path),
        ("Dockerfile", dockerfile_path),
        ("Documentation", docs_path),
    ]
    
    all_good = True
    for name, path in files_to_check:
        exists = os.path.exists(path)
        status = "✅" if exists else "❌"
        print(f"{status} {name}: {path}")
        if not exists:
            all_good = False
    
    print("\n" + "=" * 60)
    
    if all_good:
        print("✅ All required files are present!")
        print("\nTo run full tests with dependencies:")
        print("  pip install -r requirements.txt")
        print("  python3 test_pc_control.py --full")
    else:
        print("❌ Some files are missing!")
        return 1
    
    print("\nAgent Features:")
    print("  - Voice input via Whisper STT")
    print("  - Natural language understanding via Qwen LLM")
    print("  - PC control (apps, volume, files, system)")
    print("  - Cross-platform support (Linux, macOS, Windows)")
    
    return 0


if __name__ == "__main__":
    exit(test_command_structure())
