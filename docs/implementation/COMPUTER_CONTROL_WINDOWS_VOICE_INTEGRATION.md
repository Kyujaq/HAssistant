# Computer Control Agent + Windows Voice Control Integration

This document explains the integration between the Computer Control Agent and Windows Voice Control, enabling AI-powered computer control via Windows Voice Assistant.

## Overview

The Computer Control Agent can now execute actions in two modes:

1. **Direct Control Mode** (Default) - Uses PyAutoGUI for direct mouse/keyboard control
2. **Windows Voice Mode** - Routes commands through Windows Voice Assistant via audio cable

This integration allows you to use AI-powered vision and decision making (from Computer Control Agent) combined with Windows Voice Assistant for execution (via audio cable).

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                Computer Control Agent (AI Brain)                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  • Vision Gateway (screenshots)                          │  │
│  │  • Ollama LLM (decision making)                          │  │
│  │  • OCR (text recognition)                                 │  │
│  └──────────────────┬───────────────────────────────────────┘  │
│                     │ Actions                                   │
│                     ▼                                            │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │              Execution Router                             │  │
│  │  • Direct Mode → PyAutoGUI                               │  │
│  │  • Windows Voice Mode → Windows Voice Control            │  │
│  └──────────────────┬───────────────────────────────────────┘  │
└────────────────────┼──────────────────────────────────────────┘
                     │ (if Windows Voice Mode)
                     ▼
┌─────────────────────────────────────────────────────────────────┐
│              Windows Voice Control Module                        │
│  ┌──────────────┐     ┌─────────────────┐                      │
│  │   Piper TTS  │ ──► │ USB Audio Dongle│ ────┐                │
│  └──────────────┘     └─────────────────┘     │                │
└────────────────────────────────────────────────┼────────────────┘
                                                 │ 3.5mm Cable
┌────────────────────────────────────────────────┼────────────────┐
│                    Windows Laptop               │                │
│  ┌─────────────────────────────────────────┐   │                │
│  │      Headset/Microphone Port            │ ◄─┘                │
│  └────────────────┬────────────────────────┘                    │
│                   ▼                                              │
│  ┌─────────────────────────────────────────┐                    │
│  │      Windows Voice Assistant            │                    │
│  │   • Executes voice commands             │                    │
│  └─────────────────────────────────────────┘                    │
└──────────────────────────────────────────────────────────────────┘
```

## Benefits

### Advantages of Windows Voice Mode

1. **No Software on Windows** - Uses built-in Windows Voice Assistant
2. **AI-Powered** - Leverages Ollama LLM for intelligent decision making
3. **Vision-Based** - Uses screenshots to understand context
4. **Safe** - Physical separation via audio cable reduces security risks
5. **Flexible** - Can switch between direct and voice control modes

### When to Use Each Mode

**Use Direct Control Mode when:**
- Running agent directly on the target machine
- Need precise pixel-perfect control
- Working with applications requiring rapid actions
- Don't have audio cable setup

**Use Windows Voice Mode when:**
- Controlling a remote Windows machine
- Don't want to install software on Windows
- Want physical separation between control and target
- Using Home Assistant voice pipeline integration

## Setup

### Prerequisites

1. **Computer Control Agent** installed and configured
2. **Windows Voice Control** setup (see [WINDOWS_VOICE_ASSIST_SETUP.md](WINDOWS_VOICE_ASSIST_SETUP.md))
3. Hardware setup:
   - USB audio dongle with 3.5mm output
   - 3.5mm aux cable connecting Linux server to Windows laptop
   - Windows Voice Assistant enabled on target machine

### Configuration

#### Option 1: Environment Variable

Edit `computer_control_agent.env`:

```bash
# Enable Windows Voice Control mode
USE_WINDOWS_VOICE=true

# Other settings
CONFIRM_BEFORE_ACTION=false  # Disable for automation
MAX_ACTIONS_PER_TASK=50

# Optional: Configure TTS and audio
TTS_URL=http://localhost:10200
USB_AUDIO_DEVICE=hw:1,0
```

Load the configuration:
```bash
export $(cat computer_control_agent.env | xargs)
```

#### Option 2: Command Line Flag

Use the `--windows-voice` flag:

```bash
python computer_control_agent.py --windows-voice --task "Open Notepad and type Hello World"
```

#### Option 3: Python API

```python
from computer_control_agent import ComputerControlAgent

