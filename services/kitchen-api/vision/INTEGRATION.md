# Vision Intake Integration Guide

This guide explains how to integrate the Vision Intake Module with the HAssistant Kitchen Stack.

## Quick Start

### 1. Install Dependencies

```bash
# System dependencies (Tesseract OCR)
sudo apt-get update
sudo apt-get install tesseract-ocr

# Python dependencies
pip install -r vision/requirements.txt
```

### 2. Test the Module

```bash
# Run the test suite
python test_vision_intake.py

# Test with an image
python example_vision_intake.py /path/to/grocery_image.jpg
```

## Integration Points

### A. Standalone CLI Usage

Use the module directly from the command line:

```bash
python vision/intake.py /path/to/image.jpg
```

### B. Python API Integration

Import and use in your Python code:

```python
from vision.intake import process_image

# Process an image
result = process_image("/path/to/grocery_receipt.jpg")

# Access the results
for item in result['items']:
    print(f"Found: {item['name']}")
    if item['expiry_date']:
        print(f"  Expires: {item['expiry_date']}")
```

### C. Integration with Letta Bridge Memory

Store parsed grocery items in the memory system:

```python
from vision.intake import process_image
import requests
import os

LETTA_BRIDGE_URL = os.getenv("LETTA_BRIDGE_URL", "http://localhost:8081")
LETTA_API_KEY = os.getenv("LETTA_BRIDGE_API_KEY", "dev-key")

def store_grocery_item(item, image_path):
    """Store a parsed grocery item in memory"""
    
    # Create a memory entry
    memory_data = {
        "type": "event",
        "title": f"Grocery Item: {item['name']}",
        "content": f"Scanned grocery item from {image_path}. "
                   f"Quantity: {item.get('quantity', 'unknown')}, "
                   f"Expiry: {item.get('expiry_date', 'unknown')}, "
                   f"Barcode: {item.get('barcode', 'none')}",
        "tags": ["grocery", "kitchen", "inventory"],
        "source": [f"vision_intake:{image_path}"],
        "confidence": item['confidence'],
        "tier": "medium" if item['expiry_date'] else "short",
        "meta": {
            "item_name": item['name'],
            "quantity": item.get('quantity'),
            "expiry_date": item.get('expiry_date'),
            "barcode": item.get('barcode'),
            "price": item.get('price'),
            "needs_review": item['needs_review']
        }
    }
    
    # Post to Letta Bridge
    response = requests.post(
        f"{LETTA_BRIDGE_URL}/memory/add",
        json=memory_data,
        headers={"x-api-key": LETTA_API_KEY}
    )
    
    return response.json()

# Usage
result = process_image("/path/to/image.jpg")
for item in result['items']:
    if not item['needs_review']:  # Only store high-confidence items
        store_grocery_item(item, result['image_path'])
```

### D. Integration with Home Assistant

Create a REST sensor in Home Assistant to trigger vision processing:

```yaml
# configuration.yaml

rest_command:
  process_grocery_image:
    url: "http://hassistant-vision-intake:8080/process"
    method: POST
    content_type: "application/json"
    payload: '{"image_path": "{{ image_path }}"}'

automation:
  - alias: "Process Grocery Receipt Photo"
    trigger:
      - platform: event
        event_type: "grocery_photo_taken"
    action:
      - service: rest_command.process_grocery_image
        data:
          image_path: "{{ trigger.event.data.file_path }}"
```

### E. Docker Integration (Recommended)

Create a containerized service for the vision intake module:

```dockerfile
# vision/Dockerfile
FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    libzbar0 \
    libopencv-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r /app/requirements.txt

# Copy application code
COPY . /app/
WORKDIR /app

# Expose API port (if you create a REST API wrapper)
EXPOSE 8080

# Run the module
CMD ["python", "-m", "uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8080"]
```

Add to docker-compose.yml:

```yaml
services:
  vision-intake:
    build: ./vision
    container_name: hassistant-vision-intake
    environment:
      - LETTA_BRIDGE_URL=http://letta-bridge:8081
      - LETTA_BRIDGE_API_KEY=${BRIDGE_API_KEY}
    volumes:
      - ./data/grocery_images:/images
    networks:
      - assistant_default
    restart: unless-stopped
```

