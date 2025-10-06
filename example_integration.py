#!/usr/bin/env python3
"""
Example: Computer Control Agent with Windows Voice Integration

This script demonstrates how to use the Computer Control Agent
with Windows Voice Control integration.

Note: This is a conceptual demonstration. To run actual commands:
- Install dependencies: pip install pyautogui pytesseract pillow opencv-python numpy
- For Windows Voice mode, setup hardware (USB audio + aux cable)
"""

import os
import time


def example_direct_control():
    """Example using direct control mode (PyAutoGUI)"""
    print("\n" + "="*60)
    print("Example 1: Direct Control Mode")
    print("="*60)
    
    print("\nCommand: python computer_control_agent.py --task 'Open notepad'")
    print("\nHow it works:")
    print("  1. Agent takes screenshot of your screen")
    print("  2. Ollama AI analyzes the screenshot")
    print("  3. AI generates actions: click, type, press keys, etc.")
    print("  4. PyAutoGUI executes actions directly on your computer")
    
    print("\n✅ Direct control provides pixel-perfect control")


def example_windows_voice_control():
    """Example using Windows Voice Control mode"""
    print("\n" + "="*60)
    print("Example 2: Windows Voice Control Mode")
    print("="*60)
    
    print("\nCommand: python computer_control_agent.py --windows-voice --task 'Open notepad'")
    print("\nHow it works:")
    print("  1. Agent takes screenshot (for AI analysis)")
    print("  2. Ollama AI analyzes the screenshot")
    print("  3. AI generates actions: type, press, open app, etc.")
    print("  4. Actions converted to Windows Voice commands")
    print("  5. Piper TTS speaks commands via USB audio dongle")
    print("  6. Windows laptop hears commands via aux cable")
    print("  7. Windows Voice Assistant executes the commands")
    
    print("\n✅ Windows Voice mode works without software on Windows!")


def example_hybrid_mode():
    """Example using both modes intelligently"""
    print("\n" + "="*60)
    print("Example 3: Hybrid Mode (Smart Mode Selection)")
    print("="*60)
    
    print("\nBest practices for choosing modes:")
    
    print("\n  Use Windows Voice Mode for:")
    print("    ✓ Typing text")
    print("    ✓ Opening applications")
    print("    ✓ Pressing keys (Enter, Tab, etc.)")
    print("    ✓ Remote Windows control")
    print("    ✓ When you can't install software")
    
    print("\n  Use Direct Control Mode for:")
    print("    ✓ Precise mouse clicks at coordinates")
    print("    ✓ Mouse movements")
    print("    ✓ Complex GUI interactions")
    print("    ✓ High-speed automation")
    print("    ✓ When running on the same machine")
    
    print("\n✅ Choose the right mode for your use case!")


def example_from_environment():
    """Example using environment variable configuration"""
    print("\n" + "="*60)
    print("Example 4: Configuration via Environment Variable")
    print("="*60)
    
    print("\nMethod 1: Set environment variable")
    print("  export USE_WINDOWS_VOICE=true")
    print("  python computer_control_agent.py --task 'your task'")
    
    print("\nMethod 2: Use command line flag")
    print("  python computer_control_agent.py --windows-voice --task 'your task'")
    
    print("\nMethod 3: Configure in .env file")
    print("  echo 'USE_WINDOWS_VOICE=true' >> computer_control_agent.env")
    print("  export $(cat computer_control_agent.env | xargs)")
    print("  python computer_control_agent.py --task 'your task'")
    
    print("\n✅ Multiple configuration options available")


def example_ai_task():
    """Example of AI-powered task with Windows Voice"""
    print("\n" + "="*60)
    print("Example 5: AI-Powered Task Workflow")
    print("="*60)
    
    print("\nTask: 'Create a budget spreadsheet in Excel'")
    print("\nAI workflow with Windows Voice mode:")
    print("  1. AI understands the high-level task")
    print("  2. AI breaks it down into steps:")
    print("     - Open Excel")
    print("     - Type 'Budget 2024' in A1")
    print("     - Type 'Category' in A2")
    print("     - Type 'Amount' in B2")
    print("     - Add sample data")
    print("  3. Each step converted to Windows Voice command")
    print("  4. Commands spoken via audio cable")
    print("  5. Windows executes via Voice Assistant")
    
    print("\n✅ AI + Vision + Voice = Powerful automation!")


def example_home_assistant():
    """Example of Home Assistant integration"""
    print("\n" + "="*60)
    print("Example 6: Home Assistant Integration")
    print("="*60)
    
    print("\nSay to GLaDOS: 'Computer, create a spreadsheet'")
    print("\nFlow:")
    print("  1. GLaDOS (Home Assistant) hears your command")
    print("  2. HA triggers computer control webhook")
    print("  3. Computer Control Agent (in Windows Voice mode)")
    print("  4. Generates actions and speaks them")
    print("  5. Windows laptop executes via Voice Assistant")
    
    print("\nConfiguration in configuration.yaml:")
    print("""
rest_command:
  computer_control:
    url: "http://localhost:5555/webhook/task"
    method: POST
    payload: >
      {
        "secret": "your-secret",
        "task": "{{ task }}"
      }

automation:
  - alias: "AI Computer Control"
    trigger:
      platform: conversation
      command: ["computer [action]"]
    action:
      - service: rest_command.computer_control
        data:
          task: "{{ trigger.command }}"
""")
    
    print("✅ Voice → AI → Computer automation complete!")


def main():
    """Run all examples"""
    print("\n" + "="*70)
    print(" Computer Control Agent + Windows Voice Integration Examples")
    print("="*70)
    
    try:
        example_direct_control()
        time.sleep(0.5)
        
        example_windows_voice_control()
        time.sleep(0.5)
        
        example_hybrid_mode()
        time.sleep(0.5)
        
        example_from_environment()
        time.sleep(0.5)
        
        example_ai_task()
        time.sleep(0.5)
        
        example_home_assistant()
        
        print("\n" + "="*70)
        print("✅ All examples completed!")
        print("="*70)
        
        print("\nNext steps:")
        print("  1. Read: COMPUTER_CONTROL_WINDOWS_VOICE_INTEGRATION.md")
        print("  2. Setup hardware: USB audio dongle + aux cable")
        print("  3. Configure: computer_control_agent.env")
        print("  4. Test: python computer_control_agent.py --windows-voice --task 'Open Notepad'")
        print("  5. Integrate with Home Assistant for voice control")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")


if __name__ == "__main__":
    main()
