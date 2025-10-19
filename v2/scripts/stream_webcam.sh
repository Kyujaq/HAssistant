#!/bin/bash
# Stream USB webcam to MediaMTX (cam1)
# CPU-optimized: NVENC GPU encoding or ultrafast CPU fallback

set -e

HOST_IP="${HOST_IP:-localhost}"
WEBCAM_DEVICE="${WEBCAM_DEVICE:-/dev/video0}"
FPS="${FPS:-15}"
RESOLUTION="${RESOLUTION:-1280x720}"

echo "=== Streaming Webcam to MediaMTX ==="
echo "Video: $WEBCAM_DEVICE"
echo "Resolution: $RESOLUTION @ ${FPS}fps"
echo "Target: rtsp://$HOST_IP:8554/cam1"
echo ""

# Try NVENC first (GTX 1070/1080 Ti have it)
if ffmpeg -encoders 2>/dev/null | grep -q h264_nvenc; then
    echo "✅ Using NVENC (GPU encoding - near-zero CPU)"
    echo ""
    ffmpeg -f v4l2 -framerate "$FPS" -video_size "$RESOLUTION" -i "$WEBCAM_DEVICE" \
      -c:v h264_nvenc -preset p6 -b:v 2M -maxrate 2500k -bufsize 3M \
      -g $((FPS * 2)) -r "$FPS" -pix_fmt yuv420p \
      -f rtsp -rtsp_transport tcp \
      rtsp://$HOST_IP:8554/cam1
else
    echo "⚠️  NVENC not available, using CPU (ultrafast preset)"
    echo ""
    ffmpeg -f v4l2 -framerate "$FPS" -video_size "$RESOLUTION" -i "$WEBCAM_DEVICE" \
      -c:v libx264 -preset ultrafast -crf 26 -g $((FPS * 2)) -r "$FPS" \
      -pix_fmt yuv420p \
      -f rtsp -rtsp_transport tcp \
      rtsp://$HOST_IP:8554/cam1
fi
