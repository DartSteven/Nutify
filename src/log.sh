#!/bin/bash

# Logging utility functions
# This file contains all logging-related functions

# Function for startup logging
startup_log() {
    local message="$1"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    
    # Create log directory if it doesn't exist
    mkdir -p /var/log/nut 2>/dev/null
    
    # Ensure debug log file exists
    touch /var/log/nut-debug.log
    
    # Log to file always
    echo "[${timestamp}] ${message}" >> /var/log/nut-debug.log
    
    # For console output, check if we should display logs
    if [ "$ENABLE_LOG_STARTUP" = "Y" ]; then
        echo "[STARTUP] $message"
    fi
}

# Debug logging function for backward compatibility
debug_log() {
    local message="$1"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    
    # Always log to file
    echo "[DEBUG] ${timestamp}: ${message}" >> /var/log/nut-debug.log
    
    # Only log to console if DEBUG=Y and ENABLE_LOG_STARTUP=Y
    if [ "${DEBUG}" = "Y" ] && [ "$ENABLE_LOG_STARTUP" = "Y" ]; then
        echo "[DEBUG] ${timestamp}: ${message}"
    fi
}

# Function to ensure all Python log files have correct permissions
ensure_log_permissions() {
    mkdir -p /app/nutify/logs
    touch /app/nutify/logs/system.log /app/nutify/logs/database.log /app/nutify/logs/ups.log /app/nutify/logs/energy.log \
          /app/nutify/logs/web.log /app/nutify/logs/mail.log /app/nutify/logs/options.log /app/nutify/logs/battery.log \
          /app/nutify/logs/upsmon.log /app/nutify/logs/socket.log /app/nutify/logs/voltage.log /app/nutify/logs/power.log \
          /app/nutify/logs/scheduler.log /app/nutify/logs/webhook.log /app/nutify/logs/report.log /app/nutify/logs/events.log
    
    chown -R nut:nut /app/nutify/logs
    chmod -R 755 /app/nutify/logs
    
    if [ "$ENABLE_LOG_STARTUP" = "Y" ]; then
        startup_log "✅ Python log files set up with correct permissions"
    fi
}

# Function to show system information in logs
show_system_info() {
    startup_log "System information:"
    startup_log "- Uptime: $(uptime)"
    startup_log "- Memory: $(free -h | grep Mem)"
    startup_log "- Disk space: $(df -h / | grep /)"
    
    startup_log "Network information:"
    startup_log "- Network interfaces:"
    if [ "$ENABLE_LOG_STARTUP" = "Y" ]; then
        ip -br addr
    fi
    startup_log "- Listening ports:"
    if [ "$ENABLE_LOG_STARTUP" = "Y" ]; then
        netstat -tulpn | grep -E '3493|5050'
    fi
    
    startup_log "NUT information:"
    startup_log "- NUT processes:"
    if [ "$ENABLE_LOG_STARTUP" = "Y" ]; then
        ps aux | grep -E 'upsd|upsmon|upsdrvctl' | grep -v grep
    fi
    
    startup_log "Configured environment variables:"
    startup_log "- UPS_HOST: $UPS_HOST"
    startup_log "- UPS_PORT: $UPS_PORT"
    startup_log "- LISTEN_ADDRESS: $LISTEN_ADDRESS"
    startup_log "- LISTEN_PORT: $LISTEN_PORT"
} 