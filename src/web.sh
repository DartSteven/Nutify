#!/bin/bash

# Web application management functions
# This file contains functions for managing the web application

# Source common variables
SCRIPT_DIR="/usr/local/bin"
. "$SCRIPT_DIR/common.sh"

# Make sure SSL module is available
if [ -f "$SCRIPT_DIR/ssl.sh" ]; then
    . "$SCRIPT_DIR/ssl.sh"
fi

# Function to start the web application
start_web_app() {
    # Check if there are environment variables for the web app
    if [ "$ENABLE_LOG_STARTUP" = "Y" ]; then
        if [ -n "$SERVER_PORT" ]; then
            startup_log "Server port configured: $SERVER_PORT"
        fi
        
        if [ -n "$SERVER_HOST" ]; then
            startup_log "Server host configured: $SERVER_HOST"
        fi
        
        if [ -n "$DEBUG_MODE" ]; then
            startup_log "Debug mode: $DEBUG_MODE"
        fi
    fi
    
    # Ensure SSL certificates are available if SSL is enabled
    if type ensure_ssl_certificates >/dev/null 2>&1; then
        ensure_ssl_certificates
    else
        startup_log "WARNING: SSL module not loaded, cannot ensure SSL certificates"
    fi
    
    # Check if the application is already running
    if check_process "python3 /app/nutify/app.py"; then
        if [ "$ENABLE_LOG_STARTUP" = "Y" ]; then
            startup_log "Web application is already running"
        fi
        return 0
    fi
    
    # First check if we already have a web app running
    if [ -n "$APP_PID" ] && kill -0 $APP_PID 2>/dev/null; then
        if [ "$ENABLE_LOG_STARTUP" = "Y" ]; then
            startup_log "Web application is already running (PID: $APP_PID), stopping it first..."
        fi
        kill $APP_PID 2>/dev/null
        sleep 2
    fi
    
    # Run the web-facing process without root privileges. The root supervisor
    # only prepares mounted files and monitors the unprivileged child.
    local web_user="${NUTIFY_WEB_USER:-nut}"
    local web_command=(python3 app.py)
    if [ "$(id -u)" -eq 0 ]; then
        if ! id "$web_user" >/dev/null 2>&1; then
            startup_log "ERROR: Web application user does not exist: $web_user"
            return 1
        fi
        if ! command -v gosu >/dev/null 2>&1; then
            startup_log "ERROR: gosu is required to drop web application privileges"
            return 1
        fi
        web_command=(gosu "$web_user" python3 app.py)
    else
        web_user="$(id -un)"
    fi

    # Start the application
    if [ "$ENABLE_LOG_STARTUP" = "Y" ]; then
        startup_log "Starting web application as $web_user..."
        cd "$APP_DIR" && "${web_command[@]}" &
    else
        # No echo message here, start silently
        cd "$APP_DIR" && "${web_command[@]}" > /dev/null 2>&1 &
    fi
    
    APP_PID=$!
    
    # Store the PID for future reference
    echo $APP_PID > "$APP_PID_FILE"
    
    # Wait for the web app to start - in the background
    (
        local max_attempts=30
        local started=false
        
        for i in $(seq 1 $max_attempts); do
            if check_port 5050; then
                started=true
                break
            fi
            
            # Check if process is still running
            if ! kill -0 $APP_PID 2>/dev/null; then
                started=false
                break
            fi
            
            sleep 1
        done
        
        # Now that we've waited, log the appropriate message
        if [ "$started" = "true" ]; then
            if [ "$ENABLE_LOG_STARTUP" = "Y" ]; then
                startup_log "Web application started successfully (PID: $APP_PID)"
            fi
        else
            if [ "$ENABLE_LOG_STARTUP" = "Y" ]; then
                startup_log "WARNING: Web application may not have started properly"
            fi
        fi
    ) &
    
    # Return success immediately, the background process will check and log
    return 0
} 
