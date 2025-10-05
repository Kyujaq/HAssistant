#!/usr/bin/env python3
"""
Computer Control Agent for HAssistant
Uses vision-gateway to get screenshots and controls another computer via mouse/keyboard.
Can work with applications like Excel, browsers, and other GUI applications.
"""

import os
import sys
import time
import logging
import requests
import json
import base64
from typing import Dict, Any, List, Optional, Tuple
from io import BytesIO

# Computer control libraries
try:
    import pyautogui
    import pytesseract
    from PIL import Image
    import numpy as np
    import cv2
except ImportError:
    print("Missing dependencies. Install with:")
    print("pip install pyautogui pytesseract pillow opencv-python numpy")
    sys.exit(1)

# Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger('computer_control_agent')

# Configuration from environment
VISION_GATEWAY_URL = os.getenv('VISION_GATEWAY_URL', 'http://localhost:8088')
HA_URL = os.getenv('HA_URL', 'http://localhost:8123')
HA_TOKEN = os.getenv('HA_TOKEN', '')
OLLAMA_URL = os.getenv('OLLAMA_URL', 'http://localhost:11434')
OLLAMA_MODEL = os.getenv('OLLAMA_MODEL', 'qwen3:4b-instruct-2507-q4_K_M')

# Execution mode - can use Windows Voice Control instead of direct PyAutoGUI
USE_WINDOWS_VOICE = os.getenv('USE_WINDOWS_VOICE', 'false').lower() == 'true'

# Safety settings
CONFIRM_BEFORE_ACTION = os.getenv('CONFIRM_BEFORE_ACTION', 'true').lower() == 'true'
MAX_ACTIONS_PER_TASK = int(os.getenv('MAX_ACTIONS_PER_TASK', '50'))

# PyAutoGUI safety settings
pyautogui.FAILSAFE = True  # Move mouse to corner to abort
pyautogui.PAUSE = 0.5  # Pause between actions for safety


