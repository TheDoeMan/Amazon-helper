// DOM Elements
const htmlInput = document.getElementById('htmlInput');
const extractBtn = document.getElementById('extractBtn');
const inputSection = document.getElementById('inputSection');
const loadingSection = document.getElementById('loadingSection');
const errorSection = document.getElementById('errorSection');
const errorMessage = document.getElementById('errorMessage');
const shippingForm = document.getElementById('shippingForm');
const resetBtn = document.getElementById('resetBtn');
const csvForm = document.getElementById('csvForm');
const addressSelector = document.getElementById('addressSelector');
const addressSelectorContainer = document.getElementById('addressSelectorContainer');
const mergeOrdersCheckbox = document.getElementById('mergeOrdersCheckbox');
const sameDimensionsCheckbox = document.getElementById('sameDimensionsCheckbox');
const prevAddressBtn = document.getElementById('prevAddressBtn');
const nextAddressBtn = document.getElementById('nextAddressBtn');
const orderCount = document.getElementById('orderCount');

// Store extracted addresses
let extractedAddresses = [];
let currentAddressIndex = 0;

// Store package dimensions for each order
let packageDimensions = {};

// Event Listeners
document.addEventListener('DOMContentLoaded', () => {
    extractBtn.addEventListener('click', extractShippingInfo);
    resetBtn.addEventListener('click', resetForm);
    csvForm.addEventListener('submit', validateForm);
    
    // Add event listener for address selector if it exists
    if (addressSelector) {
        addressSelector.addEventListener('change', function() {
            const index = parseInt(this.value);
            if (index >= 0 && index < extractedAddresses.length) {
                currentAddressIndex = index;
                populateShippingForm(extractedAddresses[index]);
            }
        });
    }
    
    // Check for merge orders checkbox
    if (mergeOrdersCheckbox) {
        mergeOrdersCheckbox.addEventListener('change', function() {
            // We keep the selected address fields editable even when merge is checked
            // so the user can adjust weight/dimensions for all orders at once
        });
    }
    
    // Check for same dimensions checkbox
    if (sameDimensionsCheckbox) {
        sameDimensionsCheckbox.addEventListener('change', function() {
            // No action needed here - we'll check this value when generating the CSV
        });
    }
    
    // Navigation arrows for addresses
    if (prevAddressBtn) {
        prevAddressBtn.addEventListener('click', function() {
            if (extractedAddresses.length > 1) {
                // Save current dimensions before switching
                saveCurrentDimensions();
                
                // Go to previous address
                currentAddressIndex = (currentAddressIndex - 1 + extractedAddresses.length) % extractedAddresses.length;
                addressSelector.value = currentAddressIndex;
                populateShippingForm(extractedAddresses[currentAddressIndex]);
            }
        });
    }
    
    if (nextAddressBtn) {
        nextAddressBtn.addEventListener('click', function() {
            if (extractedAddresses.length > 1) {
                // Save current dimensions before switching
                saveCurrentDimensions();
                
                // Go to next address
                currentAddressIndex = (currentAddressIndex + 1) % extractedAddresses.length;
                addressSelector.value = currentAddressIndex;
                populateShippingForm(extractedAddresses[currentAddressIndex]);
            }
        });
    }
});

// Save the current package dimensions for the current address
function saveCurrentDimensions() {
    if (currentAddressIndex >= 0 && currentAddressIndex < extractedAddresses.length) {
        // Get the current dimensions from the form
        const weight = document.getElementById('Weight').value;
        const length = document.getElementById('length').value;
        const width = document.getElementById('width').value;
        const height = document.getElementById('height').value;
        const description = document.getElementById('description').value;
        
        // Store these dimensions keyed by order ID or index if no order ID
        const orderId = extractedAddresses[currentAddressIndex].order_id || currentAddressIndex.toString();
        
        packageDimensions[orderId] = {
            weight,
            length,
            width,
            height,
            description
        };
    }
}

// Extract shipping information from HTML
async function extractShippingInfo() {
    // Show loading state
    inputSection.classList.add('d-none');
    loadingSection.classList.remove('d-none');
    errorSection.classList.add('d-none');
    
    try {
        const htmlContent = htmlInput.value.trim();
        
        if (!htmlContent) {
            throw new Error('Please enter HTML content to extract shipping information.');
        }
        
        // Send HTML content to server for extraction
        const response = await fetch('/extract', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/x-www-form-urlencoded',
            },
            body: new URLSearchParams({
                'html_content': htmlContent
            })
        });
        
        const data = await response.json();
        
        if (!response.ok) {
            throw new Error(data.error || 'Failed to extract shipping information.');
        }
        
        // Show the shipping form
        shippingForm.classList.remove('d-none');
        loadingSection.classList.add('d-none');
        
        // Reset package dimensions
        packageDimensions = {};
        
        // Handle multiple addresses or single address
        if (data.multiple === true) {
            extractedAddresses = data.data;
            
            // Update order count display
            if (orderCount) {
                orderCount.textContent = `${extractedAddresses.length} orders found`;
                orderCount.classList.remove('d-none');
            }
            
            // Send all addresses to server to store in session
            await fetch('/store-addresses', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    addresses: extractedAddresses
                })
            });
            
            setupAddressSelector(extractedAddresses);
            populateShippingForm(extractedAddresses[0]);
            
            // Show navigation and options for multiple addresses
            if (addressSelectorContainer) {
                addressSelectorContainer.classList.remove('d-none');
            }
            
            // Enable navigation buttons
            if (prevAddressBtn && nextAddressBtn) {
                prevAddressBtn.disabled = false;
                nextAddressBtn.disabled = false;
            }
        } else {
            extractedAddresses = [data.data];
            
            // Update order count display
            if (orderCount) {
                orderCount.textContent = '1 order found';
                orderCount.classList.remove('d-none');
            }
            
            // Send all addresses to server to store in session
            await fetch('/store-addresses', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    addresses: extractedAddresses
                })
            });
            
            // Hide address selector and navigation for single address
            if (addressSelectorContainer) {
                addressSelectorContainer.classList.add('d-none');
            }
            
            // Disable navigation buttons
            if (prevAddressBtn && nextAddressBtn) {
                prevAddressBtn.disabled = true;
                nextAddressBtn.disabled = true;
            }
            
            populateShippingForm(data.data);
        }
        
    } catch (error) {
        // Show error message
        loadingSection.classList.add('d-none');
        errorSection.classList.remove('d-none');
        errorMessage.textContent = error.message;
        inputSection.classList.remove('d-none');
    }
}

