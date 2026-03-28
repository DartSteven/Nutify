"""
Telegram module for UPS notifications.
"""

from .telegram import TelegramNotifier, test_notification, send_event_notification
from .routes import create_blueprint
from core.logger import system_logger as logger


TelegramConfig = None


def get_telegram_model():
    """Get TelegramConfig model from db.ModelClasses."""
    try:
        from app import db
        global TelegramConfig
        if hasattr(db, 'ModelClasses') and hasattr(db.ModelClasses, 'TelegramConfig'):
            TelegramConfig = db.ModelClasses.TelegramConfig
            logger.info("✅ Telegram model loaded from central DB registry")
            return TelegramConfig
        logger.warning("⚠️ TelegramConfig model not available in db.ModelClasses")
        return None
    except Exception as exc:
        logger.error(f"Error loading TelegramConfig model: {exc}")
        return None


__all__ = [
    'TelegramNotifier',
    'test_notification',
    'send_event_notification',
    'create_blueprint',
    'TelegramConfig',
    'get_telegram_model',
]
