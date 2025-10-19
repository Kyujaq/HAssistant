#!/bin/bash
# Stream X11 screen capture to MediaMTX (screen)
# CPU-optimized: NVENC preferred, ultrafast CPU fallback

set -e

HOST_IP="${HOST_IP:-localhost}"
VIDEO_SIZE="${VIDEO_SIZE:-1280x720}"
FRAMERATE="${FRAMERATE:-8}"
CAPTURE_DEVICE="${SCREEN_CAPTURE_DEVICE:-}"
CAPTURE_INPUT_FORMAT="${SCREEN_CAPTURE_INPUT_FORMAT:-}"
DISPLAY="${DISPLAY:-:0.0}"

echo "=== Streaming Screen Feed to MediaMTX ==="
echo "Target: rtsp://$HOST_IP:8554/screen"

if [[ -n "$CAPTURE_DEVICE" && -e "$CAPTURE_DEVICE" ]]; then
    echo "Source: USB capture device ($CAPTURE_DEVICE)"
    echo "Size: $VIDEO_SIZE @ ${FRAMERATE}fps"
    echo ""

    if ffmpeg -encoders 2>/dev/null | grep -q h264_nvenc; then
        echo "✅ Using NVENC (GPU encoding - near-zero CPU)"
        echo ""
        ffmpeg -f v4l2 \
          ${CAPTURE_INPUT_FORMAT:+-input_format} ${CAPTURE_INPUT_FORMAT:+"$CAPTURE_INPUT_FORMAT"} \
          -framerate "$FRAMERATE" -video_size "$VIDEO_SIZE" -i "$CAPTURE_DEVICE" \
          -vf format=yuv420p \
          -c:v h264_nvenc -preset p6 -b:v 4500k -maxrate 5500k -bufsize 7500k \
          -g $((FRAMERATE * 6)) -r "$FRAMERATE" \
          -f rtsp -rtsp_transport tcp \
          rtsp://$HOST_IP:8554/screen
    else
        echo "⚠️  NVENC not available, using CPU (ultrafast preset)"
        echo ""
        ffmpeg -f v4l2 \
          ${CAPTURE_INPUT_FORMAT:+-input_format} ${CAPTURE_INPUT_FORMAT:+"$CAPTURE_INPUT_FORMAT"} \
          -framerate "$FRAMERATE" -video_size "$VIDEO_SIZE" -i "$CAPTURE_DEVICE" \
          -c:v libx264 -preset ultrafast -crf 28 -g $((FRAMERATE * 6)) -r "$FRAMERATE" \
          -pix_fmt yuv420p \
          -f rtsp -rtsp_transport tcp \
          rtsp://$HOST_IP:8554/screen
    fi
else
    if [[ -z "$DISPLAY" ]]; then
        echo "❌ DISPLAY not set and no SCREEN_CAPTURE_DEVICE provided."
        echo "Set SCREEN_CAPTURE_DEVICE to your HDMI capture device (e.g. /dev/video1)."
        exit 1
    fi

    echo "Source: X11 display ($DISPLAY)"
    echo "Size: $VIDEO_SIZE @ ${FRAMERATE}fps"
    echo ""

    if ffmpeg -encoders 2>/dev/null | grep -q h264_nvenc; then
        echo "✅ Using NVENC (GPU encoding - near-zero CPU)"
        echo ""
        ffmpeg -f x11grab -framerate "$FRAMERATE" -video_size "$VIDEO_SIZE" -i "$DISPLAY" \
          -c:v h264_nvenc -preset p6 -b:v 1500k -maxrate 2000k -bufsize 3000k \
          -g $((FRAMERATE * 6)) -r "$FRAMERATE" -pix_fmt yuv420p \
          -f rtsp -rtsp_transport tcp \
          rtsp://$HOST_IP:8554/screen
    else
        echo "⚠️  NVENC not available, using CPU (ultrafast preset)"
        echo ""
        ffmpeg -f x11grab -framerate "$FRAMERATE" -video_size "$VIDEO_SIZE" -i "$DISPLAY" \
          -c:v libx264 -preset ultrafast -crf 28 -g $((FRAMERATE * 6)) -r "$FRAMERATE" \
          -pix_fmt yuv420p \
          -f rtsp -rtsp_transport tcp \
          rtsp://$HOST_IP:8554/screen
    fi
fi
