# Crew Orchestrator - Execution Loop Documentation

## Overview

The crew-orchestrator v2.0 now includes a full execution loop that:
1. **Plans** - Uses Ollama LLM to break down high-level goals into steps
2. **Executes** - Sends voice commands via Windows Voice Assistant
3. **Verifies** - Uses vision to confirm each step succeeded
4. **Adapts** - Intelligently skips verification for rapid actions (typing, quick keys)

## Endpoints

### `/crew/task/kickoff` (Planning Only)
Returns just the plan without executing it.

**Use case**: Preview what the system will do before executing.

```bash
curl -X POST http://localhost:8085/crew/task/kickoff \
  -H "Content-Type: application/json" \
  -d '{"goal": "Open Notepad and type hello", "application": "Notepad"}'
```

**Response:**
```json
{
  "status": "success",
  "application": "Notepad",
  "goal": "Open Notepad and type hello",
  "result": "Step 1: voice_command='Open Notepad' verification='Is Notepad visible?'\nStep 2: voice_command='Type hello' verification='...'",
  "note": "This is the PLAN. Execution with verification loop is next phase."
}
```

### `/crew/task/execute` (Full Execution) ⭐ NEW

Generates plan, executes each step, and verifies results.

**Use case**: "Just do it" - full autonomous execution with vision verification.

```bash
curl -X POST http://localhost:8085/crew/task/execute \
  -H "Content-Type: application/json" \
  -d '{"goal": "Create a draft email about the Q4 budget meeting in Notepad", "application": "Notepad"}'
```

**Response:**
```json
{
  "status": "completed",
  "application": "Notepad",
  "goal": "Create a draft email...",
  "summary": {
    "total_steps": 5,
    "completed": 4,
    "failed": 1,
    "success_rate": "80.0%"
  },
  "steps": [
    {
      "step": 1,
      "voice_command": "Open Notepad",
      "verification_query": "Is Notepad window visible?",
      "status": "verified",
      "execution_result": "✅ Voice command executed: 'Open Notepad'",
      "verification_result": "Yes, Notepad is visible"
    },
    {
      "step": 2,
      "voice_command": "Type Subject: Q4 Budget Meeting",
      "status": "completed",
      "execution_result": "✅ Voice command executed: 'Type Subject...'"
    }
  ],
  "execution_log": [...],
  "raw_plan": "..."
}
```

## Intelligent Verification Skipping

The system automatically skips verification for rapid actions to avoid interrupting the flow:

**Skip verification for:**
- `type` commands (typing text)
- `press enter` (quick keystrokes)
- `press tab` (navigation keys)

**Always verify for:**
- Opening applications
- Clicking menus/buttons
- Major UI changes

## Example Use Cases

### Simple Task
```json
{
  "goal": "Open Notepad",
  "application": "Notepad"
}
```

### Complex Multi-Step Task
```json
{
  "goal": "Create an Excel spreadsheet with Q1 sales data: Product A sold 100 units, Product B sold 150 units, calculate total",
  "application": "Excel"
}
```

The system will:
1. Open Excel
2. Click cell A1
3. Type "Product"
4. Press Tab
5. Type "Units"
6. Press Enter
7. Type "Product A"
8. ... (continues automatically)

### Email Draft
```json
{
  "goal": "Create a draft email about the team meeting tomorrow at 2pm in conference room B. Include agenda: project updates, budget review, Q&A",
  "application": "Notepad"
}
```

## Integration with Home Assistant

### REST Command Setup

Add to `configuration.yaml`:

```yaml
rest_command:
  crew_execute:
    url: "http://hassistant-crew-orchestrator:8085/crew/task/execute"
    method: POST
    content_type: "application/json"
    payload: '{"goal": "{{ goal }}", "application": "{{ application }}"}'
    timeout: 300  # 5 minutes for complex tasks

  crew_plan:
    url: "http://hassistant-crew-orchestrator:8085/crew/task/kickoff"
    method: POST
    content_type: "application/json"
    payload: '{"goal": "{{ goal }}", "application": "{{ application }}"}'
```

### Automation Examples

#### Voice-Triggered Automation

```yaml
automation:
  - alias: "PC Control: Execute Task"
    trigger:
      - platform: conversation
        command:
          - "create {task} in {application}"
          - "make {task} in {application}"
    action:
      - service: rest_command.crew_execute
        data:
          goal: "{{ trigger.slots.task }}"
          application: "{{ trigger.slots.application }}"
      - service: notify.mobile_app
        data:
          message: "Started: {{ trigger.slots.task }}"
```

