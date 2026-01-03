"""
Receipt processing module using OpenRouter API with vision models.
"""
import os
import re
import json
import logging
import base64
from PIL import Image
import requests
from pillow_heif import register_heif_opener

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Register HEIF/HEIC format support for PIL
register_heif_opener()

# OpenRouter API configuration
OPENROUTER_API_KEY = os.environ.get('OPENROUTER_API_KEY')
OPENROUTER_API_URL = 'https://openrouter.ai/api/v1/chat/completions'

# Model to use - GPT-4 Vision is excellent for OCR tasks
# Alternative: 'anthropic/claude-3.5-sonnet' or 'google/gemini-pro-vision'
DEFAULT_MODEL = 'openai/gpt-4o'


def encode_image_to_base64(image_path):
    """
    Encode an image to base64 for API transmission.

    Args:
        image_path: Path to the image file or PIL Image object

    Returns:
        Base64 encoded string of the image
    """
    try:
        if isinstance(image_path, str):
            # Load and convert image
            image = Image.open(image_path)
        else:
            image = image_path

        # Convert to RGB if needed
        if image.mode in ('RGBA', 'LA', 'P'):
            logger.info(f"Converting image from {image.mode} to RGB")
            background = Image.new('RGB', image.size, (255, 255, 255))
            if image.mode == 'P':
                image = image.convert('RGBA')
            background.paste(image, mask=image.split()[-1] if image.mode in ('RGBA', 'LA') else None)
            image = background
        elif image.mode != 'RGB':
            image = image.convert('RGB')

        # Resize if too large (max 2048px for most vision models)
        max_dimension = 2048
        if image.size[0] > max_dimension or image.size[1] > max_dimension:
            logger.info(f"Resizing image from {image.size}")
            ratio = min(max_dimension / image.size[0], max_dimension / image.size[1])
            new_size = (int(image.size[0] * ratio), int(image.size[1] * ratio))
            image = image.resize(new_size, Image.Resampling.LANCZOS)
            logger.info(f"Resized to: {image.size}")

        # Save to bytes and encode
        import io
        buffer = io.BytesIO()
        image.save(buffer, format='JPEG', quality=95)
        image_bytes = buffer.getvalue()

        # Encode to base64
        base64_image = base64.b64encode(image_bytes).decode('utf-8')
        return base64_image

    except Exception as e:
        logger.error(f"Error encoding image: {type(e).__name__}: {str(e)}", exc_info=True)
        raise


def extract_text_from_image(image_path, model=DEFAULT_MODEL):
    """
    Extract structured data from a receipt image using OpenRouter vision API.

    Args:
        image_path: Path to the receipt image (or PIL Image object)
        model: OpenRouter model to use (default: GPT-4 Vision)

    Returns:
        Dictionary with structured receipt data containing items and prices
    """
    try:
        if not OPENROUTER_API_KEY:
            raise Exception("OPENROUTER_API_KEY environment variable not set. Please set it with your OpenRouter API key.")

        logger.info(f"Processing image with OpenRouter model: {model}")
        logger.info(f"Image: {image_path}")

        # Encode image to base64
        base64_image = encode_image_to_base64(image_path)
        logger.info(f"Image encoded, size: {len(base64_image)} characters")

        # Prepare the prompt for receipt extraction
        prompt = """Please analyze this receipt image and extract ALL items with their prices in JSON format.

For each item on the receipt, extract:
- The item name (product description)
- The price (individual item price, not quantity × price)

Return ONLY a valid JSON object with this structure:
{
  "items": [
    {"name": "ITEM NAME", "price": 1.99},
    {"name": "ANOTHER ITEM", "price": 2.49}
  ],
  "subtotal": 10.50,
  "total": 11.50,
  "store_name": "Store Name"
}

Important:
- Extract ALL line items from the receipt
- Use the individual item price, not totals for quantities
- Skip non-product lines (tax, subtotal, total, payment info)
- Price should be a number (float), not a string
- Return valid JSON only, no other text"""

        # Make API request to OpenRouter
        headers = {
            'Authorization': f'Bearer {OPENROUTER_API_KEY}',
            'Content-Type': 'application/json',
            'HTTP-Referer': 'https://github.com/kylewright/grocery-price-tracker',
        }

        payload = {
            'model': model,
            'messages': [
                {
                    'role': 'user',
                    'content': [
                        {
                            'type': 'text',
                            'text': prompt
                        },
                        {
                            'type': 'image_url',
                            'image_url': {
                                'url': f'data:image/jpeg;base64,{base64_image}'
                            }
                        }
                    ]
                }
            ],
            'max_tokens': 4000,
            'temperature': 0.1,  # Low temperature for consistent, accurate extraction
        }

        logger.info("Sending request to OpenRouter API...")
        response = requests.post(OPENROUTER_API_URL, headers=headers, json=payload, timeout=60)
        response.raise_for_status()

        result = response.json()
        logger.info(f"API Response status: {response.status_code}")

        # Extract the response text
        if 'choices' not in result or len(result['choices']) == 0:
            raise Exception(f"Unexpected API response format: {result}")

        response_text = result['choices'][0]['message']['content']
        logger.info(f"Raw API response (first 500 chars): {response_text[:500]}...")

        # Parse JSON from response
        # Sometimes the model wraps JSON in markdown code blocks
        response_text = response_text.strip()
        if response_text.startswith('```json'):
            response_text = response_text[7:]  # Remove ```json
        if response_text.startswith('```'):
            response_text = response_text[3:]  # Remove ```
        if response_text.endswith('```'):
            response_text = response_text[:-3]  # Remove trailing ```
        response_text = response_text.strip()

        # Parse JSON
        parsed_data = json.loads(response_text)
        logger.info(f"Parsed JSON structure: {list(parsed_data.keys())}")
        logger.info(f"Full parsed data: {parsed_data}")

        return parsed_data

    except requests.exceptions.RequestException as e:
        logger.error(f"API request error: {type(e).__name__}: {str(e)}", exc_info=True)
        raise Exception(f"Error calling OpenRouter API: {type(e).__name__}: {str(e)}")
    except json.JSONDecodeError as e:
        logger.error(f"JSON parsing error: {str(e)}", exc_info=True)
        logger.error(f"Response text was: {response_text}")
        raise Exception(f"Error parsing API response as JSON: {str(e)}")
    except Exception as e:
        logger.error(f"Error processing image: {type(e).__name__}: {str(e)}", exc_info=True)
        raise Exception(f"Error processing image: {type(e).__name__}: {str(e)}")


