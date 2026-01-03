"""
Receipt processing module using Donut (Document Understanding Transformer).
"""
import re
import logging
import torch
from PIL import Image
from transformers import DonutProcessor, VisionEncoderDecoderModel
from pillow_heif import register_heif_opener

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Register HEIF/HEIC format support for PIL
register_heif_opener()

# Global variables for model and processor (loaded once on first use)
_model = None
_processor = None
_device = None


def load_donut_model():
    """
    Load the Donut model and processor.
    Uses GPU if CUDA is available, otherwise falls back to CPU.
    Model is loaded once and cached globally.

    Returns:
        tuple: (model, processor, device)
    """
    global _model, _processor, _device

    if _model is not None and _processor is not None:
        logger.info(f"Using cached Donut model on {_device}")
        return _model, _processor, _device

    logger.info("Loading Donut model (naver-clova-ix/donut-base-finetuned-cord-v2)...")
    logger.info("This is a ~800MB model and may take a moment to download on first use...")

    # Determine device (GPU if available, otherwise CPU)
    _device = "cuda" if torch.cuda.is_available() else "cpu"
    logger.info(f"Using device: {_device}")

    # Load processor and model
    model_name = "naver-clova-ix/donut-base-finetuned-cord-v2"
    _processor = DonutProcessor.from_pretrained(model_name)
    _model = VisionEncoderDecoderModel.from_pretrained(model_name)

    # Move model to appropriate device
    _model.to(_device)

    logger.info("Donut model loaded successfully")
    return _model, _processor, _device


def extract_text_from_image(image_path):
    """
    Extract structured data from a receipt image using Donut model.

    Args:
        image_path: Path to the receipt image (or PIL Image object)

    Returns:
        Dictionary with structured receipt data containing:
        - menu: array of line items with nm (name), cnt (count), and price
        - sub_total: subtotal price
        - total: total price
    """
    try:
        # Load model and processor
        model, processor, device = load_donut_model()

        # Load image
        logger.info(f"Processing image: {image_path}")
        if isinstance(image_path, str):
            image = Image.open(image_path)
        else:
            image = image_path  # Already a PIL Image

        # Convert to RGB if needed
        if image.mode != 'RGB':
            logger.info(f"Converting image from {image.mode} to RGB")
            if image.mode in ('RGBA', 'LA', 'P'):
                background = Image.new('RGB', image.size, (255, 255, 255))
                if image.mode == 'P':
                    image = image.convert('RGBA')
                background.paste(image, mask=image.split()[-1] if image.mode in ('RGBA', 'LA') else None)
                image = background
            else:
                image = image.convert('RGB')

        logger.info(f"Image size: {image.size}")

        # Prepare decoder input with task prompt
        task_prompt = "<s_cord-v2>"
        decoder_input_ids = processor.tokenizer(
            task_prompt,
            add_special_tokens=False,
            return_tensors="pt"
        ).input_ids

        # Process image
        pixel_values = processor(image, return_tensors="pt").pixel_values

        # Move to device
        pixel_values = pixel_values.to(device)
        decoder_input_ids = decoder_input_ids.to(device)

        # Generate output
        logger.info("Running Donut model inference...")
        outputs = model.generate(
            pixel_values,
            decoder_input_ids=decoder_input_ids,
            max_length=model.decoder.config.max_position_embeddings,
            pad_token_id=processor.tokenizer.pad_token_id,
            eos_token_id=processor.tokenizer.eos_token_id,
            use_cache=True,
            bad_words_ids=[[processor.tokenizer.unk_token_id]],
            return_dict_in_generate=True,
        )

        # Decode output to JSON
        sequence = processor.batch_decode(outputs.sequences)[0]
        sequence = sequence.replace(processor.tokenizer.eos_token, "").replace(processor.tokenizer.pad_token, "")
        sequence = re.sub(r"<.*?>", "", sequence, count=1).strip()  # Remove first task token

        logger.info(f"Raw model output (first 500 chars): {sequence[:500]}...")
        logger.info(f"Full raw model output length: {len(sequence)} characters")

        # Parse JSON output
        result = processor.token2json(sequence)
        logger.info(f"Parsed JSON structure keys: {list(result.keys()) if isinstance(result, dict) else 'Not a dict'}")
        logger.info(f"Full parsed JSON: {result}")

        return result

    except Exception as e:
        logger.error(f"Error processing image with Donut: {type(e).__name__}: {str(e)}", exc_info=True)
        raise Exception(f"Error processing image with Donut: {type(e).__name__}: {str(e)}")


