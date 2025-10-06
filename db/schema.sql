-- Kitchen Stack Database Schema
-- SQLite schema for inventory management, meal planning, and taste profiling

-- Table: items
-- Master catalog of food items with nutritional and categorization data
CREATE TABLE IF NOT EXISTS items (
    item_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    category TEXT NOT NULL,  -- 'produce', 'dairy', 'meat', 'pantry', 'frozen', etc.
    unit TEXT NOT NULL,  -- 'kg', 'L', 'units', 'lbs', 'oz', etc.
    calories_per_unit REAL,
    protein_per_unit REAL,
    carbs_per_unit REAL,
    fat_per_unit REAL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Table: batches
-- Individual batches of items with expiration tracking
CREATE TABLE IF NOT EXISTS batches (
    batch_id INTEGER PRIMARY KEY AUTOINCREMENT,
    item_id INTEGER NOT NULL,
    quantity REAL NOT NULL,  -- Amount in units specified by item
    purchase_date DATE NOT NULL,
    expiration_date DATE,
    location TEXT,  -- 'fridge', 'freezer', 'pantry', etc.
    cost REAL,  -- Purchase cost for price tracking
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (item_id) REFERENCES items(item_id) ON DELETE CASCADE
);

-- Table: price_history
-- Historical price tracking for items
CREATE TABLE IF NOT EXISTS price_history (
    price_id INTEGER PRIMARY KEY AUTOINCREMENT,
    item_id INTEGER NOT NULL,
    price REAL NOT NULL,
    store TEXT,
    recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (item_id) REFERENCES items(item_id) ON DELETE CASCADE
);

-- Table: taste_profile
-- User taste preferences and ratings
CREATE TABLE IF NOT EXISTS taste_profile (
    profile_id INTEGER PRIMARY KEY AUTOINCREMENT,
    item_id INTEGER NOT NULL,
    rating INTEGER CHECK(rating >= 1 AND rating <= 5),  -- 1-5 star rating
    notes TEXT,
    last_consumed DATE,
    consumption_frequency TEXT,  -- 'daily', 'weekly', 'monthly', 'rarely'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (item_id) REFERENCES items(item_id) ON DELETE CASCADE
);

-- Table: weekly_menu
-- Planned meals for the week
CREATE TABLE IF NOT EXISTS weekly_menu (
    menu_id INTEGER PRIMARY KEY AUTOINCREMENT,
    meal_date DATE NOT NULL,
    meal_type TEXT NOT NULL,  -- 'breakfast', 'lunch', 'dinner', 'snack'
    recipe_name TEXT NOT NULL,
    ingredients TEXT,  -- JSON or comma-separated list of item_ids
    calories REAL,
    prep_time_minutes INTEGER,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_batches_item_id ON batches(item_id);
CREATE INDEX IF NOT EXISTS idx_batches_expiration ON batches(expiration_date);
CREATE INDEX IF NOT EXISTS idx_price_history_item_id ON price_history(item_id);
CREATE INDEX IF NOT EXISTS idx_taste_profile_item_id ON taste_profile(item_id);
CREATE INDEX IF NOT EXISTS idx_weekly_menu_date ON weekly_menu(meal_date);
