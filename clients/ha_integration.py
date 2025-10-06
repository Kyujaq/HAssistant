"""
Home Assistant Integration for Computer Control Agent

This script demonstrates how to integrate the Computer Control Agent
with Home Assistant for voice-controlled computer automation.
"""

import os
import sys
import json
import logging
from flask import Flask, request, jsonify

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from computer_control_agent import ComputerControlAgent

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('ha_integration')

# Flask app for webhook integration
app = Flask(__name__)

# Configuration
HA_WEBHOOK_SECRET = os.getenv('HA_WEBHOOK_SECRET', 'change-me-secret')
USE_WINDOWS_VOICE = os.getenv('USE_WINDOWS_VOICE', 'false').lower() == 'true'

# Create agent instance with Windows Voice mode if configured
agent = ComputerControlAgent(use_windows_voice=USE_WINDOWS_VOICE)


@app.route('/healthz', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({"status": "healthy", "service": "computer-control-agent"})


@app.route('/webhook/task', methods=['POST'])
def webhook_task():
    """
    Webhook endpoint for Home Assistant
    
    Expected payload:
    {
        "secret": "webhook_secret",
        "task": "Task description",
        "context": "Optional context",
        "excel": false
    }
    """
    try:
        data = request.get_json()
        
        # Verify secret
        if data.get('secret') != HA_WEBHOOK_SECRET:
            logger.warning("Invalid webhook secret")
            return jsonify({"error": "Unauthorized"}), 401
        
        task = data.get('task')
        context = data.get('context')
        excel = data.get('excel', False)
        
        if not task:
            return jsonify({"error": "No task specified"}), 400
        
        logger.info(f"Received task: {task}")
        
        # Execute task
        if excel:
            success = agent.control_excel(task)
        else:
            success = agent.run_task(task, context)
        
        return jsonify({
            "success": success,
            "task": task,
            "actions_performed": agent.action_count
        })
        
    except Exception as e:
        logger.error(f"Error processing webhook: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/api/screen_info', methods=['GET'])
def api_screen_info():
    """Get current screen information"""
    try:
        info = agent.get_screen_info()
        return jsonify(info)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/execute_action', methods=['POST'])
def api_execute_action():
    """
    Execute a single action
    
    Expected payload:
    {
        "type": "click",
        "params": {"x": 100, "y": 200},
        "description": "Click button"
    }
    """
    try:
        action = request.get_json()
        
        if not action or 'type' not in action:
            return jsonify({"error": "Invalid action"}), 400
        
        success = agent.execute_action(action)
        
        return jsonify({
            "success": success,
            "action": action
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# Home Assistant configuration.yaml example
HA_CONFIG_EXAMPLE = """
# Add to configuration.yaml:

# REST Command for Computer Control
rest_command:
  computer_control_task:
    url: "http://localhost:5555/webhook/task"
    method: POST
    headers:
      Content-Type: "application/json"
    payload: >
      {
        "secret": "change-me-secret",
        "task": "{{ task }}",
        "context": "{{ context | default('') }}",
        "excel": {{ excel | default('false') }}
      }

# Script to execute tasks
script:
  computer_control:
    alias: "Computer Control Task"
    sequence:
      - service: rest_command.computer_control_task
        data:
          task: "{{ task }}"
          context: "{{ context }}"
          excel: "{{ excel }}"

# Automation examples
automation:
  - alias: "Voice Control Computer"
    trigger:
      platform: conversation
      command:
        - "computer [task]"
        - "open [application]"
    action:
      - service: script.computer_control
        data:
          task: "{{ trigger.command }}"
          
  - alias: "Excel Commands"
    trigger:
      platform: conversation
      command:
        - "create spreadsheet [details]"
        - "excel [command]"
    action:
      - service: script.computer_control
        data:
          task: "{{ trigger.command }}"
          excel: true

# Sensor to monitor agent status
sensor:
  - platform: rest
    name: Computer Control Agent Status
    resource: http://localhost:5555/healthz
    method: GET
    value_template: "{{ value_json.status }}"
    scan_interval: 60
"""

# Docker compose example for integration
DOCKER_COMPOSE_EXAMPLE = """
# Add to docker-compose.yml:

  computer-control-ha-bridge:
    build:
      context: .
      dockerfile: Dockerfile.computer_control
    container_name: hassistant-computer-control-bridge
    command: python3 ha_integration.py
    environment:
      - VISION_GATEWAY_URL=http://vision-gateway:8088
      - OLLAMA_URL=http://ollama-chat:11434
      - HA_URL=http://homeassistant:8123
      - HA_TOKEN=${HA_TOKEN}
      - HA_WEBHOOK_SECRET=${HA_WEBHOOK_SECRET:-change-me-secret}
      - CONFIRM_BEFORE_ACTION=false  # Disable for automation
    ports:
      - "5555:5555"
    depends_on:
      - vision-gateway
      - ollama-chat
      - homeassistant
    restart: unless-stopped
    networks:
      - ha_network
"""


def main():
    """Run the Flask server"""
    port = int(os.getenv('PORT', '5555'))
    
    print("=" * 60)
    print("Computer Control Agent - Home Assistant Integration")
    print("=" * 60)
    print(f"\nStarting webhook server on port {port}")
    print(f"Webhook URL: http://localhost:{port}/webhook/task")
    print(f"Health check: http://localhost:{port}/healthz")
    print(f"Screen info: http://localhost:{port}/api/screen_info")
    print("\nHome Assistant Configuration:")
    print("-" * 60)
    print(HA_CONFIG_EXAMPLE)
    print("\nDocker Compose Integration:")
    print("-" * 60)
    print(DOCKER_COMPOSE_EXAMPLE)
    print("\nPress Ctrl+C to stop")
    print("=" * 60 + "\n")
    
    app.run(host='0.0.0.0', port=port, debug=False)


if __name__ == '__main__':
    main()
