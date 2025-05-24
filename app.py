import os
import logging
import csv
import io
import json
import re
import pandas as pd
import zipfile
import tempfile
import shutil
from collections import Counter, defaultdict
from flask import Flask, render_template, request, jsonify, session, redirect, url_for, send_file
from utils.html_parser import extract_shipping_info

# Configure logging
logging.basicConfig(level=logging.DEBUG)

app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "dev_secret_key")
app.config['SESSION_TYPE'] = 'filesystem'  # Store session data on the filesystem

# Default ship from details - these stay the same for all orders
DEFAULT_SHIP_FROM = {
    "FromName": "pbu",
    "PhoneFrom": "5180521229",
    "Street1From": "505 E Windmill Lane",
    "CompanyFrom": "MS",
    "Street2From": "STE #155",
    "CityFrom": "LAS VEGAS",
    "StateFrom": "NV",
    "PostalCodeFrom": "89123"
}

@app.route('/')
def index():
    # Clear any existing session data
    if 'all_addresses' in session:
        session.pop('all_addresses')
    return render_template('index.html', ship_from=DEFAULT_SHIP_FROM, active_tab='shipping')

@app.route('/asin-counter')
def asin_extractor():
    # Clear any existing ASIN data
    if 'asin_data' in session:
        session.pop('asin_data')
    if 'advanced_asin_data' in session:
        session.pop('advanced_asin_data')
    return render_template('asin_counter.html', active_tab='asin')

@app.route('/store-addresses', methods=['POST'])
def store_addresses():
    try:
        # Get addresses from the request JSON
        addresses = request.json.get('addresses', [])
        
        # Default the current_address field for the first address
        if addresses and len(addresses) > 0:
            for i, addr in enumerate(addresses):
                addr['current_address'] = 'true' if i == 0 else 'false'
        
        # Store addresses in session
        session['all_addresses'] = addresses
        
        return jsonify({"success": True, "message": "Addresses stored successfully"})
    except Exception as e:
        logging.error(f"Error storing addresses: {str(e)}")
        return jsonify({"error": f"Error storing addresses: {str(e)}"}), 500

@app.route('/extract', methods=['POST'])
def extract():
    html_content = request.form.get('html_content', '')
    
    if not html_content:
        return jsonify({"error": "No HTML content provided"}), 400
    
    try:
        shipping_info = extract_shipping_info(html_content)
        
        if not shipping_info:
            return jsonify({"error": "Could not extract shipping information from the HTML"}), 400
        
        # Check if we have multiple addresses or a single address
        if isinstance(shipping_info, list):
            return jsonify({"success": True, "data": shipping_info, "multiple": True})
        else:
            return jsonify({"success": True, "data": shipping_info, "multiple": False})
    except Exception as e:
        logging.error(f"Error extracting shipping info: {str(e)}")
        return jsonify({"error": f"Error processing HTML: {str(e)}"}), 500

