# MediaMTX Webcam Streaming Setup

MediaMTX streams your main host's webcam to the K80 VM vision services over the network.

## Architecture

```
Main Host:
  Webcam (/dev/video0)
    ↓ (ffmpeg publishes)
  MediaMTX Container (RTSP server)
    ↓ (network stream)
K80 VM:
  realworld-gateway (pulls RTSP stream)
```

## Quick Start

### 1. Start MediaMTX Server

```bash
cd v2
docker-compose up -d mediamtx
```

**Ports exposed:**
- `8554` - RTSP (for vision services)
- `9997` - API
- `9998` - Metrics

_Note: HLS/WebRTC outputs are disabled in the bundled `mediamtx.yml` to eliminate on-box transcoding._

### 2. Start Webcam Stream

```bash
# On main host (where webcam is physically connected)
cd v2
./scripts/stream_webcam.sh
```

This publishes your webcam to: `rtsp://localhost:8554/webcam`

**Custom options:**
```bash
# Use different webcam
WEBCAM_DEVICE=/dev/video1 ./scripts/stream_webcam.sh

# Higher resolution
RESOLUTION=1280x720 FPS=30 ./scripts/stream_webcam.sh

# Stream to remote MediaMTX
MEDIAMTX_HOST=192.168.2.13 ./scripts/stream_webcam.sh
```

### 3. Test the Stream

**Option A: Test with ffplay**
```bash
ffplay rtsp://localhost:8554/webcam
```

**Option B: Test with VLC**
```
Media > Open Network Stream
URL: rtsp://localhost:8554/webcam
```

### 4. Configure K80 Vision Services

The K80 VM services can now pull frames from:
```
rtsp://192.168.2.13:8554/webcam  # Replace with your main host IP
```

## Test Pattern (No Webcam Required)

MediaMTX includes a built-in test pattern for testing without a physical webcam:

```bash
# View test pattern
ffplay rtsp://localhost:8554/test
```

## Troubleshooting

### Webcam not detected
```bash
# List available video devices
ls -l /dev/video*

# Check device capabilities
v4l2-ctl --list-devices
v4l2-ctl -d /dev/video0 --list-formats-ext
```

### Stream not working
```bash
# Check MediaMTX logs
docker logs hassistant_v2_mediamtx

# Check if port is open
nc -zv localhost 8554

# Test API
curl http://localhost:9997/v3/paths/list
```

### High CPU usage
Reduce resolution or FPS in `stream_webcam.sh`:
```bash
RESOLUTION=320x240 FPS=10 ./scripts/stream_webcam.sh
```

### K80 VM can't access stream
Make sure the network is reachable:
```bash
# From K80 VM
ping 192.168.2.13
curl http://192.168.2.13:8554  # Should get RTSP response
```

## Integration with K80 Vision Gateways

### realworld-gateway configuration

The gateway will need to be configured to pull from the RTSP stream. This can be done by:

1. **Environment variable** (in `vm-k80/docker-compose.yml`):
```yaml
realworld-gateway:
  environment:
    - CAMERA_URL=rtsp://192.168.2.13:8554/webcam
```

2. **Or polling script** that fetches frames periodically and posts to `/frame` endpoint

## Performance Tuning

### Low-latency settings (realtime monitoring)
```bash
FPS=30 RESOLUTION=640x480 ./scripts/stream_webcam.sh
```

### Bandwidth-efficient (motion detection)
```bash
FPS=5 RESOLUTION=320x240 ./scripts/stream_webcam.sh
```

### High-quality (recording/archive)
```bash
FPS=30 RESOLUTION=1920x1080 ./scripts/stream_webcam.sh
```

## Security Notes

- MediaMTX is running with `network_mode: host` for simplicity
- RTSP has no authentication by default (fine for local network)
- For production, enable authentication in `mediamtx.yml`
- Consider VPN or firewall rules if exposing outside local network

## API Examples

### List active streams
```bash
curl http://localhost:9997/v3/paths/list | jq
```

### Get stream metrics
```bash
curl http://localhost:9998/metrics
```

### Kick a stream
```bash
curl -X POST http://localhost:9997/v3/config/paths/kick/webcam
```

## Alternative: Use Frigate Instead

If you already have Frigate running, you can skip MediaMTX and use Frigate's RTSP restream feature:

```yaml
# In frigate config
go2rtc:
  streams:
    webcam:
      - /dev/video0
```

Then access via: `rtsp://localhost:8554/webcam`

---

**Status:** ✅ MediaMTX configured and ready
**Next:** Start the stream and configure K80 gateways to consume it
