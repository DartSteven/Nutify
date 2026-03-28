#!/bin/bash

# Database utility functions
# This file contains all database permission management functions

# Source common variables
SCRIPT_DIR="/usr/local/bin"
. "$SCRIPT_DIR/common.sh"

# Function to ensure database permissions
ensure_database_permissions() {
    if [ "$ENABLE_LOG_STARTUP" = "Y" ]; then
        startup_log "Checking database permissions..."
    fi
    
    # Set the specific database path based on custom instructions
    DB_PATH="$APP_DIR/instance/nutify.db.sqlite"
    
    if [ "$ENABLE_LOG_STARTUP" = "Y" ]; then
        startup_log "Database path: $DB_PATH"
    fi
    
    # Check if database file exists
    if [ -f "$DB_PATH" ]; then
        # Check permissions
        PERMS=$(stat -c "%a" "$DB_PATH" 2>/dev/null || stat -f "%OLp" "$DB_PATH" 2>/dev/null)
        OWNER=$(stat -c "%U:%G" "$DB_PATH" 2>/dev/null || stat -f "%Su:%Sg" "$DB_PATH" 2>/dev/null)
        
        if [ "$ENABLE_LOG_STARTUP" = "Y" ]; then
            startup_log "Current database permissions: $PERMS, owner: $OWNER"
        fi
        
        # Ensure the database file is writable by nut user
        chmod 664 "$DB_PATH"
        chown nut:nut "$DB_PATH"
        
        # Ensure the directory is writable
        DB_DIR=$(dirname "$DB_PATH")
        chmod 775 "$DB_DIR"
        chown nut:nut "$DB_DIR"
        
        # Check for journal and WAL files
        for ext in "-journal" "-wal" "-shm"; do
            if [ -f "${DB_PATH}${ext}" ]; then
                chmod 664 "${DB_PATH}${ext}"
                chown nut:nut "${DB_PATH}${ext}"
                if [ "$ENABLE_LOG_STARTUP" = "Y" ]; then
                    startup_log "Fixed permissions for ${DB_PATH}${ext}"
                fi
            fi
        done
        
        if [ "$ENABLE_LOG_STARTUP" = "Y" ]; then
            startup_log "Database permissions updated to 664, owner: nut:nut"
        fi
    else
        if [ "$ENABLE_LOG_STARTUP" = "Y" ]; then
            startup_log "Database file not found at $DB_PATH, will be created on first run"
        fi
        
        # Ensure the directory exists and has correct permissions
        DB_DIR=$(dirname "$DB_PATH")
        mkdir -p "$DB_DIR"
        chmod 775 "$DB_DIR"
        chown nut:nut "$DB_DIR"
        
        if [ "$ENABLE_LOG_STARTUP" = "Y" ]; then
            startup_log "Created database directory with permissions 775, owner: nut:nut"
        fi
    fi
} 