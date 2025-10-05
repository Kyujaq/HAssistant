# Computer Control Agent

The Computer Control Agent enables automated control of another computer using vision-based understanding and AI-powered decision making. It can interact with any GUI application, including Excel, browsers, and desktop applications.

## Features

- **Vision-Based Control**: Takes screenshots and uses OCR to understand what's on screen
- **AI-Powered Actions**: Uses Ollama LLM to analyze screenshots and decide what actions to take
- **Safe Execution**: Confirmation prompts and failsafe mechanisms to prevent accidents
- **Excel Support**: Specialized functions for working with Excel spreadsheets
- **Flexible Actions**: Supports mouse clicks, keyboard input, hotkeys, scrolling, and more
- **Windows Voice Integration**: Can execute commands via Windows Voice Assistant (see [integration guide](COMPUTER_CONTROL_WINDOWS_VOICE_INTEGRATION.md))

## Execution Modes

The agent supports two execution modes:

1. **Direct Control Mode** (Default) - Uses PyAutoGUI for direct mouse/keyboard control
2. **Windows Voice Mode** - Routes commands through Windows Voice Assistant via audio cable

See [COMPUTER_CONTROL_WINDOWS_VOICE_INTEGRATION.md](COMPUTER_CONTROL_WINDOWS_VOICE_INTEGRATION.md) for details on Windows Voice integration.

## Architecture

```
┌─────────────────────┐
│  Vision Gateway     │  Captures screenshots from target computer
│  (vision-gateway)   │  or local screen
└──────────┬──────────┘
           │
┌──────────▼──────────┐
│ Computer Control    │  Main agent logic
│     Agent           │
└──────────┬──────────┘
           │
      ┌────┴────┬─────────────┐
      │         │             │
┌─────▼────┐ ┌──▼────────┐ ┌─▼────────┐
│ Ollama   │ │PyAutoGUI  │ │Tesseract │
│   LLM    │ │(Control)  │ │  (OCR)   │
└──────────┘ └───────────┘ └──────────┘
```

## Installation

### Prerequisites

