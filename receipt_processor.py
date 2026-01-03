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
        prompt = """Extract items from this grocery receipt image. Return ONLY valid JSON.

CRITICAL RULES:
1. Extract each product line EXACTLY ONCE - never repeat items
2. If an item appears multiple times on the receipt with the same price, list it only ONCE
3. Use the exact item name as printed on the receipt
4. Stop after extracting all unique items - do NOT continue generating

JSON format (no markdown, no extra text):
{
  "items": [
    {"name": "ITEM 1", "price": 1.99},
    {"name": "ITEM 2", "price": 2.49}
  ],
  "subtotal": 10.50,
  "total": 11.50,
  "store_name": "Store Name"
}

Skip: tax, subtotal lines, payment info, bottle deposits"""

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
            'max_tokens': 16000,  # High limit for long receipts
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
        logger.info(f"Response text length: {len(response_text)} characters")

        # Check if response was truncated
        finish_reason = result['choices'][0].get('finish_reason', 'unknown')
        logger.info(f"Finish reason: {finish_reason}")
        if finish_reason == 'length':
            logger.warning("WARNING: API response was truncated due to max_tokens limit!")

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

        # Try to fix incomplete JSON by truncating to last valid item
        if not response_text.endswith('}'):
            logger.warning("JSON appears incomplete, attempting to repair by truncating to last valid item...")

            # Find the last complete item entry before truncation
            # Look for the last occurrence of "},\n" or "}," which indicates end of an item
            last_valid_item = response_text.rfind('},')

            if last_valid_item != -1:
                # Truncate at the last valid item
                response_text = response_text[:last_valid_item + 1]  # Keep the }

                # Now close the items array and add closing fields
                response_text += '\n  ],\n  "subtotal": 0,\n  "total": 0,\n  "store_name": ""\n}'

                logger.info(f"Truncated response to last valid item at position {last_valid_item}")
            else:
                logger.warning("Could not find valid truncation point, attempting bracket closure...")
                # Fallback: just close brackets
                open_braces = response_text.count('{')
                close_braces = response_text.count('}')
                open_brackets = response_text.count('[')
                close_brackets = response_text.count(']')

                if open_brackets > close_brackets:
                    response_text += ']' * (open_brackets - close_brackets)
                if open_braces > close_braces:
                    response_text += '}' * (open_braces - close_braces)

        # Parse JSON
        parsed_data = json.loads(response_text)
        logger.info(f"Parsed JSON structure: {list(parsed_data.keys())}")
        logger.info(f"Number of items extracted: {len(parsed_data.get('items', []))}")

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
    seen_items = {}  # Track items to detect and remove duplicates/hallucinations

    try:
        # Extract items from API output
        items_list = api_output.get('items', [])

        if not items_list:
            logger.warning("No items found in API output")
            logger.warning(f"Available keys in output: {list(api_output.keys())}")
            return items

        logger.info(f"Found {len(items_list)} raw items in API output")

        for idx, item in enumerate(items_list):
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
                continue

            # Create a key for deduplication (name + price)
            item_key = f"{item_name.lower()}_{price:.2f}"

            # Check for hallucination: if we've seen this exact item more than 3 times, stop processing
            if item_key in seen_items:
                seen_items[item_key] += 1
                if seen_items[item_key] > 3:
                    logger.warning(f"Detected hallucination: '{item_name}' repeated {seen_items[item_key]} times. Stopping item extraction.")
                    break
            else:
                seen_items[item_key] = 1
                # Only add unique items
                logger.info(f"Found valid item: '{item_name}' - ${price:.2f}")
                items.append((item_name, price))

    except Exception as e:
        logger.error(f"Error parsing API output: {type(e).__name__}: {str(e)}", exc_info=True)

    logger.info(f"Total unique items parsed: {len(items)}")

    # Log if we detected hallucination
    max_repeats = max(seen_items.values()) if seen_items else 0
    if max_repeats > 3:
        logger.warning(f"Hallucination detected! Maximum item repetition: {max_repeats} times")

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