@app.route('/generate-csv', methods=['POST'])
def generate_csv():
    try:
        # Check if we need to merge all orders
        merge_orders = request.form.get('merge_orders') == 'on'
        
        # Check if we need to apply same dimensions to all orders
        same_dimensions = request.form.get('same_dimensions') == 'on'
        
        # Get all addresses from session if merging
        all_addresses = session.get('all_addresses', []) if merge_orders else []
        
        # If not merging or no addresses in session, create a single entry
        if not merge_orders or not all_addresses:
            # Get data from form for a single order
            to_name = request.form.get('ToName', '')
            phone_to = request.form.get('PhoneTo', '')
            street1_to = request.form.get('Street1To', '')
            company_to = request.form.get('CompanyTo', '')
            street2_to = request.form.get('Street2To', '')
            city_to = request.form.get('CityTo', '')
            zip_to = request.form.get('ZipTo', '')
            state_to = request.form.get('StateTo', '')
            order_id = request.form.get('order_id', '')
            
            # Get package dimensions
            weight = request.form.get('Weight', '')
            length = request.form.get('length', '')
            width = request.form.get('width', '')
            height = request.form.get('height', '')
            description = request.form.get('description', 'misc')
            
            # Add the single address to our list
            all_addresses = [{
                'ToName': to_name,
                'PhoneTo': phone_to,
                'Street1To': street1_to,
                'CompanyTo': company_to,
                'Street2To': street2_to,
                'CityTo': city_to,
                'ZipTo': zip_to,
                'StateTo': state_to,
                'order_id': order_id,
                'Weight': weight, 
                'length': length,
                'width': width,
                'height': height,
                'description': description
            }]
        
        # Create CSV data with multiple rows if needed
        csv_data = {
            'No': [],
            'FromName': [],
            'PhoneFrom': [],
            'Street1From': [],
            'CompanyFrom': [],
            'Street2From': [],
            'CityFrom': [],
            'StateFrom': [],
            'PostalCodeFrom': [],
            'ToName': [],
            'PhoneTo': [],
            'Street1To': [],
            'CompanyTo': [],
            'Street2To': [],
            'CityTo': [],
            'ZipTo': [],
            'StateTo': [],
            'Weight': [],
            'length': [],
            'width': [],
            'height': [],
            'description': [],
            'Ref01': [],
            'Ref02': [],
            'optional_file_name': [],
            'optional_amazon_order_id': []
        }
        
        # Get current form dimensions once
        form_weight = request.form.get('Weight', '')
        form_length = request.form.get('length', '')
        form_width = request.form.get('width', '')
        form_height = request.form.get('height', '')
        form_description = request.form.get('description', 'misc')
        
        # Loop through all addresses and add to CSV data
        for address in all_addresses:
            # Handle dimensions based on settings
            if same_dimensions and len(all_addresses) > 1:
                # Use the form values for dimensions when applying same dimensions checkbox is checked
                weight = form_weight
                length = form_length
                width = form_width
                height = form_height
                description = form_description
            else:
                # For each address, try to get the stored dimensions from packageDimensions field
                # which contains dimensions that were set via the UI
                order_id = address.get('order_id', '')
                
                # Update values from form if this is the currently active address
                if address.get('current_address') == 'true':
                    weight = form_weight
                    length = form_length
                    width = form_width
                    height = form_height
                    description = form_description
                    
                    # Also update these values in the address object for future use
                    address['Weight'] = weight
                    address['length'] = length
                    address['width'] = width
                    address['height'] = height
                    address['description'] = description
                else:
                    # Use the values from the address that were previously stored
                    weight = address.get('Weight', form_weight)
                    length = address.get('length', form_length)
                    width = address.get('width', form_width)
                    height = address.get('height', form_height)
                    description = address.get('description', form_description)
            
            # Add this order to the CSV data
            csv_data['No'].append(address.get('order_id', ''))
            csv_data['FromName'].append(DEFAULT_SHIP_FROM['FromName'])
            csv_data['PhoneFrom'].append(DEFAULT_SHIP_FROM['PhoneFrom'])
            csv_data['Street1From'].append(DEFAULT_SHIP_FROM['Street1From'])
            csv_data['CompanyFrom'].append(DEFAULT_SHIP_FROM['CompanyFrom'])
            csv_data['Street2From'].append(DEFAULT_SHIP_FROM['Street2From'])
            csv_data['CityFrom'].append(DEFAULT_SHIP_FROM['CityFrom'])
            csv_data['StateFrom'].append(DEFAULT_SHIP_FROM['StateFrom'])
            csv_data['PostalCodeFrom'].append(DEFAULT_SHIP_FROM['PostalCodeFrom'])
            csv_data['ToName'].append(address.get('ToName', ''))
            csv_data['PhoneTo'].append(address.get('PhoneTo', ''))
            csv_data['Street1To'].append(address.get('Street1To', ''))
            csv_data['CompanyTo'].append(address.get('CompanyTo', ''))
            csv_data['Street2To'].append(address.get('Street2To', ''))
            csv_data['CityTo'].append(address.get('CityTo', ''))
            csv_data['ZipTo'].append(address.get('ZipTo', ''))
            csv_data['StateTo'].append(address.get('StateTo', ''))
            csv_data['Weight'].append(weight)
            csv_data['length'].append(length)
            csv_data['width'].append(width)
            csv_data['height'].append(height)
            csv_data['description'].append(description)
            csv_data['Ref01'].append('')
            csv_data['Ref02'].append('')
            csv_data['optional_file_name'].append('')
            csv_data['optional_amazon_order_id'].append('')
        
        # Create DataFrame
        df = pd.DataFrame(csv_data)
        
        # Create in-memory CSV
        output = io.StringIO()
        df.to_csv(output, index=False, quoting=csv.QUOTE_MINIMAL)
        output.seek(0)
        
        # Generate filename
        if merge_orders and len(all_addresses) > 1:
            filename = "shipping_orders_merged.csv"
        else:
            order_id = all_addresses[0].get('order_id', '')
            filename = f"shipping_order_{order_id}.csv" if order_id else "shipping_order.csv"
        
        return send_file(
            io.BytesIO(output.getvalue().encode('utf-8')),
            mimetype='text/csv',
            as_attachment=True,
            download_name=filename
        )
    
    except Exception as e:
        logging.error(f"Error generating CSV: {str(e)}")
        return jsonify({"error": f"Error generating CSV: {str(e)}"}), 500

