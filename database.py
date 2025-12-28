"""
Database module for managing grocery items and price records.
"""
import sqlite3
from datetime import datetime
from contextlib import contextmanager


DATABASE_PATH = 'grocery_prices.db'


@contextmanager
def get_db():
    """Context manager for database connections."""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def init_db():
    """Initialize the database with required tables."""
    with get_db() as conn:
        cursor = conn.cursor()

        # Create items table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Create price_records table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS price_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                item_id INTEGER NOT NULL,
                price REAL NOT NULL,
                date DATE NOT NULL,
                store_name TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (item_id) REFERENCES items (id)
            )
        ''')

        # Create index for faster lookups
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_price_records_date
            ON price_records(date)
        ''')

        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_price_records_item
            ON price_records(item_id)
        ''')

        conn.commit()


def upsert_item_with_price(item_name, price, store_name=None, date=None):
    """
    Insert or update an item and add a price record.

    Args:
        item_name: Name of the grocery item
        price: Price of the item
        store_name: Optional store name
        date: Date of the price record (defaults to today)

    Returns:
        Tuple of (item_id, price_record_id)
    """
    if date is None:
        date = datetime.now().strftime('%Y-%m-%d')

    with get_db() as conn:
        cursor = conn.cursor()

        # Normalize item name (lowercase, strip whitespace)
        item_name = item_name.strip().lower()

        # Insert or get item
        cursor.execute('''
            INSERT OR IGNORE INTO items (name) VALUES (?)
        ''', (item_name,))

        # Get item ID
        cursor.execute('SELECT id FROM items WHERE name = ?', (item_name,))
        item_id = cursor.fetchone()[0]

        # Insert price record
        cursor.execute('''
            INSERT INTO price_records (item_id, price, date, store_name)
            VALUES (?, ?, ?, ?)
        ''', (item_id, price, date, store_name))

        price_record_id = cursor.lastrowid

        conn.commit()

        return item_id, price_record_id


def get_all_items_with_latest_price():
    """Get all items with their latest price."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT
                i.id,
                i.name,
                pr.price as latest_price,
                pr.date as latest_date,
                pr.store_name
            FROM items i
            LEFT JOIN (
                SELECT
                    item_id,
                    price,
                    date,
                    store_name,
                    ROW_NUMBER() OVER (PARTITION BY item_id ORDER BY date DESC) as rn
                FROM price_records
            ) pr ON i.id = pr.item_id AND pr.rn = 1
            ORDER BY i.name
        ''')
        return cursor.fetchall()


def get_item_price_history(item_id):
    """Get price history for a specific item."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT
                pr.price,
                pr.date,
                pr.store_name,
                pr.created_at
            FROM price_records pr
            WHERE pr.item_id = ?
            ORDER BY pr.date DESC
        ''', (item_id,))
        return cursor.fetchall()


def get_recent_uploads(limit=10):
    """Get recently processed items."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT
                i.name,
                pr.price,
                pr.date,
                pr.store_name,
                pr.created_at
            FROM price_records pr
            JOIN items i ON pr.item_id = i.id
            ORDER BY pr.created_at DESC
            LIMIT ?
        ''', (limit,))
        return cursor.fetchall()
