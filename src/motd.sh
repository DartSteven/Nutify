#!/bin/bash

# MOTD and summary display functions
# This file contains functions for displaying welcome messages and status summaries

# Source common variables
SCRIPT_DIR="/usr/local/bin"
. "$SCRIPT_DIR/common.sh"

# Function to show the MOTD (always displayed)
show_motd() {
    # Simple and direct method to display the MOTD
    # Avoids file descriptor issues in container environment
    
    # Read version from file
    if [ -f "$APP_DIR/version.txt" ]; then
        VERSION=$(grep "VERSION =" "$APP_DIR/version.txt" | cut -d "=" -f2 | tr -d ' ')
        LAST_UPDATE=$(grep "LAST_UPDATE =" "$APP_DIR/version.txt" | cut -d "=" -f2 | tr -d ' ')
    else
        VERSION="Unknown"
        LAST_UPDATE="Unknown"
    fi

    # ASCII Art MOTD - Always display this regardless of log settings
    cat << EOF

  _   _ _   _ _____ ___ _______   __
 | \\ | | | | |_   _|_ _|  ___\\ \\ / /
 |  \\| | | | | | |  | || |_   \\ V / 
 | |\\  | |_| | | |  | ||  _|   | |  
 |_| \\_|\\___/  |_| |___|_|     |_|  

  Network UPS Tools Interface v${VERSION}
  Last Update: ${LAST_UPDATE}
  https://github.com/DartSteven/nutify


EOF
}

# Function to set system timezone based on TIMEZONE environment variable
set_system_timezone() {
    # Check if TIMEZONE is set and not empty
    if [ -n "$TIMEZONE" ]; then
        startup_log "🕒 Setting system timezone to: $TIMEZONE"
        
        # Check if the timezone is valid
        if [ -f "/usr/share/zoneinfo/$TIMEZONE" ]; then
            # Set timezone in /etc/timezone
            echo "$TIMEZONE" > /etc/timezone
            
            # Update /etc/localtime
            ln -sf "/usr/share/zoneinfo/$TIMEZONE" /etc/localtime
            
            # Apply timezone change
            if command -v dpkg-reconfigure > /dev/null 2>&1; then
                dpkg-reconfigure -f noninteractive tzdata > /dev/null 2>&1
            fi
            
            startup_log "System timezone set to $TIMEZONE"
        else
            startup_log "WARNING: Invalid timezone '$TIMEZONE'. Using system default."
        fi
    else
        startup_log "No timezone specified. Using system default."
    fi
}

# Function to show a summary of the service status (always displayed)
show_summary() {
    # Simple and direct method to display the summary
    # Avoids file descriptor issues in container environment

    # Get the current IP address - but we'll use localhost in the output
    local ip_address="localhost"
    
    # Get the server port from settings
    local server_port=$(grep -oP 'SERVER_PORT\s*=\s*\K.*' "$SETTINGS_FILE" | tr -d '"' | tr -d "'" | tr -d ' ')
    if [ -z "$server_port" ]; then
        server_port="5050"
    fi
    
    # Use the SSL_ENABLED environment variable directly for protocol
    local protocol="http"
    if [ "$SSL_ENABLED" = "true" ]; then
        protocol="https"
    fi
    
    # Check web app status - more comprehensive check
    local web_status="ERROR"
    
    # First check if the app process is running
    if check_process "python3" && check_process "app.py"; then
        # The app is running, consider it UP even if port check fails
        web_status="UP"
    elif check_port "$server_port"; then
        # Port is open, so service is UP
        web_status="UP"
    fi
    
    # Print summary - using heredoc to avoid file descriptor issues
    cat << EOF

======== NUTIFY SERVICE SUMMARY ========
✅ Web Interface: ${web_status} (Port: ${server_port})

🔗 Access the web interface at: ${protocol}://${ip_address}:${server_port}
========================================

EOF
    
    # Redirect output again if needed - but only for the rest of the script
    if [ "$ENABLE_LOG_STARTUP" = "Y" ]; then
        # Keep standard output for logging
        true
    else
        # Silence all output for the rest of the script
        exec 1>/dev/null 2>/dev/null
    fi
} 