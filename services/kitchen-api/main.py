# services/kitchen-api/main.py
from fastapi import FastAPI, HTTPException, Depends, Body
from typing import List, Optional, Dict, Any
import logging
import os
from pydantic import BaseModel

# Import module clients/data access layers
from db import data_access as db
from paprika_bridge.kappari_client import KappariClient
from deals.providers.mock_ca import MockCAProvider

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Kitchen API",
    description="API for managing kitchen inventory, recipes, shopping lists, and more.",
    version="0.1.0",
)

# --- Module Initializations ---
paprika_client = KappariClient()
deals_provider = MockCAProvider()

# --- Pydantic Models for Request/Response Bodies ---
class Item(BaseModel):
    name: str
    brand: Optional[str] = None
    category: str
    unit: str
    calories_per_unit: Optional[float] = None
    protein_per_unit: Optional[float] = None
    carbs_per_unit: Optional[float] = None
    fat_per_unit: Optional[float] = None

class ItemResponse(Item):
    item_id: int
    images: List[str] = []

class Batch(BaseModel):
    item_id: int
    quantity: float
    purchase_date: str
    expiration_date: Optional[str] = None
    location: Optional[str] = None
    cost: Optional[float] = None
    notes: Optional[str] = None

class ShoppingListItem(BaseModel):
    item: str

class ImagePath(BaseModel):
    path: str

# --- System Endpoints ---
@app.on_event("startup")
async def startup_event():
    logger.info("Kitchen API starting up...")
    try:
        # Initialize Paprika client by logging in
        paprika_email = os.getenv("PAPRIKA_EMAIL")
        paprika_password = os.getenv("PAPRIKA_PASSWORD")
        if paprika_email and paprika_password:
            paprika_client.login(paprika_email, paprika_password)
            logger.info("Paprika client authenticated.")
        else:
            logger.warning("PAPRIKA_EMAIL or PAPRIKA_PASSWORD not set. Paprika features will be unavailable.")
        
        # Initialize database
        db.get_db_connection() # This will create the db if it doesn't exist
        logger.info("Database connection established.")

    except Exception as e:
        logger.error(f"Error during startup: {e}", exc_info=True)
    logger.info("Kitchen API startup complete.")

@app.get("/healthz", tags=["System"])
async def health_check():
    """Health check endpoint."""
    # We can add checks for db, paprika, etc. here
    return {"status": "ok"}

# --- Inventory Endpoints (DB) ---
@app.post("/inventory/items", status_code=201, tags=["Inventory"])
async def add_item(item: Item):
    """Adds a new item to the master item catalog."""
    try:
        item_id = db.add_item(item.model_dump())
        return {"item_id": item_id, "message": "Item added successfully."}
    except Exception as e:
        logger.error(f"Failed to add item: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/inventory/items", response_model=List[Dict[str, Any]], tags=["Inventory"])
async def get_all_items():
    """Retrieves all items from the master catalog."""
    try:
        return db.get_all_items()
    except Exception as e:
        logger.error(f"Failed to get all items: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/inventory/items/{item_id}", response_model=ItemResponse, tags=["Inventory"])
async def get_item(item_id: int):
    """Retrieves a single item by its ID, including its images."""
    try:
        item = db.get_item(item_id)
        if not item:
            raise HTTPException(status_code=404, detail="Item not found")
        return item
    except Exception as e:
        logger.error(f"Failed to get item {item_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/inventory/items/{item_id}/images", status_code=201, tags=["Inventory"])
async def add_item_image(item_id: int, image: ImagePath):
    """Adds an image reference to an item."""
    try:
        # In a real app, you'd save the uploaded file and get a path
        # Here we assume the path is given directly
        image_id = db.add_item_image(item_id, image.path)
        return {"image_id": image_id, "message": "Image added successfully."}
    except Exception as e:
        logger.error(f"Failed to add image to item {item_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/inventory/batches", status_code=201, tags=["Inventory"])
async def add_batch(batch: Batch):
    """Adds a new batch of an item to the inventory."""
    try:
        batch_id = db.add_batch(batch.model_dump())
        return {"batch_id": batch_id, "message": "Batch added successfully."}
    except Exception as e:
        logger.error(f"Failed to add batch: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/inventory/expiring", tags=["Inventory"])
async def get_expiring_items(days: int = 7):
    """Finds items that are expiring within a given number of days."""
    try:
        return db.get_expiring_items(days_in_future=days)
    except Exception as e:
        logger.error(f"Failed to get expiring items: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/inventory/current", tags=["Inventory"])
async def get_current_inventory():
    """Retrieves the full current inventory of all items with quantity > 0."""
    try:
        inventory = db.get_current_inventory()
        return {"data": inventory, "count": len(inventory)}
    except Exception as e:
        logger.error(f"Failed to get current inventory: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# --- Paprika Endpoints ---
@app.get("/recipes", tags=["Recipes"])
async def get_recipes():
    """Get all recipes from Paprika."""
    if not paprika_client.session_token:
        raise HTTPException(status_code=401, detail="Paprika client not authenticated.")
    try:
        return paprika_client.get_recipes()
    except Exception as e:
        logger.error(f"Failed to get recipes from Paprika: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/grocery-list", tags=["Shopping List"])
async def get_grocery_list():
    """Get the current grocery list from Paprika."""
    if not paprika_client.session_token:
        raise HTTPException(status_code=401, detail="Paprika client not authenticated.")
    try:
        return paprika_client.get_grocery_list()
    except Exception as e:
        logger.error(f"Failed to get grocery list: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/grocery-list", status_code=201, tags=["Shopping List"])
async def add_to_grocery_list(item_name: str = Body(..., embed=True)):
    """Add an item to the Paprika grocery list."""
    if not paprika_client.session_token:
        raise HTTPException(status_code=401, detail="Paprika client not authenticated.")
    try:
        result = paprika_client.add_grocery_item(name=item_name)
        return result
    except Exception as e:
        logger.error(f"Failed to add item to grocery list: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# --- Vision Endpoints ---
@app.post("/vision/scan-receipt", tags=["Vision"])
async def scan_receipt(image: ImagePath):
    """
    Processes a grocery receipt image to extract items.
    Note: Vision features are currently disabled (dependencies not installed).
    """
    try:
        # Lazy-load vision module (will fail gracefully if deps not installed)
        from vision import intake as vision_intake

        # In a real scenario, the image would be uploaded or a path on a shared volume provided.
        if not os.path.exists(image.path):
            raise HTTPException(status_code=404, detail=f"Image not found at path: {image.path}")
        result = vision_intake.process_image(image.path)
        return result
    except ImportError as e:
        logger.warning(f"Vision dependencies not installed: {e}")
        raise HTTPException(status_code=501, detail="Vision features are not currently available. Install opencv-python, pytesseract, and pyzbar to enable.")
    except Exception as e:
        logger.error(f"Failed to process image: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# --- Deals Endpoints ---
@app.post("/deals", tags=["Deals"])
async def find_deals(items: List[str] = Body(..., embed=True), postal_code: str = Body(..., embed=True)):
    """Finds grocery deals for a list of items in a given postal code."""
    try:
        # Using the mock provider for now
        deals = deals_provider.get_prices_for(items, postal_code)
        return deals
    except Exception as e:
        logger.error(f"Failed to find deals: {e}")
        raise HTTPException(status_code=500, detail=str(e))
