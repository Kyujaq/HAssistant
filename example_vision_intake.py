#!/usr/bin/env python3
"""
Example usage of the Vision Intake Module

Demonstrates how to use the vision intake module to process grocery images.
"""

import json
import sys
from pathlib import Path

# Add parent directory to path to import vision module
sys.path.insert(0, str(Path(__file__).parent))

try:
    from vision.intake import process_image
except ImportError as e:
    print(f"Error importing vision module: {e}")
    print("\nPlease install dependencies:")
    print("  pip install -r vision/requirements.txt")
    print("\nAnd ensure Tesseract OCR is installed on your system:")
    print("  Ubuntu/Debian: sudo apt-get install tesseract-ocr")
    print("  macOS: brew install tesseract")
    sys.exit(1)


def main():
    """Main example function"""
    
    print("="*70)
    print("Vision Intake Module - Example Usage")
    print("="*70)
    
    # Check if image path was provided
    if len(sys.argv) < 2:
        print("\nUsage: python example_vision_intake.py <image_path>")
        print("\nExample:")
        print("  python example_vision_intake.py /path/to/grocery_receipt.jpg")
        sys.exit(1)
    
    image_path = sys.argv[1]
    
    # Check if file exists
    if not Path(image_path).exists():
        print(f"\nError: Image file not found: {image_path}")
        sys.exit(1)
    
    print(f"\nProcessing image: {image_path}")
    print("-" * 70)
    
    # Process the image
    result = process_image(image_path)
    
    # Display results
    print(f"\n{'Status:':<20} {result['status']}")
    print(f"{'Timestamp:':<20} {result['timestamp']}")
    
    if result['error']:
        print(f"\n❌ Error: {result['error']}")
        sys.exit(1)
    
    # Display barcodes
    print(f"\n{'='*70}")
    print("BARCODES DETECTED")
    print("="*70)
    
    if result['barcodes']:
        for i, barcode in enumerate(result['barcodes'], 1):
            print(f"\nBarcode {i}:")
            print(f"  Type:       {barcode['type']}")
            print(f"  Data:       {barcode['data']}")
            print(f"  Position:   x={barcode['bbox']['x']}, y={barcode['bbox']['y']}")
            print(f"  Size:       {barcode['bbox']['width']}x{barcode['bbox']['height']}px")
            print(f"  Confidence: {barcode['confidence']:.2f}")
    else:
        print("\nNo barcodes detected in image.")
    
    # Display OCR text
    print(f"\n{'='*70}")
    print("OCR TEXT EXTRACTED")
    print("="*70)
    
    if result['ocr_text']:
        print(f"\n{result['ocr_text']}")
    else:
        print("\nNo text detected in image.")
    
    # Display parsed items
    print(f"\n{'='*70}")
    print("PARSED ITEMS")
    print("="*70)
    
    if result['items']:
        for i, item in enumerate(result['items'], 1):
            print(f"\n📦 Item {i}:")
            print(f"  Name:        {item['name']}")
            
            if item['quantity']:
                print(f"  Quantity:    {item['quantity']}")
            
            if item['expiry_date']:
                print(f"  Expiry:      {item['expiry_date']}")
            
            if item['price']:
                print(f"  Price:       ${item['price']}")
            
            if item['barcode']:
                print(f"  Barcode:     {item['barcode']}")
            
            print(f"  Confidence:  {item['confidence']:.2%}")
            
            if item['needs_review']:
                print(f"  ⚠️  Status:    NEEDS MANUAL REVIEW (low confidence)")
            else:
                print(f"  ✅ Status:    OK")
    else:
        print("\nNo items could be parsed from the image.")
    
    # Summary
    print(f"\n{'='*70}")
    print("SUMMARY")
    print("="*70)
    print(f"Total barcodes detected: {len(result['barcodes'])}")
    print(f"Total items parsed:      {len(result['items'])}")
    
    needs_review = sum(1 for item in result['items'] if item['needs_review'])
    if needs_review > 0:
        print(f"Items needing review:    {needs_review}")
    
    # Option to save results to JSON
    print(f"\n{'='*70}")
    output_file = Path(image_path).stem + "_results.json"
    
    with open(output_file, 'w') as f:
        json.dump(result, f, indent=2)
    
    print(f"Results saved to: {output_file}")
    print("="*70)


if __name__ == "__main__":
    main()