@app.route('/extract-asins', methods=['POST'])
def extract_asins():
    """Extract ASINs from order text"""
    try:
        # Get order text from form
        order_text = request.form.get('order_text', '')
        
        if not order_text:
            return render_template('asin_counter.html', error="Please enter order text to extract ASINs.")
        
        # Use regex to find all ASINs in the text (format: 10 alphanumeric characters)
        asin_pattern = r'\b[A-Z0-9]{10}\b'
        asins = re.findall(asin_pattern, order_text)
        
        # Count occurrences of each ASIN
        asin_counts = Counter(asins)
        
        # Sort by count (descending)
        sorted_asin_data = sorted(asin_counts.items(), key=lambda x: x[1], reverse=True)
        
        # Store in session for download
        session['asin_data'] = sorted_asin_data
        
        return render_template('asin_counter.html', asin_data=sorted_asin_data, active_tab='asin')
        
    except Exception as e:
        logging.error(f"Error extracting ASINs: {str(e)}")
        return render_template('asin_counter.html', error=f"Error extracting ASINs: {str(e)}", active_tab='asin')

@app.route('/extract-asins-advanced', methods=['POST'])
def extract_asins_advanced():
    """Extract ASINs with title information from order text"""
    try:
        # Get order text from form
        order_text = request.form.get('order_text', '')
        
        if not order_text:
            return render_template('asin_counter.html', error="Please enter order text to extract ASINs with titles.", active_tab='asin')
        
        # Use regex pattern to extract product titles, ASINs, and quantities
        pattern = re.compile(
            r"Sales channel: Amazon\.com(?:\s*Business customer)?\s+(.+?)\s+ASIN:\s+(\w+)\s+.*?Quantity:\s+(\d+)",
            re.DOTALL
        )
        
        # Store data with defaultdict
        asin_data = defaultdict(lambda: {"title": "", "qty": 0})
        
        # Find all matches in the text
        matches = list(pattern.finditer(order_text))
        
        if not matches:
            return render_template('asin_counter.html', 
                                  error="Could not find any products with the expected pattern. Make sure to copy the entire order page text.", 
                                  active_tab='asin')
        
        # Process each match
        for match in matches:
            title, asin, qty = match.groups()
            qty = int(qty)
            asin_data[asin]["title"] = title.strip()
            asin_data[asin]["qty"] += qty
        
        # Sort by quantity in descending order
        sorted_data = sorted(asin_data.items(), key=lambda x: x[1]["qty"], reverse=True)
        
        # Store in session for download
        session['advanced_asin_data'] = sorted_data
        
        return render_template('asin_counter.html', advanced_asin_data=sorted_data, active_tab='asin')
        
    except Exception as e:
        logging.error(f"Error extracting ASINs with titles: {str(e)}")
        return render_template('asin_counter.html', 
                              error=f"Error extracting ASINs with titles: {str(e)}", 
                              active_tab='asin')

@app.route('/download-asins')
def download_asins():
    """Download ASIN data as CSV"""
    try:
        # Get ASIN data from session
        asin_data = session.get('asin_data', [])
        
        if not asin_data:
            return redirect(url_for('asin_extractor'))
        
        # Create CSV data
        csv_data = {
            'ASIN': [],
            'Quantity': []
        }
        
        for asin, count in asin_data:
            csv_data['ASIN'].append(asin)
            csv_data['Quantity'].append(count)
        
        # Create DataFrame
        df = pd.DataFrame(csv_data)
        
        # Create in-memory CSV
        output = io.StringIO()
        df.to_csv(output, index=False, quoting=csv.QUOTE_MINIMAL)
        output.seek(0)
        
        # Generate filename
        filename = "asin_counts.csv"
        
        return send_file(
            io.BytesIO(output.getvalue().encode('utf-8')),
            mimetype='text/csv',
            as_attachment=True,
            download_name=filename
        )
    
    except Exception as e:
        logging.error(f"Error generating ASIN CSV: {str(e)}")
        return jsonify({"error": f"Error generating ASIN CSV: {str(e)}"}), 500
        