1. **Python 3.8+**
2. **Tesseract OCR**: Required for text recognition
   - **Ubuntu/Debian**: `sudo apt-get install tesseract-ocr`
   - **macOS**: `brew install tesseract`
   - **Windows**: Download from [GitHub](https://github.com/UB-Mannheim/tesseract/wiki)

3. **HAssistant services** (for remote control):
   - Vision Gateway running on port 8088
   - Ollama running on port 11434

### Install Python Dependencies

```bash
pip install -r computer_control_requirements.txt
```

Required packages:
- `pyautogui` - Mouse and keyboard control
- `pytesseract` - OCR text recognition
- `Pillow` - Image processing
- `opencv-python` - Computer vision
- `numpy` - Array operations
- `requests` - HTTP client

### Configuration

1. Copy the example configuration:
   ```bash
   cp computer_control_agent.env.example computer_control_agent.env
   ```

2. Edit `computer_control_agent.env`:
   ```bash
   # Vision Gateway URL (for remote screenshot fetching)
   VISION_GATEWAY_URL=http://localhost:8088
   
   # Ollama URL for AI decision making
   OLLAMA_URL=http://localhost:11434
   OLLAMA_MODEL=qwen3:4b-instruct-2507-q4_K_M
   
   # Execution Mode
   USE_WINDOWS_VOICE=false  # Set to 'true' to use Windows Voice Control
   
   # Safety Settings
   CONFIRM_BEFORE_ACTION=true  # Require confirmation before each action
   MAX_ACTIONS_PER_TASK=50     # Maximum number of actions per task
   ```

3. Load environment variables:
   ```bash
   export $(cat computer_control_agent.env | xargs)
   ```

## Usage

### Basic Commands

**Get screen information:**
```bash
python computer_control_agent.py --info
```

**Run a simple task:**
```bash
python computer_control_agent.py --task "Open notepad and type Hello World"
```

**Run task with Windows Voice mode:**
```bash
python computer_control_agent.py --windows-voice --task "Open notepad and type Hello World"
```

**Excel-specific task:**
```bash
python computer_control_agent.py --excel --task "Create a new spreadsheet with headers Name, Email, Phone"
```

**Provide context:**
```bash
python computer_control_agent.py --task "Click the Save button" --context "Working in Microsoft Word"
```

### Use Cases

#### 1. Opening Applications
```bash
python computer_control_agent.py --task "Open Google Chrome"
```

#### 2. Working with Excel
```bash
# Create a new spreadsheet
python computer_control_agent.py --excel --task "Create a new workbook"

# Add data to cells
python computer_control_agent.py --excel --task "In cell A1 type 'Name', in B1 type 'Email', in C1 type 'Phone'"

# Format cells
python computer_control_agent.py --excel --task "Make row 1 bold and add background color"

# Create charts
python computer_control_agent.py --excel --task "Create a bar chart from data in A1:B10"
```

#### 3. Web Browsing
```bash
python computer_control_agent.py --task "Search for 'Python automation' on Google"

python computer_control_agent.py --task "Navigate to github.com"
```

#### 4. File Management
```bash
python computer_control_agent.py --task "Open File Explorer and navigate to Documents folder"

python computer_control_agent.py --task "Create a new folder named 'Project Files'"
```

#### 5. Text Editing
```bash
python computer_control_agent.py --task "Open Notepad, type 'Meeting Notes', save as notes.txt"
```

### Using as a Python Module

```python
from computer_control_agent import ComputerControlAgent

# Initialize agent
agent = ComputerControlAgent()

# Get screen info
info = agent.get_screen_info()
print(f"Screen resolution: {info['resolution']}")
print(f"Text on screen: {info['text_preview']}")

# Run a task
success = agent.run_task(
    task="Open calculator and compute 25 * 4",
    context="Windows 10 desktop"
)

# Control Excel
success = agent.control_excel(
    task="Create a budget spreadsheet with categories and amounts"
)

# Execute specific actions
actions = [
    {"type": "click", "params": {"x": 100, "y": 200}, "description": "Click button"},
    {"type": "type", "params": {"text": "Hello"}, "description": "Type text"},
    {"type": "press", "params": {"key": "enter"}, "description": "Press Enter"}
]

for action in actions:
    agent.execute_action(action)
```

## Action Types

The agent supports the following action types:

| Action | Parameters | Description |
|--------|-----------|-------------|
| `click` | `x, y, clicks=1, button='left'` | Click at coordinates |
| `double_click` | `x, y` | Double-click at coordinates |
| `right_click` | `x, y` | Right-click at coordinates |
| `move` | `x, y, duration=0.5` | Move mouse to coordinates |
| `type` | `text, interval=0.05` | Type text |
| `press` | `key` | Press a key (e.g., 'enter', 'tab') |
| `hotkey` | `keys` | Press key combination (e.g., ['ctrl', 'c']) |
| `scroll` | `amount` | Scroll (positive=up, negative=down) |
| `wait` | `duration` | Wait for specified seconds |
| `find_and_click` | `text` | Find text on screen and click it |

## Safety Features

### 1. Confirmation Mode
When `CONFIRM_BEFORE_ACTION=true`, the agent asks for confirmation before each action:
```
Execute click with params {'x': 100, 'y': 200}? (y/n):
```

### 2. Failsafe
PyAutoGUI's failsafe feature is enabled by default. Move your mouse to the top-left corner of the screen to abort execution immediately.

### 3. Action Limit
The `MAX_ACTIONS_PER_TASK` setting prevents runaway tasks. Default is 50 actions per task.

### 4. Pause Between Actions
A 0.5 second pause between actions gives you time to see what's happening and abort if needed.

## Remote Computer Control

The agent can control a remote computer by fetching screenshots from the vision-gateway service:

1. **Setup Vision Gateway** on the target computer to capture and stream screenshots
2. **Configure the agent** to use the remote source:
   ```python
   screenshot = agent.get_screenshot("frigate_hdmi")  # Instead of "local"
   ```

3. **Use with Frigate**: The vision-gateway integrates with Frigate for webcam-based monitoring

## Excel-Specific Features

The `control_excel()` method has enhanced capabilities for Excel:

- Sheet manipulation (create, rename, delete)
- Cell operations (read, write, format)
- Formula insertion
- Chart creation
- Data filtering and sorting
- Pivot tables

Example:
```python
agent.control_excel(
    task="Create a monthly budget with categories: Rent, Food, Transport, Entertainment. "
         "Add formulas to calculate total expenses."
)
```

## Troubleshooting

### OCR Not Working
- Verify Tesseract is installed: `tesseract --version`
- Check Tesseract path: `which tesseract` (Linux/Mac) or `where tesseract` (Windows)
- If needed, set path: `pytesseract.pytesseract.tesseract_cmd = '/path/to/tesseract'`

### Actions Not Executing
- Check if confirmation mode is on (`CONFIRM_BEFORE_ACTION=true`)
- Verify screen coordinates are correct
- Ensure target application has focus
- Check if failsafe was triggered (mouse in corner)

### LLM Not Responding
- Verify Ollama is running: `curl http://localhost:11434/api/tags`
- Check if model is loaded: `ollama list`
- Ensure OLLAMA_URL is correct in configuration

### Screenshot Capture Fails
- For local mode: Check screen permissions (macOS requires screen recording permission)
- For remote mode: Verify vision-gateway is running and accessible

## Security Considerations

⚠️ **Warning**: This agent can control your computer automatically. Use with caution:

1. **Never run untrusted tasks** without reviewing the actions first
2. **Always use confirmation mode** when testing new tasks
3. **Be careful with sensitive data** - the agent can type passwords if instructed
4. **Monitor execution** - don't leave the agent running unattended
5. **Use in isolated environments** for testing and development

## Advanced Configuration

### Custom Action Handlers

You can extend the agent with custom action types:

```python
def custom_action_handler(action):
    if action['type'] == 'my_custom_action':
        # Your custom logic
        pass
    return True

# Register handler
agent.execute_action = custom_action_handler
```

### Vision-Only Mode

For analysis without execution:

```python
# Get screenshot and OCR only
screenshot = agent.get_screenshot("local")
text = agent.ocr_screenshot(screenshot)
print(f"Screen contains: {text}")
```

### Integration with Home Assistant

The agent can be triggered via Home Assistant automations:

```yaml
automation:
  - alias: "Control Excel via Voice"
    trigger:
      platform: conversation
      command:
        - "create a budget spreadsheet"
    action:
      - service: shell_command.control_excel
        data:
          task: "{{ trigger.command }}"
```

## Contributing

Contributions are welcome! Areas for improvement:

- [ ] Multi-monitor support
- [ ] Image-based element detection (not just OCR)
- [ ] Recording and playback of action sequences
- [ ] Better error recovery
- [ ] Support for more applications (browsers, IDEs, etc.)
- [ ] Web-based control interface

## License

This project is part of the HAssistant suite. See main repository for license information.

## Support

For issues and questions:
- Check the troubleshooting section above
- Review existing GitHub issues
- Create a new issue with details about your setup and the problem
