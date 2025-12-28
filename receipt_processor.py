"""
Receipt processing module using OCR and text parsing.
"""
import re
from PIL import Image
import pytesseract


def extract_text_from_image(image_path):
    """
    Extract text from an image using Tesseract OCR.

    Args:
        image_path: Path to the receipt image

    Returns:
        Extracted text as a string
    """
    try:
        image = Image.open(image_path)
        # Use Tesseract to extract text
        text = pytesseract.image_to_string(image)
        return text
    except Exception as e:
        raise Exception(f"Error processing image: {str(e)}")


def parse_receipt_text(text):
    """
    Parse receipt text to extract items and prices.

    This function looks for patterns that match grocery items with prices.
    Common patterns on receipts:
    - ITEM NAME          $X.XX
    - ITEM NAME  X.XX
    - Item description followed by price on same or next line

    Args:
        text: OCR-extracted text from receipt

    Returns:
        List of tuples (item_name, price)
    """
    items = []
    lines = text.split('\n')

    # Pattern to match prices: digits with optional decimal points
    # Matches formats like: 1.99, $1.99, 10.50, etc.
    price_pattern = r'\$?(\d+\.\d{2})'

    for i, line in enumerate(lines):
        line = line.strip()
        if not line:
            continue

        # Look for price patterns in the line
        price_matches = re.findall(price_pattern, line)

        if price_matches:
            # Get the last price on the line (usually the actual item price)
            price = float(price_matches[-1])

            # Extract item name (everything before the price)
            # Remove the price and clean up the item name
            item_name = re.sub(r'\$?\d+\.\d{2}', '', line).strip()

            # Clean up common receipt artifacts
            item_name = re.sub(r'\s+', ' ', item_name)  # Multiple spaces to single space
            item_name = re.sub(r'^\d+\s+', '', item_name)  # Remove leading numbers (quantities)
            item_name = re.sub(r'[*@#]', '', item_name)  # Remove special characters

            # Skip if item name is too short or looks like a total/subtotal
            if len(item_name) > 2 and not any(word in item_name.lower() for word in
                                              ['total', 'subtotal', 'tax', 'change', 'cash', 'credit', 'debit',
                                               'balance', 'tender', 'payment']):
                items.append((item_name, price))

    return items


def process_receipt(image_path, store_name=None):
    """
    Process a receipt image: extract text and parse items.

    Args:
        image_path: Path to the receipt image
        store_name: Optional name of the store

    Returns:
        Dictionary with:
        - 'text': Raw OCR text
        - 'items': List of (item_name, price) tuples
        - 'store_name': Store name if provided
    """
    # Extract text from image
    text = extract_text_from_image(image_path)

    # Parse items and prices
    items = parse_receipt_text(text)

    # Try to extract store name from receipt if not provided
    if not store_name:
        lines = text.split('\n')[:5]  # Check first 5 lines
        for line in lines:
            line = line.strip()
            # Store names are usually in the first few lines and all caps or title case
            if len(line) > 3 and len(line) < 50:
                store_name = line
                break

    return {
        'text': text,
        'items': items,
        'store_name': store_name
    }
