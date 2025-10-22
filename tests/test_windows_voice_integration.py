#!/usr/bin/env python3
"""
Tests for Computer Control Agent + Windows Voice Control Integration
"""

import unittest
import sys
import os
from unittest.mock import Mock, patch, MagicMock

# Add clients directory to path
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'clients'))

# Mock dependencies before imports
mock_pyautogui = MagicMock()
mock_pyautogui.FAILSAFE = True
mock_pyautogui.PAUSE = 0.5
sys.modules['pyautogui'] = mock_pyautogui

sys.modules['pytesseract'] = MagicMock()
sys.modules['cv2'] = MagicMock()

# Mock numpy
mock_np = MagicMock()
sys.modules['numpy'] = mock_np
sys.modules['np'] = mock_np

# Mock PIL
sys.modules['PIL'] = MagicMock()
sys.modules['PIL.Image'] = MagicMock()

# Mock requests
sys.modules['requests'] = MagicMock()

from computer_control_agent import ComputerControlAgent


class TestWindowsVoiceIntegration(unittest.TestCase):
    """Test suite for Windows Voice Control integration"""

    def setUp(self):
        """Set up test fixtures"""
        # Force disable confirmation for all tests
        import computer_control_agent
        computer_control_agent.CONFIRM_BEFORE_ACTION = False
        
        os.environ['CONFIRM_BEFORE_ACTION'] = 'false'
        os.environ['MAX_ACTIONS_PER_TASK'] = '10'
        os.environ['USE_WINDOWS_VOICE'] = 'false'
        
    def tearDown(self):
        """Clean up after tests"""
        if 'USE_WINDOWS_VOICE' in os.environ:
            del os.environ['USE_WINDOWS_VOICE']
    
    def test_agent_initialization_direct_mode(self):
        """Test agent initializes in direct control mode"""
        agent = ComputerControlAgent(use_windows_voice=False)
        self.assertFalse(agent.use_windows_voice)
        self.assertIsNone(agent.windows_voice_bridge)
    
    @unittest.skip("Requires complex mock setup")
    @patch('computer_control_agent.speak_command')
    @patch('computer_control_agent.type_text')
    @patch('computer_control_agent.send_keystroke')
    @patch('computer_control_agent.open_application')
    def test_agent_initialization_windows_voice_mode(self, mock_open, mock_key, mock_type, mock_speak):
        """Test agent initializes in Windows Voice mode"""
        # Mock the imports
        with patch.dict('sys.modules', {
            'windows_voice_control': MagicMock(
                speak_command=mock_speak,
                type_text=mock_type,
                send_keystroke=mock_key,
                open_application=mock_open
            )
        }):
            agent = ComputerControlAgent(use_windows_voice=True)
            self.assertTrue(agent.use_windows_voice)
            self.assertIsNotNone(agent.windows_voice_bridge)
    
    def test_windows_voice_env_variable(self):
        """Test USE_WINDOWS_VOICE environment variable"""
        os.environ['USE_WINDOWS_VOICE'] = 'true'
        
        # Reload module to pick up env var
        import importlib
        import computer_control_agent
        importlib.reload(computer_control_agent)
        
        self.assertTrue(computer_control_agent.USE_WINDOWS_VOICE)
    
    def test_execute_action_via_windows_voice_type(self):
        """Test typing action via Windows Voice"""
        mock_type_text = Mock(return_value=True)
        
        agent = ComputerControlAgent(use_windows_voice=False)
        agent.use_windows_voice = True
        agent.windows_voice_bridge = {
            'type_text': mock_type_text,
            'send_keystroke': Mock(),
            'speak_command': Mock(),
            'open_application': Mock()
        }
        
        action = {
            "type": "type",
            "params": {"text": "Hello World"},
            "description": "Test typing"
        }
        
        result = agent.execute_action_via_windows_voice(action)
        
        self.assertTrue(result)
        mock_type_text.assert_called_once_with("Hello World")
    
    def test_execute_action_via_windows_voice_keystroke(self):
        """Test keystroke action via Windows Voice"""
        mock_send_keystroke = Mock(return_value=True)
        
        agent = ComputerControlAgent(use_windows_voice=False)
        agent.use_windows_voice = True
        agent.windows_voice_bridge = {
            'type_text': Mock(),
            'send_keystroke': mock_send_keystroke,
            'speak_command': Mock(),
            'open_application': Mock()
        }
        
        action = {
            "type": "press",
            "params": {"key": "Enter"},
            "description": "Press Enter"
        }
        
        result = agent.execute_action_via_windows_voice(action)
        
        self.assertTrue(result)
        mock_send_keystroke.assert_called_once_with("Enter")
    
    def test_execute_action_via_windows_voice_hotkey(self):
        """Test hotkey action via Windows Voice"""
        mock_speak_command = Mock(return_value=True)
        
        agent = ComputerControlAgent(use_windows_voice=False)
        agent.use_windows_voice = True
        agent.windows_voice_bridge = {
            'type_text': Mock(),
            'send_keystroke': Mock(),
            'speak_command': mock_speak_command,
            'open_application': Mock()
        }
        
        action = {
            "type": "hotkey",
            "params": {"keys": ["ctrl", "c"]},
            "description": "Copy"
        }
        
        result = agent.execute_action_via_windows_voice(action)
        
        self.assertTrue(result)
        mock_speak_command.assert_called_once_with("Press ctrl c")
    
    def test_execute_action_via_windows_voice_scroll(self):
        """Test scroll action via Windows Voice"""
        mock_speak_command = Mock(return_value=True)
        
        agent = ComputerControlAgent(use_windows_voice=False)
        agent.use_windows_voice = True
        agent.windows_voice_bridge = {
            'type_text': Mock(),
            'send_keystroke': Mock(),
            'speak_command': mock_speak_command,
            'open_application': Mock()
        }
        
        # Test scroll up
        action = {
            "type": "scroll",
            "params": {"amount": 100},
            "description": "Scroll up"
        }
        
        result = agent.execute_action_via_windows_voice(action)
        
        self.assertTrue(result)
        mock_speak_command.assert_called_with("Scroll up")
        
        # Test scroll down
        action["params"]["amount"] = -100
        agent.execute_action_via_windows_voice(action)
        mock_speak_command.assert_called_with("Scroll down")
    
    def test_execute_action_via_windows_voice_wait(self):
        """Test wait action via Windows Voice"""
        agent = ComputerControlAgent(use_windows_voice=False)
        agent.use_windows_voice = True
        agent.windows_voice_bridge = {
            'type_text': Mock(),
            'send_keystroke': Mock(),
            'speak_command': Mock(),
            'open_application': Mock()
        }
        
        action = {
            "type": "wait",
            "params": {"duration": 0.1},
            "description": "Wait"
        }
        
        import time
        start = time.time()
        result = agent.execute_action_via_windows_voice(action)
        elapsed = time.time() - start
        
        self.assertTrue(result)
        self.assertGreaterEqual(elapsed, 0.1)
    
    def test_execute_action_via_windows_voice_find_and_click(self):
        """Test find and click action via Windows Voice"""
        mock_speak_command = Mock(return_value=True)
        
        agent = ComputerControlAgent(use_windows_voice=False)
        agent.use_windows_voice = True
        agent.windows_voice_bridge = {
            'type_text': Mock(),
            'send_keystroke': Mock(),
            'speak_command': mock_speak_command,
            'open_application': Mock()
        }
        
        action = {
            "type": "find_and_click",
            "params": {"text": "Submit"},
            "description": "Click Submit button"
        }
        
        result = agent.execute_action_via_windows_voice(action)
        
        self.assertTrue(result)
        mock_speak_command.assert_called_once_with("Click Submit")
    
    def test_execute_action_routing(self):
        """Test that execute_action routes to Windows Voice when enabled"""
        mock_type_text = Mock(return_value=True)
        
        agent = ComputerControlAgent(use_windows_voice=False)
        agent.use_windows_voice = True
        agent.windows_voice_bridge = {
            'type_text': mock_type_text,
            'send_keystroke': Mock(),
            'speak_command': Mock(),
            'open_application': Mock()
        }
        
        action = {
            "type": "type",
            "params": {"text": "Test"},
            "description": "Type test"
        }
        
        result = agent.execute_action(action)
        
        self.assertTrue(result)
        mock_type_text.assert_called_once_with("Test")
        self.assertEqual(agent.action_count, 1)
    
    def test_execute_action_without_bridge(self):
        """Test error handling when bridge is not available"""
        agent = ComputerControlAgent(use_windows_voice=False)
        agent.use_windows_voice = True
        agent.windows_voice_bridge = None
        
        action = {
            "type": "type",
            "params": {"text": "Test"},
            "description": "Type test"
        }
        
        result = agent.execute_action_via_windows_voice(action)
        
        self.assertFalse(result)
    
    def test_click_action_without_text(self):
        """Test that click actions without text fail gracefully"""
        agent = ComputerControlAgent(use_windows_voice=False)
        agent.use_windows_voice = True
        agent.windows_voice_bridge = {
            'type_text': Mock(),
            'send_keystroke': Mock(),
            'speak_command': Mock(),
            'open_application': Mock()
        }
        
        action = {
            "type": "click",
            "params": {"x": 100, "y": 200},
            "description": "Click at coordinates"
        }
        
        result = agent.execute_action_via_windows_voice(action)
        
        self.assertFalse(result)
    
    def test_open_application_action(self):
        """Test opening application via Windows Voice"""
        mock_open_app = Mock(return_value=True)
        
        agent = ComputerControlAgent(use_windows_voice=False)
        agent.use_windows_voice = True
        agent.windows_voice_bridge = {
            'type_text': Mock(),
            'send_keystroke': Mock(),
            'speak_command': Mock(),
            'open_application': mock_open_app
        }
        
        action = {
            "type": "open_application",
            "params": {"name": "Notepad"},
            "description": "Open Notepad"
        }
        
        result = agent.execute_action_via_windows_voice(action)
        
        self.assertTrue(result)
        mock_open_app.assert_called_once_with("Notepad")


class TestHAIntegration(unittest.TestCase):
    """Test Home Assistant integration with Windows Voice mode"""
    
    @unittest.skip("Requires flask module")
    def test_ha_integration_respects_windows_voice_env(self):
        """Test that HA integration respects USE_WINDOWS_VOICE env var"""
        os.environ['USE_WINDOWS_VOICE'] = 'true'
        os.environ['CONFIRM_BEFORE_ACTION'] = 'false'
        
        # Reload modules to pick up env vars
        import importlib
        import ha_integration
        importlib.reload(ha_integration)
        
        # The agent should be initialized with Windows Voice mode
        self.assertTrue(ha_integration.agent.use_windows_voice)


if __name__ == '__main__':
    # Run tests
    unittest.main(verbosity=2)
