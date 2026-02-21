/**
 * NUT Configuration Wizard
 * 
 * This script handles the step-by-step wizard for configuring NUT.
 */

document.addEventListener('DOMContentLoaded', function() {
    // Elements
    const prevBtn = document.getElementById('prev-btn');
    const nextBtn = document.getElementById('next-btn');
    const saveBtn = document.getElementById('save-btn');
    const testConfigBtn = document.getElementById('test-config-btn');
    const restartBtn = document.getElementById('restart-btn');
    const steps = document.querySelectorAll('.step');
    const stepContents = document.querySelectorAll('.wizard-step-content');
    const setupContainer = document.querySelector('.setup-container');
    const authDisabled = setupContainer?.dataset.authDisabled === 'true';
    const modeOptions = document.querySelectorAll('.mode-option');
    const configTabs = document.querySelectorAll('.config-tab');
    const configPreview = document.getElementById('config-preview');
    const alertsContainer = document.getElementById('alerts-container');
    
    // Scan buttons
    const scanStandaloneBtn = document.getElementById('scan-standalone');
    const scanNetserverBtn = document.getElementById('scan-netserver');
    
    // Config method radio buttons
    const manualStandaloneRadio = document.getElementById('manual-standalone');
    const autoStandaloneRadio = document.getElementById('auto-standalone');
    const manualNetserverRadio = document.getElementById('manual-netserver');
    const autoNetserverRadio = document.getElementById('auto-netserver');
    
    // Driver selects
    const standaloneDriverSelect = document.getElementById('ups_driver');
    const netserverDriverSelect = document.getElementById('server_ups_driver');
    
    // Editor elements
    const editConfigBtn = document.getElementById('edit-config-btn');
    const configEditorContainer = document.getElementById('config-editor-container');
    const configPreviewElement = document.getElementById('config-preview');
    const editorActions = document.getElementById('editor-actions');
    const saveEditBtn = document.getElementById('save-edit-btn');
    const cancelEditBtn = document.getElementById('cancel-edit-btn');
    
    // Modal elements
    const modal = document.getElementById('test-modal');
    const modalClose = document.querySelector('.modal-close');
    const closeModalBtn = document.getElementById('close-modal-btn');
    const testMessage = document.getElementById('test-message');
    const upscOutput = document.getElementById('upsc-output');
    const missingRealpowerForm = document.getElementById('missing-realpower-form');
    const realpowerInput = document.getElementById('ups-realpower-nominal');
    
    // Current step (1-based)
    const firstStep = authDisabled ? 2 : 1;
    let currentStep = firstStep;
    let selectedMode = null;
    let configData = null;
    let configFiles = {};
    let editedFiles = {};
    let currentFile = null;
    let editor = null;
    let upsRealpowerNominal = null;
    
    // Load available drivers and setup scan buttons
    loadAvailableDrivers();
    setupScanButtons();
    setupConfigMethodRadios();
    
    // Hide the save button initially - it will only be shown after successful test
    saveBtn.classList.add('hidden');

    if (authDisabled) {
        const adminStepIndicator = document.querySelector('.step[data-step="1"]');
        const adminStepContent = document.getElementById('step-1');

        if (adminStepIndicator) {
            adminStepIndicator.classList.add('hidden');
        }

        if (adminStepContent) {
            adminStepContent.classList.add('hidden');
        }

        let displayStep = 1;
        steps.forEach(stepEl => {
            if (stepEl.classList.contains('hidden')) {
                return;
            }

            const numberEl = stepEl.querySelector('.step-number');
            if (numberEl) {
                numberEl.textContent = displayStep;
            }
            displayStep += 1;
        });
    }
    
    // Add event listeners
    prevBtn.addEventListener('click', goToPreviousStep);
    nextBtn.addEventListener('click', goToNextStep);
    saveBtn.addEventListener('click', saveConfiguration);
    testConfigBtn.addEventListener('click', testConfiguration);
    restartBtn.addEventListener('click', resetWizard);
    
    // Editor event listeners
    if (editConfigBtn) {
        editConfigBtn.addEventListener('click', toggleEditor);
    }
    
    if (saveEditBtn) {
        saveEditBtn.addEventListener('click', saveEditorChanges);
    }
    
    if (cancelEditBtn) {
        cancelEditBtn.addEventListener('click', cancelEditorChanges);
    }
    
    // Modal event listeners
    modalClose.addEventListener('click', closeModal);
    closeModalBtn.addEventListener('click', closeModal);
    window.addEventListener('click', function(event) {
        if (event.target === modal) {
            closeModal();
        }
    });

    updateStepIndicators(currentStep);
    updateButtons(currentStep);
    
    /**
     * Set up configuration method radio buttons
     */
    function setupConfigMethodRadios() {
        // Get option containers
        const manualOptionStandalone = document.getElementById('manual-option-standalone');
        const autoOptionStandalone = document.getElementById('auto-option-standalone');
        const manualOptionNetserver = document.getElementById('manual-option-netserver');
        const autoOptionNetserver = document.getElementById('auto-option-netserver');
        
        // Initialize all manual and auto config sections as hidden
        document.getElementById('manual-config-standalone').classList.add('hidden');
        document.getElementById('auto-config-standalone').classList.add('hidden');
        document.getElementById('manual-config-netserver').classList.add('hidden');
        document.getElementById('auto-config-netserver').classList.add('hidden');
        
        // Standalone mode
        if (manualStandaloneRadio && autoStandaloneRadio) {
            // Click handler for the manual option container
            manualOptionStandalone.addEventListener('click', function() {
                manualStandaloneRadio.checked = true;
                
                // Update selected class
                manualOptionStandalone.classList.add('selected');
                autoOptionStandalone.classList.remove('selected');
                
                // Show manual config, hide auto config
                document.getElementById('manual-config-standalone').classList.remove('hidden');
                document.getElementById('auto-config-standalone').classList.add('hidden');
                
                // Hide scan button and results
                scanStandaloneBtn.classList.add('hidden');
                const scanResults = document.getElementById('scan-results-standalone');
                if (scanResults) {
                    scanResults.classList.add('hidden');
                }
                
                // Hide device details if they exist
                const deviceDetails = document.getElementById('device-details-standalone');
                if (deviceDetails) {
                    deviceDetails.classList.add('hidden');
                }
            });
            
            // Event handler for the radio button
            manualStandaloneRadio.addEventListener('change', function() {
                if (this.checked) {
                    manualOptionStandalone.click();
                }
            });
            
            // Click handler for the auto option container
            autoOptionStandalone.addEventListener('click', function() {
                autoStandaloneRadio.checked = true;
                
                // Update selected class
                autoOptionStandalone.classList.add('selected');
                manualOptionStandalone.classList.remove('selected');
                
                // Hide manual config, show auto config
                document.getElementById('manual-config-standalone').classList.add('hidden');
                document.getElementById('auto-config-standalone').classList.remove('hidden');
                
                // Save the current UPS name value before running the scanner
                const currentUpsName = document.getElementById('ups_name').value.trim();
                
                // Run scanner only if it hasn't been run before
                const scanResults = document.getElementById('scan-results-standalone');
                if (!scanResults || scanResults.children.length === 0) {
                    runNutScanner('standalone', currentUpsName);
                } else {
                    scanResults.classList.remove('hidden');
                    
                    // Show device details if they exist
                    const deviceDetails = document.getElementById('device-details-standalone');
                    if (deviceDetails) {
                        deviceDetails.classList.remove('hidden');
                    }
                }
            });
            
            // Event handler for the radio button
            autoStandaloneRadio.addEventListener('change', function() {
                if (this.checked) {
                    autoOptionStandalone.click();
                }
            });
        }
        
        // Netserver mode
        if (manualNetserverRadio && autoNetserverRadio) {
            // Click handler for the manual option container
            manualOptionNetserver.addEventListener('click', function() {
                manualNetserverRadio.checked = true;
                
                // Update selected class
                manualOptionNetserver.classList.add('selected');
                autoOptionNetserver.classList.remove('selected');
                
                // Show manual config, hide auto config
                document.getElementById('manual-config-netserver').classList.remove('hidden');
                document.getElementById('auto-config-netserver').classList.add('hidden');
                
                // Hide scan button and results
                scanNetserverBtn.classList.add('hidden');
                const scanResults = document.getElementById('scan-results-netserver');
                if (scanResults) {
                    scanResults.classList.add('hidden');
                }
                
                // Hide device details if they exist
                const deviceDetails = document.getElementById('device-details-netserver');
                if (deviceDetails) {
                    deviceDetails.classList.add('hidden');
                }
            });
            
            // Event handler for the radio button
            manualNetserverRadio.addEventListener('change', function() {
                if (this.checked) {
                    manualOptionNetserver.click();
                }
            });
            
            // Click handler for the auto option container
            autoOptionNetserver.addEventListener('click', function() {
                autoNetserverRadio.checked = true;
                
                // Update selected class
                autoOptionNetserver.classList.add('selected');
                manualOptionNetserver.classList.remove('selected');
                
                // Hide manual config, show auto config
                document.getElementById('manual-config-netserver').classList.add('hidden');
                document.getElementById('auto-config-netserver').classList.remove('hidden');
                
                // Save the current UPS name value before running the scanner
                const currentUpsName = document.getElementById('server_ups_name').value.trim();
                
                // Run scanner only if it hasn't been run before
                const scanResults = document.getElementById('scan-results-netserver');
                if (!scanResults || scanResults.children.length === 0) {
                    runNutScanner('netserver', currentUpsName);
                } else {
                    scanResults.classList.remove('hidden');
                    
                    // Show device details if they exist
                    const deviceDetails = document.getElementById('device-details-netserver');
                    if (deviceDetails) {
                        deviceDetails.classList.remove('hidden');
                    }
                }
            });
            
            // Event handler for the radio button
            autoNetserverRadio.addEventListener('change', function() {
                if (this.checked) {
                    autoOptionNetserver.click();
                }
            });
        }
    }
    
    /**
     * Load available drivers from the server
     */
    function loadAvailableDrivers() {
        // Fetch the list of available drivers from the server
        fetch('/nut_config/api/setup/get-available-drivers')
            .then(response => response.json())
            .then(data => {
                if (data.status === 'success' && data.drivers && data.drivers.length > 0) {
                    // Clear existing options
                    standaloneDriverSelect.innerHTML = '';
                    netserverDriverSelect.innerHTML = '';
                    
                    // Add the drivers to both dropdowns
                    let usbhidUpsFound = false;
                    
                    data.drivers.forEach(driver => {
                        // Check if this is usbhid-ups
                        const isUsbhidUps = driver.name === 'usbhid-ups';
                        if (isUsbhidUps) {
                            usbhidUpsFound = true;
                        }
                        
                        // Create option for standalone dropdown
                        const standaloneOption = document.createElement('option');
                        standaloneOption.value = driver.name;
                        standaloneOption.textContent = `${driver.name}${driver.description ? ': ' + driver.description : ''}`;
                        standaloneOption.selected = isUsbhidUps; // Set selected if it's usbhid-ups
                        standaloneDriverSelect.appendChild(standaloneOption);
                        
                        // Create option for netserver dropdown
                        const netserverOption = document.createElement('option');
                        netserverOption.value = driver.name;
                        netserverOption.textContent = `${driver.name}${driver.description ? ': ' + driver.description : ''}`;
                        netserverOption.selected = isUsbhidUps; // Set selected if it's usbhid-ups
                        netserverDriverSelect.appendChild(netserverOption);
                    });
                    
                    console.log(`Loaded ${data.drivers.length} drivers from ${data.directory}`);
                    
                    // If usbhid-ups wasn't found in the list, try to select it programmatically
                    if (!usbhidUpsFound) {
                        // Try to find and select usbhid-ups by value
                        for (let i = 0; i < standaloneDriverSelect.options.length; i++) {
                            if (standaloneDriverSelect.options[i].value === 'usbhid-ups') {
                                standaloneDriverSelect.selectedIndex = i;
                                break;
                            }
                        }
                        
                        for (let i = 0; i < netserverDriverSelect.options.length; i++) {
                            if (netserverDriverSelect.options[i].value === 'usbhid-ups') {
                                netserverDriverSelect.selectedIndex = i;
                                break;
                            }
                        }
                    }
                } else {
                    // Show error in UI with specific message from API if possible
                    const errorMsg = data.message || 'Failed to load drivers from server';
                    showAlert(`${errorMsg}. Check the driver directory settings in settings_path.txt file.`, 'error');
                    console.warn('Failed to load available drivers:', errorMsg);
                    
                    // Add a minimal set of common drivers for testing
                    const defaultDrivers = ['usbhid-ups', 'snmp-ups'];
                    
                    defaultDrivers.forEach((driverName, index) => {
                        // Add to standalone dropdown
                        const standaloneOption = document.createElement('option');
                        standaloneOption.value = driverName;
                        standaloneOption.textContent = driverName;
                        standaloneOption.selected = driverName === 'usbhid-ups'; // Select usbhid-ups
                        standaloneDriverSelect.appendChild(standaloneOption);
                        
                        // Add to netserver dropdown
                        const netserverOption = document.createElement('option');
                        netserverOption.value = driverName;
                        netserverOption.textContent = driverName;
                        netserverOption.selected = driverName === 'usbhid-ups'; // Select usbhid-ups
                        netserverDriverSelect.appendChild(netserverOption);
                    });
                }
            })
            .catch(error => {
                console.error('Error loading available drivers:', error);
                showAlert(`Error loading drivers: ${error.message}. Check server logs for details.`, 'error');
                
                // Add a minimal fallback option so the form can still be submitted
                const defaultOption = document.createElement('option');
                defaultOption.value = 'usbhid-ups';
                defaultOption.textContent = 'USB UPS (usbhid-ups)';
                defaultOption.selected = true;
                
                standaloneDriverSelect.innerHTML = '';
                netserverDriverSelect.innerHTML = '';
                
                standaloneDriverSelect.appendChild(defaultOption.cloneNode(true));
                netserverDriverSelect.appendChild(defaultOption);
            });
    }
    
    /**
     * Set up scan buttons
     */
    function setupScanButtons() {
        if (scanStandaloneBtn) {
            scanStandaloneBtn.addEventListener('click', function() {
                runNutScanner('standalone');
            });
        }
        
        if (scanNetserverBtn) {
            scanNetserverBtn.addEventListener('click', function() {
                runNutScanner('netserver');
            });
        }
    }
    
    /**
     * Run nut-scanner and show results
     */
    function runNutScanner(mode, currentUpsName) {
        // Get the relevant elements based on mode
        const portInput = mode === 'standalone' ? 
            document.getElementById('ups_port') : 
            document.getElementById('server_ups_port');
        
        const driverSelect = mode === 'standalone' ? 
            document.getElementById('ups_driver') : 
            document.getElementById('server_ups_driver');
        
        const nameInput = mode === 'standalone' ? 
            document.getElementById('ups_name') : 
            document.getElementById('server_ups_name');
        
        const descInput = mode === 'standalone' ? 
            document.getElementById('ups_desc') : 
            document.getElementById('server_ups_desc');
        
        // Get the auto-config section to place results
        const autoConfigSection = document.getElementById(`auto-config-${mode}`);
        
        // Create or get scan results container
        let scanResults = document.getElementById(`scan-results-${mode}`);
        if (!scanResults) {
            scanResults = document.createElement('div');
            scanResults.id = `scan-results-${mode}`;
            scanResults.className = 'scan-results';
            autoConfigSection.appendChild(scanResults);
        }
        
        // Show loading indicator
        scanResults.innerHTML = '<div class="scan-loading"><i class="fas fa-spinner fa-spin"></i> Scanning for UPS devices...</div>';
        scanResults.classList.remove('hidden');
        
        // If no name is provided, use the current value from the input
        if (!currentUpsName && nameInput.value.trim()) {
            currentUpsName = nameInput.value.trim();
        }
        
        // Call the API to run nut-scanner
        fetch('/nut_config/api/setup/run-nut-scanner', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                scan_types: ['usb', 'snmp'], // Add other types as needed
                current_ups_name: currentUpsName || 'ups' // Use default 'ups' if no name is provided
            })
        })
        .then(response => response.json())
        .then(data => {
            if (data.status === 'success' && data.devices && data.devices.length > 0) {
                scanResults.innerHTML = `
                    <div class="scan-results-title">Detected UPS Devices:</div>
                `;
                
                // Add each device to the results
                data.devices.forEach(device => {
                    const deviceElement = document.createElement('div');
                    deviceElement.className = 'scan-device';
                    // Store the device object on the DOM element for later use
                    deviceElement.__device = device;
                    
                    deviceElement.innerHTML = `
                        <div class="scan-device-name">${device.name}</div>
                        <div class="scan-device-details">
                            Driver: ${device.driver || 'Unknown'}<br>
                            Port: ${device.port || 'Unknown'}
                        </div>
                    `;
                    
                    // Add click event to select this device
                    deviceElement.addEventListener('click', function() {
                        // Remove selected class from all devices
                        scanResults.querySelectorAll('.scan-device').forEach(el => {
                            el.classList.remove('selected');
                        });
                        
                        // Add selected class to this device
                        this.classList.add('selected');
                        
                        // Update form fields with all available device information
                        if (device.driver) {
                            const driverOptions = Array.from(driverSelect.options);
                            const matchingOption = driverOptions.find(opt => opt.value === device.driver);
                            if (matchingOption) {
                                driverSelect.value = device.driver;
                            }
                        }
                        
                        if (device.port) {
                            portInput.value = device.port;
                        }
                        
                        // Set UPS name from device or keep user-provided name
                        if (currentUpsName && currentUpsName.trim() !== '') {
                            // Keep user-provided name
                            nameInput.value = currentUpsName;
                        } else if (device.name && device.name !== "unknown") {
                            // If no user-provided name, use device name
                            nameInput.value = device.name;
                        } else if (device.model) {
                            // Generate a name from model if available
                            nameInput.value = device.model.toLowerCase().replace(/[^a-z0-9]/g, '_');
                        }
                        
                        // Generate a descriptive name
                        let description = [];
                        if (device.model) description.push(device.model);
                        if (device.vendor) description.push(device.vendor);
                        if (device.serial) description.push(`S/N:${device.serial}`);
                        
                        if (description.length > 0) {
                            descInput.value = description.join(' ');
                        } else {
                            descInput.value = `Detected ${nameInput.value}`;
                        }
                        
                        // Store the raw config for use in the preview
                        if (device.raw_config) {
                            device.formattedConfig = device.raw_config;
                            // Update the config in the global configData if it exists
                            if (configData) {
                                configData.raw_ups_config = device.formattedConfig;
                            }
                        }
                        
                        // Show additional device details
                        let deviceDetailsHTML = '<div class="device-details-header">Selected Device Details:</div>';
                        deviceDetailsHTML += '<div class="device-details-grid">';
                        
                        // Add all available properties
                        if (device.name) deviceDetailsHTML += `<div class="device-detail-item"><strong>Name:</strong> ${device.name}</div>`;
                        if (device.driver) deviceDetailsHTML += `<div class="device-detail-item"><strong>Driver:</strong> ${device.driver}</div>`;
                        if (device.port) deviceDetailsHTML += `<div class="device-detail-item"><strong>Port:</strong> ${device.port}</div>`;
                        if (device.model) deviceDetailsHTML += `<div class="device-detail-item"><strong>Model:</strong> ${device.model}</div>`;
                        if (device.vendor) deviceDetailsHTML += `<div class="device-detail-item"><strong>Vendor:</strong> ${device.vendor}</div>`;
                        if (device.serial) deviceDetailsHTML += `<div class="device-detail-item"><strong>Serial:</strong> ${device.serial}</div>`;
                        
                        // Add any other properties
                        Object.keys(device).forEach(key => {
                            if (!['name', 'driver', 'port', 'model', 'vendor', 'serial', 'raw_config', 'formattedConfig', 'desc'].includes(key) && device[key]) {
                                deviceDetailsHTML += `<div class="device-detail-item"><strong>${key}:</strong> ${device[key]}</div>`;
                            }
                        });
                        
                        deviceDetailsHTML += '</div>';
                        
                        // Show raw config if available
                        if (device.raw_config) {
                            deviceDetailsHTML += '<div class="device-details-header mt-3">Raw Configuration:</div>';
                            deviceDetailsHTML += `<pre class="raw-config">${device.raw_config}</pre>`;
                        }
                        
                        // Add or update device details element
                        let deviceDetails = document.getElementById(`device-details-${mode}`);
                        if (!deviceDetails) {
                            deviceDetails = document.createElement('div');
                            deviceDetails.id = `device-details-${mode}`;
                            deviceDetails.className = 'device-details';
                            scanResults.after(deviceDetails);
                        }
                        deviceDetails.innerHTML = deviceDetailsHTML;
                        deviceDetails.classList.remove('hidden');
                        
                        // Show server configuration section
                        const serverConfigSection = document.getElementById(`server-config-${mode}`);
                        if (serverConfigSection) {
                            serverConfigSection.classList.remove('hidden');
                        }
                        
                        // If this is the only device detected, auto-select it
                        if (data.devices.length === 1) {
                            // No need to show further UI - auto-populate the form
                            showAlert('Automatically selected detected UPS device', 'success');
                        }
                    });
                    
                    scanResults.appendChild(deviceElement);
                });
                
                // If only one device found, trigger auto-selection
                if (data.devices.length === 1) {
                    scanResults.querySelector('.scan-device').click();
                }
            } else {
                scanResults.innerHTML = '<div class="no-devices-found">No UPS devices detected. Try connecting your UPS and scan again.</div>';
            }
        })
        .catch(error => {
            console.error('Error:', error);
            scanResults.innerHTML = `<div class="no-devices-found">Error scanning for UPS devices: ${error.message}</div>`;
        });
    }
    
    // Add click events to mode options
    modeOptions.forEach(option => {
        option.addEventListener('click', function() {
            const radio = this.querySelector('input[type="radio"]');
            radio.checked = true;
            
            // Update UI for selected mode
            modeOptions.forEach(m => m.classList.remove('selected'));
            this.classList.add('selected');
            
            selectedMode = this.dataset.mode;
        });
    });
    
    /**
     * Add click events to config tabs
     */
    configTabs.forEach(tab => {
        tab.addEventListener('click', function() {
            // Update active tab
            configTabs.forEach(t => t.classList.remove('active'));
            this.classList.add('active');
            
            // Show selected config file
            const filename = this.dataset.file;
            currentFile = filename;
            
            if (configFiles[filename]) {
                if (editor && editor.isActive) {
                    // If editor is active, update it with the file content
                    editor.setValue(editedFiles[filename] || configFiles[filename]);
                } else {
                    // Otherwise update the preview
                    configPreview.textContent = editedFiles[filename] || configFiles[filename];
                }
            }
        });
    });
    
    // Handle "Restart Server" button click in the completion step
    const restartServerBtn = document.getElementById('restart-server-btn');
    if (restartServerBtn) {
        restartServerBtn.addEventListener('click', restartServer);
    }
    
    /**
     * Reset the wizard to the first step
     */
    function resetWizard() {
        // Reset step
        goToStep(firstStep);
        
        // Reset mode selection
        selectedMode = null;
        modeOptions.forEach(m => {
            m.classList.remove('selected');
            const radio = m.querySelector('input[type="radio"]');
            radio.checked = false;
        });
        
        // Clear form inputs
        const formInputs = document.querySelectorAll('input, select');
        formInputs.forEach(input => {
            if (input.type === 'radio' || input.type === 'checkbox') {
                input.checked = false;
            } else if (input.tagName === 'SELECT') {
                input.selectedIndex = 0;
            } else {
                // Preserve default values
                if (input.name === 'ups_name' || input.name === 'server_ups_name' || input.name === 'remote_ups_name') {
                    input.value = 'ups';
                } else if (input.name === 'ups_port' || input.name === 'server_ups_port') {
                    input.value = 'auto';
                } else if (input.name === 'listen_address') {
                    input.value = '0.0.0.0';
                } else if (input.name === 'listen_port' || input.name === 'remote_port') {
                    input.value = '3493';
                } else if (input.name === 'admin_user') {
                    input.value = 'admin';
                } else if (input.name === 'remote_user') {
                    input.value = 'monuser';
                } else if (input.name === 'ups_desc') {
                    input.value = 'Local UPS';
                } else if (input.name === 'server_ups_desc') {
                    input.value = 'Network UPS';
                } else if (input.type === 'password') {
                    input.value = '';
                }
            }
        });
        
        // Clear alerts
        clearAlerts();
        
        // Clear configuration preview
        configPreview.textContent = '';
        configFiles = {};
        editedFiles = {};
    }
    
    /**
     * Go to the previous step
     */
    function goToPreviousStep() {
        // Special handling for step 5 (after successful save)
        if (currentStep === 5) {
            // Ask for confirmation before going back
            if (confirm("Are you sure you want to go back? This will delete the configuration files you just created.")) {
                // Delete configuration files
                fetch('/nut_config/api/delete-config', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    }
                })
                .then(response => response.json())
                .then(data => {
                    console.log('Configuration deletion result:', data);
                    // Go back after files are deleted
                    if (currentStep > firstStep) {
                        goToStep(currentStep - 1);
                    }
                })
                .catch(error => {
                    console.error('Error deleting configuration:', error);
                    // Still go back even if deletion fails
                    if (currentStep > firstStep) {
                        goToStep(currentStep - 1);
                    }
                });
            }
        } else {
            // Normal back button behavior for other steps
            if (currentStep > firstStep) {
                goToStep(currentStep - 1);
            }
        }
    }
    
    /**
     * Reset configuration method selection
     */
    function resetConfigMethodSelection() {
        // Get all configuration method radio buttons
        const configMethodRadios = document.querySelectorAll('input[name^="config-method-"]');
        
        // Uncheck all radio buttons
        configMethodRadios.forEach(radio => {
            radio.checked = false;
        });
        
        // Remove 'selected' class from all option containers
        const configMethodOptions = document.querySelectorAll('.config-method-option');
        configMethodOptions.forEach(option => {
            option.classList.remove('selected');
        });
        
        // Hide all configuration method sections
        const configMethodSections = document.querySelectorAll('.config-method-section');
        configMethodSections.forEach(section => {
            section.classList.add('hidden');
        });
        
        // Hide scan results and device details if they exist
        const scanResults = document.querySelectorAll('[id^="scan-results-"]');
        scanResults.forEach(result => {
            if (result) result.classList.add('hidden');
        });
        
        const deviceDetails = document.querySelectorAll('[id^="device-details-"]');
        deviceDetails.forEach(detail => {
            if (detail) detail.classList.add('hidden');
        });
    }
    
    /**
     * Get the current wizard step number
     * @returns {number} - Current step number (1-based)
     */
    function getCurrentStep() {
        // Find which step content is visible (not hidden)
        const visibleStepContent = document.querySelector('.wizard-step-content:not(.hidden)');
        if (visibleStepContent) {
            // Extract step number from the element ID (step-1, step-2, etc.)
            const stepMatch = visibleStepContent.id.match(/step-(\d+)/);
            if (stepMatch && stepMatch[1]) {
                return parseInt(stepMatch[1], 10);
            }
        }
        return currentStep; // Fallback to the currentStep variable
    }
    
    /**
     * Update the step indicators to show the current step
     * @param {number} step - The step number to set as active
     */
    function updateStepIndicators(step) {
        // Update the steps indicators
        steps.forEach((stepEl, index) => {
            // Remove all classes first
            stepEl.classList.remove('active', 'completed');
            
            // Add appropriate class based on step number
            if (index + 1 < step) {
                stepEl.classList.add('completed'); // Previous steps are completed
            } else if (index + 1 === step) {
                stepEl.classList.add('active'); // Current step is active
            }
            // Future steps have no special class
        });
        
        // Update the step content visibility
        stepContents.forEach((content, index) => {
            if (index + 1 === step) {
                content.classList.remove('hidden');
            } else {
                content.classList.add('hidden');
            }
        });
        
        // Update current step variable
        currentStep = step;
    }
    
    /**
     * Update buttons visibility based on current step
     * @param {number} step - The current step number
     */
    function updateButtons(step) {
        if (step === firstStep) {
            // First step (Admin Setup): hide previous button, show next button aligned right
            prevBtn.classList.add('hidden');
            nextBtn.classList.remove('hidden');
            saveBtn.classList.add('hidden');
        } else if (step === 4) {
            // Review step: show previous button, hide next button
            prevBtn.classList.remove('hidden');
            nextBtn.classList.add('hidden');
            // Save button visibility is controlled by the test result
        } else if (step === 5) {
            // Final step: hide next button
            prevBtn.classList.remove('hidden');
            nextBtn.classList.add('hidden');
            saveBtn.classList.add('hidden');
        } else {
            // Other steps (2, 3): show prev and next buttons
            prevBtn.classList.remove('hidden');
            nextBtn.classList.remove('hidden');
            saveBtn.classList.add('hidden');
        }
    }
    
    /**
     * Apply the configuration and move to the final step
     */
    function applyConfiguration() {
        // Move to step 5 (completion)
        updateStepIndicators(5);
        updateButtons(5);
        
        // Show success message
        showAlert('Configuration is ready to be saved.', 'success');
    }
    
    /**
     * Advance to the next step
     */
    function goToNextStep() {
        // Clear previous alerts
        clearAlerts();

        // Validate current step
        if (currentStep === 1) {
            if (authDisabled) {
                goToStep(currentStep + 1);
                return;
            }

            // Validate Admin Setup fields
            const adminUsername = document.getElementById('admin_username').value.trim();
            const adminPassword = document.getElementById('admin_password').value.trim();
            const adminPasswordConfirm = document.getElementById('admin_password_confirm').value.trim();
            
            if (!adminUsername) {
                showAlert('Please enter an admin username.', 'error');
                return;
            }
            
            if (adminUsername.length < 3) {
                showAlert('Admin username must be at least 3 characters long.', 'error');
                return;
            }
            
            if (!adminPassword) {
                showAlert('Please enter an admin password.', 'error');
                return;
            }
            
            if (adminPassword.length < 6) {
                showAlert('Admin password must be at least 6 characters long.', 'error');
                return;
            }
            
            if (adminPassword !== adminPasswordConfirm) {
                showAlert('Passwords do not match. Please check your password confirmation.', 'error');
                return;
            }
            
            // Save admin credentials for later use
            configData = configData || {};
            configData.admin_username = adminUsername;
            configData.admin_password = adminPassword;
            
        } else if (currentStep === 2) {
            // Check if a mode is selected
            if (!selectedMode) {
                showAlert('Please select an operating mode before continuing.', 'error');
                return;
            }

            // Clear the configuration method selection when changing modes
            resetConfigMethodSelection();

            // Hide all mode configurations
            document.querySelectorAll('.mode-config').forEach(el => el.classList.add('hidden'));
            
            // Show configuration for selected mode
            document.getElementById(`config-${selectedMode}`).classList.remove('hidden');
            
            // Update step title
            const stepTitle = document.getElementById('step-title');
            
            if (stepTitle) {
                stepTitle.textContent = `Step ${currentStep + 1}: ${selectedMode.charAt(0).toUpperCase() + selectedMode.slice(1)} Configuration`;
            }
            
        } else if (currentStep === 3) {
            // Validate configuration fields
            
            // For all modes, the UPS name is required
            if (selectedMode === 'standalone') {
                const upsName = document.getElementById('ups_name').value.trim();
                
                if (!upsName) {
                    showAlert('Please enter a UPS name.', 'error');
                    return;
                }
                
                // Check if a configuration method is selected
                const manualRadio = document.getElementById('manual-standalone');
                const autoRadio = document.getElementById('auto-standalone');
                
                if (!manualRadio.checked && !autoRadio.checked) {
                    showAlert('Please select a configuration method (Manual or Auto-detect).', 'error');
                    return;
                }
                
                // If manual, validate driver and port
                if (manualRadio.checked) {
                    const upsDriver = document.getElementById('ups_driver').value;
                    const upsPort = document.getElementById('ups_port').value.trim();
                    
                    if (!upsDriver) {
                        showAlert('Please select a UPS driver.', 'error');
                        return;
                    }
                    
                    if (!upsPort) {
                        showAlert('Please enter a port for the UPS connection.', 'error');
                        return;
                    }
                }
                
                // If auto, check if a device has been selected
                if (autoRadio.checked) {
                    const scanResults = document.getElementById('scan-results-standalone');
                    if (!scanResults || !scanResults.querySelector('.scan-device.selected')) {
                        showAlert('Please select a detected UPS device, or switch to manual configuration.', 'error');
                        return;
                    }
                    
                    // Validate server address for auto mode
                    const serverAddress = document.getElementById('auto_server_address').value.trim();
                    if (!serverAddress) {
                        showAlert('Please enter a server address.', 'error');
                        return;
                    }
                }
                
            } else if (selectedMode === 'netserver') {
                const upsName = document.getElementById('server_ups_name').value.trim();
                
                if (!upsName) {
                    showAlert('Please enter a UPS name.', 'error');
                    return;
                }
                
                // Check if a configuration method is selected
                const manualRadio = document.getElementById('manual-netserver');
                const autoRadio = document.getElementById('auto-netserver');
                
                if (!manualRadio.checked && !autoRadio.checked) {
                    showAlert('Please select a configuration method (Manual or Auto-detect).', 'error');
                    return;
                }
                
                // If manual, validate driver, port, and admin credentials
                if (manualRadio.checked) {
                    const upsDriver = document.getElementById('server_ups_driver').value;
                    const upsPort = document.getElementById('server_ups_port').value.trim();
                    const adminUser = document.getElementById('admin_user').value.trim();
                    const adminPassword = document.getElementById('admin_password').value.trim();
                    
                    if (!upsDriver) {
                        showAlert('Please select a UPS driver.', 'error');
                        return;
                    }
                    
                    if (!upsPort) {
                        showAlert('Please enter a port for the UPS connection.', 'error');
                        return;
                    }
                    
                    if (!adminUser) {
                        showAlert('Please enter an admin username.', 'error');
                        return;
                    }
                    
                    if (!adminPassword) {
                        showAlert('Please enter an admin password.', 'error');
                        return;
                    }
                }
                
                // If auto, check if a device has been selected and validate admin credentials
                if (autoRadio.checked) {
                    const scanResults = document.getElementById('scan-results-netserver');
                    if (!scanResults || !scanResults.querySelector('.scan-device.selected')) {
                        showAlert('Please select a detected UPS device, or switch to manual configuration.', 'error');
                        return;
                    }
                    
                    // Validate server address and admin credentials for auto mode
                    const serverAddress = document.getElementById('auto_server_address_ns').value.trim();
                    const listenAddress = document.getElementById('auto_listen_address').value.trim();
                    const adminUser = document.getElementById('auto_admin_user').value.trim();
                    const adminPassword = document.getElementById('auto_admin_password').value.trim();
                    
                    if (!serverAddress) {
                        showAlert('Please enter a server address.', 'error');
                        return;
                    }
                    
                    if (!listenAddress) {
                        showAlert('Please enter a listen address.', 'error');
                        return;
                    }
                    
                    if (!adminUser) {
                        showAlert('Please enter an admin username.', 'error');
                        return;
                    }
                    
                    if (!adminPassword) {
                        showAlert('Please enter an admin password.', 'error');
                        return;
                    }
                }
                
            } else if (selectedMode === 'netclient') {
                const remoteUpsName = document.getElementById('remote_ups_name').value.trim();
                const remoteHost = document.getElementById('remote_host').value.trim();
                const remoteUser = document.getElementById('remote_user').value.trim();
                
                if (!remoteUpsName) {
                    showAlert('Please enter the remote UPS name.', 'error');
                    return;
                }
                
                if (!remoteHost) {
                    showAlert('Please enter the remote server address.', 'error');
                    return;
                }
                
                if (!remoteUser) {
                    showAlert('Please enter the remote username.', 'error');
                    return;
                }
            }
            
            // Generate config preview before going to step 4
            generateConfigPreview();
            
        } else if (currentStep === 4) {
            // No validation needed for step 4, just show the appropriate content for step 5
            // This is handled by showing/hiding success/error messages in the saveConfiguration function
            // But we don't want to advance to step 5 yet, so return here.
            
            // Show the save button and hide the next button
            nextBtn.classList.add('hidden');
            saveBtn.classList.remove('hidden');
            return;
        }
        
        // Advance to the next step
        goToStep(currentStep + 1);
    }
    
    /**
     * Go to a specific step
     */
    function goToStep(step) {
        if (step < firstStep) {
            step = firstStep;
        }

        // Store the current step before updating
        const previousStep = currentStep;
        
        // Update current step
        currentStep = step;
        
        // Reset configuration method selection when entering step 3 from any other step
        if (currentStep === 3 && previousStep !== 3) {
            resetConfigMethodSelection();
        }
        
        // Update step indicators
        updateStepIndicators(currentStep);
        
        // Update buttons
        updateButtons(currentStep);
        
        // Update page scroll
        window.scrollTo(0, 0);
    }
    
    /**
     * Show an alert message
     */
    function showAlert(message, type = 'info') {
        // Clear existing alerts
        clearAlerts();
        
        // Create alert element
        const alert = document.createElement('div');
        alert.className = `alert alert-${type}`;
        alert.textContent = message;
        
        // Add close button
        const closeBtn = document.createElement('button');
        closeBtn.innerHTML = '&times;';
        closeBtn.className = 'close-alert';
        closeBtn.addEventListener('click', function() {
            alertsContainer.removeChild(alert);
        });
        
        alert.appendChild(closeBtn);
        alertsContainer.appendChild(alert);
    }
    
    /**
     * Clear all alerts
     */
    function clearAlerts() {
        alertsContainer.innerHTML = '';
    }
    
    /**
     * Open the modal
     */
    function openModal(isSuccess, message, output) {
        testMessage.textContent = message;
        
        // Reset the missing realpower form
        missingRealpowerForm.classList.add('hidden');
        realpowerInput.value = '';
        
        // Check if output contains HTML
        if (output && output.startsWith('<div')) {
            // If it's formatted HTML, use innerHTML
            upscOutput.innerHTML = output;
        } else {
            // Otherwise use textContent for plain text
            upscOutput.textContent = output || '';
        }
        
        // If test was successful, check for ups.realpower.nominal
        if (isSuccess && output && output !== "Connection successful") {
            const hasRealpowerNominal = output.includes('ups.realpower.nominal');
            
            if (!hasRealpowerNominal) {
                // Show the form to input the missing variable
                missingRealpowerForm.classList.remove('hidden');
                
                // Add event listener to the close button to save the value
                closeModalBtn.onclick = function() {
                    upsRealpowerNominal = realpowerInput.value;
                    closeModal();
                };
            } else {
                // Normal close behavior
                closeModalBtn.onclick = closeModal;
            }
        } else {
            // Normal close behavior for non-success or empty output
            closeModalBtn.onclick = closeModal;
        }
        
        if (isSuccess) {
            testMessage.className = 'alert alert-success';
        } else {
            testMessage.className = 'alert alert-error';
        }
        
        modal.style.display = 'block';
    }
    
    /**
     * Close the modal
     */
    function closeModal() {
        modal.style.display = 'none';
    }
    
    /**
     * Initialize the Code Mirror editor
     */
    function initializeEditor() {
        if (!editor) {
            const editorTextarea = document.getElementById('config-editor');
            if (editorTextarea) {
                editor = CodeMirror.fromTextArea(editorTextarea, {
                    lineNumbers: true,
                    mode: 'shell',
                    theme: 'monokai',
                    lineWrapping: true,
                    indentUnit: 4,
                    smartIndent: true,
                    tabSize: 4
                });
                
                editor.setSize('100%', '400px');
                editor.isActive = false;
                
                // Mark file as modified when content changes
                editor.on('change', function() {
                    const activeTab = document.querySelector('.config-tab.active');
                    if (activeTab && !activeTab.classList.contains('modified-tab')) {
                        activeTab.classList.add('modified-tab');
                    }
                });
            }
        }
    }
    
    /**
     * Check if the editor has unsaved changes
     * @returns {boolean} - True if there are unsaved changes
     */
    function hasEditorChanges() {
        if (!editor || !currentFile) return false;
        
        // Get current content from editor
        const currentContent = editor.getValue();
        
        // Get original content (or last saved content)
        const originalContent = editedFiles[currentFile] || configFiles[currentFile] || '';
        
        // Compare current content with original
        return currentContent !== originalContent;
    }
    
    /**
     * Toggle between preview and editor mode
     */
    function toggleEditor() {
        // Initialize editor if not already done
        initializeEditor();
        
        if (editor.isActive) {
            // Check for unsaved changes before switching to preview mode
            if (hasEditorChanges()) {
                // Show confirmation dialog
                if (!confirm('You have unsaved changes. Are you sure you want to close the editor without saving?')) {
                    return; // User cancelled, stay in editor mode
                }
            }
            
            // Switch to preview mode
            configEditorContainer.classList.add('hidden');
            configPreviewElement.classList.remove('hidden');
            editorActions.classList.add('hidden');
            editConfigBtn.innerHTML = '<i class="fas fa-edit"></i> Edit';
            editor.isActive = false;
            
            // Show the test configuration button when in preview mode
            if (testConfigBtn) {
                testConfigBtn.classList.remove('hidden');
            }
        } else {
            // Switch to editor mode
            configPreviewElement.classList.add('hidden');
            configEditorContainer.classList.remove('hidden');
            editorActions.classList.remove('hidden');
            editConfigBtn.innerHTML = '<i class="fas fa-eye"></i> Preview';
            editor.isActive = true;
            
            // Hide the test configuration button when in editor mode
            if (testConfigBtn) {
                testConfigBtn.classList.add('hidden');
            }
            
            // Set content of current file
            if (currentFile && configFiles[currentFile]) {
                editor.setValue(editedFiles[currentFile] || configFiles[currentFile]);
                editor.refresh();
            }
        }
    }
    
    /**
     * Save changes made in the editor
     */
    function saveEditorChanges() {
        if (!editor || !currentFile) return;
        
        // Get content from editor
        const content = editor.getValue();
        
        // Check if content has changed
        if (content === configFiles[currentFile]) {
            // Content is the same as original
            if (editedFiles[currentFile]) {
                delete editedFiles[currentFile];
                
                // Remove modified marker from tab
                const tab = document.querySelector(`.config-tab[data-file="${currentFile}"]`);
                if (tab) {
                    tab.classList.remove('modified-tab');
                }
            }
        } else {
            // Save edited content
            editedFiles[currentFile] = content;
        }
        
        // Switch back to preview mode
        configEditorContainer.classList.add('hidden');
        configPreviewElement.classList.remove('hidden');
        editorActions.classList.add('hidden');
        editConfigBtn.innerHTML = '<i class="fas fa-edit"></i> Edit';
        editor.isActive = false;
        
        // Show the test configuration button after saving changes
        if (testConfigBtn) {
            testConfigBtn.classList.remove('hidden');
        }
        
        // Update preview with edited content
        configPreview.textContent = editedFiles[currentFile] || configFiles[currentFile];
        
        showAlert(`Changes to ${currentFile} saved`, 'success');
    }
    
    /**
     * Cancel editing and revert to original content
     */
    function cancelEditorChanges() {
        if (!editor || !currentFile) return;
        
        // Revert to original content or last saved edit
        editor.setValue(editedFiles[currentFile] || configFiles[currentFile]);
        
        // Switch back to preview mode
        configEditorContainer.classList.add('hidden');
        configPreviewElement.classList.remove('hidden');
        editorActions.classList.add('hidden');
        editConfigBtn.innerHTML = '<i class="fas fa-edit"></i> Edit';
        editor.isActive = false;
        
        // Show the test configuration button after cancelling edit
        if (testConfigBtn) {
            testConfigBtn.classList.remove('hidden');
        }
        
        showAlert('Edit cancelled', 'info');
    }
    
    /**
     * Generate configuration preview
     */
    function generateConfigPreview() {
        // Build configuration data based on selected mode
        configData = {
            mode: selectedMode
        };
        
        if (selectedMode === 'standalone') {
            // Check if auto-detect is selected
            const autoRadio = document.getElementById('auto-standalone');
            const isAutoMode = autoRadio && autoRadio.checked;
            
            // Get UPS configuration details
            configData.ups_name = document.getElementById('ups_name').value.trim();
            configData.ups_driver = document.getElementById('ups_driver').value;
            configData.ups_port = document.getElementById('ups_port').value.trim();
            configData.ups_desc = document.getElementById('ups_desc').value.trim();
            
            // Get server configuration based on mode (auto or manual)
            if (isAutoMode) {
                configData.server_address = document.getElementById('auto_server_address').value.trim() || '127.0.0.1';
            } else {
                configData.server_address = document.getElementById('server_address').value.trim() || '127.0.0.1';
            }
            
            // Add monitor user credentials
            configData.monitor_username = 'monuser';
            configData.monitor_password = 'monpass';
            
            // Add admin user credentials
            configData.admin_username = 'admin';
            configData.admin_password = 'adminpass';
            
            // Check for auto-detect selection and raw config
            if (isAutoMode) {
                const scanResults = document.getElementById('scan-results-standalone');
                if (scanResults) {
                    const selectedDevice = scanResults.querySelector('.scan-device.selected');
                    if (selectedDevice) {
                        // Get the device index from the DOM element
                        const index = Array.from(scanResults.querySelectorAll('.scan-device')).indexOf(selectedDevice);
                        const deviceElements = scanResults.querySelectorAll('.scan-device');
                        
                        // If we have a selected device with raw_config, use it
                        if (index >= 0 && deviceElements[index].__device && deviceElements[index].__device.raw_config) {
                            configData.raw_ups_config = deviceElements[index].__device.raw_config;
                        }
                    }
                }
            }
            
        } else if (selectedMode === 'netserver') {
            // Check if auto-detect is selected
            const autoRadio = document.getElementById('auto-netserver');
            const isAutoMode = autoRadio && autoRadio.checked;
            
            // Get UPS configuration details
            configData.ups_name = document.getElementById('server_ups_name').value.trim();
            configData.ups_driver = document.getElementById('server_ups_driver').value;
            configData.ups_port = document.getElementById('server_ups_port').value.trim();
            configData.ups_desc = document.getElementById('server_ups_desc').value.trim();
            
            // Get server configuration based on mode (auto or manual)
            if (isAutoMode) {
                configData.server_address = document.getElementById('auto_server_address_ns').value.trim() || '127.0.0.1';
                configData.listen_address = document.getElementById('auto_listen_address').value.trim() || '0.0.0.0';
                configData.listen_port = document.getElementById('auto_listen_port').value.trim() || '3493';
                configData.admin_user = document.getElementById('auto_admin_user').value.trim();
                configData.admin_password = document.getElementById('auto_admin_password').value.trim();
            } else {
                configData.server_address = document.getElementById('server_address_ns').value.trim() || '127.0.0.1';
                configData.listen_address = document.getElementById('listen_address').value.trim() || '0.0.0.0';
                configData.listen_port = document.getElementById('listen_port').value.trim() || '3493';
                configData.admin_user = document.getElementById('admin_user').value.trim();
                configData.admin_password = document.getElementById('admin_password').value.trim();
            }
            
            // Add monitor user credentials
            configData.monitor_username = 'monuser';
            configData.monitor_password = 'monpass';
            
            // Check for auto-detect selection and raw config
            if (isAutoMode) {
                const scanResults = document.getElementById('scan-results-netserver');
                if (scanResults) {
                    const selectedDevice = scanResults.querySelector('.scan-device.selected');
                    if (selectedDevice) {
                        // Get the device index from the DOM element
                        const index = Array.from(scanResults.querySelectorAll('.scan-device')).indexOf(selectedDevice);
                        const deviceElements = scanResults.querySelectorAll('.scan-device');
                        
                        // If we have a selected device with raw_config, use it
                        if (index >= 0 && deviceElements[index].__device && deviceElements[index].__device.raw_config) {
                            configData.raw_ups_config = deviceElements[index].__device.raw_config;
                        }
                    }
                }
            }
            
        } else if (selectedMode === 'netclient') {
            configData.remote_ups_name = document.getElementById('remote_ups_name').value.trim();
            configData.remote_host = document.getElementById('remote_host').value.trim();
            configData.remote_port = document.getElementById('remote_port').value.trim();
            configData.remote_user = document.getElementById('remote_user').value.trim();
            configData.remote_password = document.getElementById('remote_password').value.trim();
        }
        
        // Send data to server to generate configuration
        fetch('/nut_config/api/setup/generate-preview', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(configData)
        })
        .then(response => response.json())
        .then(data => {
            if (data.status === 'success') {
                // Save any existing edits to upsmon.conf before resetting
                const upsmonEdits = editedFiles['upsmon.conf'];
                
                configFiles = data.config_files;
                editedFiles = {}; // Reset edited files when generating new configs
                
                // Restore upsmon.conf edits if they exist
                if (upsmonEdits) {
                    editedFiles['upsmon.conf'] = upsmonEdits;
                    
                    // Mark the upsmon.conf tab as modified if it exists
                    const upsmonTab = document.querySelector('.config-tab[data-file="upsmon.conf"]');
                    if (upsmonTab) {
                        upsmonTab.classList.add('modified-tab');
                    }
                    
                    // Notify the user that their edits were preserved
                    showAlert('Your edits to upsmon.conf have been preserved.', 'info');
                }
                
                // Display configuration summary
                const summary = document.querySelector('.config-summary');
                summary.innerHTML = '';
                
                // Add mode to summary
                const modeItem = document.createElement('div');
                modeItem.className = 'summary-item';
                modeItem.innerHTML = `
                    <div class="summary-label">Mode:</div>
                    <div class="summary-value">${getModeLabel(selectedMode)}</div>
                `;
                summary.appendChild(modeItem);
                
                // Add other configuration details based on mode
                if (selectedMode === 'standalone' || selectedMode === 'netserver') {
                    const isNetServer = selectedMode === 'netserver';
                    
                    // UPS details
                    summary.appendChild(createSummaryItem('UPS Name:', configData[`ups_name`]));
                    summary.appendChild(createSummaryItem('UPS Driver:', getDriverLabel(configData[`ups_driver`])));
                    summary.appendChild(createSummaryItem('Port/Device:', configData[`ups_port`]));
                    summary.appendChild(createSummaryItem('Server Address:', configData.server_address));
                    
                    if (isNetServer) {
                        // Network details
                        summary.appendChild(createSummaryItem('Listen Address:', configData.listen_address));
                        summary.appendChild(createSummaryItem('Listen Port:', configData.listen_port));
                        summary.appendChild(createSummaryItem('Admin User:', configData.admin_user));
                        summary.appendChild(createSummaryItem('Admin Password:', '********'));
                    }
                } else if (selectedMode === 'netclient') {
                    // Remote UPS details
                    summary.appendChild(createSummaryItem('Remote UPS Name:', configData.remote_ups_name));
                    summary.appendChild(createSummaryItem('Remote Server:', configData.remote_host));
                    summary.appendChild(createSummaryItem('Remote Port:', configData.remote_port));
                    summary.appendChild(createSummaryItem('Remote User:', configData.remote_user));
                    if (configData.remote_password) {
                        summary.appendChild(createSummaryItem('Remote Password:', '********'));
                    }
                }
                
                // Display the first config file by default
                configTabs[0].click();
                
                // Clear any modified markers
                configTabs.forEach(tab => {
                    tab.classList.remove('modified-tab');
                });
            } else {
                showAlert('Failed to generate configuration: ' + data.message, 'error');
            }
        })
        .catch(error => {
            console.error('Error:', error);
            showAlert('An error occurred while generating configuration preview.', 'error');
        });
    }
    
    /**
     * Create a summary item
     */
    function createSummaryItem(label, value) {
        const item = document.createElement('div');
        item.className = 'summary-item';
        item.innerHTML = `
            <div class="summary-label">${label}</div>
            <div class="summary-value">${value || 'N/A'}</div>
        `;
        return item;
    }
    
    /**
     * Get human-readable mode label
     */
    function getModeLabel(mode) {
        switch (mode) {
            case 'standalone': return 'Standalone (Local UPS only)';
            case 'netserver': return 'Network Server (Local UPS with remote access)';
            case 'netclient': return 'Network Client (Remote UPS monitoring)';
            default: return mode;
        }
    }
    
    /**
     * Get human-readable driver label
     */
    function getDriverLabel(driver) {
        switch (driver) {
            case 'usbhid-ups': return 'USB UPS (usbhid-ups)';
            case 'blazer_usb': return 'Blazer USB';
            case 'apcsmart': return 'APC Smart Protocol';
            case 'bcmxcp_usb': return 'Powerware USB';
            case 'richcomm_usb': return 'Richcomm USB';
            case 'tripplite_usb': return 'Tripp Lite USB';
            default: return driver;
        }
    }
    
    /**
     * Test the configuration
     */
    function testConfiguration() {
        // Update button state
        testConfigBtn.disabled = true;
        testConfigBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Testing...';
        
        // Clear previous test results
        const testResult = document.getElementById('test-result');
        testResult.classList.add('hidden');
        
        // Hide save button by default (until test passes)
        saveBtn.classList.add('hidden');
        
        // Send configuration to server for testing
        fetch('/nut_config/api/setup/test-configuration', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                nut_conf: editedFiles['nut.conf'] || configFiles['nut.conf'] || '',
                ups_conf: editedFiles['ups.conf'] || configFiles['ups.conf'] || '',
                upsd_conf: editedFiles['upsd.conf'] || configFiles['upsd.conf'] || '',
                upsd_users: editedFiles['upsd.users'] || configFiles['upsd.users'] || '',
                upsmon_conf: editedFiles['upsmon.conf'] || configFiles['upsmon.conf'] || '' // Any custom edits to upsmon.conf will be preserved
            })
        })
        .then(response => response.json())
        .then(data => {
            testConfigBtn.disabled = false;
            testConfigBtn.innerHTML = '<i class="fas fa-check-circle"></i> Test Configuration';
            
            // Show modal with results instead of inline results
            if (data.status === 'success') {
                let output = '';
                // Check for output in different possible response fields
                if (data.upsc_output) {
                    output = data.upsc_output;
                } else if (data.test_details) {
                    output = data.test_details;
                }
                
                // Format the UPS output for better readability
                if (output && output !== "Connection successful") {
                    // Split the output by lines and create a formatted display
                    const outputLines = output.split('\n');
                    const formattedOutput = outputLines.map(line => {
                        // If line contains a key-value pair (contains colon)
                        if (line.includes(':')) {
                            const [key, value] = line.split(':', 2);
                            return `<div class="ups-data-item"><strong>${key.trim()}:</strong> ${value.trim()}</div>`;
                        }
                        return line;
                    }).join('');
                    
                    output = `<div class="ups-data">${formattedOutput}</div>`;
                }
                
                // Show success in modal with formatted output
                openModal(true, 'Configuration test successful!', output);
                
                // Also update the inline result for reference
                testResult.classList.remove('hidden');
                testResult.innerHTML = `
                    <div class="alert alert-success">
                        <i class="fas fa-check-circle"></i> Configuration test successful!
                    </div>
                `;
                
                // Show save button only after successful test
                saveBtn.classList.remove('hidden');
            } else {
                let errorMessage = data.message || 'Unknown error';
                if (data.errors && data.errors.length > 0) {
                    errorMessage = data.errors.join('\n');
                }
                
                // Show error in modal
                openModal(false, 'Configuration test failed', errorMessage);
                
                // Also update the inline result for reference
                testResult.classList.remove('hidden');
                testResult.innerHTML = `
                    <div class="alert alert-error">
                        <i class="fas fa-times-circle"></i> Configuration test failed:<br>
                        ${errorMessage.replace(/\n/g, '<br>')}
                    </div>
                `;
                
                // Hide save button on test failure
                saveBtn.classList.add('hidden');
            }
        })
        .catch(error => {
            console.error('Error:', error);
            testConfigBtn.disabled = false;
            testConfigBtn.innerHTML = '<i class="fas fa-check-circle"></i> Test Configuration';
            
            // Show error in modal
            openModal(false, 'Error testing configuration', 'Network error occurred while testing.');
            
            // Also update the inline result for reference
            testResult.classList.remove('hidden');
            testResult.innerHTML = `
                <div class="alert alert-error">
                    <i class="fas fa-times-circle"></i> Error testing configuration: Network error
                </div>
            `;
            
            // Hide save button on error
            saveBtn.classList.add('hidden');
        });
    }
    
    /**
     * Restart the server
     */
    function restartServer() {
        restartServerBtn.disabled = true;
        
        // Create overlay
        const overlay = document.createElement('div');
        overlay.className = 'countdown-overlay';
        document.body.appendChild(overlay);
        
        // Create countdown container
        const countdownContainer = document.createElement('div');
        countdownContainer.className = 'countdown-container';
        countdownContainer.innerHTML = `
            <div class="countdown-circle-container">
                <svg class="countdown-circle" viewBox="0 0 36 36">
                    <path class="countdown-circle-bg"
                        d="M18 2.0845
                        a 15.9155 15.9155 0 0 1 0 31.831
                        a 15.9155 15.9155 0 0 1 0 -31.831"
                        fill="none" />
                    <path class="countdown-circle-progress"
                        d="M18 2.0845
                        a 15.9155 15.9155 0 0 1 0 31.831
                        a 15.9155 15.9155 0 0 1 0 -31.831"
                        fill="none"
                        stroke-dasharray="100, 100" />
                </svg>
                <div class="countdown-number">30</div>
            </div>
            <div class="countdown-text">Server restarting, please wait...</div>
        `;
        
        // Add countdown to body instead of replacing the button
        document.body.appendChild(countdownContainer);
        
        // Set countdown duration in seconds
        const totalSeconds = 30;
        let secondsLeft = totalSeconds;
        
        // Get countdown elements
        const countdownNumber = countdownContainer.querySelector('.countdown-number');
        const progressCircle = countdownContainer.querySelector('.countdown-circle-progress');
        
        // Setup countdown
        const circumference = 2 * Math.PI * 15.9155; // Circle path length
        progressCircle.style.strokeDasharray = `${circumference} ${circumference}`;
        progressCircle.style.strokeDashoffset = '0';
        
        // Update countdown every second
        const countdownInterval = setInterval(() => {
            secondsLeft--;
            
            // Update text
            countdownNumber.textContent = secondsLeft;
            
            // Update progress circle
            const progress = (secondsLeft / totalSeconds) * circumference;
            progressCircle.style.strokeDashoffset = circumference - progress;
            
            // When countdown reaches zero
            if (secondsLeft <= 0) {
                clearInterval(countdownInterval);
                window.location.href = '/';
            }
        }, 1000);
        
        // Show a message that the server is restarting
        showAlert('The server is restarting. Please wait...', 'info');
        
        // Send request to restart the server
        fetch('/nut_config/api/restart', {
            method: 'POST'
        })
        .then(response => response.json())
        .then(data => {
            if (!data.success) {
                // Only handle error case - success will continue the countdown
                clearInterval(countdownInterval);
                showAlert('Error restarting server: ' + data.message, 'error');
                
                // Remove countdown and overlay
                document.body.removeChild(countdownContainer);
                document.body.removeChild(overlay);
                
                // Re-enable the button
                restartServerBtn.disabled = false;
                restartServerBtn.innerHTML = '<i class="fas fa-sync"></i> Restart Server';
            }
        })
        .catch(error => {
            console.error('Error:', error);
            // The error might be because the server is already restarting
            // We'll continue the countdown in this case
        });
    }
    
    /**
     * Save the configuration
     */
    function saveConfiguration() {
        // Update button state
        saveBtn.disabled = true;
        saveBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Saving...';
        
        // Collect all configuration data
        let configurationData = {
            // Common configuration
            nut_mode: selectedMode,
            
            // File content for custom configurations
            nut_conf: editedFiles['nut.conf'] || configFiles['nut.conf'] || '',
            ups_conf: editedFiles['ups.conf'] || configFiles['ups.conf'] || '',
            upsd_conf: editedFiles['upsd.conf'] || configFiles['upsd.conf'] || '',
            upsd_users: editedFiles['upsd.users'] || configFiles['upsd.users'] || '',
            upsmon_conf: editedFiles['upsmon.conf'] || configFiles['upsmon.conf'] || '' // Any custom edits to upsmon.conf will be preserved
        };
        
        // Add ups.realpower.nominal if it was provided
        if (upsRealpowerNominal) {
            configurationData.ups_realpower_nominal = upsRealpowerNominal;
        }
        
        // Add admin credentials - collect directly from form fields
        const adminUsernameField = document.getElementById('admin_username');
        const adminPasswordField = document.getElementById('admin_password');
        
        if (adminUsernameField && adminPasswordField) {
            const adminUsername = adminUsernameField.value.trim();
            const adminPassword = adminPasswordField.value.trim();
            
            if (adminUsername && adminPassword) {
                configurationData.admin_username = adminUsername;
                configurationData.admin_password = adminPassword;
                console.log('Admin credentials added to configuration:', adminUsername);
            }
        }
        
        // Mode-specific configurations
        if (selectedMode === 'standalone') {
            configurationData = {
                ...configurationData,
                ups_name: document.getElementById('ups_name').value.trim(),
                ups_driver: document.getElementById('ups_driver').value,
                ups_port: document.getElementById('ups_port').value.trim(),
                ups_desc: document.getElementById('ups_desc').value.trim(),
                server_address: document.getElementById('server_address').value.trim() || '127.0.0.1',
                upsc_command: 'upsc',
                upscmd_command: 'upscmd'
            };
        } else if (selectedMode === 'netserver') {
            configurationData = {
                ...configurationData,
                ups_name: document.getElementById('server_ups_name').value.trim(),
                ups_driver: document.getElementById('server_ups_driver').value,
                ups_port: document.getElementById('server_ups_port').value.trim(),
                ups_desc: document.getElementById('server_ups_desc').value.trim(),
                server_address: document.getElementById('server_address_ns').value.trim() || '127.0.0.1',
                listen_address: document.getElementById('listen_address').value.trim() || '0.0.0.0',
                listen_port: document.getElementById('listen_port').value.trim() || '3493',
                admin_user: document.getElementById('admin_user').value.trim(),
                admin_password: document.getElementById('admin_password').value.trim(),
                upsc_command: 'upsc',
                upscmd_command: 'upscmd',
                upscmd_user: document.getElementById('admin_user').value.trim(),
                upscmd_password: document.getElementById('admin_password').value.trim()
            };
        } else if (selectedMode === 'netclient') {
            configurationData = {
                ...configurationData,
                remote_ups_name: document.getElementById('remote_ups_name').value.trim(),
                remote_host: document.getElementById('remote_host').value.trim(),
                ups_name: document.getElementById('remote_ups_name').value.trim(),
                ups_host: document.getElementById('remote_host').value.trim(), 
                remote_port: document.getElementById('remote_port').value.trim() || '3493',
                remote_user: document.getElementById('remote_user').value.trim(),
                remote_password: document.getElementById('remote_password').value.trim(),
                upsc_command: 'upsc',
                upscmd_command: 'upscmd',
                upscmd_user: document.getElementById('remote_user').value.trim(),
                upscmd_password: document.getElementById('remote_password').value.trim()
            };
        }
        
        // Send data to server
        fetch('/nut_config/api/setup/save-config', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(configurationData)
        })
        .then(response => response.json())
        .then(data => {
            saveBtn.disabled = false;
            saveBtn.innerHTML = '<i class="fas fa-save"></i> Save Configuration';
            
            if (data.status === 'success') {
                // Success
                showAlert('Configuration saved successfully!', 'success');
                
                // Move to completion step and show success message
                goToStep(5);
                
                // Show success message in step 5
                document.getElementById('complete-success').classList.remove('hidden');
                document.getElementById('complete-error').classList.add('hidden');
                
                // If a redirect URL is provided, navigate there
                if (data.redirect) {
                    window.location.href = data.redirect;
                }
            } else {
                // Error
                showAlert('Error saving configuration: ' + data.message, 'error');
                
                // Move to completion step but show error message
                goToStep(5);
                document.getElementById('complete-error').classList.remove('hidden');
                document.getElementById('complete-success').classList.add('hidden');
                document.getElementById('error-message').textContent = data.message;
            }
        })
        .catch(error => {
            console.error('Error:', error);
            saveBtn.disabled = false;
            saveBtn.innerHTML = '<i class="fas fa-save"></i> Save Configuration';
            showAlert('Network error while saving configuration.', 'error');
        });
    }
}); 