@app.route('/save-shopping-list', methods=['POST'])
def save_shopping_list():
    """Save edited shopping list and download as CSV"""
    try:
        # Get the count of items
        item_count = int(request.form.get('item_count', 0))
        
        if item_count == 0:
            return jsonify({"error": "No items in shopping list"}), 400
        
        # Create CSV data
        csv_data = {
            'ASIN': [],
            'Title': [],
            'Quantity': []
        }
        
        # Process each item from the form
        for i in range(item_count):
            asin = request.form.get(f'asin_{i}')
            title = request.form.get(f'title_{i}')
            qty = request.form.get(f'qty_{i}')
            
            # Skip if any required field is missing
            if not all([asin, title, qty]):
                continue
                
            csv_data['ASIN'].append(asin)
            csv_data['Title'].append(title)
            csv_data['Quantity'].append(int(qty))
        
        # Create DataFrame
        df = pd.DataFrame(csv_data)
        
        # Create in-memory CSV
        output = io.StringIO()
        df.to_csv(output, index=False, quoting=csv.QUOTE_MINIMAL)
        output.seek(0)
        
        # Generate filename
        filename = "shopping_list.csv"
        
        return send_file(
            io.BytesIO(output.getvalue().encode('utf-8')),
            mimetype='text/csv',
            as_attachment=True,
            download_name=filename
        )
    
    except Exception as e:
        logging.error(f"Error saving shopping list: {str(e)}")
        return jsonify({"error": f"Error saving shopping list: {str(e)}"}), 500

@app.route('/download-asins-advanced')
def download_asins_advanced():
    """Download advanced ASIN data with titles as CSV"""
    try:
        # Get advanced ASIN data from session
        advanced_asin_data = session.get('advanced_asin_data', [])
        
        if not advanced_asin_data:
            return redirect(url_for('asin_extractor'))
        
        # Create CSV data
        csv_data = {
            'ASIN': [],
            'Title': [],
            'Quantity': []
        }
        
        for asin, info in advanced_asin_data:
            csv_data['ASIN'].append(asin)
            csv_data['Title'].append(info['title'])
            csv_data['Quantity'].append(info['qty'])
        
        # Create DataFrame
        df = pd.DataFrame(csv_data)
        
        # Create in-memory CSV
        output = io.StringIO()
        df.to_csv(output, index=False, quoting=csv.QUOTE_MINIMAL)
        output.seek(0)
        
        # Generate filename
        filename = "asin_counts_with_titles.csv"
        
        return send_file(
            io.BytesIO(output.getvalue().encode('utf-8')),
            mimetype='text/csv',
            as_attachment=True,
            download_name=filename
        )
    
    except Exception as e:
        logging.error(f"Error generating advanced ASIN CSV: {str(e)}")
        return jsonify({"error": f"Error generating advanced ASIN CSV: {str(e)}"}), 500

@app.route('/download-app')
def download_app():
    """Create a ZIP file with the entire application for download"""
    try:
        # Create temporary directory
        temp_dir = tempfile.mkdtemp()
        zip_path = os.path.join(temp_dir, 'shipping_extractor_app.zip')
        
        # Create ZIP file
        with zipfile.ZipFile(zip_path, 'w') as zipf:
            # Add Python files in root directory
            for file in os.listdir('.'):
                if file.endswith('.py'):
                    zipf.write(file, file)
            
            # Add templates and static directories
            for folder in ['templates', 'static']:
                for root, dirs, files in os.walk(folder):
                    for file in files:
                        file_path = os.path.join(root, file)
                        zipf.write(file_path, file_path)
            
            # Add utils directory
            for root, dirs, files in os.walk('utils'):
                for file in files:
                    file_path = os.path.join(root, file)
                    zipf.write(file_path, file_path)
            
            # Add requirements.txt
            with open(os.path.join(temp_dir, 'requirements.txt'), 'w') as req_file:
                req_file.write('flask==2.0.1\nbeautifulsoup4==4.10.0\npandas==1.3.3\n')
            zipf.write(os.path.join(temp_dir, 'requirements.txt'), 'requirements.txt')
            
            # Add README with instructions
            readme_content = """# Shipping Information Extractor

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
"""
            readme_path = os.path.join(temp_dir, 'README.md')
            with open(readme_path, 'w') as readme_file:
                readme_file.write(readme_content)
            zipf.write(readme_path, 'README.md')
        
        return send_file(
            zip_path,
            mimetype='application/zip',
            as_attachment=True,
            download_name='shipping_extractor_app.zip'
        )
    
    except Exception as e:
        logging.error(f"Error creating download package: {str(e)}")
        return jsonify({"error": "Failed to create download package"}), 500
    
    finally:
        # Clean up temporary directory
        if 'temp_dir' in locals():
            shutil.rmtree(temp_dir)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
