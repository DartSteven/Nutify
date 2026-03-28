"""
Initialization Module for Core Components.

This module initializes all the core components of the application,
including the database, the connection monitor, and other services.
"""

import logging
import threading
import time
from datetime import datetime

from core.logger import system_logger as logger

def init_connection_monitor():
    """
    Initialize the UPS connection monitor.
    
    This function initializes and starts the UPS connection monitor,
    which is responsible for tracking the connection state to the UPS
    and handling recovery when the connection is lost.
    
    Returns:
        bool: True if initialization was successful, False otherwise
    """
    try:
        # Import connection monitor here to avoid circular imports
        from core.db.internal_checker import start_connection_monitoring
        
        # Start the connection monitor
        success = start_connection_monitoring()
        if success:
            logger.info("🔌 UPS Connection monitor initialized and started")
        else:
            logger.warning("⚠️ UPS Connection monitor initialization failed")
        
        return success
    except Exception as e:
        logger.error(f"❌ Error initializing UPS connection monitor: {str(e)}")
        return False

def initialize_core_components():
    """
    Initialize all core components of the application.
    
    This function is called during application startup to initialize
    all the core components, such as the connection monitor, that
    should be running before the main application starts.
    
    Returns:
        bool: True if all components were initialized successfully, False otherwise
    """
    success = True
    
    # Initialize the connection monitor
    if not init_connection_monitor():
        logger.warning("⚠️ UPS Connection monitor initialization failed. Application will continue but may experience issues.")
        success = False
    
    # Add more component initializations here as needed
    
    return success 