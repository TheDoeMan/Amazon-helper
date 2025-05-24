import sys
from utils.html_parser import extract_shipping_info
import pprint

# Load the HTML file
with open(sys.argv[1], 'r') as f:
    html_content = f.read()

# Extract shipping info
result = extract_shipping_info(html_content)

# Print the result nicely formatted
print("Extracted shipping information:")
pprint.pprint(result)