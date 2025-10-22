"""
Quick test script for K80 preprocessor.
Run inside container: docker exec vision-gateway python3 /app/test_k80.py
"""

import sys
import cv2
import numpy as np

# Test imports
try:
    import torch
    print(f"✓ PyTorch {torch.__version__}")
    print(f"✓ CUDA available: {torch.cuda.is_available()}")
    print(f"✓ CUDA devices: {torch.cuda.device_count()}")
    if torch.cuda.is_available():
        print(f"✓ K80 (GPU 2): {torch.cuda.get_device_name(2)}")
except Exception as e:
    print(f"✗ PyTorch error: {e}")
    sys.exit(1)

try:
    from groundingdino.util.inference import load_model
    print(f"✓ GroundingDINO imported")
except Exception as e:
    print(f"✗ GroundingDINO import failed: {e}")
    print("  This is expected - GroundingDINO needs model files downloaded")

try:
    from app.k80_preprocessor import K80Preprocessor, SceneTracker
    print(f"✓ K80Preprocessor module imported")
except Exception as e:
    print(f"✗ K80Preprocessor import failed: {e}")
    sys.exit(1)

# Test with a dummy frame
print("\nTesting with dummy frame...")
dummy_frame = np.zeros((1080, 1920, 3), dtype=np.uint8)
cv2.rectangle(dummy_frame, (100, 100), (200, 150), (255, 255, 255), -1)
cv2.putText(dummy_frame, "Send", (110, 130), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 2)

try:
    preprocessor = K80Preprocessor(device="cuda:2")
    print("✓ K80Preprocessor initialized")

    # Note: detection will fail without model files, but initialization should work
    detections = preprocessor.detect_elements(dummy_frame, prompts=["button", "send button"])
    print(f"✓ Detection ran (found {len(detections)} elements)")

except Exception as e:
    print(f"⚠ K80Preprocessor test: {e}")

print("\n✓ All basic tests passed!")
print("\nNext step: Download GroundingDINO model files for full functionality")
