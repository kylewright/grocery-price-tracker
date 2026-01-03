# Grocery Price Tracker

A web-based application to track grocery prices over time by processing receipt images. Upload or take photos of your grocery receipts, and the application will automatically extract items and prices using OCR (Optical Character Recognition) technology.

## Features

- **Receipt Upload**: Take photos with your device camera or upload existing receipt images
- **Automatic Processing**: Uses OpenRouter with GPT-4 Vision to extract items and prices from receipts with high accuracy
- **Price Tracking**: Stores historical pricing data for all grocery items
- **Price History**: View price changes over time for individual items
- **Search & Filter**: Easily search and sort through tracked items
- **Store Tracking**: Optional store name tracking for multi-store price comparison

## Technology Stack

- **Backend**: Python Flask
- **Database**: SQLite
- **AI/OCR**: OpenRouter API with GPT-4 Vision (or Claude 3.5 Sonnet)
- **Frontend**: HTML, CSS, JavaScript
- **Image Processing**: Pillow (PIL)

## Prerequisites

Before running this application, you need:

1. **Python 3.8+**
2. **OpenRouter API Key**: Sign up at [OpenRouter.ai](https://openrouter.ai/) to get an API key
   - Free tier available for testing
   - Pay-as-you-go pricing (very affordable for OCR tasks)

## Installation

1. **Clone the repository**
```bash
git clone <repository-url>
cd grocery-price-tracker
```

2. **Create a virtual environment** (recommended)
```bash
python -m venv venv

# On Linux/macOS
source venv/bin/activate

# On Windows
venv\Scripts\activate
```

3. **Install Python dependencies**
```bash
pip install -r requirements.txt
```

4. **Set up your OpenRouter API key**
```bash
# On Linux/macOS
export OPENROUTER_API_KEY='your-api-key-here'

# On Windows (Command Prompt)
set OPENROUTER_API_KEY=your-api-key-here

# On Windows (PowerShell)
$env:OPENROUTER_API_KEY='your-api-key-here'
```

Alternatively, add it to your shell profile (~/.bashrc, ~/.zshrc, etc.) to make it permanent.

5. **Initialize the database**
The database will be automatically created when you first run the application.

## Usage

1. **Start the Flask server**
```bash
python app.py
```

2. **Open your browser**
Navigate to: http://localhost:5001

3. **Upload a receipt**
   - Click "Choose File" to upload an existing image, or use your device camera
   - Optionally enter the store name
   - Click "Process Receipt"
   - The application will extract items and prices automatically

4. **View tracked items**
   - Click "View All Items" to see all tracked grocery items
   - Click "View History" on any item to see price changes over time
   - Use the search box to find specific items
   - Click column headers to sort

## Project Structure

```
grocery-price-tracker/
├── app.py                  # Main Flask application
├── database.py             # Database models and operations
├── receipt_processor.py    # OCR and text parsing logic
├── requirements.txt        # Python dependencies
├── grocery_prices.db       # SQLite database (created on first run)
├── static/
│   └── style.css          # CSS styles
├── templates/
│   ├── index.html         # Upload page
│   └── items.html         # Items listing page
└── uploads/               # Temporary storage for uploaded receipts
```

## Database Schema

### Items Table
- `id`: Primary key
- `name`: Item name (unique, normalized to lowercase)
- `created_at`: Timestamp of first encounter

### Price Records Table
- `id`: Primary key
- `item_id`: Foreign key to items table
- `price`: Item price
- `date`: Date of price record
- `store_name`: Optional store name
- `created_at`: Timestamp of record creation

## API Endpoints

- `GET /` - Main upload page
- `POST /upload` - Upload and process receipt
- `GET /items` - View all items
- `GET /items/<id>/history` - Get price history for an item (JSON)
- `GET /api/items` - Get all items as JSON

## Tips for Best Results

1. **Image Quality**: Use clear, well-lit photos of receipts
2. **Orientation**: Ensure receipt is upright and flat
3. **Receipt Type**: Works with all receipt types - printed, handwritten, or digital
4. **API Costs**: GPT-4 Vision costs ~$0.01-0.03 per receipt (check OpenRouter pricing)
5. **Accuracy**: Vision models are highly accurate but always verify extracted data

## Troubleshooting

### API Key Issues
- Ensure `OPENROUTER_API_KEY` environment variable is set correctly
- Verify your API key is valid at [OpenRouter.ai](https://openrouter.ai/)
- Check that you have credits/payment method configured on OpenRouter

### No Items Detected
- Check image quality and lighting
- Ensure receipt text is clear and readable
- Verify the receipt isn't too faded or damaged
- Try uploading a different image

### Processing Time
- Typical processing time: 5-15 seconds per receipt
- Time varies based on API response speed
- No local model loading required - starts immediately

### Database Errors
- Delete `grocery_prices.db` and restart the application to recreate the database
- Ensure you have write permissions in the application directory

## Future Enhancements

Potential improvements for future versions:
- Manual item entry and editing
- Price trend graphs and analytics
- Multi-store price comparison
- Export data to CSV/Excel
- Mobile app version
- Barcode scanning support
- Shopping list integration

## License

This project is open source and available under the MIT License.

## Contributing

Contributions are welcome! Please feel free to submit pull requests or open issues for bugs and feature requests.