// Set up address selector dropdown for multiple addresses
function setupAddressSelector(addresses) {
    // Show address selector container
    if (addressSelectorContainer) {
        addressSelectorContainer.classList.remove('d-none');
    }
    
    // Clear previous options
    if (addressSelector) {
        addressSelector.innerHTML = '';
        
        // Add options for each address
        addresses.forEach((address, index) => {
            const option = document.createElement('option');
            option.value = index;
            
            // Create a descriptive label
            const name = address.ToName || 'Unknown';
            const city = address.CityTo || '';
            const state = address.StateTo || '';
            const orderId = address.order_id ? `(Order: ${address.order_id})` : '';
            
            option.textContent = `${name} - ${city}, ${state} ${orderId}`;
            addressSelector.appendChild(option);
        });
    }
}

// Populate shipping form with extracted data
function populateShippingForm(data) {
    // Mark current address for all addresses
    extractedAddresses.forEach((addr, idx) => {
        addr.current_address = 'false';
    });
    
    // Mark the currently selected address
    extractedAddresses[currentAddressIndex].current_address = 'true';
    
    // Fill in the form fields with extracted data
    document.getElementById('ToName').value = data.ToName || '';
    document.getElementById('PhoneTo').value = data.PhoneTo || '';
    document.getElementById('Street1To').value = data.Street1To || '';
    document.getElementById('CompanyTo').value = data.CompanyTo || '';
    document.getElementById('Street2To').value = data.Street2To || '';
    document.getElementById('CityTo').value = data.CityTo || '';
    document.getElementById('StateTo').value = data.StateTo || '';
    document.getElementById('ZipTo').value = data.ZipTo || '';
    document.getElementById('order_id').value = data.order_id || '';
    
    // Check if we have package dimensions stored for this order
    const orderId = data.order_id || currentAddressIndex.toString();
    if (packageDimensions[orderId]) {
        document.getElementById('Weight').value = packageDimensions[orderId].weight;
        document.getElementById('length').value = packageDimensions[orderId].length;
        document.getElementById('width').value = packageDimensions[orderId].width;
        document.getElementById('height').value = packageDimensions[orderId].height;
        document.getElementById('description').value = packageDimensions[orderId].description;
    }
    
    // Scroll to the form
    shippingForm.scrollIntoView({ behavior: 'smooth' });
}

// Reset the form and go back to input section
function resetForm() {
    // Reset the HTML input
    htmlInput.value = '';
    
    // Hide shipping form and show input section
    shippingForm.classList.add('d-none');
    inputSection.classList.remove('d-none');
    errorSection.classList.add('d-none');
    
    // Hide the order count badge
    if (orderCount) {
        orderCount.classList.add('d-none');
    }
    
    // Reset the extracted addresses and dimensions
    extractedAddresses = [];
    currentAddressIndex = 0;
    packageDimensions = {};
    
    // Scroll to the top
    window.scrollTo({ top: 0, behavior: 'smooth' });
}

// Validate form before submission
function validateForm(event) {
    const requiredFields = [
        'ToName', 'Street1To', 'CityTo', 'StateTo', 'ZipTo',
        'Weight', 'length', 'width', 'height'
    ];
    
    let isValid = true;
    
    // Check each required field
    requiredFields.forEach(fieldId => {
        const field = document.getElementById(fieldId);
        if (!field.value.trim()) {
            field.classList.add('is-invalid');
            isValid = false;
        } else {
            field.classList.remove('is-invalid');
        }
    });
    
    if (!isValid) {
        event.preventDefault();
        alert('Please fill in all required fields.');
        return;
    }
    
    // Save current dimensions for the current address
    saveCurrentDimensions();
    
    // Add the current address flag to each address
    extractedAddresses.forEach((addr, idx) => {
        // Create hidden field for current address status
        const currentAddrField = document.createElement('input');
        currentAddrField.type = 'hidden';
        currentAddrField.name = `address[${idx}][current_address]`;
        currentAddrField.value = addr.current_address || 'false';
        event.target.appendChild(currentAddrField);
    });
    
    // If user is merging orders and applying same dimensions to all
    if (mergeOrdersCheckbox && mergeOrdersCheckbox.checked && 
        sameDimensionsCheckbox && sameDimensionsCheckbox.checked) {
        // Add a hidden field to indicate same dimensions for all
        const sameDimensionsField = document.createElement('input');
        sameDimensionsField.type = 'hidden';
        sameDimensionsField.name = 'same_dimensions';
        sameDimensionsField.value = 'on';
        event.target.appendChild(sameDimensionsField);
    }
}

// Add visual feedback while fields are being completed
document.querySelectorAll('.form-control').forEach(input => {
    input.addEventListener('input', function() {
        if (this.hasAttribute('required') && this.value.trim() === '') {
            this.classList.add('is-invalid');
        } else {
            this.classList.remove('is-invalid');
        }
    });
});
