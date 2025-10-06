#!/usr/bin/env python3
"""
Basic tests for Computer Control Agent
Tests core functionality without requiring external dependencies
"""

import unittest
import sys
import os
from unittest.mock import Mock, patch, MagicMock
import numpy as np

# Add clients directory to path
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'clients'))

from computer_control_agent import ComputerControlAgent


class TestComputerControlAgent(unittest.TestCase):
    """Test suite for ComputerControlAgent"""

    def setUp(self):
        """Set up test fixtures"""
        # Mock environment variables
        os.environ['CONFIRM_BEFORE_ACTION'] = 'false'
        os.environ['MAX_ACTIONS_PER_TASK'] = '10'
        
    def test_agent_initialization(self):
        """Test agent initializes correctly"""
        agent = ComputerControlAgent()
        self.assertEqual(agent.action_count, 0)
        self.assertEqual(agent.task_history, [])
    
    @patch('computer_control_agent.pyautogui')
    @patch('computer_control_agent.cv2')
    @patch('computer_control_agent.np')
    def test_get_screenshot_local(self, mock_np, mock_cv2, mock_pyautogui):
        """Test local screenshot capture"""
        # Mock screenshot
        mock_img = Mock()
        mock_pyautogui.screenshot.return_value = mock_img
        mock_np.array.return_value = np.zeros((100, 100, 3), dtype=np.uint8)
        mock_cv2.cvtColor.return_value = np.zeros((100, 100, 3), dtype=np.uint8)
        
        agent = ComputerControlAgent()
        screenshot = agent.get_screenshot("local")
        
        self.assertIsNotNone(screenshot)
        mock_pyautogui.screenshot.assert_called_once()
    
    @patch('computer_control_agent.pyautogui')
    def test_execute_action_click(self, mock_pyautogui):
        """Test click action execution"""
        agent = ComputerControlAgent()
        
        action = {
            "type": "click",
            "params": {"x": 100, "y": 200},
            "description": "Test click"
        }
        
        result = agent.execute_action(action)
        
        self.assertTrue(result)
        mock_pyautogui.click.assert_called_once_with(100, 200, clicks=1, button='left')
        self.assertEqual(agent.action_count, 1)
    
    @patch('computer_control_agent.pyautogui')
    def test_execute_action_type(self, mock_pyautogui):
        """Test type action execution"""
        agent = ComputerControlAgent()
        
        action = {
            "type": "type",
            "params": {"text": "Hello World"},
            "description": "Test typing"
        }
        
        result = agent.execute_action(action)
        
        self.assertTrue(result)
        mock_pyautogui.write.assert_called_once_with("Hello World", interval=0.05)
        self.assertEqual(agent.action_count, 1)
    
    @patch('computer_control_agent.pyautogui')
    def test_execute_action_hotkey(self, mock_pyautogui):
        """Test hotkey action execution"""
        agent = ComputerControlAgent()
        
        action = {
            "type": "hotkey",
            "params": {"keys": ["ctrl", "c"]},
            "description": "Test hotkey"
        }
        
        result = agent.execute_action(action)
        
        self.assertTrue(result)
        mock_pyautogui.hotkey.assert_called_once_with("ctrl", "c")
    
    @patch('computer_control_agent.time.sleep')
    def test_execute_action_wait(self, mock_sleep):
        """Test wait action execution"""
        agent = ComputerControlAgent()
        
        action = {
            "type": "wait",
            "params": {"duration": 2.0},
            "description": "Test wait"
        }
        
        result = agent.execute_action(action)
        
        self.assertTrue(result)
        mock_sleep.assert_called_once_with(2.0)
    
    def test_execute_action_max_limit(self):
        """Test action limit enforcement"""
        agent = ComputerControlAgent()
        agent.action_count = 10  # Set to max
        
        action = {
            "type": "wait",
            "params": {"duration": 1.0},
            "description": "Test"
        }
        
        result = agent.execute_action(action)
        
        self.assertFalse(result)  # Should fail due to limit
    
    def test_execute_action_unknown_type(self):
        """Test handling of unknown action type"""
        agent = ComputerControlAgent()
        
        action = {
            "type": "unknown_action",
            "params": {},
            "description": "Test unknown"
        }
        
        result = agent.execute_action(action)
        
        self.assertFalse(result)
    
    @patch('computer_control_agent.pytesseract')
    @patch('computer_control_agent.Image')
    @patch('computer_control_agent.cv2')
    def test_ocr_screenshot(self, mock_cv2, mock_Image, mock_pytesseract):
        """Test OCR functionality"""
        mock_cv2.cvtColor.return_value = np.zeros((100, 100, 3), dtype=np.uint8)
        mock_pytesseract.image_to_string.return_value = "Sample text"
        
        agent = ComputerControlAgent()
        image = np.zeros((100, 100, 3), dtype=np.uint8)
        
        text = agent.ocr_screenshot(image)
        
        self.assertEqual(text, "Sample text")
    
    @patch('computer_control_agent.requests.post')
    def test_ask_llm(self, mock_post):
        """Test LLM interaction"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"response": "Test response"}
        mock_post.return_value = mock_response
        
        agent = ComputerControlAgent()
        response = agent.ask_llm("Test prompt")
        
        self.assertEqual(response, "Test response")
        mock_post.assert_called_once()
    
    @patch('computer_control_agent.pytesseract')
    @patch('computer_control_agent.Image')
    @patch('computer_control_agent.cv2')
    @patch('computer_control_agent.pyautogui')
    def test_find_text_on_screen(self, mock_pyautogui, mock_cv2, mock_Image, mock_pytesseract):
        """Test finding text on screen"""
        # Mock screenshot
        mock_pyautogui.screenshot.return_value = Mock()
        mock_cv2.cvtColor.return_value = np.zeros((100, 100, 3), dtype=np.uint8)
        
        # Mock OCR result
        mock_pytesseract.image_to_data.return_value = {
            'text': ['Hello', 'World', 'Test'],
            'left': [10, 50, 100],
            'top': [10, 10, 50],
            'width': [40, 50, 30],
            'height': [20, 20, 20]
        }
        
        agent = ComputerControlAgent()
        image = np.zeros((100, 100, 3), dtype=np.uint8)
        
        coords = agent.find_text_on_screen("World", image)
        
        self.assertIsNotNone(coords)
        self.assertEqual(coords, (75, 20))  # 50 + 50/2, 10 + 20/2
    
    @patch('computer_control_agent.pyautogui')
    @patch('computer_control_agent.cv2')
    @patch('computer_control_agent.np')
    def test_get_screen_info(self, mock_np, mock_cv2, mock_pyautogui):
        """Test getting screen information"""
        # Mock screenshot
        mock_pyautogui.screenshot.return_value = Mock()
        mock_np.array.return_value = np.zeros((1080, 1920, 3), dtype=np.uint8)
        mock_cv2.cvtColor.return_value = np.zeros((1080, 1920, 3), dtype=np.uint8)
        
        with patch.object(ComputerControlAgent, 'ocr_screenshot', return_value="Sample screen text"):
            agent = ComputerControlAgent()
            info = agent.get_screen_info()
            
            self.assertIn('resolution', info)
            self.assertIn('text_preview', info)
            self.assertEqual(info['text_preview'], 'Sample screen text')


class TestActionTypes(unittest.TestCase):
    """Test different action types"""
    
    def setUp(self):
        os.environ['CONFIRM_BEFORE_ACTION'] = 'false'
        os.environ['MAX_ACTIONS_PER_TASK'] = '10'
    
    @patch('computer_control_agent.pyautogui')
    def test_double_click(self, mock_pyautogui):
        """Test double click action"""
        agent = ComputerControlAgent()
        action = {"type": "double_click", "params": {"x": 100, "y": 100}}
        
        agent.execute_action(action)
        
        mock_pyautogui.doubleClick.assert_called_once_with(100, 100)
    
    @patch('computer_control_agent.pyautogui')
    def test_right_click(self, mock_pyautogui):
        """Test right click action"""
        agent = ComputerControlAgent()
        action = {"type": "right_click", "params": {"x": 100, "y": 100}}
        
        agent.execute_action(action)
        
        mock_pyautogui.rightClick.assert_called_once_with(100, 100)
    
    @patch('computer_control_agent.pyautogui')
    def test_move(self, mock_pyautogui):
        """Test mouse move action"""
        agent = ComputerControlAgent()
        action = {"type": "move", "params": {"x": 500, "y": 500, "duration": 1.0}}
        
        agent.execute_action(action)
        
        mock_pyautogui.moveTo.assert_called_once_with(500, 500, duration=1.0)
    
    @patch('computer_control_agent.pyautogui')
    def test_press(self, mock_pyautogui):
        """Test key press action"""
        agent = ComputerControlAgent()
        action = {"type": "press", "params": {"key": "enter"}}
        
        agent.execute_action(action)
        
        mock_pyautogui.press.assert_called_once_with("enter")
    
    @patch('computer_control_agent.pyautogui')
    def test_scroll(self, mock_pyautogui):
        """Test scroll action"""
        agent = ComputerControlAgent()
        action = {"type": "scroll", "params": {"amount": 100}}
        
        agent.execute_action(action)
        
        mock_pyautogui.scroll.assert_called_once_with(100)


if __name__ == '__main__':
    # Run tests
    unittest.main(verbosity=2)