## Workflow Examples

### 1. Grocery Receipt Processing Workflow

```python
import os
from pathlib import Path
from vision.intake import process_image

def process_grocery_receipt(image_path):
    """Process a grocery receipt and return shopping list"""
    
    result = process_image(image_path)
    
    if result['status'] == 'error':
        print(f"Error: {result['error']}")
        return None
    
    shopping_list = []
    
    for item in result['items']:
        shopping_item = {
            'name': item['name'],
            'quantity': item.get('quantity'),
            'price': item.get('price'),
            'confidence': item['confidence']
        }
        
        if item['needs_review']:
            shopping_item['status'] = 'needs_review'
        
        shopping_list.append(shopping_item)
    
    return {
        'items': shopping_list,
        'total_items': len(shopping_list),
        'needs_review_count': sum(1 for i in shopping_list if i.get('status') == 'needs_review')
    }

# Usage
receipt = process_grocery_receipt('/images/receipt_2024_01_15.jpg')
print(f"Found {receipt['total_items']} items")
```

### 2. Inventory Tracking Workflow

```python
from datetime import datetime, timedelta
from vision.intake import process_image

def track_grocery_inventory(image_path):
    """Track grocery items with expiry dates"""
    
    result = process_image(image_path)
    
    inventory = []
    alerts = []
    
    for item in result['items']:
        if item['expiry_date']:
            # Parse expiry date (simplified - you'd want better date parsing)
            try:
                # This is a simplified example
                inventory.append({
                    'name': item['name'],
                    'expiry_date': item['expiry_date'],
                    'quantity': item.get('quantity'),
                    'barcode': item.get('barcode')
                })
                
                # Check if expiring soon (you'd parse the date properly)
                # This is just a placeholder
                alerts.append({
                    'item': item['name'],
                    'message': f"Check expiry date: {item['expiry_date']}"
                })
            except Exception as e:
                print(f"Could not parse date for {item['name']}: {e}")
    
    return {
        'inventory': inventory,
        'alerts': alerts
    }
```

## API Wrapper (Optional)

Create a REST API wrapper for easy integration:

```python
# vision/api.py
from fastapi import FastAPI, UploadFile, File
from pathlib import Path
import tempfile
from vision.intake import process_image

app = FastAPI(title="Vision Intake API")

@app.post("/process")
async def process_upload(file: UploadFile = File(...)):
    """Process an uploaded image"""
    
    # Save uploaded file temporarily
    with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as tmp:
        contents = await file.read()
        tmp.write(contents)
        tmp_path = tmp.name
    
    try:
        # Process the image
        result = process_image(tmp_path)
        return result
    finally:
        # Cleanup
        Path(tmp_path).unlink(missing_ok=True)

@app.get("/health")
async def health():
    """Health check endpoint"""
    return {"status": "ok"}
```

## Best Practices

1. **Image Quality**: Ensure images are well-lit and text is clear
2. **Preprocessing**: Consider image preprocessing for better OCR results
3. **Error Handling**: Always check the `status` field in results
4. **Review Flag**: Items with `needs_review: true` should be manually verified
5. **Confidence Threshold**: Adjust confidence thresholds based on your use case
6. **Memory Storage**: Store only high-confidence items in long-term memory
7. **Batch Processing**: Process multiple images in batches for efficiency

## Troubleshooting

### Issue: "No module named cv2"
**Solution**: Install OpenCV with `pip install opencv-python`

### Issue: "Tesseract not found"
**Solution**: Install system package: `sudo apt-get install tesseract-ocr`

### Issue: "No barcodes detected"
**Solution**: Ensure barcode is clear and not obscured. Try better lighting.

### Issue: "Poor OCR accuracy"
**Solution**: 
- Improve image quality (lighting, focus)
- Use image preprocessing (contrast enhancement, noise reduction)
- Try different Tesseract PSM modes in the code

## Next Steps

1. Create a web UI for uploading and reviewing processed images
2. Integrate with a product database for barcode lookups
3. Add machine learning for better product classification
4. Implement batch processing for multiple images
5. Create scheduled scanning routines for regular inventory checks

## Support

For issues or questions, refer to the main repository documentation or create an issue on GitHub.