# Create agent in Windows Voice mode
agent = ComputerControlAgent(use_windows_voice=True)

# Execute tasks
agent.run_task("Open Excel and create a budget spreadsheet")
```

## Usage Examples

### Basic Commands

**Open an application:**
```bash
python computer_control_agent.py --windows-voice --task "Open Notepad"
```

**Type text:**
```bash
python computer_control_agent.py --windows-voice --task "Type 'Hello from AI'"
```

**Complex workflow:**
```bash
python computer_control_agent.py --windows-voice --task "Open Excel, type Budget 2024 in A1, type 1000 in A2"
```

### Python API Examples

```python
from computer_control_agent import ComputerControlAgent

# Initialize in Windows Voice mode
agent = ComputerControlAgent(use_windows_voice=True)

# Execute individual actions
actions = [
    {"type": "open_application", "params": {"name": "Notepad"}, "description": "Open Notepad"},
    {"type": "wait", "params": {"duration": 2}, "description": "Wait for app to open"},
    {"type": "type", "params": {"text": "Meeting Notes"}, "description": "Type title"},
    {"type": "press", "params": {"key": "Enter"}, "description": "New line"},
    {"type": "type", "params": {"text": "Date: 2024-01-15"}, "description": "Type date"}
]

for action in actions:
    agent.execute_action(action)
```

### Home Assistant Integration

Add to `configuration.yaml`:

```yaml
rest_command:
  computer_control_task:
    url: "http://localhost:5555/webhook/task"
    method: POST
    headers:
      Content-Type: "application/json"
    payload: >
      {
        "secret": "your-secret",
        "task": "{{ task }}",
        "context": "{{ context | default('') }}"
      }

automation:
  - alias: "AI Computer Control via Voice"
    trigger:
      platform: conversation
      command:
        - "computer [action]"
    action:
      - service: rest_command.computer_control_task
        data:
          task: "{{ trigger.command }}"
```

Set environment variable for HA integration:
```bash
# In docker-compose.yml or .env
USE_WINDOWS_VOICE=true
```

## Action Mapping

The integration automatically maps Computer Control Agent actions to Windows Voice commands:

| Agent Action | Windows Voice Command | Example |
|--------------|----------------------|---------|
| `type` | "Type [text]" | Type "Hello World" |
| `press` | "Press [key]" | Press Enter |
| `hotkey` | "Press [key] [key]" | Press Control C |
| `scroll` | "Scroll [up/down]" | Scroll up |
| `find_and_click` | "Click [text]" | Click Submit |
| `wait` | (Local wait) | Wait 2 seconds |
| `open_application` | "Open [app]" | Open Excel |

### Unsupported Actions

Some actions cannot be executed via Windows Voice and will fail:

- **Direct coordinate clicks** (`click` without text label)
- **Mouse movements** without text targets
- **Screen captures** (only available in direct mode)

For these operations, use Direct Control Mode instead.

## Testing

### Run Integration Tests

```bash
python test_windows_voice_integration.py
```

Expected output:
```
test_agent_initialization_direct_mode ... ok
test_agent_initialization_windows_voice_mode ... ok
test_execute_action_routing ... ok
test_execute_action_via_windows_voice_type ... ok
test_execute_action_via_windows_voice_keystroke ... ok
...
----------------------------------------------------------------------
Ran 15 tests in 0.123s

OK
```

### Manual Testing

1. **Test Direct Mode:**
   ```bash
   python computer_control_agent.py --task "Get screen info" --info
   ```

2. **Test Windows Voice Mode:**
   ```bash
   # Ensure Windows Voice Assistant is listening
   python computer_control_agent.py --windows-voice --task "Open Notepad"
   ```

3. **Verify audio output:**
   ```bash
   # You should hear Piper TTS speaking the command
   # Windows should recognize and execute the command
   ```

## Troubleshooting

### Agent doesn't switch to Windows Voice mode

**Check environment:**
```bash
echo $USE_WINDOWS_VOICE  # Should print 'true'
```

**Check imports:**
```python
# Verify windows_voice_control module is available
python -c "import windows_voice_control; print('OK')"
```

### Commands not executing on Windows

**Verify audio setup:**
1. Check USB audio device is working
2. Verify aux cable is connected
3. Test with: `python windows_voice_control.py --test`
4. Ensure Windows Voice Assistant is listening

**Check Windows recognition:**
1. Open Windows Sound settings → Recording
2. Verify headset microphone shows activity when TTS plays
3. Adjust microphone boost if needed (usually +20dB to +30dB)

### Actions failing in Windows Voice mode

**Review logs:**
```bash
# Agent will log which actions fail
python computer_control_agent.py --windows-voice --task "your task" 2>&1 | grep ERROR
```

**Common issues:**
- Click actions without text labels won't work
- Complex hotkeys may need adjustment
- Some applications may not respond to voice commands

**Solution:** Use Direct Control Mode for problematic actions:
```python
# Create two agents
voice_agent = ComputerControlAgent(use_windows_voice=True)
direct_agent = ComputerControlAgent(use_windows_voice=False)

