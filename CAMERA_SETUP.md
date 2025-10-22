# Camera Setup Guide

## Architecture Overview

```
Raw Feeds → MediaMTX (RTSP Server) → K80 VM Services → Home Assistant (MJPEG)
```

1. **MediaMTX** (main system, v2 stack): RTSP relay server at port 8554
2. **K80 VM** (192.168.122.71): Processes RTSP feeds, outputs MJPEG
3. **Home Assistant**: Displays processed MJPEG streams

---

## Part 1: Add MJPEG Cameras in Home Assistant

**Important**: Home Assistant no longer supports YAML configuration for MJPEG cameras. You must add them via the UI.

### Step 1: Access Integration Settings
1. Open Home Assistant web interface
2. Go to **Settings → Devices & Services**
3. Click **+ ADD INTEGRATION** (bottom right)
4. Search for **MJPEG Camera**

### Step 2: Add Vision Screen Stream
1. Click **MJPEG Camera** integration
2. Fill in the form:
   - **MJPEG URL**: `http://192.168.122.71:8051/mjpeg/screen`
   - **Still Image URL** (optional): `http://192.168.122.71:8051/frames/latest.jpg`
   - **Name**: `Vision Screen Stream`
3. Click **Submit**

### Step 3: Add Vision Realworld Stream
1. Repeat the process:
   - **MJPEG URL**: `http://192.168.122.71:8052/mjpeg/cam`
   - **Still Image URL** (optional): `http://192.168.122.71:8052/frames/latest.jpg`
   - **Name**: `Vision Realworld Stream`
2. Click **Submit**

### Viewing the Cameras
- **Dashboard**: Navigate to **Vision Signals** dashboard (should auto-update with new camera entities)
- **Direct**: Settings → Devices & Services → MJPEG Camera → Click on each camera
- **Developer Tools**: Settings → Developer Tools → States → Filter for `camera.`

---

## Part 2: Push RTSP Streams to MediaMTX

The K80 VM services pull RTSP streams from MediaMTX. You need to publish feeds to MediaMTX first.

### MediaMTX Configuration
MediaMTX is already configured in `v2/mediamtx.yml` with two stream paths:
- `cam1` - Webcam stream
- `screen` - Screen capture stream

**RTSP Server**: `rtsp://localhost:8554`

### Option A: Push Webcam Stream with FFmpeg

From your main system, publish a webcam to MediaMTX:

```bash
# Find your webcam device
ls -la /dev/video*

# Push webcam to MediaMTX (example using /dev/video0)
ffmpeg -f v4l2 -i /dev/video0 \
  -c:v libx264 -preset ultrafast -tune zerolatency \
  -f rtsp rtsp://localhost:8554/cam1
```

**To run in background**:
```bash
nohup ffmpeg -f v4l2 -i /dev/video0 \
  -c:v libx264 -preset ultrafast -tune zerolatency \
  -f rtsp rtsp://localhost:8554/cam1 \
  > /tmp/ffmpeg_cam1.log 2>&1 &
```

### Option B: Push Screen Capture with FFmpeg

Capture your desktop and stream to MediaMTX:

```bash
# X11 screen capture (Linux)
ffmpeg -f x11grab -video_size 1920x1080 -i :0.0 \
  -c:v libx264 -preset ultrafast -tune zerolatency \
  -f rtsp rtsp://localhost:8554/screen

# Or use specific display
ffmpeg -f x11grab -video_size 1920x1080 -i :0.0+0,0 \
  -c:v libx264 -preset ultrafast -tune zerolatency \
  -f rtsp rtsp://localhost:8554/screen
```

**To run in background**:
```bash
nohup ffmpeg -f x11grab -video_size 1920x1080 -i :0.0 \
  -c:v libx264 -preset ultrafast -tune zerolatency \
  -f rtsp rtsp://localhost:8554/screen \
  > /tmp/ffmpeg_screen.log 2>&1 &
```

### Option C: Use Existing HDMI Capture Device

If you have a UGREEN HDMI capture dongle (e.g., `/dev/video2`):

```bash
# Push HDMI capture to MediaMTX
ffmpeg -f v4l2 -i /dev/video2 \
  -c:v libx264 -preset ultrafast -tune zerolatency \
  -f rtsp rtsp://localhost:8554/screen
```

### Verify Streams are Publishing

Check MediaMTX API:
```bash
# List active streams
curl http://localhost:9997/v3/paths/list

# Check specific path
curl http://localhost:9997/v3/paths/get/cam1
curl http://localhost:9997/v3/paths/get/screen
```

Or use VLC to test:
```bash
vlc rtsp://localhost:8554/cam1
vlc rtsp://localhost:8554/screen
```

---

## Part 3: Verify End-to-End Pipeline

### On Main System (MediaMTX Host)
1. Start MediaMTX: `docker compose -f v2/docker-compose.yml up -d mediamtx`
2. Push streams (see Part 2 above)
3. Verify: `curl http://localhost:9997/v3/paths/list`

### On K80 VM
1. Ensure vision services are running:
   ```bash
   # SSH to VM
   ssh user@192.168.122.71

   # Check services
   docker ps | grep -E "vision-gateway|realworld-gateway"
   ```

2. Check if VM is pulling streams:
   ```bash
   # Check vision-gateway logs
   docker logs vision-gateway

   # Check if MJPEG endpoint works
   curl -I http://localhost:8051/mjpeg/screen
   curl -I http://localhost:8052/mjpeg/cam
   ```

3. From main system, test VM endpoints:
   ```bash
   curl -I http://192.168.122.71:8051/mjpeg/screen
   curl -I http://192.168.122.71:8052/mjpeg/cam
   ```

### In Home Assistant
1. Go to **Vision Signals** dashboard
2. You should see live video from both cameras
3. Or navigate to Settings → Devices & Services → MJPEG Camera

---

## Troubleshooting

### Cameras show "Unavailable" in HA
- Check VM services are running: `ssh user@192.168.122.71 'docker ps'`
- Verify network connectivity: `curl http://192.168.122.71:8051/health`
- Check HA logs: `docker compose logs homeassistant | grep mjpeg`

### VM not receiving RTSP streams
- Verify MediaMTX is running: `docker ps | grep mediamtx`
- Check streams are published: `curl http://localhost:9997/v3/paths/list`
- Test RTSP locally: `vlc rtsp://localhost:8554/cam1`

### No video in MediaMTX
- Check FFmpeg is running: `ps aux | grep ffmpeg`
- Review FFmpeg logs: `tail -f /tmp/ffmpeg_*.log`
- Verify device permissions: `ls -la /dev/video*`

---

## Summary

**Stream Flow**:
1. **Publish** raw video to MediaMTX (RTSP) using FFmpeg
2. **K80 VM** pulls RTSP, processes with GPU, outputs MJPEG
3. **Home Assistant** displays MJPEG streams via UI-configured cameras

**Key URLs**:
- MediaMTX RTSP: `rtsp://localhost:8554/{cam1|screen}`
- MediaMTX API: `http://localhost:9997/v3/`
- Vision Screen: `http://192.168.122.71:8051/mjpeg/screen`
- Vision Realworld: `http://192.168.122.71:8052/mjpeg/cam`