**Usage:**
> "Hey, create a draft email about the project deadline in Notepad"
> "Hey, make a spreadsheet with sales data in Excel"

#### Script for Recurring Tasks

```yaml
script:
  create_daily_report:
    sequence:
      - service: rest_command.crew_execute
        data:
          goal: "Create a daily report with today's date, list 3 tasks completed, and notes section"
          application: "Notepad"
```

## Architecture

```
┌─────────────────────────────────────────────┐
│         Home Assistant / User               │
│              (Voice/API)                    │
└─────────────┬───────────────────────────────┘
              │
              ↓
┌─────────────────────────────────────────────┐
│      Crew Orchestrator (FastAPI)            │
│  ┌────────────────────────────────────────┐ │
│  │  1. Planner Agent                      │ │
│  │     (Ollama Qwen 4B)                   │ │
│  │     → Breaks goal into steps           │ │
│  └────────────────────────────────────────┘ │
│  ┌────────────────────────────────────────┐ │
│  │  2. Execution Loop                     │ │
│  │     For each step:                     │ │
│  │     ├─ Execute voice command           │ │
│  │     ├─ Wait 2 seconds                  │ │
│  │     └─ Verify (if not rapid action)    │ │
│  └────────────────────────────────────────┘ │
└──────┬─────────────────────────────┬────────┘
       │                             │
       ↓                             ↓
┌──────────────┐            ┌─────────────────┐
│ Voice Tool   │            │  Vision Tool    │
│ (Windows)    │            │  (Gateway)      │
└──────┬───────┘            └────────┬────────┘
       │                             │
       ↓                             ↓
┌──────────────┐            ┌─────────────────┐
│ Piper TTS    │            │  Qwen Vision    │
│ (GLaDOS)     │            │  (Screenshot    │
└──────┬───────┘            │   Analysis)     │
       │                    └─────────────────┘
       ↓
┌──────────────┐
│ USB Audio    │
│ (to Windows) │
└──────────────┘
```

## Troubleshooting

### Issue: Steps not being parsed

**Symptom:** Returns "Could not parse plan into executable steps"

**Solution:** The LLM didn't follow the format. Check `raw_plan` in response. May need to adjust prompt or use different model.

### Issue: Voice commands timing out

**Symptom:** Execution log shows timeout errors

**Solution:**
- Check Piper TTS is running: `docker ps | grep piper`
- Check audio device: `docker exec hassistant-windows-voice-control aplay -L`
- Verify USB audio cable (needs TRRS 4-ring for mic input)

### Issue: Verification always fails

**Symptom:** All steps show `failed_verification`

**Solution:**
- Check vision-gateway is running: `curl http://vision-gateway:8088/healthz`
- Verify HDMI capture is connected
- Check if Windows screen is visible to vision system

## Performance

**Typical execution times:**
- Planning: 5-15 seconds (depends on LLM and task complexity)
- Per step execution: 2-5 seconds (voice command + wait + verification)
- Simple task (3 steps): ~15-30 seconds
- Complex task (10 steps): ~1-2 minutes

## Next Steps / Future Enhancements

- [ ] Retry logic for failed steps
- [ ] Parallel execution for independent steps
- [ ] Learning from past executions
- [ ] Dynamic wait times based on action type
- [ ] Screenshot capture on failures for debugging
- [ ] Support for mouse/keyboard direct control fallback
- [ ] Multi-application workflows (Excel → Email → Browser)

## Testing

### Test Plan Generation Only
```bash
curl -X POST http://localhost:8085/crew/task/kickoff \
  -H "Content-Type: application/json" \
  -d '{"goal": "Open Notepad", "application": "Notepad"}'
```

### Test Full Execution (After Audio Cable Arrives!)
```bash
curl -X POST http://localhost:8085/crew/task/execute \
  -H "Content-Type: application/json" \
  -d '{"goal": "Open Notepad and type Hello World", "application": "Notepad"}'
```

## Version History

**v2.0.0** (Current)
- ✅ Full execution loop with voice + vision
- ✅ Intelligent verification skipping
- ✅ Structured step parsing
- ✅ Detailed execution logs

**v1.0.0**
- ✅ Planning-only endpoint
- ✅ Basic crew setup
