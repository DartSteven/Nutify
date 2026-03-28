#!/bin/bash

# Common variables and settings for all modules
# This file should be sourced by all other scripts

# ENABLE_LOG_STARTUP is preserved from the calling environment
# If not set, default to "N"
if [ "$ENABLE_LOG_STARTUP" != "Y" ]; then
    # Force to N regardless of previous value
    ENABLE_LOG_STARTUP="N"
fi
export ENABLE_LOG_STARTUP

# SSL_ENABLED is preserved from the calling environment
# If not set, default to "false"
if [ "$SSL_ENABLED" != "true" ]; then
    # Force to false regardless of previous value
    SSL_ENABLED="false"
fi
export SSL_ENABLED

# Set defaults for logging variables if not defined
# This ensures we never have empty values in the settings.txt file
if [ -z "${LOG}" ]; then
    LOG="false"
fi

if [ -z "${LOG_LEVEL}" ]; then
    LOG_LEVEL="INFO"
fi

if [ -z "${LOG_WERKZEUG}" ]; then
    LOG_WERKZEUG="false"
fi

# Common file paths
SETTINGS_FILE="/app/nutify/config/settings.txt"
APP_DIR="/app/nutify"
PID_FILE="/tmp/nutify_running.pid"
APP_PID_FILE="/tmp/nutify_app.pid"
NUT_LOG_DIR="/var/log/nut"
NUT_CONFIG_DIR="/etc/nut"
NUT_RUN_DIR="/var/run/nut"

# Define script directory as a fixed location in the container
SCRIPT_DIR="/usr/local/bin"

# Source log.sh if it exists to ensure logging is available
# Check if log.sh is in the same directory as this script
if [ -f "$SCRIPT_DIR/log.sh" ]; then
    . "$SCRIPT_DIR/log.sh"
fi 