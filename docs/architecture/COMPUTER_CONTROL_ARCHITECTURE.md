# Computer Control Agent Architecture

## Overview

The Computer Control Agent is a vision-based automation system that can control another computer using AI-powered decision making and OCR for screen understanding.

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                        USER INTERFACES                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐ │
│  │ Voice Input  │  │   CLI Tool   │  │  Home Assistant UI   │ │
│  │ (HA Assist)  │  │  (Terminal)  │  │     (Browser)        │ │
│  └──────┬───────┘  └──────┬───────┘  └──────────┬───────────┘ │
│         │                 │                      │             │
└─────────┼─────────────────┼──────────────────────┼─────────────┘
          │                 │                      │
          │                 │                      │
┌─────────▼─────────────────▼──────────────────────▼─────────────┐
│                   Home Assistant Core                           │
│  ┌────────────────────────────────────────────────────────────┐│
│  │ Conversation Agent (Ollama)                                ││
│  │ • Natural language understanding                           ││
│  │ • Intent parsing                                           ││
│  │ • Task decomposition                                       ││
│  └────────────────────────────────────────────────────────────┘│
│                           │                                     │
│  ┌────────────────────────▼────────────────────────────────┐  │
│  │ Automation / REST Command                               │  │
│  │ • Triggers computer control tasks                       │  │
│  │ • Passes task description to agent                      │  │
│  └────────────────────────────────────────────────────────┘  │
└─────────────────────────────┬───────────────────────────────────┘
                              │
                              │ HTTP POST
                              │ /webhook/task
                              │
┌─────────────────────────────▼───────────────────────────────────┐
│              HA Integration Bridge (Flask Server)               │
│  Port: 5555                                                     │
│  ┌────────────────────────────────────────────────────────────┐│
│  │ Endpoints:                                                 ││
│  │ • POST /webhook/task     - Execute task                   ││
│  │ • GET  /api/screen_info  - Get screen info                ││
│  │ • POST /api/execute_action - Single action               ││
│  │ • GET  /healthz          - Health check                   ││
│  └────────────────────────────────────────────────────────────┘│
└─────────────────────────────┬───────────────────────────────────┘
                              │
                              │
┌─────────────────────────────▼───────────────────────────────────┐
│            Computer Control Agent (Main Logic)                  │
│  ┌────────────────────────────────────────────────────────────┐│
│  │ ComputerControlAgent Class                                 ││
│  │ • Task planning and execution                              ││
│  │ • Action sequencing                                        ││
│  │ • Error handling                                           ││
│  │ • Safety checks                                            ││
│  └────────────────────────────────────────────────────────────┘│
│                                                                 │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐              │
│  │  Vision    │  │    AI      │  │  Control   │              │
│  │  System    │  │  Decision  │  │  System    │              │
│  └─────┬──────┘  └─────┬──────┘  └─────┬──────┘              │
└────────┼───────────────┼───────────────┼────────────────────────┘
         │               │               │
         │               │               │
┌────────▼──────┐ ┌──────▼──────┐ ┌─────▼──────────────────────┐
│ Screenshot    │ │   Ollama    │ │    PyAutoGUI               │
│ Capture       │ │   LLM       │ │    Mouse & Keyboard        │
│               │ │             │ │                            │
│ ┌───────────┐ │ │ ┌─────────┐ │ │ ┌────────────────────────┐ │
│ │Local:     │ │ │ │ Qwen3/  │ │ │ │ Actions:               │ │
│ │pyautogui  │ │ │ │ Hermes  │ │ │ │ • click(x, y)          │ │
│ │screenshot │ │ │ │         │ │ │ │ • type(text)           │ │
│ └───────────┘ │ │ │ Models  │ │ │ │ • press(key)           │ │
│               │ │ │         │ │ │ │ • hotkey(keys)         │ │
│ ┌───────────┐ │ │ └─────────┘ │ │ │ • scroll(amount)       │ │
│ │Remote:    │ │ │             │ │ │ • move(x, y)           │ │
│ │Vision     │ │ │ Analyzes    │ │ └────────────────────────┘ │
│ │Gateway    │ │ │ screenshots │ │                            │
│ │API        │ │ │ and plans   │ │ Target: Local Computer     │
│ └───────────┘ │ │ actions     │ │ or Remote via X11/VNC      │
└───────┬───────┘ └──────┬──────┘ └────────────────────────────┘
        │                │
        │                │
