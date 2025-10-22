# Crew Orchestrator Port Change

## Issue
Port 8084 was already in use by the `overnight` service.

## Solution
Changed crew-orchestrator to use **port 8085** instead.

## Updated Configuration

**docker-compose.yml**:
```yaml
crew-orchestrator:
  environment:
    - PORT=8085  # Changed from 8084
  ports:
    - "8085:8085"  # Changed from 8084:8084
```

## Testing Commands (Updated)

**Health Check**:
```bash
curl http://localhost:8085/healthz
```

**Kickoff Task**:
```bash
curl -X POST http://localhost:8085/crew/task/kickoff \
  -H "Content-Type: application/json" \
  -d '{
    "goal": "Open Notepad and type Hello World",
    "application": "Notepad"
  }'
```

## Files to Update

If following guides, replace port 8084 with **8085** in:
- ✅ docker-compose.yml (already updated)
- ⚠️ QUICKSTART.md (needs update)
- ⚠️ PC_CONTROL_TESTING_GUIDE.md (needs update)
- ⚠️ CREW_ORCHESTRATOR_SUMMARY.md (needs update)

**Note**: Build is currently in progress with import fix (`crewai.tools.BaseTool` instead of `crewai_tools.BaseTool`)
