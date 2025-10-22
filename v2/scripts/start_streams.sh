#!/bin/bash
# Start both webcam and screen streams in background
# Use systemd or supervisord for production

set -e

SCRIPT_DIR="$(dirname "$0")"
SCREEN_CAPTURE_DEVICE="${SCREEN_CAPTURE_DEVICE:-/dev/video2}"
SCREEN_CAPTURE_INPUT_FORMAT="${SCREEN_CAPTURE_INPUT_FORMAT:-mjpeg}"

echo "=== Starting MediaMTX Streams ==="

# Check if MediaMTX is running
if ! docker ps | grep -q hassistant_v2_mediamtx; then
    echo "❌ MediaMTX container not running!"
    echo "Start it first: cd v2 && docker-compose up -d mediamtx"
    exit 1
fi

echo "✅ MediaMTX is running"
echo ""

# Start webcam stream in background
if [ -e /dev/video0 ]; then
    echo "Starting webcam stream (cam1)..."
    "$SCRIPT_DIR/stream_webcam.sh" > /tmp/stream_webcam.log 2>&1 &
    WEBCAM_PID=$!
    echo "  PID: $WEBCAM_PID"
    echo "  Log: /tmp/stream_webcam.log"
else
    echo "⚠️  Webcam /dev/video0 not found, skipping"
fi

echo ""

# Start screen stream in background
if { [ -n "$DISPLAY" ] || { [ -n "$SCREEN_CAPTURE_DEVICE" ] && [ -e "$SCREEN_CAPTURE_DEVICE" ]; }; }; then
    echo "Starting screen capture stream (screen)..."
    echo "  Device: ${SCREEN_CAPTURE_DEVICE:-'(using X11)'}"
    SCREEN_CAPTURE_DEVICE="$SCREEN_CAPTURE_DEVICE" \
    SCREEN_CAPTURE_INPUT_FORMAT="$SCREEN_CAPTURE_INPUT_FORMAT" \
    DISPLAY="${DISPLAY}" \
    "$SCRIPT_DIR/stream_screen.sh" > /tmp/stream_screen.log 2>&1 &
    SCREEN_PID=$!
    echo "  PID: $SCREEN_PID"
    echo "  Log: /tmp/stream_screen.log"
else
    echo "⚠️  No screen capture device or DISPLAY available, skipping screen capture"
fi

echo ""
echo "=== Streams Started ==="
echo ""
echo "View streams (RTSP):"
echo "  Webcam:  ffplay rtsp://localhost:8554/cam1"
echo "  Screen:  ffplay rtsp://localhost:8554/screen"
echo ""
echo "Stop streams:"
echo "  pkill -f ffmpeg"
echo ""
echo "Check logs:"
echo "  tail -f /tmp/stream_webcam.log"
echo "  tail -f /tmp/stream_screen.log"
