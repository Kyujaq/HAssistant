"""
Example integration: Use PC Control Agent from Home Assistant

This example shows how to trigger the PC control agent from
Home Assistant automations or scripts.
"""

import requests
import json


# PC Control Agent API wrapper
class PCControlAPI:
    """Wrapper for PC Control Agent commands"""
    
    def __init__(self, agent_host: str = "localhost", agent_port: int = 8083):
        self.base_url = f"http://{agent_host}:{agent_port}"
    
    def execute_voice_command(self, text: str) -> dict:
        """Execute a text command (no voice recording needed)"""
        response = requests.post(
            f"{self.base_url}/execute",
            json={"text": text}
        )
        return response.json()


# Example Home Assistant REST command configuration
HOME_ASSISTANT_REST_COMMAND = """
# In Home Assistant configuration.yaml:

rest_command:
  pc_control:
    url: "http://hassistant-qwen-agent:8083/execute"
    method: POST
    content_type: "application/json"
    payload: '{"text": "{{ command }}"}'
"""

# Example Home Assistant automation
HOME_ASSISTANT_AUTOMATION = """
# In Home Assistant automations.yaml:

- alias: "PC Control via Voice"
  trigger:
    platform: conversation
    command: "computer *"
  action:
    - service: rest_command.pc_control
      data:
        command: "{{ trigger.command | replace('computer ', '') }}"
    - service: notify.mobile_app
      data:
        message: "Executed: {{ trigger.command }}"

# Example usage in HA:
# Say: "Computer, open Firefox"
# Say: "Computer, increase volume"
# Say: "Computer, take a screenshot"
"""

# Example Python usage
if __name__ == "__main__":
    # Note: This example assumes an API endpoint exists
    # The current pc_control_agent.py runs interactively
    # You could extend it with a REST API using FastAPI
    
    print("PC Control Agent Integration Examples")
    print("=" * 60)
    print("\n1. Direct Python API (requires API wrapper):")
    print("-" * 60)
    print("""
    from pc_control_api import PCControlAPI
    
    api = PCControlAPI()
    result = api.execute_voice_command("open firefox")
    print(result)
    """)
    
    print("\n2. Home Assistant REST Command:")
    print("-" * 60)
    print(HOME_ASSISTANT_REST_COMMAND)
    
    print("\n3. Home Assistant Automation:")
    print("-" * 60)
    print(HOME_ASSISTANT_AUTOMATION)
    
    print("\n4. Direct Agent Usage:")
    print("-" * 60)
    print("""
    # Run the agent interactively
    docker exec -it hassistant-qwen-agent python3 /app/pc_control_agent.py
    
    # Or use the start script
    cd qwen-agent && ./start_agent.sh
    """)
    
    print("\n" + "=" * 60)
    print("See qwen-agent/PC_CONTROL_AGENT.md for full documentation")
