#!/bin/bash
# Script to generate settings.txt and NUT configuration files from environment variables

# Source the required modules
SCRIPT_DIR="/usr/local/bin"
. "$SCRIPT_DIR/common.sh"
. "$SCRIPT_DIR/log.sh"
. "$SCRIPT_DIR/filesystem.sh"
. "$SCRIPT_DIR/settings.sh"
. "$SCRIPT_DIR/motd.sh"

# Export ENABLE_LOG_STARTUP to ensure it's passed to child processes
export ENABLE_LOG_STARTUP

# Create required directories
if ! create_dirs; then
    startup_log "CRITICAL ERROR: Failed to create required directories"
    exit 1
fi

# Generate settings.txt file
if ! generate_settings; then
    startup_log "CRITICAL ERROR: Failed to generate settings.txt"
    exit 1
fi

startup_log "Configuration completed successfully"

# Continue with the original command
exec "$@" 