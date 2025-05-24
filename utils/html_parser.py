import re
import logging
from bs4 import BeautifulSoup

def extract_shipping_info(html_content):
    """
    Extract customer shipping information from the HTML content.
    
    Args:
        html_content (str): The HTML content containing shipping information
        
    Returns:
        dict or list: A dictionary with extracted shipping details or a list of dictionaries 
                     if multiple addresses are found
    """
    try:
        # Parse HTML with BeautifulSoup
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Initialize shipping addresses list
        shipping_addresses = []
        
        # First look for all shipping-section-buyer-po spans which contain the address
        # This is the specific format you mentioned in your example
        buyer_spans = soup.find_all('span', attrs={'data-test-id': 'shipping-section-buyer-po'})
        
        if buyer_spans:
            # For each buyer span, try to find the address div and order ID
            for span_index, buyer_span in enumerate(buyer_spans):
                # Find the parent row to get the order ID
                current = buyer_span
                order_id = ""
                
                # Go up the DOM tree to find the parent row which contains the order link
                for _ in range(8):  # Limit the depth of parent search
                    if not current or current.name == 'tr':
                        break
                    current = current.parent
                
                if current and current.name == 'tr':
                    # Try to find the order link
                    order_links = current.find_all('a', href=lambda href: href and '/order/' in href)
                    if order_links:
                        order_id_match = re.search(r'(\d{3}-\d{7}-\d{7})', order_links[0].text.strip())
                        if order_id_match:
                            order_id = order_id_match.group(1)
                
                # Find the address div within this buyer span
                address_div = buyer_span.find('div', attrs={'data-test-id': 'shipping-section-buyer-address'})
                
                if address_div:
                    shipping_info = {
                        'ToName': '',
                        'PhoneTo': '',
                        'Street1To': '',
                        'CompanyTo': '',
                        'Street2To': '',
                        'CityTo': '',
                        'ZipTo': '',
                        'StateTo': '',
                        'order_id': order_id
                    }
                    
                    # Find all spans in the address div (name, street, city, state, zip)
                    spans = address_div.find_all('span')
                    
                    # Get text from each span
                    span_texts = []
                    for span in spans:
                        text = span.get_text().strip()
                        if text:
                            # Remove <br> tag
                            text = text.replace('<br>', '')
                            span_texts.append(text)
                    
                    # First span is usually the name
                    if len(span_texts) >= 1:
                        shipping_info['ToName'] = span_texts[0]
                    
                    # Second span is usually the street address
                    if len(span_texts) >= 2:
                        shipping_info['Street1To'] = span_texts[1]
                    
                    # Check remaining spans for city, state, zip
                    city_state_zip_text = " ".join(span_texts[2:]) if len(span_texts) > 2 else ""
                    
                    # Extract city, state, zip from combined text
                    city_state_zip_pattern = r'([A-Za-z\s]+),\s*([A-Z]{2})\s*(\d{5}(?:-\d{4})?)'
                    city_state_zip_match = re.search(city_state_zip_pattern, city_state_zip_text)
                    
                    if city_state_zip_match:
                        shipping_info['CityTo'] = city_state_zip_match.group(1).strip()
                        shipping_info['StateTo'] = city_state_zip_match.group(2).strip()
                        shipping_info['ZipTo'] = city_state_zip_match.group(3).strip()
                    
                    # Only add if we have all the essential shipping info
                    if all([shipping_info['ToName'], shipping_info['Street1To'], 
                          shipping_info['CityTo'], shipping_info['StateTo'], shipping_info['ZipTo']]):
                        shipping_addresses.append(shipping_info)
        
        # If we found addresses from the spans, return them
        if shipping_addresses:
            return shipping_addresses[0] if len(shipping_addresses) == 1 else shipping_addresses
            
        # If no spans found, try with table row approach
        shipping_rows = soup.find_all('tr')
        
        for row in shipping_rows:
            # Look for the order ID in this row
            order_id = ""
            order_links = row.find_all('a', href=lambda href: href and '/order/' in href)
            if order_links:
                order_id_match = re.search(r'(\d{3}-\d{7}-\d{7})', order_links[0].text.strip())
                if order_id_match:
                    order_id = order_id_match.group(1)
            
            # Look for address div in this row
            address_div = row.find('div', attrs={'data-test-id': 'shipping-section-buyer-address'})
            
            if address_div:
                shipping_info = {
                    'ToName': '',
                    'PhoneTo': '',
                    'Street1To': '',
                    'CompanyTo': '',
                    'Street2To': '',
                    'CityTo': '',
                    'ZipTo': '',
                    'StateTo': '',
                    'order_id': order_id
                }
                
                # Find all spans in the address div (name, street, city, state, zip)
                spans = address_div.find_all('span')
                span_texts = []
                
                # Extract text from each span
                for span in spans:
                    text = span.get_text().strip()
                    if text:
                        span_texts.append(text.replace('<br>', ''))
                
                # First span is usually the name
                if len(span_texts) >= 1:
                    shipping_info['ToName'] = span_texts[0]
                
                # Second span is usually the street address
                if len(span_texts) >= 2:
                    shipping_info['Street1To'] = span_texts[1]
                
                # Last spans usually have city, state, zip
                city_state_zip_text = ""
                if len(span_texts) >= 3:
                    # Combine the remaining spans which might have city, state, zip
                    city_state_zip_text = " ".join(span_texts[2:])
                
                # Extract city, state, zip from combined text
                city_state_zip_pattern = r'([A-Za-z\s]+),\s*([A-Z]{2})\s*(\d{5}(?:-\d{4})?)'
                city_state_zip_match = re.search(city_state_zip_pattern, city_state_zip_text)
                
                if city_state_zip_match:
                    shipping_info['CityTo'] = city_state_zip_match.group(1).strip()
                    shipping_info['StateTo'] = city_state_zip_match.group(2).strip()
                    shipping_info['ZipTo'] = city_state_zip_match.group(3).strip()
                
                # Only add if we have all the essential shipping info
                if all([shipping_info['ToName'], shipping_info['Street1To'], 
                       shipping_info['CityTo'], shipping_info['StateTo'], shipping_info['ZipTo']]):
                    shipping_addresses.append(shipping_info)
        
        # If we found addresses from any method, return them
        if shipping_addresses:
            return shipping_addresses[0] if len(shipping_addresses) == 1 else shipping_addresses
        
        # If we couldn't find addresses in the table format, try other methods
        
        # Try to find form fields with labels like "To Name", "Street 1", etc.
        form_fields = {
            'ToName': soup.find(['input', 'textarea'], attrs={'id': re.compile(r'ToName|to[-_]?name|receiver[-_]?name', re.IGNORECASE)}),
            'Street1To': soup.find(['input', 'textarea'], attrs={'id': re.compile(r'Street1To|street[-_]?1|address[-_]?1', re.IGNORECASE)}),
            'CityTo': soup.find(['input', 'textarea'], attrs={'id': re.compile(r'CityTo|city', re.IGNORECASE)}),
            'StateTo': soup.find(['input', 'textarea'], attrs={'id': re.compile(r'StateTo|state', re.IGNORECASE)}),
            'ZipTo': soup.find(['input', 'textarea'], attrs={'id': re.compile(r'ZipTo|zip|postal[-_]?code', re.IGNORECASE)}),
            'PhoneTo': soup.find(['input', 'textarea'], attrs={'id': re.compile(r'PhoneTo|phone|tel', re.IGNORECASE)}),
            'CompanyTo': soup.find(['input', 'textarea'], attrs={'id': re.compile(r'CompanyTo|company', re.IGNORECASE)}),
            'Street2To': soup.find(['input', 'textarea'], attrs={'id': re.compile(r'Street2To|street[-_]?2|address[-_]?2', re.IGNORECASE)}),
            'order_id': soup.find(['input', 'textarea'], attrs={'id': re.compile(r'order[-_]?id|orderId', re.IGNORECASE)})
        }
        
        # Check if we found form fields
        if any(field for field in form_fields.values()):
            address_info = {
                'ToName': '',
                'PhoneTo': '',
                'Street1To': '',
                'CompanyTo': '',
                'Street2To': '',
                'CityTo': '',
                'ZipTo': '',
                'StateTo': '',
                'order_id': ''
            }
            
            # Extract values from form fields
            for field_name, field_element in form_fields.items():
                if field_element:
                    value = field_element.get('value', '')
                    if value:
                        # Special handling for fields that might contain combined information
                        if field_name == 'ToName' and (re.search(r'\d+\s+[A-Za-z]+', value) or ',' in value):
                            # This looks like it contains address info, not just a name
                            parts = parse_combined_field(value)
                            if parts.get('name'):
                                address_info['ToName'] = parts['name']
                            if parts.get('street'):
                                address_info['Street1To'] = parts['street']
                            if parts.get('city'):
                                address_info['CityTo'] = parts['city']
                            if parts.get('state'):
                                address_info['StateTo'] = parts['state']
                            if parts.get('zip'):
                                address_info['ZipTo'] = parts['zip']
                        elif field_name == 'Street1To' and (re.search(r'[A-Z][a-z]+\s+[A-Z][a-z]+', value) or ',' in value):
                            # This might contain name and street combined
                            parts = parse_combined_field(value)
                            if parts.get('name') and not address_info['ToName']:
                                address_info['ToName'] = parts['name']
                            if parts.get('street'):
                                address_info['Street1To'] = parts['street']
                            if parts.get('city'):
                                address_info['CityTo'] = parts['city']
                            if parts.get('state'):
                                address_info['StateTo'] = parts['state']
                            if parts.get('zip'):
                                address_info['ZipTo'] = parts['zip']
                        else:
                            # Regular field
                            address_info[field_name] = value
            
            # Check if we have the essential info and add to addresses
            if address_info['ToName'] or address_info['Street1To']:
                shipping_addresses.append(address_info)
            
            # Return form field addresses if found
            if shipping_addresses:
                return shipping_addresses[0] if len(shipping_addresses) == 1 else shipping_addresses
        
        # Look for general Amazon-specific address elements (if not in table format)
        amazon_addresses = soup.find_all('div', attrs={'data-test-id': 'shipping-section-buyer-address'})
        
        # If we found Amazon address format but not in the table format we tried earlier
        if amazon_addresses and not shipping_addresses:
            for address_div in amazon_addresses:
                shipping_info = {
                    'ToName': '',
                    'PhoneTo': '',
                    'Street1To': '',
                    'CompanyTo': '',
                    'Street2To': '',
                    'CityTo': '',
                    'ZipTo': '',
                    'StateTo': '',
                    'order_id': ''
                }
                
                # Extract text content from the address div
                address_text = address_div.get_text()
                
                # Find the name (first line) and street address (second line)
                try:
                    spans = address_div.find_all('span', class_='')
                    if spans and len(spans) >= 1:
                        shipping_info['ToName'] = spans[0].get_text().strip().rstrip('<br>')
                    
                    if spans and len(spans) >= 2:
                        shipping_info['Street1To'] = spans[1].get_text().strip().rstrip('<br>')
                except (AttributeError, TypeError):
                    logging.warning("Could not extract spans from address div")
                
                # Extract city, state, zip from the last part
                city_state_zip_pattern = r'([A-Za-z\s]+),\s*([A-Z]{2})\s*(\d{5}(?:-\d{4})?)'
                city_state_zip_match = re.search(city_state_zip_pattern, address_text)
                
                if city_state_zip_match:
                    shipping_info['CityTo'] = city_state_zip_match.group(1).strip()
                    shipping_info['StateTo'] = city_state_zip_match.group(2).strip()
                    shipping_info['ZipTo'] = city_state_zip_match.group(3).strip()
                
                # Try to find order ID near this address
                order_element = None
                current = address_div
                
                # Look for order ID in parent elements
                for _ in range(5):  # limit the search depth
                    if not current.parent:
                        break
                    current = current.parent
                    try:
                        order_links = current.find_all('a', href=re.compile(r'/order/'))
                        if order_links:
                            order_element = order_links[0]
                            break
                    except (AttributeError, TypeError):
                        continue
                
                # Extract order ID if found
                if order_element:
                    order_id_match = re.search(r'(\d{3}-\d{7}-\d{7})', order_element.get_text())
                    if order_id_match:
                        shipping_info['order_id'] = order_id_match.group(1)
                
                # Only add if we have the essential shipping info
                if shipping_info['ToName'] and shipping_info['Street1To'] and shipping_info['CityTo'] and shipping_info['StateTo'] and shipping_info['ZipTo']:
                    shipping_addresses.append(shipping_info)
        
        # Return addresses if found through any method
        if shipping_addresses:
            return shipping_addresses[0] if len(shipping_addresses) == 1 else shipping_addresses
        
        # If no structured addresses found, try to extract from text content as last resort
        full_text = soup.get_text()
        addr_components = extract_address_components(full_text)
        
        if addr_components and addr_components['ToName'] and addr_components['Street1To']:
            return addr_components
        
        # If we still couldn't find any addresses, return None
        return None
        
    except Exception as e:
        logging.error(f"Error parsing HTML: {str(e)}")
        return None

