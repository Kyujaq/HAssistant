"""
Vision Intake Module for Grocery Item Processing

This module processes images of groceries to extract:
- Barcodes (using pyzbar)
- Text content (using pytesseract OCR)
- Parsed product information (names, quantities, expiry dates)
"""

import re
from typing import Dict, List, Any, Optional
from datetime import datetime
import cv2
import numpy as np
from pyzbar import pyzbar
import pytesseract
from PIL import Image


def process_image(image_path: str) -> Dict[str, Any]:
    """
    Process a grocery image to extract barcodes, text, and product information.
    
    Args:
        image_path: Path to the image file to process
        
    Returns:
        Dictionary matching the vision_intake.json schema with:
        - status: Processing status ("success" or "error")
        - image_path: Original image path
        - timestamp: Processing timestamp
        - barcodes: List of detected barcodes with their data and type
        - ocr_text: Full OCR extracted text
        - items: Parsed product items with confidence scores
        - error: Error message if processing failed
    """
    result = {
        "status": "success",
        "image_path": image_path,
        "timestamp": datetime.now().isoformat(),
        "barcodes": [],
        "ocr_text": "",
        "items": [],
        "error": None
    }
    
    try:
        # Load the image
        image = cv2.imread(image_path)
        if image is None:
            raise ValueError(f"Could not load image from path: {image_path}")
        
        # Detect and decode barcodes
        result["barcodes"] = _detect_barcodes(image)
        
        # Extract text using OCR
        result["ocr_text"] = _extract_text_ocr(image)
        
        # Parse OCR text to identify products
        result["items"] = _parse_products(result["ocr_text"], result["barcodes"])
        
    except Exception as e:
        result["status"] = "error"
        result["error"] = str(e)
    
    return result


def _detect_barcodes(image: np.ndarray) -> List[Dict[str, Any]]:
    """
    Detect and decode barcodes in the image using pyzbar.
    
    Args:
        image: OpenCV image (BGR format)
        
    Returns:
        List of barcode dictionaries with data, type, and bounding box
    """
    barcodes = []
    
    # Convert to grayscale for better barcode detection
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    
    # Detect barcodes
    detected = pyzbar.decode(gray)
    
    for barcode in detected:
        # Extract barcode data
        barcode_data = barcode.data.decode('utf-8')
        barcode_type = barcode.type
        
        # Get bounding box coordinates
        x, y, w, h = barcode.rect
        
        barcodes.append({
            "data": barcode_data,
            "type": barcode_type,
            "bbox": {
                "x": x,
                "y": y,
                "width": w,
                "height": h
            },
            "confidence": 1.0  # pyzbar doesn't provide confidence, assume high
        })
    
    return barcodes


def _extract_text_ocr(image: np.ndarray) -> str:
    """
    Extract all text from the image using pytesseract OCR.
    
    Args:
        image: OpenCV image (BGR format)
        
    Returns:
        Extracted text as a string
    """
    # Convert BGR to RGB for PIL/pytesseract
    rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    pil_image = Image.fromarray(rgb_image)
    
    # Perform OCR
    # Using config to optimize for grocery items (single block of text)
    custom_config = r'--oem 3 --psm 6'
    text = pytesseract.image_to_string(pil_image, config=custom_config)
    
    return text.strip()


