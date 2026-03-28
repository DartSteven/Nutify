#!/bin/bash

# Filesystem utility functions
# This file contains all directory and permission management functions

# Source common variables
SCRIPT_DIR="/usr/local/bin"
. "$SCRIPT_DIR/common.sh"

# Function to ensure directories exist with proper permissions
create_dirs() {
    # Get settings directory path
    settings_dir="$(dirname "$SETTINGS_FILE")"
    
    for dir in "$settings_dir" "$NUT_CONFIG_DIR"; do
        if [ ! -d "$dir" ]; then
            startup_log "Creating directory: $dir"
            mkdir -p "$dir"
            if [ $? -ne 0 ]; then
                startup_log "ERROR: Failed to create directory $dir"
                return 1
            fi
        fi
    done
    
    # Set proper permissions for NUT directory
    chown -R nut:nut "$NUT_CONFIG_DIR"
    chmod 750 "$NUT_CONFIG_DIR"
    return 0
}

# Function to ensure proper PID directory permissions
ensure_pid_dirs() {
    # Create PID directories if they don't exist
    for dir in "$NUT_RUN_DIR" "/run"; do
        if [ ! -d "$dir" ]; then
            if [ "$ENABLE_LOG_STARTUP" = "Y" ]; then
                startup_log "Creating PID directory: $dir"
            fi
            mkdir -p "$dir"
        fi
        
        # Set explicit and consistent ownership and permissions
        chown -R nut:nut "$dir"
        chmod 770 "$dir"
        if [ "$ENABLE_LOG_STARTUP" = "Y" ]; then
            startup_log "Set permissions for $dir: owner=nut:nut, mode=770"
        fi
    done
    
    # Create specific PID directory for upsmon if it doesn't exist
    if [ ! -d "/run/nut" ]; then
        mkdir -p "/run/nut"
        chown -R nut:nut "/run/nut"
        chmod 770 "/run/nut"
        if [ "$ENABLE_LOG_STARTUP" = "Y" ]; then
            startup_log "Created /run/nut directory for upsmon PID files"
        fi
    fi
    
    # Ensure symbolic link exists for consistent paths
    if [ ! -L "/run/nut" ] && [ ! -d "/run/nut" ]; then
        ln -sf "$NUT_RUN_DIR" /run/nut
        if [ "$ENABLE_LOG_STARTUP" = "Y" ]; then
            startup_log "Created symbolic link from $NUT_RUN_DIR to /run/nut"
        fi
    fi
    
    # Cleanup any stale PID files
    find "$NUT_RUN_DIR" /run -name "*.pid" -type f -delete
    if [ "$ENABLE_LOG_STARTUP" = "Y" ]; then
        startup_log "Cleaned up stale PID files"
    fi
}

# Function to setup NUT directory permissions
setup_nut_directories() {
    startup_log "Setting up NUT directories..."
    mkdir -p "$NUT_RUN_DIR" "$NUT_CONFIG_DIR" "$NUT_LOG_DIR"
    chown -R nut:nut "$NUT_RUN_DIR" "$NUT_CONFIG_DIR" "$NUT_LOG_DIR"
    chmod 750 "$NUT_RUN_DIR" "$NUT_CONFIG_DIR"
    chmod 755 "$NUT_LOG_DIR"
    startup_log "NUT directories prepared with correct permissions"
}

# Function to setup email directory and file permissions
setup_email_config() {
    startup_log "Generating email configuration..."
    cat > /etc/msmtprc << EOF
# Set default values for all following accounts.
defaults
auth           on
tls            on
tls_trust_file /etc/ssl/certs/ca-certificates.crt
logfile        /var/log/msmtp.log

# Mail account configuration
account        default
host           ${SMTP_HOST:-localhost}
port           ${SMTP_PORT:-25}
from           ${NOTIFY_FROM:-ups@localhost}
user           ${SMTP_USER:-}
password       ${SMTP_PASS:-}
EOF

    chmod 640 /etc/msmtprc
    chown root:nut /etc/msmtprc
    startup_log "Email configuration completed"
}

# Function to detect USB devices
detect_usb_devices() {
    startup_log "Detecting USB devices..."
    lsusb 2>/dev/null || startup_log "WARNING: lsusb command not found or failed"
}

# Function to fix USB permissions if applicable
fix_usb_permissions() {
    case "${SKIP_PERMCHECK,,}" in
        true|1|yes)
            startup_log "Skipping USB permission updates (SKIP_PERMCHECK=${SKIP_PERMCHECK})"
            if [ "$ENABLE_LOG_STARTUP" = "Y" ]; then
                startup_log "Skipping SUID permissions for NUT commands (SKIP_PERMCHECK=${SKIP_PERMCHECK})"
            fi
            ;;
        *)
            if [ -d "/dev/bus/usb" ]; then
                # First set ownership to root:nut for good measure
                chown -R root:nut /dev/bus/usb
                # Now grant read-write to all users (old method that worked better)
                chmod -R o+rw /dev/bus/usb 2>/dev/null
                startup_log "USB device permissions updated (all users access granted)"
            else
                startup_log "WARNING: Directory /dev/bus/usb not found!"
            fi

            # Set the suid bit on the nut commands
            chmod u+s /usr/bin/upsc /usr/bin/upscmd /usr/bin/upsrw 2>/dev/null
            if [ "$ENABLE_LOG_STARTUP" = "Y" ]; then
                startup_log "Set suid permissions for NUT commands"
            fi
            ;;
    esac
}

# Clean up existing PID files to prevent conflicts
cleanup_pid_files() {
    startup_log "Cleaning up existing PID files..."
    find "$NUT_RUN_DIR" /run -name "*.pid" -type f -delete
    rm -f "$NUT_RUN_DIR"/* 2>/dev/null
}

# Function to cleanup socat processes and sockets
cleanup_socat() {
    # Kill all existing socat processes
    pkill -9 socat 2>/dev/null || true
    # Remove existing socket
    rm -f /tmp/ups_events.sock
    if [ "$ENABLE_LOG_STARTUP" = "Y" ]; then
        startup_log "Cleaned up existing socat processes and socket"
    fi
} 