def parse_receipt_data(api_output):
    """
    Parse OpenRouter API output to extract items and prices.

    Args:
        api_output: Structured output from OpenRouter vision model

    Returns:
        List of tuples (item_name, price)
    """
    logger.info("Parsing API output...")
    items = []

    try:
        # Extract items from API output
        items_list = api_output.get('items', [])

        if not items_list:
            logger.warning("No items found in API output")
            logger.warning(f"Available keys in output: {list(api_output.keys())}")
            return items

        logger.info(f"Found {len(items_list)} items in API output")

        for idx, item in enumerate(items_list):
            logger.info(f"Processing item {idx + 1}: {item}")

            # Extract name and price
            item_name = item.get('name', '').strip()
            price = item.get('price', 0)

            # Ensure price is a float
            try:
                if isinstance(price, str):
                    # Remove currency symbols and convert
                    price = float(re.sub(r'[^\d.]', '', price))
                else:
                    price = float(price)
            except (ValueError, TypeError):
                logger.warning(f"Could not parse price for item '{item_name}': {item.get('price')}")
                continue

            # Skip invalid items
            if not item_name or price <= 0 or price > 1000:
                logger.warning(f"Skipping invalid item: '{item_name}' - ${price} (empty name or invalid price)")
                continue

            logger.info(f"Found valid item: '{item_name}' - ${price:.2f}")
            items.append((item_name, price))

    except Exception as e:
        logger.error(f"Error parsing API output: {type(e).__name__}: {str(e)}", exc_info=True)

    logger.info(f"Total items parsed: {len(items)}")
    return items


def process_receipt(image_path, store_name=None):
    """
    Process a receipt image using OpenRouter: extract structured data and parse items.

    Args:
        image_path: Path to the receipt image
        store_name: Optional name of the store

    Returns:
        Dictionary with:
        - 'text': Raw JSON output from API (as string)
        - 'items': List of (item_name, price) tuples
        - 'store_name': Store name if provided or detected
        - 'structured_data': Full structured output from API
    """
    logger.info(f"Processing receipt with OpenRouter: {image_path}")

    # Extract structured data from image using OpenRouter
    api_output = extract_text_from_image(image_path)

    # Parse items and prices from API output
    items = parse_receipt_data(api_output)
    logger.info(f"Found {len(items)} items in receipt")

    # Try to extract store name from API output if not provided
    if not store_name and 'store_name' in api_output:
        store_name = api_output.get('store_name', None)
        if store_name:
            logger.info(f"Detected store name from API: {store_name}")

    return {
        'text': json.dumps(api_output, indent=2),  # JSON output as formatted string
        'items': items,
        'store_name': store_name,
        'structured_data': api_output  # Full structured data for advanced use
    }
