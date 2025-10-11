# Crew Orchestrator - Quick Start Guide

Get the multi-agent PC control system running in 5 minutes!

## Prerequisites

✅ USB audio dongle connected (hw:1,0)
✅ 3.5mm cable: USB dongle → Windows PC mic
✅ Windows Voice Assistant enabled and listening
✅ Piper TTS service running
✅ Vision Gateway running

## Step 1: Enable Crew Orchestrator

```bash
cd /home/qjaq/HAssistant

# Edit docker-compose.yml
nano docker-compose.yml

# Find "crew-orchestrator" section and uncomment all lines
# (Remove the # from lines 474-500)

# Save and exit (Ctrl+X, Y, Enter)
```

## Step 2: Build and Start

```bash
# Build the crew orchestrator image
docker compose build crew-orchestrator

# Start the service
docker compose up -d crew-orchestrator

# Check status
docker compose ps | grep crew
# Should show: hassistant-crew-orchestrator running

# Check health
curl http://localhost:8084/healthz
# Should return: {"ok":true,"service":"crew-orchestrator",...}
```

## Step 3: Test Basic Windows Voice Control

First, verify voice control works without crew:

```bash
cd /home/qjaq/HAssistant/clients
python3 windows_voice_control.py "Open Notepad"
```

**On Windows**: Watch for Notepad to open
✅ If it works → proceed to Step 4
❌ If not → check PC_CONTROL_TESTING_GUIDE.md

## Step 4: Test Crew Orchestrator (Planning Only)

Test the planner agent:

```bash
curl -X POST http://localhost:8084/crew/task/kickoff \
  -H "Content-Type: application/json" \
  -d '{
    "goal": "Open Notepad and type Hello World",
    "application": "Notepad"
  }'
```

**Expected Response**:
```json
{
  "status": "success",
  "application": "Notepad",
  "goal": "Open Notepad and type Hello World",
  "result": "Step 1: voice_command='Open Notepad', verification='Is Notepad open?'\nStep 2: voice_command='Type Hello World', verification='Does Notepad contain text?'",
  "note": "This is the PLAN. Execution with verification loop is next phase."
}
```

✅ If you see a plan → Planner is working!

## Step 5: Test with Different Applications

### Excel Test
```bash
curl -X POST http://localhost:8084/crew/task/kickoff \
  -H "Content-Type: application/json" \
  -d '{
    "goal": "Create a new spreadsheet with headers Name, Age, Email",
    "application": "Excel"
  }'
```

### Chrome Test
```bash
curl -X POST http://localhost:8084/crew/task/kickoff \
  -H "Content-Type: application/json" \
  -d '{
    "goal": "Open Chrome and navigate to github.com",
    "application": "Chrome"
  }'
```

### Calculator Test
```bash
curl -X POST http://localhost:8084/crew/task/kickoff \
  -H "Content-Type: application/json" \
  -d '{
    "goal": "Open Calculator and add 5 plus 3",
    "application": "Calculator"
  }'
```

## Step 6: Check Vision Gateway Integration

Verify vision gateway is providing data:

```bash
# Check recent detections
curl http://localhost:8088/api/detections | python3 -m json.tool

# Should show recent HDMI capture detections (if dongle connected)
```

## Troubleshooting

### Service won't start
```bash
# Check logs
docker logs hassistant-crew-orchestrator --tail 50

# Common issues:
# - Missing dependencies → Check requirements.txt
# - Port 8084 in use → Change PORT in docker-compose.yml
# - Can't import shared modules → Check volume mounts
```

### Planning returns empty/errors
```bash
# Verify Ollama is accessible
curl http://localhost:11434/api/tags

# Check CrewAI can initialize
docker exec hassistant-crew-orchestrator python -c "from crewai import Agent; print('OK')"
```

### Voice commands don't execute
```bash
# Test voice control directly
cd /home/qjaq/HAssistant/clients
python3 windows_voice_control.py "Test command"

# If that works but crew doesn't, check shared/voice.py import
docker exec hassistant-crew-orchestrator python -c "from shared.voice import WindowsVoiceExecutor; print('OK')"
```

## What's Next?

Once basic testing works:

1. **Enable Full Execution Loop** - Currently only plans, needs execution phase
2. **Add Error Recovery** - Retry failed steps automatically
3. **Integrate with Home Assistant** - Trigger via voice commands
4. **Add Task History** - Track what worked/failed
5. **Expand Verification** - More sophisticated vision checks

## Architecture Diagram

```
┌─────────────┐
│  You send   │  POST /crew/task/kickoff
│    goal     │  {"goal": "...", "application": "Excel"}
└──────┬──────┘
       │
┌──────▼──────────────────────────────────────────┐
│          Crew Orchestrator (3 Agents)           │
│                                                  │
│  1. Planner: Breaks goal into steps             │
│     → Step 1: "Open Excel" + "Is Excel open?"   │
│     → Step 2: "Click A1" + "Is A1 selected?"    │
│                                                  │
│  2. Action Agent: Executes voice commands       │
│     → Calls windows_voice_control.py             │
│     → TTS → USB audio → Windows Voice Assistant │
│                                                  │
│  3. Verifier: Checks using Vision Gateway       │
│     → Queries detections cache                   │
│     → Confirms action succeeded                  │
│                                                  │
└─────────┬────────────┬───────────────────────────┘
          │            │
    ┌─────▼────┐  ┌────▼────────┐
    │ Windows  │  │   Vision    │
    │  Voice   │  │  Gateway    │
    │ Control  │  │  (cache)    │
    └──────────┘  └─────────────┘
```

## Success Criteria

You'll know it's working when:

✅ Health check returns OK
✅ Planning creates step-by-step plans
✅ Plans are application-specific (mentions Excel/Chrome/etc.)
✅ Voice commands execute (Notepad opens, etc.)
✅ Vision gateway provides detection data
✅ No errors in `docker logs hassistant-crew-orchestrator`

## Need Help?

- **Full Testing Guide**: `/home/qjaq/HAssistant/docs/PC_CONTROL_TESTING_GUIDE.md`
- **Architecture Details**: `/home/qjaq/HAssistant/services/crew-orchestrator/README.md`
- **Vision Gateway Docs**: `/home/qjaq/HAssistant/services/vision-gateway/`
- **Windows Voice Control**: `/home/qjaq/HAssistant/clients/windows_voice_control.py`

Happy automating! 🤖
