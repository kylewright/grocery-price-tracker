"""
Receipt processing module using OCR and text parsing.
"""
import re
import logging
from PIL import Image
import pytesseract
from pillow_heif import register_heif_opener

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Register HEIF/HEIC format support for PIL
register_heif_opener()


def extract_text_from_image(image_path):
    """
    Extract text from an image using Tesseract OCR.

    Args:
        image_path: Path to the receipt image

    Returns:
        Extracted text as a string
    """
    try:
        logger.info(f"Opening image: {image_path}")
        image = Image.open(image_path)

        logger.info(f"Image details - Format: {image.format}, Mode: {image.mode}, Size: {image.size}")

        # Convert RGBA to RGB if needed (some images have alpha channel)
        if image.mode in ('RGBA', 'LA', 'P'):
            logger.info(f"Converting image from {image.mode} to RGB")
            background = Image.new('RGB', image.size, (255, 255, 255))
            if image.mode == 'P':
                image = image.convert('RGBA')
            background.paste(image, mask=image.split()[-1] if image.mode in ('RGBA', 'LA') else None)
            image = background
        elif image.mode != 'RGB':
            logger.info(f"Converting image from {image.mode} to RGB")
            image = image.convert('RGB')

        # Resize if image is too large (over 4000px in any dimension)
        max_dimension = 4000
        if image.size[0] > max_dimension or image.size[1] > max_dimension:
            logger.info(f"Image is large ({image.size}), resizing for better performance")
            ratio = min(max_dimension / image.size[0], max_dimension / image.size[1])
            new_size = (int(image.size[0] * ratio), int(image.size[1] * ratio))
            image = image.resize(new_size, Image.Resampling.LANCZOS)
            logger.info(f"Resized to: {image.size}")

        logger.info("Running Tesseract OCR...")
        # Use Tesseract to extract text
        text = pytesseract.image_to_string(image)
        logger.info(f"OCR completed. Extracted {len(text)} characters")

        return text
    except Exception as e:
        logger.error(f"Error processing image: {type(e).__name__}: {str(e)}", exc_info=True)
        raise Exception(f"Error processing image: {type(e).__name__}: {str(e)}")


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
    logger.info(f"Processing receipt: {image_path}")

    # Extract text from image
    text = extract_text_from_image(image_path)

    # Parse items and prices
    items = parse_receipt_text(text)
    logger.info(f"Found {len(items)} items in receipt")

    # Try to extract store name from receipt if not provided
    if not store_name:
        lines = text.split('\n')[:5]  # Check first 5 lines
        for line in lines:
            line = line.strip()
            # Store names are usually in the first few lines and all caps or title case
            if len(line) > 3 and len(line) < 50:
                store_name = line
                break
        if store_name:
            logger.info(f"Detected store name: {store_name}")

    return {
        'text': text,
        'items': items,
        'store_name': store_name
    }
