# MediaMTX Streaming Setup - CPU-Optimized

Stream webcam and screen from main host to K80 VM with minimal CPU usage.

## Key Optimizations ✅

- **HLS/WebRTC disabled** - No expensive encoding in MediaMTX
- **NVENC GPU encoding** - Uses GTX 1070/1080 Ti (near-zero CPU)
- **On-demand streaming** - Only streams when K80 VM requests
- **No audio encoding** - ffmpeg scripts don't capture/encode audio
- **Low FPS** - 8-15fps for screen, 15fps for webcam

## Quick Start

### 1. Start MediaMTX (RTSP relay only)

```bash
cd v2
docker-compose up -d mediamtx
docker logs hassistant_v2_mediamtx  # Verify it started
```

### 2. Start Streams

**Option A: Start both (recommended)**
```bash
./scripts/start_streams.sh
```

**Option B: Individual streams**
```bash
# Webcam (will use NVENC if available)
./scripts/stream_webcam.sh

# Screen capture (another terminal)
./scripts/stream_screen.sh
```

### 3. Verify

**Check MediaMTX API:**
```bash
curl http://localhost:9997/v3/paths/list
```

**Test stream (requires ffplay/VLC):**
```bash
ffplay rtsp://localhost:8554/cam1
ffplay rtsp://localhost:8554/screen
```

## K80 VM Access

The K80 VM consumes streams at (replace with your host IP):

```
rtsp://192.168.2.13:8554/cam1     # Webcam
rtsp://192.168.2.13:8554/screen   # Screen
```

**Note:** Streams start on-demand when K80 VM connects!

## Ports

| Port | Service | Notes |
|------|---------|-------|
| 8554 | RTSP | Only protocol enabled (no HLS/WebRTC) |
| 9997 | API | MediaMTX control |
| 9998 | Metrics | Prometheus metrics |

## CPU Usage

**Expected CPU usage per stream:**

| Encoder | Webcam 720p15 | Screen 720p8 |
|---------|---------------|--------------|
| NVENC (GPU) | ~5% CPU | ~3% CPU |
| libx264 ultrafast | ~15-20% CPU | ~10-15% CPU |

**Before optimizations:** 125% CPU (HLS encoding)  
**After optimizations:** <10% CPU (NVENC) or ~25% CPU (ultrafast)

## Tuning

### Lower quality (save bandwidth/CPU)
```bash
# Webcam: 480p @ 10fps
RESOLUTION=640x480 FPS=10 ./scripts/stream_webcam.sh

# Screen: 480p @ 5fps
VIDEO_SIZE=640x480 FRAMERATE=5 ./scripts/stream_screen.sh
```

### Higher quality (use if CPU allows)
```bash
# Webcam: 1080p @ 30fps (NVENC only!)
RESOLUTION=1920x1080 FPS=30 ./scripts/stream_webcam.sh
```

## Troubleshooting

### Check if NVENC is available
```bash
ffmpeg -encoders | grep nvenc
# Should see: h264_nvenc (if GPU supports it)
```

### High CPU despite NVENC
- Check MediaMTX isn't re-encoding (it shouldn't with this config)
- Verify HLS/WebRTC are disabled: `curl localhost:9997/v3/config/global | jq`

### Webcam not found
```bash
ls -l /dev/video*
# Add user to video group if needed:
# sudo usermod -aG video $USER
```

### Screen capture permission denied
```bash
xhost +local:
```

### K80 VM can't connect
```bash
# From K80 VM
ping 192.168.2.13
telnet 192.168.2.13 8554
```

## Files

- `v2/mediamtx.yml` - Config (HLS/WebRTC disabled, on-demand)
- `v2/scripts/stream_webcam.sh` - NVENC/ultrafast webcam
- `v2/scripts/stream_screen.sh` - NVENC/ultrafast screen
- `v2/scripts/start_streams.sh` - Start both

## Next Steps

1. **Start MediaMTX:** `docker-compose up -d mediamtx`
2. **Start streams:** `./scripts/start_streams.sh`
3. **Configure K80 gateways** to pull from rtsp://HOST_IP:8554/cam1 and /screen
4. **Monitor CPU:** `htop` (should be <10% with NVENC)

---

**Status:** ✅ CPU-optimized streaming ready (NVENC + RTSP-only)