# Use voice for simple commands
voice_agent.execute_action({"type": "type", "params": {"text": "Hello"}})

# Use direct control for complex ones
direct_agent.execute_action({"type": "click", "params": {"x": 123, "y": 456}})
```

## Advanced Configuration

### Hybrid Mode Script

Combine both modes for optimal results:

```python
from computer_control_agent import ComputerControlAgent

class HybridControlAgent:
    """Uses Windows Voice when possible, falls back to direct control"""
    
    def __init__(self):
        self.voice_agent = ComputerControlAgent(use_windows_voice=True)
        self.direct_agent = ComputerControlAgent(use_windows_voice=False)
    
    def execute_action(self, action):
        """Try Windows Voice first, fallback to direct control"""
        action_type = action.get('type')
        
        # Actions that work well via voice
        voice_compatible = ['type', 'press', 'hotkey', 'scroll', 
                           'find_and_click', 'open_application', 'wait']
        
        if action_type in voice_compatible:
            if self.voice_agent.execute_action(action):
                return True
        
        # Fall back to direct control
        return self.direct_agent.execute_action(action)
```

### Custom Voice Commands

For better recognition, customize voice commands:

```python
def execute_action_via_windows_voice(self, action):
    """Custom implementation with better voice commands"""
    action_type = action.get('type')
    
    if action_type == 'type':
        # Spell out punctuation for better recognition
        text = action['params']['text']
        text = text.replace('.', ' period')
        text = text.replace(',', ' comma')
        return self.windows_voice_bridge['type_text'](text)
    
    # ... rest of implementation
```

## Performance Considerations

**Windows Voice Mode:**
- Latency: ~2-4 seconds per command (TTS + recognition)
- Reliability: ~90-95% (depends on audio quality)
- Throughput: ~15-20 commands per minute

**Direct Control Mode:**
- Latency: ~0.1-0.5 seconds per command
- Reliability: ~99%
- Throughput: ~100+ commands per minute

**Recommendation:** Use Windows Voice Mode for:
- Setup/initialization tasks
- User-facing applications
- Situations where safety is paramount

Use Direct Control Mode for:
- Data entry tasks
- Repetitive operations
- Performance-critical workflows

## Security Considerations

### Advantages of Windows Voice Mode

1. **Physical Separation** - Linux and Windows systems are separate
2. **No Network Access** - Communication via audio cable only
3. **Auditable** - Every command is "spoken" and can be heard
4. **Limited Scope** - Restricted to Windows Voice Assistant capabilities

### Security Best Practices

1. **Monitor Commands** - Listen to TTS output to verify commands
2. **Use Confirmation** - Enable `CONFIRM_BEFORE_ACTION` for testing
3. **Limit Actions** - Set `MAX_ACTIONS_PER_TASK` appropriately
4. **Secure Tokens** - Protect HA_TOKEN and other credentials
5. **Physical Security** - Secure the audio cable connection

## Conclusion

The Computer Control Agent + Windows Voice Control integration provides:

✅ AI-powered computer control  
✅ Windows Voice Assistant execution  
✅ No software on Windows required  
✅ Physical security via audio cable  
✅ Flexible mode switching  
✅ Home Assistant integration  

Choose the right mode for your use case, or use hybrid mode for the best of both worlds!

## See Also

- [Computer Control Agent Documentation](COMPUTER_CONTROL_AGENT.md)
- [Windows Voice Control Setup](WINDOWS_VOICE_ASSIST_SETUP.md)
- [Windows Voice Control Quick Reference](WINDOWS_VOICE_CONTROL_QUICK_REF.md)
- [Home Assistant Integration](ha_integration.py)
