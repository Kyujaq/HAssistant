#!/usr/bin/env python3
"""
Vision Worker Integration Tests
Can run with or without GPU - validates CPU fallback mode
"""
import os
import sys
import time
import json
import requests
from typing import Dict, Any

# Test configuration
VISION_SCREEN_URL = os.getenv("VISION_SCREEN_URL", "http://localhost:8089")
VISION_ROOM_URL = os.getenv("VISION_ROOM_URL", "http://localhost:8090")
TIMEOUT = 30  # seconds


def test_worker_health(worker_url: str, role: str) -> bool:
    """Test worker health endpoint"""
    print(f"\n{'='*60}")
    print(f"Testing {role} worker health: {worker_url}")
    print('='*60)
    
    try:
        response = requests.get(f"{worker_url}/health", timeout=10)
        response.raise_for_status()
        
        health = response.json()
        print(json.dumps(health, indent=2))
        
        # Validate response structure
        assert health.get("ok") == True, "Health check failed"
        assert health.get("role") == role, f"Wrong role: {health.get('role')}"
        assert "gpu_name" in health, "Missing gpu_name"
        assert "warmup_completed" in health, "Missing warmup_completed"
        
        # Check if GPU was used or CPU fallback
        if health.get("device") == "cpu":
            print(f"⚠️  {role} worker running in CPU mode (no GPU available)")
        else:
            print(f"✅ {role} worker using GPU: {health.get('gpu_name')}")
            
        return True
        
    except Exception as e:
        print(f"❌ Health check failed: {e}")
        return False


def test_worker_frame_processing(worker_url: str, role: str) -> bool:
    """Test frame processing endpoint"""
    print(f"\n{'='*60}")
    print(f"Testing {role} worker frame processing")
    print('='*60)
    
    try:
        # Create a test frame (red square on black background)
        import numpy as np
        import cv2
        
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        cv2.rectangle(frame, (200, 150), (440, 330), (0, 0, 255), -1)
        
        # Encode as JPEG
        _, encoded = cv2.imencode('.jpg', frame)
        
        # Send to worker
        response = requests.post(
            f"{worker_url}/process/frame",
            files={"file": ("test.jpg", encoded.tobytes(), "image/jpeg")},
            timeout=30
        )
        response.raise_for_status()
        
        result = response.json()
        print(json.dumps(result, indent=2))
        
        assert result.get("ok") == True, "Processing failed"
        assert "detections" in result, "Missing detections"
        assert "gpu" in result, "Missing GPU info"
        
        print(f"✅ Frame processing successful")
        print(f"   GPU: {result.get('gpu')}")
        print(f"   Detections: {len(result.get('detections', []))}")
        
        return True
        
    except Exception as e:
        print(f"❌ Frame processing failed: {e}")
        return False


def test_worker_ocr(worker_url: str, role: str) -> bool:
    """Test OCR endpoint"""
    print(f"\n{'='*60}")
    print(f"Testing {role} worker OCR")
    print('='*60)
    
    try:
        import numpy as np
        import cv2
        
        # Create a test image with text
        img = np.ones((100, 400, 3), dtype=np.uint8) * 255
        cv2.putText(img, "TEST TEXT 123", (10, 60),
                   cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 0, 0), 2)
        
        # Encode as JPEG
        _, encoded = cv2.imencode('.jpg', img)
        
        # Send to worker
        response = requests.post(
            f"{worker_url}/ocr/crop",
            files={"file": ("test.jpg", encoded.tobytes(), "image/jpeg")},
            timeout=30
        )
        response.raise_for_status()
        
        result = response.json()
        print(json.dumps(result, indent=2))
        
        assert result.get("ok") == True, "OCR failed"
        assert "text_lines" in result, "Missing text_lines"
        assert "ocr_ms" in result, "Missing OCR timing"
        
        print(f"✅ OCR successful")
        print(f"   Processing time: {result.get('ocr_ms')} ms")
        print(f"   Text lines detected: {len(result.get('text_lines', []))}")
        
        return True
        
    except Exception as e:
        print(f"❌ OCR failed: {e}")
        return False


def wait_for_worker(worker_url: str, timeout: int = 60) -> bool:
    """Wait for worker to become ready"""
    print(f"\nWaiting for worker at {worker_url} (timeout: {timeout}s)...")
    
    start = time.time()
    while time.time() - start < timeout:
        try:
            response = requests.get(f"{worker_url}/health", timeout=5)
            if response.status_code == 200:
                print(f"✅ Worker ready")
                return True
        except:
            pass
        time.sleep(2)
    
    print(f"❌ Worker not ready after {timeout}s")
    return False


def main():
    """Run all tests"""
    print("\n" + "="*60)
    print("Vision Worker Integration Tests")
    print("="*60)
    
    # Check for required dependencies
    try:
        import numpy
        import cv2
    except ImportError as e:
        print(f"❌ Missing dependency: {e}")
        print("Install: pip install numpy opencv-python-headless")
        sys.exit(1)
    
    results = []
    
    # Test screen worker
    if wait_for_worker(VISION_SCREEN_URL, TIMEOUT):
        results.append(("screen-health", test_worker_health(VISION_SCREEN_URL, "screen")))
        results.append(("screen-frame", test_worker_frame_processing(VISION_SCREEN_URL, "screen")))
        results.append(("screen-ocr", test_worker_ocr(VISION_SCREEN_URL, "screen")))
    else:
        print(f"⚠️  Screen worker not available at {VISION_SCREEN_URL}")
        results.append(("screen-health", False))
    
    # Test room worker (if different URL)
    if VISION_ROOM_URL != VISION_SCREEN_URL:
        if wait_for_worker(VISION_ROOM_URL, TIMEOUT):
            results.append(("room-health", test_worker_health(VISION_ROOM_URL, "room")))
            results.append(("room-frame", test_worker_frame_processing(VISION_ROOM_URL, "room")))
            results.append(("room-ocr", test_worker_ocr(VISION_ROOM_URL, "room")))
        else:
            print(f"⚠️  Room worker not available at {VISION_ROOM_URL}")
            results.append(("room-health", False))
    
    # Summary
    print("\n" + "="*60)
    print("Test Results Summary")
    print("="*60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {test_name}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All tests passed!")
        sys.exit(0)
    else:
        print(f"\n⚠️  {total - passed} test(s) failed")
        sys.exit(1)


if __name__ == "__main__":
    main()
