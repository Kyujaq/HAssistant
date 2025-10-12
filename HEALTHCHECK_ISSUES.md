# Health Check Issues - Summary

## ✅ FIXED: crew-orchestrator

**Problem**: Health check was checking wrong port (8084 instead of 8085)
**Solution**: Updated docker-compose.yml health check to port 8085
**Status**: ✅ **HEALTHY**

## ⚠️ ISSUE: overnight & kitchen-api

**Problem**: Both containers report "unhealthy" even though services work fine
**Root Cause**: `curl` command not found in containers

**Evidence**:
```bash
$ curl http://localhost:8084/healthz
{"status":"ok"}  ✅ Works from host

$ docker exec hassistant-overnight curl -f http://localhost:8000/healthz
exec: "curl": executable file not found in $PATH  ❌ Fails inside container
```

**Why They're Unhealthy**:
Both use `CMD curl -f http://localhost:XXXX/healthz` but curl isn't installed in Python slim images.

## 🔧 Solutions (Pick One)

### Option 1: Use Python for Health Check (Recommended)
Update their Dockerfiles to use Python instead of curl:

**For overnight**:
```yaml
healthcheck:
  test: ["CMD", "python", "-c", "import requests; requests.get('http://localhost:8000/healthz', timeout=5).raise_for_status()"]
```

**For kitchen-api**:
```yaml
healthcheck:
  test: ["CMD", "python", "-c", "import requests; requests.get('http://localhost:8083/healthz', timeout=5).raise_for_status()"]
```

### Option 2: Install curl in Dockerfiles
Add to their Dockerfiles:
```dockerfile
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*
```

### Option 3: Remove Health Checks
If health checks aren't critical, just remove them from docker-compose.yml.

## 📊 Current Status

| Service | Status | Port | Issue |
|---------|--------|------|-------|
| crew-orchestrator | ✅ healthy | 8085 | Fixed |
| overnight | ⚠️ unhealthy | 8084 | curl missing |
| kitchen-api | ⚠️ unhealthy | 8083 | curl missing |

## 🎯 Recommendation

**Option 1** (Python health checks) is best because:
- No need to install extra packages (curl)
- Smaller image size
- Both services already have `requests` library installed
- Consistent with crew-orchestrator approach

## 📝 Quick Fix Commands

If you want to fix them right now:

1. Find their healthcheck definitions in docker-compose.yml
2. Replace `curl` with Python (see Option 1 above)
3. Rebuild/restart: `docker compose up -d overnight kitchen-api`

**Note**: Both services are **functionally working** - they're just reporting unhealthy because the health check command fails. This is a monitoring/reporting issue, not a service issue.
