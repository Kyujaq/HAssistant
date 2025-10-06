# Vision Intake Module

A Python module for processing images of groceries to extract barcodes, text, and product information.

## Features

- **Barcode Detection**: Detects and decodes various barcode types (EAN-13, UPC-A, QR codes, etc.) using pyzbar
- **OCR Text Extraction**: Extracts all text from images using pytesseract
- **Product Parsing**: Intelligently parses extracted text to identify:
  - Product names
  - Quantities (weight, volume, count)
  - Expiry dates (multiple date formats)
  - Prices
- **Confidence Scoring**: Assigns confidence scores to parsed items
- **Review Flagging**: Marks low-confidence items for manual review

## Installation

### System Dependencies

First, install Tesseract OCR on your system:

**Ubuntu/Debian:**
```bash
sudo apt-get update
sudo apt-get install tesseract-ocr
```

**macOS:**
```bash
brew install tesseract
```

**Windows:**
Download and install from: https://github.com/UB-Mannheim/tesseract/wiki

### Python Dependencies

Install the required Python packages:

```bash
pip install -r vision/requirements.txt
```

## Usage

### Basic Usage

```python
from vision.intake import process_image

# Process a grocery image
result = process_image("/path/to/grocery_image.jpg")

print(f"Status: {result['status']}")
print(f"Barcodes found: {len(result['barcodes'])}")
print(f"Items parsed: {len(result['items'])}")

# Access parsed items
for item in result['items']:
    print(f"Product: {item['name']}")
    print(f"  Quantity: {item['quantity']}")
    print(f"  Expiry: {item['expiry_date']}")
    print(f"  Confidence: {item['confidence']}")
    if item['needs_review']:
        print(f"  ⚠ Needs manual review")
```

### Command Line Usage

```bash
python vision/intake.py /path/to/image.jpg
```

## Output Schema

The `process_image()` function returns a dictionary with the following structure:

```python
{
    "status": "success",           # "success" or "error"
    "image_path": "path/to/image.jpg",
    "timestamp": "2024-01-15T10:30:00",
    "barcodes": [
        {
            "data": "1234567890123",
            "type": "EAN13",
            "bbox": {
                "x": 100,
                "y": 200,
                "width": 150,
                "height": 80
            },
            "confidence": 1.0
        }
    ],
    "ocr_text": "Full extracted text...",
    "items": [
        {
            "name": "Organic Milk",
            "quantity": "2 L",
            "expiry_date": "12/25/2024",
            "price": "4.99",
            "barcode": "1234567890123",
            "confidence": 0.85,
            "needs_review": false,
            "raw_text": "Original OCR line..."
        }
    ],
    "error": null                  # Error message if status is "error"
}
```

## Testing

Run the test suite:

```bash
python test_vision_intake.py
```

The test suite includes:
- Basic functionality tests
- Error handling validation
- Parsing function tests
- Schema validation

## Text Parsing Patterns

The module recognizes various patterns for grocery items:

### Expiry Date Patterns
- `Exp: 12/25/2024`
- `Expiry: 12-25-2024`
- `Best before: 12/25/24`
- `Use by: 25/12/2024`

### Quantity Patterns
- `2kg`, `500g`, `2.5 lb`
- `1L`, `500ml`, `16 oz`
- `12 pack`, `24 pcs`
- `6 x 330ml`

### Price Patterns
- `$4.99`
- `4.99 USD`
- `€3.50`

## Confidence Scoring

Items are assigned confidence scores based on:
- Presence of product name: +0.6
- Expiry date found: +0.2
- Quantity found: +0.15
- Price found: +0.1
- Barcode association: +0.2

Items with confidence < 0.7 are marked for manual review.

## Integration with Home Assistant

This module is designed to work as part of the HAssistant Kitchen Stack for:
- Grocery inventory management
- Expiry date tracking
- Shopping list automation

## Limitations

- OCR accuracy depends on image quality and text clarity
- Date parsing may vary across different regional formats
- Product names may include noise from packaging text
- Manual review recommended for low-confidence items

## Future Enhancements

- Integration with product databases for barcode lookup
- Machine learning-based product classification
- Support for receipt processing
- Nutritional information extraction
- Multi-language support
