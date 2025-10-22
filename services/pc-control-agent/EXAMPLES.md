# Qwen PC Control Agent - Example Commands

This file contains example voice commands and their expected behavior.

## Basic Application Control

### Opening Applications
```
"Open Firefox" → Opens Firefox browser
"Launch Chrome" → Opens Google Chrome
"Start terminal" → Opens terminal/command prompt
"Open file manager" → Opens file explorer/finder
"Launch text editor" → Opens default text editor
"Start calculator" → Opens calculator app
"Open code editor" → Opens VS Code (if installed)
```

### Closing Applications
```
"Close Firefox" → Terminates Firefox process
"Kill Chrome" → Terminates Chrome process
"Stop terminal" → Closes terminal window
```

## Volume and Audio Control

### Volume Adjustment
```
"Increase volume" → +5% volume
"Decrease volume" → -5% volume
"Turn up the volume" → +5% volume
"Turn down the volume" → -5% volume
"Volume up" → +5% volume
"Volume down" → -5% volume
```

### Mute/Unmute
```
"Mute" → Mutes all audio
"Mute audio" → Mutes all audio
"Unmute" → Unmutes audio
"Unmute audio" → Unmutes audio
"Turn on sound" → Unmutes audio
```

## Screen and Display Control

### Screen Lock
```
"Lock screen" → Locks the screen
"Lock the computer" → Locks the screen
"Lock PC" → Locks the screen
```

### Screenshots
```
"Take a screenshot" → Saves screenshot to ~/Pictures/
"Capture screen" → Saves screenshot to ~/Pictures/
"Screenshot" → Saves screenshot to ~/Pictures/
```

## File Operations

### Opening Files
```
"Open document.pdf" → Opens document.pdf with default app
"Open ~/Downloads/file.txt" → Opens specific file
"Launch /path/to/file" → Opens file at path
```

### Listing Files
```
"List files in Downloads" → Shows files in Downloads folder
"Show files in Documents" → Shows files in Documents folder
"What's in my Pictures folder" → Shows files in Pictures
"List files" → Shows files in home directory
```

## System Information

### System Stats
```
"Show system info" → Displays CPU, memory, disk usage
"What's my CPU usage" → Shows system information
"How much memory is used" → Shows memory statistics
"Check disk space" → Shows disk usage
"System status" → Shows all system information
```

## Complex Natural Language Examples

These demonstrate Qwen's natural language understanding:

### Conversational Commands
```
"Hey, can you open Firefox for me?" → Opens Firefox
"I need to see what's in my Downloads" → Lists Downloads
"Please increase the volume a bit" → +5% volume
"Could you take a screenshot?" → Takes screenshot
"I want to lock my screen now" → Locks screen
```

### Contextual Commands
```
"Open the browser" → Opens default browser (Firefox)
"Launch my code editor" → Opens VS Code
"Show me the files in my home folder" → Lists home directory
"What's going on with my system?" → Shows system info
"Turn the sound off" → Mutes audio
```

## Platform-Specific Examples

### Linux-Specific
```
"Open Nautilus" → Opens file manager
"Launch gnome-terminal" → Opens terminal
"Start gedit" → Opens text editor
```

### macOS-Specific
```
"Open Safari" → Opens Safari browser
"Launch Finder" → Opens Finder
"Start Terminal" → Opens Terminal app
```

### Windows-Specific
```
"Open Explorer" → Opens File Explorer
"Launch Notepad" → Opens Notepad
"Start cmd" → Opens Command Prompt
```

## Error Handling Examples

### Unclear Commands
```
"Do something" → Response: "Unknown command - please be more specific"
"Execute order 66" → Response: "Cannot understand this command"
"Make me a sandwich" → Response: "Cannot execute - unclear action"
```

### Invalid Targets
```
"Open nonexistent-app" → Attempts to open, may fail gracefully
"List files in /invalid/path" → Response: "Directory not found"
```

## Advanced Use Cases

### Chaining with Home Assistant
```yaml
# In Home Assistant automation:
- "Computer, open Firefox and increase volume"
  → Opens Firefox
  → Increases volume
```

### Context-Aware Commands
```
"I need to present, lock my screen after" → Can be interpreted as multi-step
"Before I leave, take a screenshot" → Takes screenshot
```

## Voice Command Tips

1. **Be Clear**: Speak clearly and at normal pace
2. **Be Specific**: "Open Firefox" is better than "Open something"
3. **Use Natural Language**: "Can you increase the volume?" works fine
4. **Wait for Response**: Let the system process before next command
5. **Check Logs**: If command fails, check the agent logs for details

## Testing Without Voice

You can test the agent's command parsing without voice:

```python
from pc_control_agent import PCControlAgent, PCCommand

agent = PCControlAgent()

# Test a command directly
command = PCCommand(
    action="open_app",
    target="firefox",
    parameters={}
)

result = agent.execute_command(command)
print(result)
```

## Extending Commands

To add new commands, edit `pc_control_agent.py`:

1. Add to `self.commands` dictionary in `__init__`
2. Implement the command method
3. Update the Qwen prompt to include the new action
4. Test the command

Example:
```python
def __init__(self):
    # ...
    self.commands['my_command'] = self._my_command

def _my_command(self, target: str, params: Dict) -> str:
    """My custom command"""
    # Implementation
    return "Command executed"
```

## Debugging

Enable verbose logging:
```bash
export LOG_LEVEL=DEBUG
python3 pc_control_agent.py
```

Test individual components:
```bash
# Test STT
curl -X POST http://localhost:10300/api/stt \
  -H "Content-Type: audio/wav" \
  --data-binary @test.wav

# Test Qwen
curl http://localhost:11434/api/generate \
  -d '{"model": "qwen2.5:7b", "prompt": "Hello"}'
```

## See Also

- [PC_CONTROL_AGENT.md](PC_CONTROL_AGENT.md) - Full documentation
- [../README.md](../README.md) - Main project documentation
- [integration_example.py](integration_example.py) - Integration examples