┌───────▼────────────────▼────────────────────────────────────────┐
│                    OCR & Image Analysis                         │
│  ┌────────────────────────────────────────────────────────────┐│
│  │ Tesseract OCR                                              ││
│  │ • Text extraction from screenshots                         ││
│  │ • Element location by text                                 ││
│  │ • Button/UI element detection                              ││
│  └────────────────────────────────────────────────────────────┘│
│                                                                 │
│  ┌────────────────────────────────────────────────────────────┐│
│  │ OpenCV / PIL                                               ││
│  │ • Image processing                                         ││
│  │ • Format conversion                                        ││
│  │ • Region of interest extraction                            ││
│  └────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────┘
```

## Component Details

### 1. User Interfaces

#### Voice Input (Home Assistant Assist)
- User says: "Computer, open Excel"
- HA processes speech → text
- Conversation agent interprets intent
- Triggers automation

#### CLI Tool
- Direct command execution
- Testing and debugging
- Batch processing
- Example: `python computer_control_agent.py --task "open notepad"`

#### Web Interface
- Home Assistant UI
- Manual task triggers
- Status monitoring
- Configuration management

### 2. Home Assistant Core

#### Conversation Agent
- Powered by Ollama (Qwen/Hermes models)
- Natural language understanding
- Context awareness via Letta Bridge
- Intent classification

#### Automation & REST Commands
```yaml
automation:
  - trigger: conversation
    action: rest_command.computer_control_task
```

### 3. HA Integration Bridge

**Flask Web Server** (port 5555)
- Receives HTTP webhooks from Home Assistant
- Validates requests
- Routes to Computer Control Agent
- Returns status and results

**Endpoints:**
- `POST /webhook/task` - Main task execution
- `GET /api/screen_info` - Get current screen state
- `POST /api/execute_action` - Execute single action
- `GET /healthz` - Service health check

### 4. Computer Control Agent

**Core Responsibilities:**
1. **Screenshot Analysis**
   - Capture screen (local or remote)
   - Extract text via OCR
   - Identify UI elements

2. **AI Decision Making**
   - Send screenshot + task to Ollama
   - Get action plan as JSON
   - Validate and parse actions

3. **Action Execution**
   - Execute mouse clicks
   - Type keyboard input
   - Press hotkeys
   - Scroll and navigate

4. **Safety & Error Handling**
   - Confirmation prompts (optional)
   - Action limits
   - Failsafe mechanisms
   - Error recovery

**Action Flow:**
```
Task → Screenshot → OCR → LLM Analysis → Action Plan → Execute → Verify
   ↑                                                              │
   └──────────────────── Loop if needed ────────────────────────┘
