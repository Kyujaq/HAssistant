"""
Unit tests for HAClient (Home Assistant API client)

Uses pytest and requests-mock to test the client without making real API calls.
"""

import os
import pytest
import requests
from unittest.mock import patch
import sys
from pathlib import Path

# Add parent directory to path to import modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from integrations.ha_client import HAClient


class TestHAClientInitialization:
    """Test HAClient initialization and configuration."""
    
    def test_init_success(self):
        """Test successful initialization with environment variables."""
        with patch.dict(os.environ, {
            'HA_BASE_URL': 'http://homeassistant:8123',
            'HA_TOKEN': 'test-token-12345'
        }):
            client = HAClient()
            assert client.base_url == 'http://homeassistant:8123'
            assert client.token == 'test-token-12345'
            assert 'Bearer test-token-12345' in client.headers['Authorization']
    
    def test_init_removes_trailing_slash(self):
        """Test that trailing slash is removed from base URL."""
        with patch.dict(os.environ, {
            'HA_BASE_URL': 'http://homeassistant:8123/',
            'HA_TOKEN': 'test-token'
        }):
            client = HAClient()
            assert client.base_url == 'http://homeassistant:8123'
    
    def test_init_missing_base_url(self):
        """Test that missing HA_BASE_URL raises ValueError."""
        with patch.dict(os.environ, {'HA_TOKEN': 'test-token'}, clear=True):
            with pytest.raises(ValueError, match="HA_BASE_URL"):
                HAClient()
    
    def test_init_missing_token(self):
        """Test that missing HA_TOKEN raises ValueError."""
        with patch.dict(os.environ, {'HA_BASE_URL': 'http://homeassistant:8123'}, clear=True):
            with pytest.raises(ValueError, match="HA_TOKEN"):
                HAClient()


class TestHAClientGetState:
    """Test HAClient.get_state() method."""
    
    @pytest.fixture
    def client(self):
        """Create a HAClient instance for testing."""
        with patch.dict(os.environ, {
            'HA_BASE_URL': 'http://homeassistant:8123',
            'HA_TOKEN': 'test-token'
        }):
            return HAClient()
    
    def test_get_state_success(self, client, requests_mock):
        """Test successful state retrieval."""
        entity_id = 'light.living_room'
        expected_state = {
            'entity_id': entity_id,
            'state': 'on',
            'attributes': {
                'brightness': 255,
                'friendly_name': 'Living Room Light'
            }
        }
        
        requests_mock.get(
            f'http://homeassistant:8123/api/states/{entity_id}',
            json=expected_state,
            status_code=200
        )
        
        result = client.get_state(entity_id)
        
        assert result == expected_state
        assert result['state'] == 'on'
        assert result['attributes']['brightness'] == 255
    
    def test_get_state_not_found(self, client, requests_mock):
        """Test that 404 returns None."""
        entity_id = 'light.nonexistent'
        
        requests_mock.get(
            f'http://homeassistant:8123/api/states/{entity_id}',
            status_code=404
        )
        
        result = client.get_state(entity_id)
        
        assert result is None
    
    def test_get_state_unauthorized(self, client, requests_mock):
        """Test that 401 raises ValueError."""
        entity_id = 'light.living_room'
        
        requests_mock.get(
            f'http://homeassistant:8123/api/states/{entity_id}',
            json={'message': 'Unauthorized'},
            status_code=401
        )
        
        with pytest.raises(ValueError, match="HTTP 401"):
            client.get_state(entity_id)
    
    def test_get_state_server_error(self, client, requests_mock):
        """Test that 500 raises ValueError."""
        entity_id = 'light.living_room'
        
        requests_mock.get(
            f'http://homeassistant:8123/api/states/{entity_id}',
            status_code=500,
            text='Internal Server Error'
        )
        
        with pytest.raises(ValueError, match="HTTP 500"):
            client.get_state(entity_id)
    
    def test_get_state_timeout(self, client, requests_mock):
        """Test that timeout raises RequestException."""
        entity_id = 'light.living_room'
        
        requests_mock.get(
            f'http://homeassistant:8123/api/states/{entity_id}',
            exc=requests.exceptions.Timeout
        )
        
        with pytest.raises(requests.exceptions.Timeout):
            client.get_state(entity_id)
    
    def test_get_state_connection_error(self, client, requests_mock):
        """Test that connection error raises RequestException."""
        entity_id = 'light.living_room'
        
        requests_mock.get(
            f'http://homeassistant:8123/api/states/{entity_id}',
            exc=requests.exceptions.ConnectionError
        )
        
        with pytest.raises(requests.exceptions.ConnectionError):
            client.get_state(entity_id)
    
    def test_get_state_correct_headers(self, client, requests_mock):
        """Test that correct headers are sent."""
        entity_id = 'light.living_room'
        
        mock = requests_mock.get(
            f'http://homeassistant:8123/api/states/{entity_id}',
            json={'state': 'on'}
        )
        
        client.get_state(entity_id)
        
        assert mock.last_request.headers['Authorization'] == 'Bearer test-token'
        assert 'application/json' in mock.last_request.headers['Content-Type']


