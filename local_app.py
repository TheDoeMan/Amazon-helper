import os
import csv
import io
import json
import logging
import pandas as pd
from flask import Flask, render_template, request, jsonify, session, redirect, url_for, send_file, send_from_directory
from bs4 import BeautifulSoup

# Configure logging
logging.basicConfig(level=logging.DEBUG)

app = Flask(__name__)
app.secret_key = "local_secret_key"  # Local development secret key
app.config['SESSION_TYPE'] = 'filesystem'

# Default ship from details - these stay the same for all orders
DEFAULT_SHIP_FROM = {
    "FromName": "pbu",
    "PhoneFrom": "7025050499",
    "Street1From": "4225 Arville st",
    "CompanyFrom": "pbu",
    "Street2From": "suite 3",
    "CityFrom": "Las Vegas",
    "StateFrom": "NV",
    "PostalCodeFrom": "89123"
}

def extract_shipping_info(html_content):
    """
    Extract shipping information from the HTML content.
    This is a simplified version of the parser that focuses on the most common patterns.
    """
    soup = BeautifulSoup(html_content, 'html.parser')
    addresses = []
    
    # Look for shipping sections
    shipping_sections = soup.find_all(attrs={"data-test-id": "shipping-section-buyer-address"})
    
    if not shipping_sections:
        # Try alternative pattern - look for address blocks
        address_divs = soup.find_all('div', class_=lambda c: c and 'shipping-address' in c)
        if address_divs:
            for div in address_divs:
                address_text = div.get_text(separator='\n').strip()
                if address_text:
                    # Extract order ID if available
                    order_id = ''
                    order_id_elem = soup.find(string=lambda text: text and 'Order #' in text)
                    if order_id_elem:
                        order_id = order_id_elem.split('#')[-1].strip()
                    
                    # Parse address
                    parts = address_text.split('\n')
                    address = parse_address_from_parts(parts)
                    if address:
                        address['order_id'] = order_id
                        addresses.append(address)
    else:
        # Process standard shipping sections
        for section in shipping_sections:
            address = {}
            
            # Extract name
            name_elem = section.find('span', class_='a-dropdown-prompt')
            if name_elem:
                address['ToName'] = name_elem.text.strip()
            
            # Extract full address
            address_div = section.find('div', {'data-a-input-name': 'address-ui-widgets-enterAddressFullName'})
            if address_div:
                address_lines = []
                for span in address_div.find_all('span'):
                    if span.text.strip():
                        address_lines.append(span.text.strip())
                
                if address_lines:
                    parsed = parse_address_from_parts(address_lines)
                    address.update(parsed)
            
            # Get order ID if available
            order_elem = section.find_previous(string=lambda text: text and 'Order #' in text)
            if order_elem:
                order_id = order_elem.split('#')[-1].strip()
                address['order_id'] = order_id
            
            if address and 'ToName' in address and 'Street1To' in address:
                addresses.append(address)
    
    # If no addresses found, try generic pattern matching
    if not addresses:
        # Look for any potential address blocks
        address_blocks = soup.find_all('div', class_=lambda c: c and ('address' in c.lower() if c else False))
        
        for block in address_blocks:
            text = block.get_text(separator='\n').strip()
            if text and len(text.split('\n')) >= 3:  # Simple heuristic for address
                address = parse_address_from_parts(text.split('\n'))
                if address and 'Street1To' in address and 'CityTo' in address:
                    # Try to find an order ID nearby
                    order_id = ''
                    for parent in block.parents:
                        order_text = parent.find(string=lambda t: t and ('Order' in t or '#' in t))
                        if order_text:
                            import re
                            order_match = re.search(r'[#:]?\s*(\w+[-]?\w+)', order_text)
                            if order_match:
                                order_id = order_match.group(1)
                                break
                    
                    address['order_id'] = order_id
                    addresses.append(address)
    
    return addresses

def parse_address_from_parts(parts):
    """
    Parse address components from a list of text parts.
    This is a simplified version focusing on common patterns.
    """
    address = {}
    
    if not parts or len(parts) < 3:
        return address
    
    # First line is typically the name
    address['ToName'] = parts[0].strip()
    
    # Last line is typically City, State ZIP
    last_line = parts[-1].strip()
    
    # Try to parse city, state, zip
    if ',' in last_line:
        city_part, state_zip_part = last_line.split(',', 1)
        address['CityTo'] = city_part.strip()
        
        # Parse state and zip
        state_zip = state_zip_part.strip().split()
        if len(state_zip) >= 2:
            address['StateTo'] = state_zip[0].strip()
            address['ZipTo'] = state_zip[1].strip()
    else:
        # Fallback if no comma
        words = last_line.split()
        if len(words) >= 2:
            address['StateTo'] = words[-2].strip()
            address['ZipTo'] = words[-1].strip()
            address['CityTo'] = ' '.join(words[:-2]).strip()
    
    # Middle parts are street address
    if len(parts) == 3:
        address['Street1To'] = parts[1].strip()
        address['Street2To'] = ''
    elif len(parts) >= 4:
        address['Street1To'] = parts[1].strip()
        address['Street2To'] = parts[2].strip()
        
        # If there are more parts, check if any could be a company name
        if len(parts) > 4 and not any(c.isdigit() for c in parts[2]):
            address['CompanyTo'] = parts[2].strip()
            address['Street2To'] = parts[3].strip() if len(parts) > 5 else ''
    
    # Phone number - not always present, would need a more sophisticated parser
    address['PhoneTo'] = ''
    
    return address

@app.route('/')
def index():
    # Clear any existing session data
    if 'all_addresses' in session:
        session.pop('all_addresses')
    return render_template('index.html', ship_from=DEFAULT_SHIP_FROM)

@app.route('/store-addresses', methods=['POST'])
def store_addresses():
    try:
        # Get addresses from the request JSON
        addresses = request.json.get('addresses', [])
        
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
        # Extract shipping info from HTML
        addresses = extract_shipping_info(html_content)
        
        if not addresses:
            return jsonify({"error": "No shipping information found in the provided HTML"}), 404
        
        # Return single address or multiple addresses
        if len(addresses) == 1:
            return jsonify({"data": addresses[0], "multiple": False})
        else:
            return jsonify({"data": addresses, "multiple": True})
    
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
            # Apply dimensions based on settings
            if (merge_orders or same_dimensions) and len(all_addresses) > 1:
                # Use the form values for dimensions when merging or applying same dimensions
                weight = form_weight
                length = form_length
                width = form_width
                height = form_height
                description = form_description
            else:
                # Use the values from the address
                weight = address.get('Weight', '')
                length = address.get('length', '')
                width = address.get('width', '')
                height = address.get('height', '')
                description = address.get('description', 'misc')
            
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

@app.route('/download-app')
def download_app():
    """Create a ZIP file with the entire application for download"""
    import zipfile
    import tempfile
    import shutil
    
    try:
        # Create temporary directory
        temp_dir = tempfile.mkdtemp()
        zip_path = os.path.join(temp_dir, 'shipping_extractor_app.zip')
        
        # Create ZIP file
        with zipfile.ZipFile(zip_path, 'w') as zipf:
            # Add main Python file
            zipf.write('local_app.py', 'app.py')
            
            # Add templates and static files
            for folder in ['templates', 'static']:
                for root, dirs, files in os.walk(folder):
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