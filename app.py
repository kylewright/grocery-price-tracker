"""
Grocery Price Tracker - Flask Application
Web-based application to track grocery prices from receipt images.
"""
import os
from datetime import datetime
from flask import Flask, render_template, request, jsonify, redirect, url_for
from werkzeug.utils import secure_filename

from database import init_db, upsert_item_with_price, get_all_items_with_latest_price, get_item_price_history, get_recent_uploads
from receipt_processor import process_receipt


app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'gif', 'bmp'}

# Ensure upload folder exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Initialize database on startup
init_db()


def allowed_file(filename):
    """Check if file extension is allowed."""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']


@app.route('/')
def index():
    """Main page with upload form and recent uploads."""
    recent = get_recent_uploads(10)
    return render_template('index.html', recent_uploads=recent)


@app.route('/upload', methods=['POST'])
def upload_receipt():
    """Handle receipt image upload and processing."""
    if 'receipt' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400

    file = request.files['receipt']

    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400

    if not allowed_file(file.filename):
        return jsonify({'error': 'Invalid file type. Please upload an image file.'}), 400

    try:
        # Save the uploaded file
        filename = secure_filename(file.filename)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{timestamp}_{filename}"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)

        # Get optional store name from form
        store_name = request.form.get('store_name', '').strip() or None

        # Process the receipt
        result = process_receipt(filepath, store_name)

        # Store items and prices in database
        items_added = []
        for item_name, price in result['items']:
            try:
                item_id, price_record_id = upsert_item_with_price(
                    item_name=item_name,
                    price=price,
                    store_name=result['store_name']
                )
                items_added.append({
                    'name': item_name,
                    'price': price,
                    'item_id': item_id
                })
            except Exception as e:
                print(f"Error adding item {item_name}: {str(e)}")

        # Clean up: optionally delete the uploaded file
        # os.remove(filepath)  # Uncomment to delete after processing

        return jsonify({
            'success': True,
            'items_count': len(items_added),
            'items': items_added,
            'store_name': result['store_name'],
            'raw_text': result['text']
        })

    except Exception as e:
        return jsonify({'error': f'Error processing receipt: {str(e)}'}), 500


@app.route('/items')
def view_items():
    """View all items with their latest prices."""
    items = get_all_items_with_latest_price()
    return render_template('items.html', items=items)


@app.route('/items/<int:item_id>/history')
def item_history(item_id):
    """View price history for a specific item."""
    history = get_item_price_history(item_id)
    return jsonify([{
        'price': row['price'],
        'date': row['date'],
        'store_name': row['store_name'],
        'created_at': row['created_at']
    } for row in history])


@app.route('/api/items')
def api_items():
    """API endpoint to get all items."""
    items = get_all_items_with_latest_price()
    return jsonify([{
        'id': row['id'],
        'name': row['name'],
        'latest_price': row['latest_price'],
        'latest_date': row['latest_date'],
        'store_name': row['store_name']
    } for row in items])


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
