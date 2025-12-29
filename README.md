# Grocery Price Tracker

A web-based application to track grocery prices over time by processing receipt images. Upload or take photos of your grocery receipts, and the application will automatically extract items and prices using OCR (Optical Character Recognition) technology.

## Features

- **Receipt Upload**: Take photos with your device camera or upload existing receipt images
- **Automatic Processing**: Uses Donut (Document Understanding Transformer) AI model to extract items and prices from receipts
- **Price Tracking**: Stores historical pricing data for all grocery items
- **Price History**: View price changes over time for individual items
- **Search & Filter**: Easily search and sort through tracked items
- **Store Tracking**: Optional store name tracking for multi-store price comparison

## Technology Stack

- **Backend**: Python Flask
- **Database**: SQLite
- **AI/OCR**: Donut (Document Understanding Transformer) - naver-clova-ix/donut-base-finetuned-cord-v2
- **Deep Learning**: PyTorch and Hugging Face Transformers
- **Frontend**: HTML, CSS, JavaScript
- **Image Processing**: Pillow (PIL)

## Prerequisites

Before running this application, you need:

1. **Python 3.8+**
2. **Sufficient disk space**: The Donut model is ~800MB and will be downloaded automatically on first use
3. **GPU (Optional)**: CUDA-compatible GPU for faster processing (CPU works but is slower)

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

**Note**: The first time you run the application, it will automatically download the Donut model (~800MB) from Hugging Face. This is a one-time download.

4. **Initialize the database**
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
3. **Receipt Type**: The Donut model is fine-tuned on receipts and works best with standard printed receipts
4. **Structured Data**: Donut extracts structured JSON including items, prices, subtotals, and totals
5. **Manual Editing**: After processing, verify extracted items for accuracy

## Troubleshooting

### Model Download Issues
- Ensure you have a stable internet connection for the initial ~800MB model download
- The model is cached locally after the first download
- Check that you have sufficient disk space (~1GB free)

### No Items Detected
- The Donut model is specifically trained on receipt data and should work well with most receipts
- Check image quality and lighting
- Ensure receipt text is clear and readable
- Try a different image or use manual entry as a fallback

### Slow Processing
- First-time processing may be slow due to model loading
- GPU acceleration (CUDA) significantly speeds up processing
- CPU-only processing works but takes longer (~10-30 seconds per receipt)

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
