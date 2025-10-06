# Vision Intake Module - Quick Start Guide

Get started with the Vision Intake Module in under 5 minutes!

## 1. Install System Dependencies

```bash
# Ubuntu/Debian
sudo apt-get update
sudo apt-get install tesseract-ocr

# macOS
brew install tesseract

# Windows
# Download from: https://github.com/UB-Mannheim/tesseract/wiki
```

## 2. Install Python Dependencies

```bash
cd vision
pip install -r requirements.txt
```

## 3. Test the Installation

```bash
# Run the test suite
cd ..
python test_vision_intake.py
```

## 4. Process Your First Image

### Option A: Command Line

```bash
python vision/intake.py /path/to/grocery_image.jpg
```

### Option B: Example Script

```bash
python example_vision_intake.py /path/to/grocery_image.jpg
```

### Option C: Python Code

```python
from vision.intake import process_image

result = process_image("/path/to/image.jpg")

print(f"Status: {result['status']}")
print(f"Barcodes found: {len(result['barcodes'])}")
print(f"Items parsed: {len(result['items'])}")

for item in result['items']:
    print(f"- {item['name']}")
    if item['needs_review']:
        print("  ⚠️  Needs review")
```

## 5. View Results

The module returns a structured dictionary:

```python
{
  "status": "success",
  "barcodes": [...],
  "ocr_text": "...",
  "items": [
    {
      "name": "Organic Milk",
      "quantity": "2L",
      "expiry_date": "12/25/2024",
      "price": "4.99",
      "confidence": 0.85,
      "needs_review": false
    }
  ]
}
```

## 6. Next Steps

- Read the full [README](README.md) for detailed documentation
- Check [INTEGRATION.md](INTEGRATION.md) for integration examples
- Review the [JSON Schema](vision_intake_schema.json) for output format

## Troubleshooting

**Problem:** `ModuleNotFoundError: No module named 'cv2'`
**Solution:** `pip install opencv-python`

**Problem:** `TesseractNotFoundError`
**Solution:** Install Tesseract OCR system package (see step 1)

**Problem:** Poor OCR accuracy
**Solution:** Ensure image is clear, well-lit, and in focus

## Support

For issues, refer to the repository documentation or create an issue on GitHub.
