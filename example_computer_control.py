#!/usr/bin/env python3
"""
Example usage of Computer Control Agent
Demonstrates various capabilities
"""

import sys
import os

# Add parent directory to path to import the agent
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from computer_control_agent import ComputerControlAgent

def example_screen_info():
    """Example: Get information about current screen"""
    print("\n=== Example 1: Get Screen Info ===")
    agent = ComputerControlAgent()
    info = agent.get_screen_info()
    print(f"Resolution: {info['resolution']}")
    print(f"Text found: {info['text_length']} characters")
    print(f"Preview: {info['text_preview'][:100]}...")

def example_simple_actions():
    """Example: Execute simple actions"""
    print("\n=== Example 2: Simple Actions ===")
    agent = ComputerControlAgent()
    
    # Example action sequence
    actions = [
        {
            "type": "move",
            "params": {"x": 500, "y": 500, "duration": 1.0},
            "description": "Move mouse to center"
        },
        {
            "type": "wait",
            "params": {"duration": 1.0},
            "description": "Wait 1 second"
        }
    ]
    
    print("Executing sample actions (move mouse, wait)...")
    for action in actions:
        success = agent.execute_action(action)
        print(f"  {action['description']}: {'✓' if success else '✗'}")

def example_find_text():
    """Example: Find text on screen"""
    print("\n=== Example 3: Find Text ===")
    agent = ComputerControlAgent()
    
    # Try to find common text
    search_terms = ["File", "Edit", "View", "Chrome", "Firefox"]
    
    for term in search_terms:
        coords = agent.find_text_on_screen(term)
        if coords:
            print(f"  Found '{term}' at {coords}")
            break
    else:
        print("  No common menu items found on screen")

def example_excel_task():
    """Example: Excel automation"""
    print("\n=== Example 4: Excel Task ===")
    print("NOTE: This requires Excel to be open!")
    print("Task: Would create a simple spreadsheet with headers")
    
    # Uncomment to actually run:
    # agent = ComputerControlAgent()
    # success = agent.control_excel(
    #     task="Create a table with headers: Name, Age, Email"
    # )
    # print(f"Excel task: {'Success' if success else 'Failed'}")

def example_custom_task():
    """Example: Custom task with context"""
    print("\n=== Example 5: Custom Task ===")
    print("Example task: Open calculator (disabled in demo)")
    
    # Uncomment to actually run:
    # agent = ComputerControlAgent()
    # success = agent.run_task(
    #     task="Open calculator application",
    #     context="Windows 10 desktop environment"
    # )
    # print(f"Task result: {'Success' if success else 'Failed'}")

def example_safe_mode():
    """Example: Safe mode with confirmations"""
    print("\n=== Example 6: Safe Mode ===")
    print("When CONFIRM_BEFORE_ACTION=true, agent asks before each action")
    print("Set in environment or computer_control_agent.env file")

def main():
    """Run all examples"""
    print("=" * 60)
    print("Computer Control Agent - Example Usage")
    print("=" * 60)
    
    print("\nThese examples demonstrate the agent's capabilities.")
    print("Some examples are disabled by default for safety.")
    print("Uncomment code to enable actual execution.\n")
    
    try:
        # Safe examples that won't affect the system
        example_screen_info()
        example_simple_actions()
        example_find_text()
        
        # Informational examples (no actual execution)
        example_safe_mode()
        example_excel_task()
        example_custom_task()
        
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "=" * 60)
    print("Examples completed!")
    print("=" * 60)

if __name__ == "__main__":
    main()
