#!/bin/bash

# Process management functions
# This file contains functions for managing processes

# Source common variables
SCRIPT_DIR="/usr/local/bin"
. "$SCRIPT_DIR/common.sh"

# Function to check if a process is running by PID file AND verify process exists
check_pid_file() {
    local pid_file="$1"
    local process_name="$2"
    
    # Check if PID file exists
    if [ ! -f "$pid_file" ]; then
        startup_log "PID file $pid_file not found for $process_name"
        return 1
    fi
    
    # Read PID from file
    local pid=$(cat "$pid_file" 2>/dev/null)
    
    # Check if PID was read successfully
    if [ -z "$pid" ]; then
        startup_log "Empty PID file for $process_name"
        return 1
    fi
    
    # Check if process is running with that PID
    if ! ps -p $pid > /dev/null; then
        startup_log "Process $process_name with PID $pid is not running"
        return 1
    fi
    
    return 0
}

# Function to check if a process is running by name
check_process() {
    local process_name="$1"
    local output=$(ps aux | grep -v grep | grep "$process_name")
    
    if [ -z "$output" ]; then
        startup_log "Process $process_name not found"
        return 1
    fi
    
    return 0
}

# Function to kill a process safely with increasing force
safe_kill() {
    local process_name="$1"
    local pid_file="$2"
    local max_attempts=3
    local pid
    
    # If PID file provided, try to read PID from it
    if [ -n "$pid_file" ] && [ -f "$pid_file" ]; then
        pid=$(cat "$pid_file" 2>/dev/null)
    fi
    
    # If no PID from file, try to find it by name
    if [ -z "$pid" ]; then
        pid=$(pgrep -f "$process_name" 2>/dev/null)
    fi
    
    # If we still don't have a PID, there's nothing to kill
    if [ -z "$pid" ]; then
        if [ "$ENABLE_LOG_STARTUP" = "Y" ]; then
            startup_log "No running process found for $process_name"
        fi
        return 0
    fi
    
    # Try gentle kill first (SIGTERM)
    if [ "$ENABLE_LOG_STARTUP" = "Y" ]; then
        startup_log "Stopping $process_name (PID: $pid) with SIGTERM..."
    fi
    kill $pid 2>/dev/null
    
    # Wait and check if process terminated
    for i in $(seq 1 $max_attempts); do
        sleep 1
        if ! ps -p $pid > /dev/null 2>&1; then
            if [ "$ENABLE_LOG_STARTUP" = "Y" ]; then
                startup_log "$process_name terminated successfully"
            fi
            # Clean up PID file if it exists
            [ -f "$pid_file" ] && rm -f "$pid_file"
            return 0
        fi
        if [ "$ENABLE_LOG_STARTUP" = "Y" ]; then
            startup_log "Process $process_name still running, waiting... ($i/$max_attempts)"
        fi
    done
    
    # If still running, use SIGKILL
    if [ "$ENABLE_LOG_STARTUP" = "Y" ]; then
        startup_log "Sending SIGKILL to $process_name (PID: $pid)..."
    fi
    kill -9 $pid 2>/dev/null
    
    # Wait and check if process terminated
    sleep 1
    if ! ps -p $pid > /dev/null 2>&1; then
        if [ "$ENABLE_LOG_STARTUP" = "Y" ]; then
            startup_log "$process_name terminated with SIGKILL"
        fi
        # Clean up PID file if it exists
        [ -f "$pid_file" ] && rm -f "$pid_file"
        return 0
    else
        if [ "$ENABLE_LOG_STARTUP" = "Y" ]; then
            startup_log "CRITICAL: Failed to kill $process_name process!"
        fi
        return 1
    fi
}

# Function to monitor services
monitor_services() {
    # Log that we're starting the monitoring loop
    if [ "$ENABLE_LOG_STARTUP" = "Y" ]; then
        startup_log "Starting service monitoring loop..."
    fi
    
    # Infinite loop to keep the script running and monitoring services
    while true; do
        # Check if web app is still running
        if ! check_process "python3" || ! check_process "app.py"; then
            if [ "$ENABLE_LOG_STARTUP" = "Y" ]; then
                startup_log "Web application not running, restarting..."
            fi
            # Source web.sh to get the start_web_app function
            if [ -f "$SCRIPT_DIR/web.sh" ]; then
                . "$SCRIPT_DIR/web.sh"
                start_web_app
            else
                startup_log "ERROR: web.sh module not found, cannot restart web app"
            fi
        fi
        
        # Sleep for a while before checking again
        sleep 60
    done
} 