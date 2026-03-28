#!/bin/bash

# Settings generation functions
# This file contains functions for generating settings files

# Source common variables
SCRIPT_DIR="/usr/local/bin"
. "$SCRIPT_DIR/common.sh"

# Function to generate settings.txt file
generate_settings() {
    # Create settings.txt file
    startup_log "Creating settings.txt file"
    cat > "$SETTINGS_FILE" << EOF


# Server Configuration
DEBUG_MODE = development
SERVER_PORT = ${SERVER_PORT:-5050}
SERVER_HOST = ${SERVER_HOST:-0.0.0.0}

# Database Configuration
DB_NAME = nutify.db.sqlite
INSTANCE_PATH = instance

# Log level: DEBUG, INFO, WARNING, ERROR, CRITICAL
LOG_LEVEL = ${LOG_LEVEL}

# Werkzeug log control: true or false
LOG_WERKZEUG = ${LOG_WERKZEUG}

# General logging enabled: true or false
LOG = ${LOG}

# SSL Configuration
SSL_ENABLED = ${SSL_ENABLED:-false}
EOF

    # Check if the settings file was created successfully
    if [ ! -f "$SETTINGS_FILE" ]; then
        startup_log "CRITICAL ERROR: Failed to create settings file"
        return 1
    fi

    startup_log "Settings file created successfully: $SETTINGS_FILE"
    return 0
}

# Function to generate configuration files
generate_config_file() {
    local file_path="$1"
    local content="$2"
    local description="$3"
    
    startup_log "Generating $description: $file_path"
    
    echo "$content" > "$file_path"
    
    if [ $? -ne 0 ] || [ ! -f "$file_path" ]; then
        startup_log "ERROR: Failed to create $description: $file_path"
        return 1
    fi
    
    return 0
} 