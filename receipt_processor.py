"""
Receipt processing module using OCR and text parsing.
"""
import re
import logging
from PIL import Image, ImageEnhance, ImageFilter
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

        # Try multiple preprocessing approaches and use the best result
        logger.info("Trying multiple OCR preprocessing approaches...")

        best_text = ""
        best_char_count = 0

        # Approach 1: Simple grayscale with high contrast
        logger.info("Attempt 1: High contrast grayscale...")
        img1 = image.convert('L')
        enhancer = ImageEnhance.Contrast(img1)
        img1 = enhancer.enhance(3.0)
        text1 = pytesseract.image_to_string(img1, config=r'--oem 3 --psm 6')
        logger.info(f"Approach 1: {len(text1)} characters")
        if len(text1) > best_char_count:
            best_text = text1
            best_char_count = len(text1)

        # Approach 2: Binary threshold
        logger.info("Attempt 2: Binary threshold...")
        img2 = image.convert('L')
        # Convert to black and white with threshold
        threshold = 128
        img2 = img2.point(lambda x: 0 if x < threshold else 255, '1')
        text2 = pytesseract.image_to_string(img2, config=r'--oem 3 --psm 6')
        logger.info(f"Approach 2: {len(text2)} characters")
        if len(text2) > best_char_count:
            best_text = text2
            best_char_count = len(text2)

        # Approach 3: Minimal processing with PSM 4 (single column)
        logger.info("Attempt 3: Minimal processing, PSM 4...")
        img3 = image.convert('L')
        text3 = pytesseract.image_to_string(img3, config=r'--oem 3 --psm 4')
        logger.info(f"Approach 3: {len(text3)} characters")
        if len(text3) > best_char_count:
            best_text = text3
            best_char_count = len(text3)

        text = best_text
        logger.info(f"OCR completed. Using best result with {len(text)} characters")

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
    logger.info("Parsing receipt text...")
    logger.info(f"First 500 characters of OCR text:\n{text[:500]}")

    items = []
    lines = text.split('\n')

    # Pattern to match prices: digits with optional decimal points
    # More flexible patterns to match various formats including OCR errors
    price_patterns = [
        r'\$\s?(\d+\.\d{2})',           # $1.99 or $ 1.99
        r'(\d+\.\d{2})\s*$',            # 1.99 at end of line
        r'\s(\d+\.\d{2})\s',            # 1.99 with spaces around it
        r'\$(\d+\.\d{2})',              # $1.99
        r"(\d+)'(\d{2})\$",             # OCR error: 2'99$ instead of $2.99
        r'(\d+)[,\'](\d{2})',           # OCR error: 2,99 or 2'99
        r'\$\s?(\d+)[,\'](\d{2})',      # OCR error: $2,99 or $2'99
    ]

    for i, line in enumerate(lines):
        line = line.strip()
        if not line:
            continue

        # Try each price pattern
        price_matches = []
        for pattern in price_patterns:
            matches = re.findall(pattern, line)
            for match in matches:
                # Handle tuple results from multi-group patterns
                if isinstance(match, tuple):
                    # Join tuple parts (e.g., ('2', '99') -> '2.99')
                    price_str = '.'.join(match)
                else:
                    price_str = match
                price_matches.append(price_str)

        if price_matches:
            # Get the last price on the line (usually the actual item price)
            try:
                price = float(price_matches[-1])
                # Skip unrealistic prices
                if price <= 0 or price > 1000:
                    continue
            except ValueError:
                continue

            # Extract item name (everything before the price)
            # Remove the price and clean up the item name
            item_name = re.sub(r'\$?\s?\d+[\.\,\']\d{2}\$?', '', line).strip()  # Remove price patterns
            item_name = re.sub(r'\$?\s?\d+\.\d{2}', '', item_name).strip()

            # Clean up common receipt artifacts
            item_name = re.sub(r'\s+', ' ', item_name)  # Multiple spaces to single space
            item_name = re.sub(r'^\d+\s+', '', item_name)  # Remove leading numbers (quantities)
            item_name = re.sub(r'[*@#\[\]]', '', item_name)  # Remove special characters
            item_name = item_name.strip()

            # Skip if item name is too short or looks like a total/subtotal
            skip_words = ['total', 'subtotal', 'tax', 'change', 'cash', 'credit', 'debit',
                         'balance', 'tender', 'payment', 'discount', 'coupon', 'savings']

            if len(item_name) > 2 and not any(word in item_name.lower() for word in skip_words):
                logger.info(f"Found item: '{item_name}' - ${price:.2f}")
                items.append((item_name, price))

    logger.info(f"Total items parsed: {len(items)}")
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