```

### 5. Vision System

#### Local Screenshot
- Uses `pyautogui.screenshot()`
- Captures entire screen
- Fast, direct access
- No network latency

#### Remote Screenshot (Vision Gateway)
- Fetches from vision-gateway API
- Supports multiple sources
- Can use webcam/HDMI capture
- Useful for monitoring remote systems

### 6. AI Decision Engine

**Ollama LLM Models:**
- **Qwen3**: Detailed analysis, complex tasks
- **Hermes3**: Fast responses, simple tasks

**Input to LLM:**
```json
{
  "screenshot": "base64_image",
  "task": "Open Excel and create budget",
  "screen_text": "OCR extracted text..."
}
```

**Output from LLM:**
```json
[
  {"type": "click", "params": {"x": 50, "y": 100}, "description": "Click Start"},
  {"type": "type", "params": {"text": "excel"}, "description": "Type Excel"},
  {"type": "press", "params": {"key": "enter"}, "description": "Press Enter"}
]
```

### 7. Control System (PyAutoGUI)

**Supported Actions:**
- **Mouse:** click, double_click, right_click, move, drag
- **Keyboard:** type, press, hotkey
- **Screen:** scroll, screenshot
- **Wait:** pause execution
- **Smart:** find_and_click (OCR-based)

**Safety Features:**
- Failsafe (move to corner to abort)
- Pause between actions
- Confirmation mode
- Action count limits

### 8. OCR & Image Analysis

**Tesseract OCR:**
- Extracts text from screenshots
- Locates UI elements by text
- Confidence scoring
- Multi-language support

**OpenCV/PIL:**
- Image preprocessing
- Format conversions (RGB/BGR)
- ROI extraction
- Base64 encoding for API transfer

## Data Flow Example

### Use Case: "Create Excel Budget"

1. **User speaks:** "Computer, create an Excel budget"

2. **Home Assistant:**
   - Whisper transcribes speech
   - Ollama interprets: "Open Excel and create a budget spreadsheet"
   - Triggers REST command

3. **HA Integration Bridge:**
   - Receives POST to `/webhook/task`
   - Payload: `{"task": "create excel budget", "excel": true}`
   - Forwards to agent

4. **Computer Control Agent:**
   - Takes screenshot
   - Runs OCR to see desktop
   - Sends to Ollama LLM

5. **Ollama LLM:**
   - Analyzes screenshot
   - Generates action plan:
     ```json
     [
       {"type": "find_and_click", "params": {"text": "Start"}},
       {"type": "type", "params": {"text": "excel"}},
       {"type": "press", "params": {"key": "enter"}},
       {"type": "wait", "params": {"duration": 2}},
       {"type": "hotkey", "params": {"keys": ["ctrl", "n"]}},
       ...
     ]
     ```

6. **Action Execution:**
   - Agent executes each action
   - Monitors for errors
   - Takes screenshots after key actions
   - Sends feedback to LLM if needed

7. **Verification:**
   - Final screenshot
   - OCR check for expected elements
   - Report success/failure to HA

## Deployment Options

### Option 1: Local Agent
```bash
python computer_control_agent.py --task "..."
```
- Direct execution
- Lowest latency
- Manual operation

### Option 2: Docker Container
```bash
docker compose up computer-control-agent
```
- Isolated environment
- Easy deployment
- Consistent configuration

### Option 3: HA Integration (Recommended)
```bash
python ha_integration.py
```
- Voice control enabled
- Automation triggers
- Full integration with smart home

## Security Considerations

1. **Authentication:** Webhook secret for HA integration
2. **Confirmation Mode:** Optional approval for each action
3. **Action Limits:** Maximum actions per task
4. **Failsafe:** Emergency abort (mouse to corner)
5. **Network:** Run on isolated network or localhost only

## Performance

- **Screenshot capture:** ~50ms (local), ~200ms (remote)
- **OCR processing:** ~300-500ms
- **LLM inference:** ~1-3s (depending on model)
- **Action execution:** ~500ms per action (with pause)
- **Total for simple task:** 5-10 seconds
- **Excel complex task:** 30-60 seconds

## Limitations

1. **Screen resolution dependent:** Coordinates vary by display
2. **Application state:** Assumes expected UI is visible
3. **No pixel-perfect clicking:** Uses OCR text matching
4. **Sequential only:** Actions run one at a time
5. **Local execution:** Cannot control multiple computers simultaneously

## Future Enhancements

- [ ] Multi-monitor support
- [ ] Image-based element detection (not just OCR)
- [ ] Action recording and playback
- [ ] Parallel execution on multiple machines
- [ ] Web-based control interface
- [ ] Browser-specific automation (Selenium integration)
- [ ] Mobile device control support
