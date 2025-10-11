"""
Vision Intake Module
Process images of groceries to extract barcodes, text, and product information.
"""

from .intake import process_image

__version__ = "1.0.0"
__all__ = ["process_image"]
