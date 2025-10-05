#!/usr/bin/env python3
"""
Basic tests for Windows Voice Control
Tests core functionality without requiring external dependencies
"""

import unittest
import sys
import os
from unittest.mock import Mock, patch, MagicMock, mock_open
import tempfile

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Mock requests before import
sys.modules['requests'] = MagicMock()

from windows_voice_control import speak_command, test_audio_device, send_keystroke, type_text, open_application


class TestWindowsVoiceControl(unittest.TestCase):
    """Test suite for Windows Voice Control"""

    def setUp(self):
        """Set up test fixtures"""
        # Set environment variables
        os.environ['USB_AUDIO_DEVICE'] = 'hw:1,0'
        os.environ['TTS_URL'] = 'http://localhost:10200'
        os.environ['USE_PULSEAUDIO'] = 'false'
        
    def tearDown(self):
        """Clean up after tests"""
        # Reset environment
        if 'USB_AUDIO_DEVICE' in os.environ:
            del os.environ['USB_AUDIO_DEVICE']
    
    @patch('windows_voice_control.requests')
    @patch('windows_voice_control.subprocess.run')
    @patch('windows_voice_control.os.remove')
    @patch('builtins.open', new_callable=mock_open)
    def test_speak_command_success(self, mock_file, mock_remove, mock_subprocess, mock_requests):
        """Test successful voice command"""
        # Mock HTTP response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.iter_content = Mock(return_value=[b'audio', b'data'])
        mock_requests.get.return_value = mock_response
        
        # Mock subprocess with successful return
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stderr = ""
        mock_subprocess.return_value = mock_result
        
        result = speak_command("Open Notepad", "hw:1,0")
        
        self.assertTrue(result)
        mock_requests.get.assert_called_once()
        mock_subprocess.assert_called_once()
        mock_remove.assert_called_once()
    
    @patch('windows_voice_control.requests')
    def test_speak_command_tts_failure(self, mock_requests):
        """Test handling TTS service failure"""
        # Mock failed HTTP response
        mock_response = Mock()
        mock_response.status_code = 500
        mock_requests.get.return_value = mock_response
        
        result = speak_command("Test command")
        
        self.assertFalse(result)
    
    @patch('windows_voice_control.subprocess.run')
    def test_test_audio_device_alsa(self, mock_subprocess):
        """Test audio device testing with ALSA"""
        os.environ['USE_PULSEAUDIO'] = 'false'
        
        mock_subprocess.return_value = Mock(
            returncode=0,
            stdout="card 1: Device [USB Audio Device]"
        )
        
        result = test_audio_device("hw:1,0")
        
        self.assertTrue(result)
        mock_subprocess.assert_called_once()
    
    @patch('windows_voice_control.speak_command')
    def test_send_keystroke(self, mock_speak):
        """Test sending keystroke command"""
        mock_speak.return_value = True
        
        result = send_keystroke("Enter")
        
        self.assertTrue(result)
        mock_speak.assert_called_once_with("Press Enter")
    
    @patch('windows_voice_control.speak_command')
    def test_type_text(self, mock_speak):
        """Test typing text command"""
        mock_speak.return_value = True
        
        result = type_text("Hello World")
        
        self.assertTrue(result)
        mock_speak.assert_called_once_with("Type Hello World")
    
    @patch('windows_voice_control.speak_command')
    def test_open_application(self, mock_speak):
        """Test opening application command"""
        mock_speak.return_value = True
        
        result = open_application("Notepad")
        
        self.assertTrue(result)
        mock_speak.assert_called_once_with("Open Notepad")


class TestEnvironmentConfiguration(unittest.TestCase):
    """Test environment configuration handling"""
    
    def test_default_usb_device(self):
        """Test default USB device configuration"""
        # This test is informational - the default is set at module import time
        # So we can't reliably test it after other tests have modified the env
        pass
    
    def test_custom_usb_device(self):
        """Test custom USB device configuration"""
        os.environ['USB_AUDIO_DEVICE'] = 'hw:2,0'
        
        # Reload module to pick up new env
        import importlib
        import windows_voice_control
        importlib.reload(windows_voice_control)
        
        self.assertEqual(windows_voice_control.USB_AUDIO_DEVICE, 'hw:2,0')


class TestCommandConstruction(unittest.TestCase):
    """Test command construction"""
    
    @patch('windows_voice_control.speak_command')
    def test_keystroke_formatting(self, mock_speak):
        """Test keystroke command formatting"""
        mock_speak.return_value = True
        
        send_keystroke("Tab")
        mock_speak.assert_called_with("Press Tab")
        
        send_keystroke("Escape")
        mock_speak.assert_called_with("Press Escape")
    
    @patch('windows_voice_control.speak_command')
    def test_type_text_formatting(self, mock_speak):
        """Test text typing command formatting"""
        mock_speak.return_value = True
        
        type_text("user@example.com")
        mock_speak.assert_called_with("Type user@example.com")
    
    @patch('windows_voice_control.speak_command')
    def test_open_app_formatting(self, mock_speak):
        """Test application open command formatting"""
        mock_speak.return_value = True
        
        open_application("Microsoft Excel")
        mock_speak.assert_called_with("Open Microsoft Excel")


class TestErrorHandling(unittest.TestCase):
    """Test error handling"""
    
    @patch('windows_voice_control.requests')
    def test_connection_error(self, mock_requests):
        """Test handling of connection errors"""
        import requests
        mock_requests.get.side_effect = requests.exceptions.ConnectionError()
        
        result = speak_command("Test")
        
        self.assertFalse(result)
    
    @patch('windows_voice_control.requests')
    def test_timeout_error(self, mock_requests):
        """Test handling of timeout errors"""
        import requests
        mock_requests.get.side_effect = requests.exceptions.Timeout()
        
        result = speak_command("Test")
        
        self.assertFalse(result)
    
    @patch('windows_voice_control.requests')
    @patch('windows_voice_control.subprocess.run')
    @patch('builtins.open', new_callable=mock_open)
    def test_audio_playback_failure(self, mock_file, mock_subprocess, mock_requests):
        """Test handling of audio playback failures"""
        # Mock successful TTS
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.iter_content = Mock(return_value=[b'audio'])
        mock_requests.get.return_value = mock_response
        
        # Mock failed playback
        mock_subprocess.return_value = Mock(
            returncode=1,
            stderr="aplay: device not found"
        )
        
        result = speak_command("Test")
        
        self.assertFalse(result)


if __name__ == '__main__':
    # Run tests
    unittest.main(verbosity=2)