class ComputerControlAgent:
    """Agent that can control a computer using vision and AI"""

    def __init__(self, use_windows_voice=None):
        self.action_count = 0
        self.task_history = []
        
        # Use parameter if provided, otherwise use environment variable
        if use_windows_voice is None:
            use_windows_voice = USE_WINDOWS_VOICE
        
        self.use_windows_voice = use_windows_voice
        self.windows_voice_bridge = None
        
        if use_windows_voice:
            try:
                from windows_voice_control import speak_command, type_text, send_keystroke, open_application
                self.windows_voice_bridge = {
                    'speak_command': speak_command,
                    'type_text': type_text,
                    'send_keystroke': send_keystroke,
                    'open_application': open_application
                }
                logger.info("🤖 Computer Control Agent initialized (Windows Voice Mode)")
                logger.info("   Using Windows Voice Assistant for command execution")
            except ImportError:
                logger.warning("Windows voice control not available, falling back to direct control")
                self.use_windows_voice = False
        
        if not use_windows_voice:
            logger.info("🤖 Computer Control Agent initialized (Direct Control Mode)")
            logger.info(f"   Vision Gateway: {VISION_GATEWAY_URL}")
            logger.info(f"   Ollama: {OLLAMA_URL}")
        
        logger.info(f"   Safety: Confirm={CONFIRM_BEFORE_ACTION}, Max Actions={MAX_ACTIONS_PER_TASK}")

    def get_screenshot(self, source: str = "local") -> Optional[np.ndarray]:
        """
        Get screenshot from vision-gateway or local screen
        
        Args:
            source: 'local' for local screen, or vision-gateway source name
            
        Returns:
            Screenshot as numpy array (BGR format) or None
        """
        try:
            if source == "local":
                # Take local screenshot
                screenshot = pyautogui.screenshot()
                # Convert PIL to OpenCV format (RGB to BGR)
                return cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)
            else:
                # Fetch from vision-gateway
                # Note: vision-gateway needs to expose an endpoint to get latest frame
                response = requests.get(f"{VISION_GATEWAY_URL}/api/latest_frame/{source}", timeout=5)
                if response.status_code == 200:
                    data = response.json()
                    if 'image' in data:
                        img_bytes = base64.b64decode(data['image'])
                        nparr = np.frombuffer(img_bytes, np.uint8)
                        return cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                logger.warning(f"Failed to get screenshot from vision-gateway: {response.status_code}")
                return None
        except Exception as e:
            logger.error(f"Error getting screenshot: {e}")
            return None

    def ocr_screenshot(self, image: np.ndarray) -> str:
        """
        Extract text from screenshot using OCR
        
        Args:
            image: Screenshot as numpy array
            
        Returns:
            Extracted text
        """
        try:
            # Convert BGR to RGB for PIL
            pil_image = Image.fromarray(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))
            text = pytesseract.image_to_string(pil_image)
            return text.strip()
        except Exception as e:
            logger.error(f"OCR error: {e}")
            return ""

    def find_text_on_screen(self, text: str, image: Optional[np.ndarray] = None) -> Optional[Tuple[int, int]]:
        """
        Find text on screen and return its center coordinates
        
        Args:
            text: Text to find
            image: Optional screenshot to search in (otherwise takes new one)
            
        Returns:
            (x, y) coordinates of text center, or None if not found
        """
        try:
            if image is None:
                image = self.get_screenshot("local")
            
            if image is None:
                return None
            
            # Convert to PIL for pytesseract
            pil_image = Image.fromarray(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))
            
            # Get bounding boxes
            data = pytesseract.image_to_data(pil_image, output_type=pytesseract.Output.DICT)
            
            # Search for text
            text_lower = text.lower()
            for i, word in enumerate(data['text']):
                if word.lower().strip() == text_lower:
                    x = data['left'][i] + data['width'][i] // 2
                    y = data['top'][i] + data['height'][i] // 2
                    return (x, y)
            
            return None
        except Exception as e:
            logger.error(f"Error finding text: {e}")
            return None

    def ask_llm(self, prompt: str, image_b64: Optional[str] = None) -> str:
        """
        Ask Ollama LLM for guidance
        
        Args:
            prompt: Question or instruction
            image_b64: Optional base64-encoded image
            
        Returns:
            LLM response
        """
        try:
            payload = {
                "model": OLLAMA_MODEL,
                "prompt": prompt,
                "stream": False
            }
            
            if image_b64:
                payload["images"] = [image_b64]
            
            response = requests.post(
                f"{OLLAMA_URL}/api/generate",
                json=payload,
                timeout=30
            )
            
            if response.status_code == 200:
                return response.json().get('response', '').strip()
            else:
                logger.error(f"LLM request failed: {response.status_code}")
                return ""
        except Exception as e:
            logger.error(f"Error asking LLM: {e}")
            return ""

    def execute_action_via_windows_voice(self, action: Dict[str, Any]) -> bool:
        """
        Execute action using Windows Voice Control
        
        Args:
            action: Action dictionary with 'type' and parameters
            
        Returns:
            True if successful
        """
        if not self.windows_voice_bridge:
            logger.error("Windows Voice Control not available")
            return False
        
        action_type = action.get('type', '')
        params = action.get('params', {})
        
        try:
            if action_type == 'type':
                # Use Windows voice "Type text" command
                return self.windows_voice_bridge['type_text'](params['text'])
                
            elif action_type == 'press':
                # Use Windows voice "Press key" command
                return self.windows_voice_bridge['send_keystroke'](params['key'])
                
            elif action_type == 'hotkey':
                # Convert hotkey to Windows voice command
                keys = params['keys']
                # For common hotkeys like Ctrl+C, use Windows voice format
                if len(keys) == 2:
                    return self.windows_voice_bridge['speak_command'](f"Press {keys[0]} {keys[1]}")
                else:
                    return self.windows_voice_bridge['speak_command'](f"Press {' '.join(keys)}")
                    
            elif action_type == 'open_application':
                # Use Windows voice "Open app" command
                return self.windows_voice_bridge['open_application'](params.get('name', ''))
                
            elif action_type in ['click', 'double_click', 'right_click', 'move']:
                # Windows Voice Access supports click by number/label
                # This is more complex, use a generic command
                logger.warning(f"Action type '{action_type}' requires Windows Voice Access numbers mode")
                # Try to find text at location and click
                if 'text' in params:
                    return self.windows_voice_bridge['speak_command'](f"Click {params['text']}")
                else:
                    # Can't directly click coordinates via voice
                    logger.error("Cannot execute click action via Windows voice without text label")
                    return False
                    
            elif action_type == 'scroll':
                # Windows voice scroll command
                amount = params['amount']
                direction = "up" if amount > 0 else "down"
                return self.windows_voice_bridge['speak_command'](f"Scroll {direction}")
                
            elif action_type == 'wait':
                # Just wait locally
                import time
                time.sleep(params['duration'])
                return True
                
            elif action_type == 'find_and_click':
                # Use Windows voice to click by text
                text = params['text']
                return self.windows_voice_bridge['speak_command'](f"Click {text}")
                
            else:
                # Try to send as generic voice command
                logger.warning(f"Unknown action type '{action_type}', trying generic voice command")
                command_str = f"{action_type} {' '.join(str(v) for v in params.values())}"
                return self.windows_voice_bridge['speak_command'](command_str)
                
        except Exception as e:
            logger.error(f"Error executing action via Windows voice: {e}")
            return False

    def execute_action(self, action: Dict[str, Any]) -> bool:
        """
        Execute a single action
        
        Args:
            action: Action dictionary with 'type' and parameters
            
        Returns:
            True if successful
        """
        if self.action_count >= MAX_ACTIONS_PER_TASK:
            logger.warning(f"Max actions ({MAX_ACTIONS_PER_TASK}) reached, stopping")
            return False
        
        action_type = action.get('type', '')
        logger.info(f"Executing action: {action_type}")
        
        if CONFIRM_BEFORE_ACTION:
            confirm = input(f"Execute {action_type} with params {action.get('params', {})}? (y/n): ")
            if confirm.lower() != 'y':
                logger.info("Action cancelled by user")
                return False
        
        # Route to Windows Voice Control if enabled
        if self.use_windows_voice:
            success = self.execute_action_via_windows_voice(action)
            if success:
                self.action_count += 1
                self.task_history.append(action)
            return success
        
        # Otherwise use direct control
        try:
            if action_type == 'click':
                x, y = action['params']['x'], action['params']['y']
                clicks = action['params'].get('clicks', 1)
                button = action['params'].get('button', 'left')
                pyautogui.click(x, y, clicks=clicks, button=button)
                
            elif action_type == 'double_click':
                x, y = action['params']['x'], action['params']['y']
                pyautogui.doubleClick(x, y)
                
            elif action_type == 'right_click':
                x, y = action['params']['x'], action['params']['y']
                pyautogui.rightClick(x, y)
                
            elif action_type == 'move':
                x, y = action['params']['x'], action['params']['y']
                duration = action['params'].get('duration', 0.5)
                pyautogui.moveTo(x, y, duration=duration)
                
            elif action_type == 'type':
                text = action['params']['text']
                interval = action['params'].get('interval', 0.05)
                pyautogui.write(text, interval=interval)
                
            elif action_type == 'press':
                key = action['params']['key']
                pyautogui.press(key)
                
            elif action_type == 'hotkey':
                keys = action['params']['keys']
                pyautogui.hotkey(*keys)
                
            elif action_type == 'scroll':
                amount = action['params']['amount']
                pyautogui.scroll(amount)
                
            elif action_type == 'wait':
                duration = action['params']['duration']
                time.sleep(duration)
                
            elif action_type == 'find_and_click':
                text = action['params']['text']
                coords = self.find_text_on_screen(text)
                if coords:
                    pyautogui.click(*coords)
                else:
                    logger.warning(f"Could not find text '{text}' on screen")
                    return False
                    
            else:
                logger.error(f"Unknown action type: {action_type}")
                return False
            
            self.action_count += 1
            self.task_history.append(action)
            return True
            
        except Exception as e:
            logger.error(f"Error executing action: {e}")
            return False

    def control_excel(self, task: str) -> bool:
        """
        Control Excel application with specific task
        
        Args:
            task: Natural language description of task
            
        Returns:
            True if successful
        """
        logger.info(f"Excel task: {task}")
        
        # Get current screenshot
        screenshot = self.get_screenshot("local")
        if screenshot is None:
            logger.error("Failed to get screenshot")
            return False
        
        # Convert to base64 for LLM
        _, buffer = cv2.imencode('.jpg', screenshot)
        img_b64 = base64.b64encode(buffer).decode('utf-8')
        
        # Ask LLM for action plan
        prompt = f"""You are controlling Excel on a Windows/Mac computer.
Task: {task}

Current screen shows the Excel application.
Provide a step-by-step action plan to complete this task.

Return your response as a JSON array of actions. Each action should have:
- "type": one of [click, double_click, type, press, hotkey, scroll, wait, find_and_click]
- "params": parameters for the action (x, y for clicks, text for typing, key for press, keys array for hotkey, etc.)
- "description": what this action does

Example:
[
  {{"type": "find_and_click", "params": {{"text": "File"}}, "description": "Open File menu"}},
  {{"type": "wait", "params": {{"duration": 0.5}}, "description": "Wait for menu"}},
  {{"type": "type", "params": {{"text": "Hello"}}, "description": "Type text"}}
]

Return ONLY the JSON array, no other text."""

        response = self.ask_llm(prompt, img_b64)
        
        if not response:
            logger.error("No response from LLM")
            return False
        
        # Parse action plan
        try:
            # Extract JSON from response
            import re
            json_match = re.search(r'\[.*\]', response, re.DOTALL)
            if json_match:
                actions = json.loads(json_match.group(0))
            else:
                logger.error("Could not find JSON in LLM response")
                return False
            
            # Execute actions
            logger.info(f"Executing {len(actions)} actions")
            for i, action in enumerate(actions):
                logger.info(f"Step {i+1}/{len(actions)}: {action.get('description', '')}")
                if not self.execute_action(action):
                    logger.error(f"Failed at step {i+1}")
                    return False
                
                # Take screenshot after each action for feedback
                time.sleep(0.5)
            
            logger.info("Task completed successfully")
            return True
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse action plan: {e}")
            logger.debug(f"Response was: {response}")
            return False

    def run_task(self, task: str, context: Optional[str] = None) -> bool:
        """
        Run a general computer control task
        
        Args:
            task: Natural language description of task
            context: Optional context about the application or environment
            
        Returns:
            True if successful
        """
        logger.info(f"Running task: {task}")
        if context:
            logger.info(f"Context: {context}")
        
        self.action_count = 0
        self.task_history = []
        
        # Get current screenshot
        screenshot = self.get_screenshot("local")
        if screenshot is None:
            logger.error("Failed to get screenshot")
            return False
        
        # OCR to understand what's on screen
        text_content = self.ocr_screenshot(screenshot)
        logger.info(f"Screen content preview: {text_content[:200]}...")
        
        # Convert screenshot to base64
        _, buffer = cv2.imencode('.jpg', screenshot)
        img_b64 = base64.b64encode(buffer).decode('utf-8')
        
        # Create prompt for LLM
        system_context = context or "You are controlling a computer desktop application."
        prompt = f"""{system_context}

Task: {task}

Current screen text content:
{text_content[:1000]}

Analyze the screenshot and provide a JSON array of actions to complete this task.
Each action should have:
- "type": action type (click, type, press, hotkey, scroll, wait, find_and_click, etc.)
- "params": action parameters
- "description": what this action does

Return ONLY the JSON array of actions, nothing else."""

        response = self.ask_llm(prompt, img_b64)
        
        if not response:
            logger.error("No response from LLM")
            return False
        
        # Parse and execute actions
        try:
            import re
            json_match = re.search(r'\[.*\]', response, re.DOTALL)
            if json_match:
                actions = json.loads(json_match.group(0))
            else:
                logger.error("Could not find JSON in LLM response")
                logger.debug(f"Response: {response}")
                return False
            
            # Execute actions
            logger.info(f"Executing {len(actions)} actions")
            for i, action in enumerate(actions):
                logger.info(f"Step {i+1}/{len(actions)}: {action.get('description', '')}")
                if not self.execute_action(action):
                    logger.warning(f"Action failed at step {i+1}, continuing...")
                time.sleep(0.5)
            
            logger.info("Task execution completed")
            return True
            
        except Exception as e:
            logger.error(f"Error executing task: {e}")
            return False

    def get_screen_info(self) -> Dict[str, Any]:
        """Get information about the current screen"""
        try:
            screenshot = self.get_screenshot("local")
            if screenshot is None:
                return {"error": "Failed to get screenshot"}
            
            text = self.ocr_screenshot(screenshot)
            
            return {
                "resolution": f"{screenshot.shape[1]}x{screenshot.shape[0]}",
                "text_preview": text[:500],
                "text_length": len(text)
            }
        except Exception as e:
            return {"error": str(e)}


def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Computer Control Agent')
    parser.add_argument('--task', type=str, help='Task to perform')
    parser.add_argument('--excel', action='store_true', help='Excel-specific task')
    parser.add_argument('--context', type=str, help='Context for the task')
    parser.add_argument('--info', action='store_true', help='Get screen information')
    parser.add_argument('--windows-voice', action='store_true', 
                        help='Use Windows Voice Control for command execution')
    
    args = parser.parse_args()
    
    agent = ComputerControlAgent(use_windows_voice=args.windows_voice)
    
    if args.info:
        info = agent.get_screen_info()
        print(json.dumps(info, indent=2))
    elif args.task:
        if args.excel:
            success = agent.control_excel(args.task)
        else:
            success = agent.run_task(args.task, args.context)
        
        sys.exit(0 if success else 1)
    else:
        print("No task specified. Use --task 'your task here'")
        print("Examples:")
        print("  python computer_control_agent.py --task 'Open notepad'")
        print("  python computer_control_agent.py --excel --task 'Create a new spreadsheet'")
        print("  python computer_control_agent.py --info")
        print("  python computer_control_agent.py --windows-voice --task 'Open notepad'")
        sys.exit(1)


if __name__ == "__main__":
    main()
