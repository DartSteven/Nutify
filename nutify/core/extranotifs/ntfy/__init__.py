"""Extranotifs Package.

Defines package exports and module-level initialization helpers.
"""

from .ntfy import NtfyNotifier, test_notification, send_event_notification
from .routes import create_blueprint
import os
from core.logger import system_logger as logger

# SQL schema path for the ntfy module (legacy path, kept for backward compatibility)
NTFY_SCHEMA_PATH = 'core/extranotifs/ntfy/db.ntfy.schema.sql'

# Import the new schema path from core.db module
try:
    from core.db import NTFY_SCHEMA_PATH as DB_NTFY_SCHEMA_PATH
except ImportError:
    # Fallback to legacy path if core.db is not available
    DB_NTFY_SCHEMA_PATH = NTFY_SCHEMA_PATH

# Global model variable (will be set in app.py when db.ModelClasses is available)
NtfyConfig = None

# Try to get the NtfyConfig model from db.ModelClasses
def get_ntfy_model():
    """Get the NtfyConfig model from db.ModelClasses"""
    try:
        from app import db
        global NtfyConfig
        if hasattr(db, 'ModelClasses') and hasattr(db.ModelClasses, 'NtfyConfig'):
            NtfyConfig = db.ModelClasses.NtfyConfig
            logger.info("✅ Ntfy model loaded from central DB registry")
            return True
        else:
            logger.warning("⚠️ NtfyConfig model not available in db.ModelClasses")
            return False
    except Exception as e:
        logger.error(f"Error loading NtfyConfig model: {str(e)}")
        return False

# Export all necessary functions and classes
__all__ = [
    'NtfyNotifier', 'test_notification', 'send_event_notification',
    'create_blueprint', 'NTFY_SCHEMA_PATH',
    'NtfyConfig', 'DB_NTFY_SCHEMA_PATH', 'get_ntfy_model'
] 