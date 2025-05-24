# Shipping Information Extractor

## Setup Instructions

1. Install Python 3.8 or newer
2. Install required packages: `pip install -r requirements.txt`
3. Run the application: `python app.py`
4. Open your browser and go to: http://localhost:5000

## Usage

1. Copy HTML from Amazon order pages
2. Paste into the HTML input field
3. Click "Extract Information"
4. Review and edit shipping details
5. Click "Generate CSV" to download shipping information

For multiple orders, you can:
- Use the address selector to navigate between orders
- Check "Merge all orders in one CSV" to create a single CSV file
- Check "Apply same dimensions to all" to use the same package size for all orders
- Use the navigation arrows to scroll through multiple addresses