def parse_receipt_data(donut_output):
    """
    Parse Donut model output to extract items and prices.

    The Donut CORD-v2 model outputs structured JSON with:
    - menu: array of items with nm (name), cnt (count), and price
    - sub_total: subtotal
    - total: total price

    Args:
        donut_output: Structured output from Donut model

    Returns:
        List of tuples (item_name, price)
    """
    logger.info("Parsing Donut output...")
    logger.info(f"Full Donut output structure: {donut_output}")
    items = []

    try:
        # Extract menu items from Donut output
        menu_items = donut_output.get('menu', [])

        if not menu_items:
            logger.warning("No menu items found in Donut output")
            logger.warning(f"Available keys in output: {list(donut_output.keys())}")
            return items

        logger.info(f"Found {len(menu_items)} menu items in Donut output")

        for idx, item in enumerate(menu_items):
            logger.info(f"Processing item {idx + 1}: {item}")

            # Extract name and price
            item_name = item.get('nm', '').strip()
            price_info = item.get('price', {})

            # Price can be a dict with 'price' key or directly a string
            if isinstance(price_info, dict):
                # Could be {'price': '1.99'} or {'unitprice': '1.99', 'price': '3.98'}
                price_str = price_info.get('price', price_info.get('unitprice', '0'))
            else:
                price_str = str(price_info)

            logger.info(f"Item '{item_name}' has price_info: {price_info}, extracted price_str: {price_str}")

            # Clean and parse price
            # Remove currency symbols and convert to float
            price_str = re.sub(r'[^\d.]', '', str(price_str))

            try:
                price = float(price_str) if price_str else 0.0

                # Skip invalid items
                if not item_name or price <= 0 or price > 1000:
                    logger.warning(f"Skipping invalid item: '{item_name}' - ${price} (empty name or invalid price)")
                    continue

                logger.info(f"Found valid item: '{item_name}' - ${price:.2f}")
                items.append((item_name, price))

            except ValueError:
                logger.warning(f"Could not parse price for item '{item_name}': {price_str}")
                continue

    except Exception as e:
        logger.error(f"Error parsing Donut output: {type(e).__name__}: {str(e)}", exc_info=True)

    logger.info(f"Total items parsed: {len(items)}")
    return items


def process_receipt(image_path, store_name=None):
    """
    Process a receipt image using Donut: extract structured data and parse items.

    Args:
        image_path: Path to the receipt image
        store_name: Optional name of the store

    Returns:
        Dictionary with:
        - 'text': Raw JSON output from Donut (as string)
        - 'items': List of (item_name, price) tuples
        - 'store_name': Store name if provided
        - 'structured_data': Full structured output from Donut
    """
    logger.info(f"Processing receipt with Donut: {image_path}")

    # Extract structured data from image using Donut
    donut_output = extract_text_from_image(image_path)

    # Parse items and prices from Donut output
    items = parse_receipt_data(donut_output)
    logger.info(f"Found {len(items)} items in receipt")

    # Try to extract store name from Donut output if not provided
    if not store_name and 'store' in donut_output:
        store_name = donut_output.get('store', {}).get('name', None)
        if store_name:
            logger.info(f"Detected store name from Donut: {store_name}")

    return {
        'text': str(donut_output),  # JSON output as string for compatibility
        'items': items,
        'store_name': store_name,
        'structured_data': donut_output  # Full structured data for advanced use
    }