def _parse_products(ocr_text: str, barcodes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Parse OCR text to identify product names, quantities, and expiry dates.
    
    Args:
        ocr_text: Full OCR extracted text
        barcodes: List of detected barcodes (for correlation)
        
    Returns:
        List of parsed product items with confidence scores
    """
    items = []
    
    if not ocr_text:
        return items
    
    # Split text into lines for processing
    lines = [line.strip() for line in ocr_text.split('\n') if line.strip()]
    
    # Regular expressions for parsing
    # Expiry date patterns (various formats)
    expiry_patterns = [
        r'(?:exp|expiry|expires?|best before|use by)[\s:]*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})',
        r'(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})',  # Generic date
    ]
    
    # Quantity patterns (weight, volume, count)
    quantity_patterns = [
        r'(\d+(?:\.\d+)?)\s*(kg|g|lb|oz|ml|l|liters?)',
        r'(\d+)\s*(?:pack|pcs?|pieces?|items?|count)',
        r'(\d+)\s*x\s*(\d+(?:\.\d+)?)\s*(g|ml|oz)',
    ]
    
    # Price patterns
    price_patterns = [
        r'\$\s*(\d+(?:\.\d{2})?)',
        r'(\d+(?:\.\d{2})?)\s*(?:USD|EUR|GBP)',
    ]
    
    # Process each line as a potential product
    i = 0
    while i < len(lines):
        line = lines[i]
        
        # Skip very short lines (likely noise)
        if len(line) < 3:
            i += 1
            continue
        
        item = {
            "name": "",
            "quantity": None,
            "expiry_date": None,
            "price": None,
            "barcode": None,
            "confidence": 0.5,  # Default medium confidence
            "needs_review": False,
            "raw_text": line
        }
        
        # Extract product name (assume it's the current line, cleaned)
        # Remove common non-product words
        name = line
        for pattern in expiry_patterns + quantity_patterns + price_patterns:
            name = re.sub(pattern, '', name, flags=re.IGNORECASE)
        name = name.strip()
        
        if name and len(name) > 2:
            item["name"] = name
            item["confidence"] = 0.6  # Slightly higher confidence if we found a name
            
            # Try to extract expiry date from this line or next few lines
            for j in range(i, min(i + 3, len(lines))):
                for pattern in expiry_patterns:
                    match = re.search(pattern, lines[j], re.IGNORECASE)
                    if match:
                        item["expiry_date"] = match.group(1) if match.lastindex else match.group(0)
                        item["confidence"] = min(item["confidence"] + 0.2, 0.95)
                        break
            
            # Try to extract quantity
            for pattern in quantity_patterns:
                match = re.search(pattern, line, re.IGNORECASE)
                if match:
                    if len(match.groups()) >= 2:
                        item["quantity"] = f"{match.group(1)} {match.group(2)}"
                    else:
                        item["quantity"] = match.group(0)
                    item["confidence"] = min(item["confidence"] + 0.15, 0.95)
                    break
            
            # Try to extract price
            for pattern in price_patterns:
                match = re.search(pattern, line, re.IGNORECASE)
                if match:
                    item["price"] = match.group(1) if match.lastindex else match.group(0)
                    item["confidence"] = min(item["confidence"] + 0.1, 0.95)
                    break
            
            # Associate with barcode if we only have one
            if len(barcodes) == 1:
                item["barcode"] = barcodes[0]["data"]
                item["confidence"] = min(item["confidence"] + 0.2, 0.95)
            
            # Mark for review if confidence is low
            if item["confidence"] < 0.7:
                item["needs_review"] = True
            
            items.append(item)
        
        i += 1
    
    # If we have barcodes but no items, create items from barcodes
    if barcodes and not items:
        for barcode in barcodes:
            items.append({
                "name": f"Product with barcode {barcode['data']}",
                "quantity": None,
                "expiry_date": None,
                "price": None,
                "barcode": barcode["data"],
                "confidence": 0.5,
                "needs_review": True,
                "raw_text": f"Barcode: {barcode['data']}"
            })
    
    # If we couldn't parse anything meaningful, create a generic item
    if not items and ocr_text:
        items.append({
            "name": "Unknown product",
            "quantity": None,
            "expiry_date": None,
            "price": None,
            "barcode": None,
            "confidence": 0.3,
            "needs_review": True,
            "raw_text": ocr_text[:100]  # First 100 chars
        })
    
    return items


# Example usage
if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python intake.py <image_path>")
        sys.exit(1)
    
    image_path = sys.argv[1]
    result = process_image(image_path)
    
    print(f"\n{'='*60}")
    print(f"Vision Intake Results")
    print(f"{'='*60}")
    print(f"Status: {result['status']}")
    print(f"Image: {result['image_path']}")
    print(f"Timestamp: {result['timestamp']}")
    
    if result['error']:
        print(f"Error: {result['error']}")
    else:
        print(f"\nBarcodes found: {len(result['barcodes'])}")
        for barcode in result['barcodes']:
            print(f"  - {barcode['type']}: {barcode['data']}")
        
        print(f"\nOCR Text:\n{result['ocr_text'][:200]}...")
        
        print(f"\nItems parsed: {len(result['items'])}")
        for i, item in enumerate(result['items'], 1):
            print(f"\n  Item {i}:")
            print(f"    Name: {item['name']}")
            print(f"    Quantity: {item.get('quantity', 'N/A')}")
            print(f"    Expiry: {item.get('expiry_date', 'N/A')}")
            print(f"    Price: {item.get('price', 'N/A')}")
            print(f"    Barcode: {item.get('barcode', 'N/A')}")
            print(f"    Confidence: {item['confidence']:.2f}")
            print(f"    Needs Review: {item['needs_review']}")
