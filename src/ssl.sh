#!/bin/bash

# SSL certificate management functions
# This file contains functions for managing SSL certificates

# Source common variables
SCRIPT_DIR="/usr/local/bin"
. "$SCRIPT_DIR/common.sh"

# Function to generate SSL certificates if they don't exist
ensure_ssl_certificates() {
    # Check if SSL is enabled
    SSL_ENABLED=$(grep -oP 'SSL_ENABLED\s*=\s*\K.*' "$SETTINGS_FILE" | tr -d '"' | tr -d "'" | tr '[:upper:]' '[:lower:]')
    
    if [ "$SSL_ENABLED" = "true" ]; then
        if [ "$ENABLE_LOG_STARTUP" = "Y" ]; then
            startup_log "SSL is enabled, checking for certificates..."
        fi
        
        # Define certificate paths
        CERT_PATH="/app/ssl/cert.pem"
        KEY_PATH="/app/ssl/key.pem"
        
        # Check if certificates already exist
        if [ -f "$CERT_PATH" ] && [ -f "$KEY_PATH" ]; then
            # Check if certificates are valid
            if openssl x509 -in "$CERT_PATH" -noout -checkend 0 > /dev/null 2>&1; then
                if [ "$ENABLE_LOG_STARTUP" = "Y" ]; then
                    startup_log "Valid SSL certificates found at $CERT_PATH and $KEY_PATH"
                fi
                return 0
            else
                if [ "$ENABLE_LOG_STARTUP" = "Y" ]; then
                    startup_log "SSL certificate at $CERT_PATH has expired, generating new certificates..."
                fi
            fi
        else
            if [ "$ENABLE_LOG_STARTUP" = "Y" ]; then
                startup_log "SSL certificates not found, generating new self-signed certificates..."
            fi
        fi
        
        # Ensure SSL directory exists with proper permissions
        mkdir -p /app/ssl
        chown nut:nut /app/ssl
        chmod 750 /app/ssl
        
        # Generate self-signed certificates
        if [ "$ENABLE_LOG_STARTUP" = "Y" ]; then
            startup_log "Generating self-signed SSL certificates..."
        fi
        if openssl req -x509 -newkey rsa:4096 -nodes -out "$CERT_PATH" -keyout "$KEY_PATH" -days 365 -subj "/CN=nutify.local" -addext "subjectAltName=DNS:nutify.local,DNS:localhost,IP:127.0.0.1" > /dev/null 2>&1; then
            # Set proper permissions
            chown nut:nut "$CERT_PATH" "$KEY_PATH"
            chmod 640 "$CERT_PATH" "$KEY_PATH"
            if [ "$ENABLE_LOG_STARTUP" = "Y" ]; then
                startup_log "SSL certificates generated successfully"
            fi
            return 0
        else
            if [ "$ENABLE_LOG_STARTUP" = "Y" ]; then
                startup_log "Failed to generate SSL certificates"
            fi
            return 1
        fi
    else
        if [ "$ENABLE_LOG_STARTUP" = "Y" ]; then
            startup_log "SSL is disabled, skipping certificate generation"
        fi
        return 0
    fi
} 