#!/bin/bash

# Source all required modules
SCRIPT_DIR="/usr/local/bin"
. "$SCRIPT_DIR/common.sh"
. "$SCRIPT_DIR/log.sh"
. "$SCRIPT_DIR/filesystem.sh"
. "$SCRIPT_DIR/db.sh"
. "$SCRIPT_DIR/motd.sh"
. "$SCRIPT_DIR/network.sh"
. "$SCRIPT_DIR/process.sh"
. "$SCRIPT_DIR/ssl.sh"
. "$SCRIPT_DIR/web.sh"

# Setup trap to clean up on exit
trap 'rm -f "$PID_FILE"; startup_log "Exiting NUT services due to signal"; exit' INT TERM

# Main function
main() {
    # Verify that NUT is properly installed
    if ! command -v upsd >/dev/null || ! command -v upsmon >/dev/null; then
        if [ "$ENABLE_LOG_STARTUP" = "Y" ]; then
            startup_log "CRITICAL ERROR: NUT is not installed or the commands are not in the PATH"
        else
            echo "❌ CRITICAL ERROR: NUT is not installed or the commands are not in the PATH"
        fi
        exit 1
    fi
    
    # Ensure clean startup
    rm -f "$PID_FILE"
    
    # Create the PID file
    echo $$ > "$PID_FILE"
    
    # Detect USB devices
    detect_usb_devices
    
    # Fix permissions for USB devices
    fix_usb_permissions
    
    # Display available environment variables
    if [ "$ENABLE_LOG_STARTUP" = "Y" ]; then
        startup_log "Available environment variables:"
        env
    fi
    
    # Verify configuration files
    if ! check_config_files; then
        if [ "$ENABLE_LOG_STARTUP" = "Y" ]; then
            startup_log "CRITICAL ERROR: Unable to verify configuration files!"
        else
            echo "❌ CRITICAL ERROR: Unable to verify configuration files!"
        fi
        exit 1
    fi
    
    # Cleanup any stale processes
    cleanup_socat
    
    # Before starting UPS services, ensure the notifier script has correct permissions
    chmod 755 "$APP_DIR/core/events/ups_notifier.py"
    chown nut:nut "$APP_DIR/core/events/ups_notifier.py"
    
    # Start the web application
    if ! start_web_app; then
        if [ "$ENABLE_LOG_STARTUP" = "Y" ]; then
            startup_log "WARNING: Problems starting the web application."
        else
            echo "⚠️ WARNING: Problems starting the web application."
        fi
        # Don't exit, the NUT service might still work
    fi
    
    # Show system information
    if [ "$ENABLE_LOG_STARTUP" = "Y" ]; then
        show_system_info
    fi
    
    # Call the function to ensure database permissions
    ensure_database_permissions
    
    # Ensure all Python log files have correct permissions
    ensure_log_permissions
    
    if [ "$ENABLE_LOG_STARTUP" = "Y" ]; then
        startup_log "NUT services successfully started"
    fi
    
    # Show summary (always displayed regardless of log settings)
    show_summary
    
    # Only redirect output after the summary has been displayed
    if [ "$ENABLE_LOG_STARTUP" != "Y" ]; then
        exec > /dev/null 2>&1
    fi
    
    if [ "$ENABLE_LOG_STARTUP" = "Y" ]; then
        startup_log "Starting service monitoring..."
    fi
    
    # Start service monitoring (this will run indefinitely)
    monitor_services
    
    # We should never get here
    if [ "$ENABLE_LOG_STARTUP" = "Y" ]; then
        startup_log "WARNING: Script unexpectedly terminated"
    fi
    rm -f "$PID_FILE"
    exit 1
}

# Start the script
main 