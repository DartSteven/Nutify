#!/bin/bash

# Network utility functions
# This file contains functions for checking network services and ports

# Source common variables
SCRIPT_DIR="/usr/local/bin"
. "$SCRIPT_DIR/common.sh"

# Function to check if a service is listening on a port
check_port() {
    local port="$1"
    local timeout="${2:-1}"
    
    # First try netstat to check for listening ports
    timeout $timeout bash -c "netstat -tulpn | grep -q ':$port'" 2>/dev/null
    
    if [ $? -eq 0 ]; then
        return 0
    fi
    
    # If netstat doesn't show the port, try connecting to it
    # This is especially useful for web applications where the service might be running
    # but not immediately visible in netstat output
    if timeout $timeout bash -c "( echo > /dev/tcp/localhost/$port ) 2>/dev/null"; then
        return 0
    fi
    
    # If port 5050 is specifically being checked and the app process is running,
    # assume the web app is running even if the port check failed
    if [ "$port" = "5050" ]; then
        if check_process "python3" && check_process "app.py"; then
            if [ "$ENABLE_LOG_STARTUP" = "Y" ]; then
                startup_log "Web app process is running, assuming port $port is available"
            fi
            return 0
        fi
    fi
    
    if [ "$ENABLE_LOG_STARTUP" = "Y" ]; then
        startup_log "No service listening on port $port"
    fi
    return 1
}

# Function to start socat socket listener - DISABLED to let Nutify handle the socket
start_socat() {
    # This function is intentionally empty to prevent socat from interfering with Nutify
    startup_log "Socat disabled to let Nutify handle the socket"
}

# Function to verify configuration files
check_config_files() {
    # Check if settings.txt exists
    if [ ! -f "$SETTINGS_FILE" ]; then
        startup_log "CRITICAL: Missing settings.txt configuration file!"
        return 1
    fi
    
    # Basic validation that settings.txt is properly formatted
    if ! grep -q "SERVER_PORT" "$SETTINGS_FILE"; then
        startup_log "CRITICAL: settings.txt appears to be invalid or corrupted!"
        return 1
    fi
    
    return 0
} 