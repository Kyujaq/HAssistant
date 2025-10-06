#!/usr/bin/env python3
"""
Test suite for Vision Intake Module
Tests the process_image function with various scenarios
"""

import os
import sys
import tempfile
import json
from pathlib import Path

# Add vision module to path (robust absolute path resolution)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

try:
    import cv2
    import numpy as np
    from vision.intake import process_image, _detect_barcodes, _extract_text_ocr, _parse_products
    DEPENDENCIES_AVAILABLE = True
except ImportError as e:
    print(f"Warning: Dependencies not installed: {e}")
    print("Run: pip install -r vision/requirements.txt")
    DEPENDENCIES_AVAILABLE = False


def create_test_image_with_text(text: str, filename: str) -> str:
    """Create a simple test image with text"""
    if not DEPENDENCIES_AVAILABLE:
        return None
    
    # Create a white image
    img = np.ones((400, 600, 3), dtype=np.uint8) * 255
    
    # Add text to the image
    font = cv2.FONT_HERSHEY_SIMPLEX
    y_position = 100
    for line in text.split('\n'):
        cv2.putText(img, line, (50, y_position), font, 0.7, (0, 0, 0), 2)
        y_position += 50
    
    # Save the image
    cv2.imwrite(filename, img)
    return filename


def test_basic_functionality():
    """Test basic image processing without dependencies"""
    print("\n=== Test 1: Basic Functionality ===")
    
    if not DEPENDENCIES_AVAILABLE:
        print("⚠ Skipping - dependencies not available")
        return True
    
    # Create a temporary test image
    with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp:
        test_image = create_test_image_with_text(
            "Organic Milk\n2L\nExp: 12/25/2024\n$4.99",
            tmp.name
        )
    
    try:
        result = process_image(test_image)
        
        # Validate result structure
        assert result['status'] == 'success', f"Expected success status, got {result['status']}"
        assert 'barcodes' in result, "Missing 'barcodes' field"
        assert 'ocr_text' in result, "Missing 'ocr_text' field"
        assert 'items' in result, "Missing 'items' field"
        assert 'timestamp' in result, "Missing 'timestamp' field"
        assert 'image_path' in result, "Missing 'image_path' field"
        
        print(f"✓ Result structure is valid")
        print(f"  - Status: {result['status']}")
        print(f"  - Barcodes: {len(result['barcodes'])}")
        print(f"  - Items: {len(result['items'])}")
        print(f"  - OCR Text length: {len(result['ocr_text'])}")
        
        return True
        
    except Exception as e:
        print(f"✗ Test failed: {e}")
        return False
    finally:
        # Cleanup
        if os.path.exists(test_image):
            os.unlink(test_image)


def test_invalid_image():
    """Test error handling for invalid image path"""
    print("\n=== Test 2: Invalid Image Handling ===")
    
    if not DEPENDENCIES_AVAILABLE:
        print("⚠ Skipping - dependencies not available")
        return True
    
    result = process_image("/nonexistent/image.jpg")
    
    try:
        assert result['status'] == 'error', f"Expected error status, got {result['status']}"
        assert result['error'] is not None, "Expected error message"
        print(f"✓ Error handling works correctly")
        print(f"  - Error: {result['error']}")
        return True
    except AssertionError as e:
        print(f"✗ Test failed: {e}")
        return False


def test_parsing_functions():
    """Test individual parsing functions"""
    print("\n=== Test 3: Parsing Functions ===")
    
    if not DEPENDENCIES_AVAILABLE:
        print("⚠ Skipping - dependencies not available")
        return True
    
    try:
        # Test _parse_products with sample text
        sample_text = """
        Fresh Apples
        2kg
        Exp: 01/15/2025
        $5.99
        
        Whole Wheat Bread
        500g
        Best before: 12-20-2024
        """
        
        items = _parse_products(sample_text, [])
        
        assert len(items) > 0, "No items parsed from sample text"
        
        print(f"✓ Parsing functions work correctly")
        print(f"  - Parsed {len(items)} items from sample text")
        
        for i, item in enumerate(items, 1):
            print(f"  - Item {i}: {item['name']}")
            if item['needs_review']:
                print(f"    (marked for review, confidence: {item['confidence']:.2f})")
        
        return True
        
    except Exception as e:
        print(f"✗ Test failed: {e}")
        return False


def test_result_schema():
    """Test that the result matches expected schema"""
    print("\n=== Test 4: Result Schema Validation ===")
    
    if not DEPENDENCIES_AVAILABLE:
        print("⚠ Skipping - dependencies not available")
        return True
    
    with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp:
        test_image = create_test_image_with_text("Test Product", tmp.name)
    
    try:
        result = process_image(test_image)
        
        # Expected top-level keys
        required_keys = ['status', 'image_path', 'timestamp', 'barcodes', 'ocr_text', 'items', 'error']
        
        for key in required_keys:
            assert key in result, f"Missing required key: {key}"
        
        # Validate items structure
        if result['items']:
            item = result['items'][0]
            item_keys = ['name', 'quantity', 'expiry_date', 'price', 'barcode', 'confidence', 'needs_review', 'raw_text']
            for key in item_keys:
                assert key in item, f"Missing required item key: {key}"
        
        # Validate barcodes structure
        if result['barcodes']:
            barcode = result['barcodes'][0]
            barcode_keys = ['data', 'type', 'bbox', 'confidence']
            for key in barcode_keys:
                assert key in barcode, f"Missing required barcode key: {key}"
        
        print(f"✓ Result schema is valid")
        print(f"  - All required fields present")
        
        # Pretty print the result structure
        print(f"\n  Sample result structure:")
        print(json.dumps({
            'status': result['status'],
            'barcodes_count': len(result['barcodes']),
            'items_count': len(result['items']),
            'has_ocr_text': len(result['ocr_text']) > 0
        }, indent=2))
        
        return True
        
    except Exception as e:
        print(f"✗ Test failed: {e}")
        return False
    finally:
        if os.path.exists(test_image):
            os.unlink(test_image)


def main():
    """Run all tests"""
    print("="*60)
    print("Vision Intake Module Test Suite")
    print("="*60)
    
    if not DEPENDENCIES_AVAILABLE:
        print("\n⚠ WARNING: Dependencies not installed")
        print("Install them with: pip install -r vision/requirements.txt")
        print("\nNote: Tesseract OCR must also be installed on the system:")
        print("  - Ubuntu/Debian: sudo apt-get install tesseract-ocr")
        print("  - macOS: brew install tesseract")
        print("  - Windows: Download from https://github.com/UB-Mannheim/tesseract/wiki")
        return
    
    tests = [
        test_basic_functionality,
        test_invalid_image,
        test_parsing_functions,
        test_result_schema,
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            if test():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"✗ Test crashed: {e}")
            failed += 1
    
    print("\n" + "="*60)
    print(f"Test Results: {passed} passed, {failed} failed")
    print("="*60)
    
    if failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