class TestHAClientCallService:
    """Test HAClient.call_service() method."""
    
    @pytest.fixture
    def client(self):
        """Create a HAClient instance for testing."""
        with patch.dict(os.environ, {
            'HA_BASE_URL': 'http://homeassistant:8123',
            'HA_TOKEN': 'test-token'
        }):
            return HAClient()
    
    def test_call_service_success(self, client, requests_mock):
        """Test successful service call."""
        domain = 'light'
        service = 'turn_on'
        service_data = {
            'entity_id': 'light.living_room',
            'brightness': 200
        }
        expected_response = [
            {
                'entity_id': 'light.living_room',
                'state': 'on'
            }
        ]
        
        requests_mock.post(
            f'http://homeassistant:8123/api/services/{domain}/{service}',
            json=expected_response,
            status_code=200
        )
        
        result = client.call_service(domain, service, service_data)
        
        assert result == expected_response
    
    def test_call_service_no_data(self, client, requests_mock):
        """Test service call without service data."""
        domain = 'homeassistant'
        service = 'restart'
        
        requests_mock.post(
            f'http://homeassistant:8123/api/services/{domain}/{service}',
            json=[],
            status_code=200
        )
        
        result = client.call_service(domain, service)
        
        assert result == []
    
    def test_call_service_bad_request(self, client, requests_mock):
        """Test that 400 raises ValueError."""
        domain = 'light'
        service = 'turn_on'
        
        requests_mock.post(
            f'http://homeassistant:8123/api/services/{domain}/{service}',
            json={'message': 'Invalid service data'},
            status_code=400
        )
        
        with pytest.raises(ValueError, match="HTTP 400"):
            client.call_service(domain, service, {})
    
    def test_call_service_unauthorized(self, client, requests_mock):
        """Test that 401 raises ValueError."""
        domain = 'light'
        service = 'turn_on'
        
        requests_mock.post(
            f'http://homeassistant:8123/api/services/{domain}/{service}',
            json={'message': 'Unauthorized'},
            status_code=401
        )
        
        with pytest.raises(ValueError, match="HTTP 401"):
            client.call_service(domain, service, {})
    
    def test_call_service_not_found(self, client, requests_mock):
        """Test that 404 raises ValueError."""
        domain = 'invalid_domain'
        service = 'invalid_service'
        
        requests_mock.post(
            f'http://homeassistant:8123/api/services/{domain}/{service}',
            status_code=404
        )
        
        with pytest.raises(ValueError, match="HTTP 404"):
            client.call_service(domain, service, {})
    
    def test_call_service_timeout(self, client, requests_mock):
        """Test that timeout raises RequestException."""
        domain = 'light'
        service = 'turn_on'
        
        requests_mock.post(
            f'http://homeassistant:8123/api/services/{domain}/{service}',
            exc=requests.exceptions.Timeout
        )
        
        with pytest.raises(requests.exceptions.Timeout):
            client.call_service(domain, service, {})
    
    def test_call_service_connection_error(self, client, requests_mock):
        """Test that connection error raises RequestException."""
        domain = 'light'
        service = 'turn_on'
        
        requests_mock.post(
            f'http://homeassistant:8123/api/services/{domain}/{service}',
            exc=requests.exceptions.ConnectionError
        )
        
        with pytest.raises(requests.exceptions.ConnectionError):
            client.call_service(domain, service, {})
    
    def test_call_service_correct_headers_and_payload(self, client, requests_mock):
        """Test that correct headers and payload are sent."""
        domain = 'light'
        service = 'turn_on'
        service_data = {
            'entity_id': 'light.bedroom',
            'brightness': 150
        }
        
        mock = requests_mock.post(
            f'http://homeassistant:8123/api/services/{domain}/{service}',
            json=[]
        )
        
        client.call_service(domain, service, service_data)
        
        assert mock.last_request.headers['Authorization'] == 'Bearer test-token'
        assert 'application/json' in mock.last_request.headers['Content-Type']
        assert mock.last_request.json() == service_data