def parse_combined_field(text):
    """
    Parse a field that might contain multiple pieces of address information.
    
    Args:
        text (str): The text to parse
        
    Returns:
        dict: A dictionary with parsed components
    """
    result = {
        'name': '',
        'street': '',
        'city': '',
        'state': '',
        'zip': ''
    }
    
    # Try to extract city, state, zip first
    city_state_zip = re.search(r'([A-Za-z\s]+),\s*([A-Z]{2})\s*(\d{5}(?:-\d{4})?)', text)
    if city_state_zip:
        result['city'] = city_state_zip.group(1).strip()
        result['state'] = city_state_zip.group(2).strip()
        result['zip'] = city_state_zip.group(3).strip()
        
        # Remove the city, state, zip part from text
        text = text[:city_state_zip.start()].strip()
    
    # Try to identify street address (contains numbers)
    street_match = re.search(r'\d+\s+[A-Za-z\s]+(?:(?:St|Street|Ave|Avenue|Rd|Road|Dr|Drive|Ln|Lane|Blvd|Boulevard|Pl|Place|Ct|Court|Way|Trl|Trail|Cir|Circle|Pkwy|Parkway))?', text, re.IGNORECASE)
    if street_match:
        result['street'] = street_match.group(0).strip()
        
        # The name is likely before the street address
        name_part = text[:street_match.start()].strip()
        if name_part and re.match(r'^[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+$', name_part):
            result['name'] = name_part
        
    # If we couldn't find a street pattern but there are digits, try another approach
    elif re.search(r'\d+', text):
        parts = text.split()
        for i, part in enumerate(parts):
            if re.match(r'\d+', part):
                # Assume everything before this is the name, and this + following is the street
                if i > 0:
                    result['name'] = ' '.join(parts[:i]).strip()
                street_end = min(i + 5, len(parts))  # Take up to 5 words for the street
                result['street'] = ' '.join(parts[i:street_end]).strip()
                break
    
    # If we still don't have a name but have a street, assume anything not matched is the name
    if result['street'] and not result['name']:
        name_match = re.match(r'^([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)', text)
        if name_match:
            result['name'] = name_match.group(1).strip()
    
    # If we have city, state, zip but no street, try to extract street
    if result['city'] and result['state'] and result['zip'] and not result['street'] and not result['name']:
        # Try to split the remaining text into name and street
        remaining = text[:city_state_zip.start()].strip()
        parts = remaining.split()
        
        if len(parts) >= 3:  # Need at least 3 parts for name and street
            # Try to find a pattern with numbers for street
            for i, part in enumerate(parts):
                if re.match(r'\d+', part) and i > 0:
                    result['name'] = ' '.join(parts[:i]).strip()
                    result['street'] = ' '.join(parts[i:]).strip()
                    break
            
            # If no street with numbers found, assume last 2+ words are street
            if not result['street']:
                split_idx = max(1, len(parts) // 2)  # split roughly in half, but keep at least 1 word for name
                result['name'] = ' '.join(parts[:split_idx]).strip()
                result['street'] = ' '.join(parts[split_idx:]).strip()
    
    return result

def extract_address_components(text):
    """
    Extract address components from a block of text.
    
    Args:
        text (str): The text to extract from
        
    Returns:
        dict: Dictionary with address components
    """
    result = {
        'ToName': '',
        'PhoneTo': '',
        'Street1To': '',
        'CompanyTo': '',
        'Street2To': '',
        'CityTo': '',
        'StateTo': '',
        'ZipTo': '',
        'PhoneTo': ''
    }
    
    # Find name patterns
    name_pattern = r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})'
    name_match = re.search(name_pattern, text)
    if name_match:
        # Make sure it's not followed by a comma and state code (which would make it a city)
        if not re.search(name_match.group(1) + r',\s*[A-Z]{2}', text):
            result['ToName'] = name_match.group(1)
    
    # Find street address pattern
    street_pattern = r'(\d+\s+[A-Za-z\s]+(?:(?:St|Street|Ave|Avenue|Rd|Road|Dr|Drive|Ln|Lane|Blvd|Boulevard|Pl|Place|Ct|Court|Way|Trl|Trail|Cir|Circle|Pkwy|Parkway))?)'
    street_match = re.search(street_pattern, text, re.IGNORECASE)
    if street_match:
        result['Street1To'] = street_match.group(1)
    
    # Find city, state, zip pattern
    csz_pattern = r'([A-Za-z\s]+),\s*([A-Z]{2})\s*(\d{5}(?:-\d{4})?)'
    csz_match = re.search(csz_pattern, text)
    if csz_match:
        result['CityTo'] = csz_match.group(1).strip()
        result['StateTo'] = csz_match.group(2)
        result['ZipTo'] = csz_match.group(3)
    
    # Find phone pattern
    phone_pattern = r'(?:\+\d{1,2}\s*)?(?:\(\d{3}\)|\d{3})[-.\s]?\d{3}[-.\s]?\d{4}'
    phone_match = re.search(phone_pattern, text)
    if phone_match:
        result['PhoneTo'] = phone_match.group(0)
    
    return result
