# Quick Start Guide - Computer Control Agent

This guide will help you get started with the Computer Control Agent in minutes.

## Prerequisites

- Python 3.8 or higher
- Tesseract OCR
- HAssistant services running (optional, for remote control)

## Installation (5 minutes)

### 1. Install System Dependencies

**Ubuntu/Debian:**
```bash
sudo apt-get update
sudo apt-get install tesseract-ocr tesseract-ocr-eng
```

**macOS:**
```bash
brew install tesseract
```

**Windows:**
Download and install from: https://github.com/UB-Mannheim/tesseract/wiki

### 2. Install Python Dependencies

```bash
pip install -r computer_control_requirements.txt
```

### 3. Configure the Agent

```bash
# Copy example configuration
cp computer_control_agent.env.example computer_control_agent.env

# Edit if needed (defaults work for local control)
nano computer_control_agent.env
```

Key environment variables:

- `VISION_GATEWAY_URL` – HTTP endpoint for screenshots from the Vision Gateway service (defaults to `http://vision-gateway:8088`).
- `WINDOWS_VOICE_CONTROL_URL` – Optional HTTP bridge for routing actions through Windows Voice Control. Set this when running the agent in voice mode.

## First Test (2 minutes)

### Test 1: Check Installation

```bash
python computer_control_agent.py --info
```

Expected output:
```json
{
  "resolution": "1920x1080",
  "text_preview": "...",
  "text_length": 1234
}
```

### Test 2: Safe Mouse Movement

```bash
python computer_control_agent.py --task "Move mouse to center of screen"
```

This will:
1. Take a screenshot
2. Ask LLM to analyze
3. Prompt for confirmation (y/n)
4. Move the mouse safely

### Test 3: Simple Task

```bash
python computer_control_agent.py --task "Open notepad" --context "Windows desktop"
```

## Excel Example (5 minutes)

### 1. Open Excel

Open Microsoft Excel or LibreOffice Calc.

### 2. Run Excel Task

```bash
python computer_control_agent.py --excel --task "Create a simple budget spreadsheet with categories: Rent, Food, Transport, Entertainment"
```

The agent will:
1. Analyze the Excel window
2. Generate action steps
3. Ask for confirmation
4. Execute each action

### 3. More Excel Tasks

```bash
# Add headers
python computer_control_agent.py --excel --task "Add headers: Name, Email, Phone in row 1"

# Format cells
python computer_control_agent.py --excel --task "Make row 1 bold with yellow background"

# Add data
python computer_control_agent.py --excel --task "Add sample data in rows 2-5"
```

## Safety Tips

### Confirmation Mode (Recommended for First Use)

Keep `CONFIRM_BEFORE_ACTION=true` in your config. This shows each action before execution:

```
Execute click with params {'x': 100, 'y': 200}? (y/n):
```

### Failsafe

Move your mouse to the **top-left corner** of the screen to immediately abort execution.

### Disable Confirmation (Advanced)

For automated workflows, set in `computer_control_agent.env`:
```bash
CONFIRM_BEFORE_ACTION=false
```

## Example Script

Create a file `my_automation.py`:

```python
#!/usr/bin/env python3
from computer_control_agent import ComputerControlAgent

agent = ComputerControlAgent()

# Get screen info
info = agent.get_screen_info()
print(f"Working on {info['resolution']} screen")

# Simple task
success = agent.run_task(
    task="Open calculator and compute 25 * 4",
    context="Windows 10 desktop"
)

if success:
    print("Task completed!")
else:
    print("Task failed")
```

Run it:
```bash
python my_automation.py
```

## Common Use Cases

### 1. Data Entry
```bash
python computer_control_agent.py --excel --task "Fill cells A1 to A10 with numbers 1 to 10"
```

### 2. Web Browsing
```bash
python computer_control_agent.py --task "Open Chrome and search for 'Python automation'"
```

### 3. File Management
```bash
python computer_control_agent.py --task "Open File Explorer and create a folder named 'Projects'"
```

### 4. Text Editing
```bash
python computer_control_agent.py --task "Open Notepad, type 'Meeting Notes', and save as meeting.txt"
```

## Troubleshooting

### "Tesseract not found"
```bash
# Check installation
tesseract --version

# If missing, reinstall (Ubuntu):
sudo apt-get install tesseract-ocr
```

### "No module named 'pyautogui'"
```bash
pip install -r computer_control_requirements.txt
```

### "Actions not executing"
- Make sure target application has focus
- Check if confirmation mode is waiting for input
- Verify coordinates are correct for your screen resolution

### "LLM not responding"
```bash
# Check Ollama is running
curl http://localhost:11434/api/tags

# If not running, start Ollama service
```

## Next Steps

1. Read full documentation: [COMPUTER_CONTROL_AGENT.md](COMPUTER_CONTROL_AGENT.md)
2. Try the example script: `python example_computer_control.py`
3. Create custom automations for your workflow
4. Integrate with Home Assistant for voice control

## Integration with Home Assistant

Add to your Home Assistant `configuration.yaml`:

```yaml
shell_command:
  excel_task: "python3 /path/to/computer_control_agent.py --excel --task '{{ task }}'"
  computer_task: "python3 /path/to/computer_control_agent.py --task '{{ task }}'"
```

Then create automation:

```yaml
automation:
  - alias: "Voice Computer Control"
    trigger:
      platform: conversation
      command:
        - "computer [task]"
    action:
      - service: shell_command.computer_task
        data:
          task: "{{ trigger.command }}"
```

Now you can say: "Computer, open notepad"

## Support

- Documentation: [COMPUTER_CONTROL_AGENT.md](COMPUTER_CONTROL_AGENT.md)
- Examples: [example_computer_control.py](example_computer_control.py)
- Issues: GitHub Issues page

Happy automating! 🤖
