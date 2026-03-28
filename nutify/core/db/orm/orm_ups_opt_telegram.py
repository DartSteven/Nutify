"""
Telegram Configuration ORM Model.
This module defines the SQLAlchemy ORM model for the ups_opt_telegram table.
"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime, LargeBinary
import pytz
from cryptography.fernet import Fernet
import base64
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

# These will be set during initialization
logger = None
SECRET_KEY = None  # This will be set from the environment during initialization


def get_encryption_key():
    """
    Generate a Fernet object using the SECRET_KEY from environment.

    Returns:
        Fernet: An encryption key derived from SECRET_KEY

    Raises:
        RuntimeError: If SECRET_KEY is not available
    """
    try:
        from flask import current_app

        if current_app and current_app.config.get('SECRET_KEY'):
            secret_key = current_app.config.get('SECRET_KEY')
            if isinstance(secret_key, str):
                secret_key = secret_key.encode()
            if logger:
                logger.debug("Using SECRET_KEY from Flask's current_app.config for Telegram encryption")
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=b'fixed-salt',
                iterations=100000,
            )
            key = base64.urlsafe_b64encode(kdf.derive(secret_key))
            return Fernet(key)
    except Exception as exc:
        if logger:
            logger.debug(f"Could not get SECRET_KEY from current_app for Telegram: {exc}")

    global SECRET_KEY
    if not SECRET_KEY:
        if logger:
            logger.error("SECRET_KEY is not set for Telegram data encryption")
        raise RuntimeError("SECRET_KEY is not available. Telegram data encryption is disabled.")

    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=b'fixed-salt',
        iterations=100000,
    )
    key = base64.urlsafe_b64encode(kdf.derive(SECRET_KEY))
    return Fernet(key)


class TelegramConfig:
    """Model for Telegram configuration."""

    __tablename__ = 'ups_opt_telegram'

    id = Column(Integer, primary_key=True)
    target_id = Column(Integer, nullable=True, index=True)
    display_name = Column(String(80), nullable=False, default='Telegram')
    _bot_token = Column('bot_token', LargeBinary, nullable=False)
    _chat_id = Column('chat_id', LargeBinary, nullable=False)
    parse_mode = Column(String(20), nullable=False, default='HTML')
    disable_web_preview = Column(Boolean, default=False)
    render_mode = Column(String(20), nullable=False, default='graphic')
    is_default = Column(Boolean, default=False)

    # Event notification settings
    notify_onbatt = Column(Boolean, default=False)
    notify_online = Column(Boolean, default=False)
    notify_lowbatt = Column(Boolean, default=False)
    notify_commok = Column(Boolean, default=False)
    notify_commbad = Column(Boolean, default=False)
    notify_shutdown = Column(Boolean, default=False)
    notify_replbatt = Column(Boolean, default=False)
    notify_nocomm = Column(Boolean, default=False)
    notify_noparent = Column(Boolean, default=False)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(pytz.UTC))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(pytz.UTC),
        onupdate=lambda: datetime.now(pytz.UTC),
    )

    @property
    def bot_token(self):
        """Decrypts bot token safely."""
        if self._bot_token is None:
            return None
        try:
            fernet = get_encryption_key()
            return fernet.decrypt(self._bot_token).decode()
        except Exception as exc:
            if logger:
                logger.error(
                    "⚠️ Telegram bot token decryption failed for config ID %s: %s",
                    getattr(self, 'id', 'unknown'),
                    str(exc),
                )
            return None

    @bot_token.setter
    def bot_token(self, value):
        """Encrypt bot token."""
        if value is None:
            self._bot_token = None
            return
        fernet = get_encryption_key()
        self._bot_token = fernet.encrypt(str(value).encode())

    @property
    def chat_id(self):
        """Decrypts chat id safely."""
        if self._chat_id is None:
            return None
        try:
            fernet = get_encryption_key()
            return fernet.decrypt(self._chat_id).decode()
        except Exception as exc:
            if logger:
                logger.error(
                    "⚠️ Telegram chat id decryption failed for config ID %s: %s",
                    getattr(self, 'id', 'unknown'),
                    str(exc),
                )
            return None

    @chat_id.setter
    def chat_id(self, value):
        """Encrypt chat id."""
        if value is None:
            self._chat_id = None
            return
        fernet = get_encryption_key()
        self._chat_id = fernet.encrypt(str(value).encode())

    def is_event_enabled(self, event_type):
        """Return whether event notifications are enabled for this config."""
        event = str(event_type or '').strip().upper()
        if event == 'FSD':
            event = 'SHUTDOWN'
        event_map = {
            'ONBATT': self.notify_onbatt,
            'ONLINE': self.notify_online,
            'LOWBATT': self.notify_lowbatt,
            'COMMOK': self.notify_commok,
            'COMMBAD': self.notify_commbad,
            'SHUTDOWN': self.notify_shutdown,
            'REPLBATT': self.notify_replbatt,
            'NOCOMM': self.notify_nocomm,
            'NOPARENT': self.notify_noparent,
        }
        return bool(event_map.get(event, False))

    def to_dict(self):
        """Convert model to dictionary."""
        from core.db.ups.utils import utc_to_local

        return {
            'id': self.id,
            'target_id': self.target_id,
            'name': self.display_name,
            'display_name': self.display_name,
            'bot_token': '********' if self.bot_token else '',
            'chat_id': '********' if self.chat_id else '',
            'parse_mode': self.parse_mode,
            'disable_web_preview': bool(self.disable_web_preview),
            'render_mode': self.render_mode or 'graphic',
            'is_default': bool(self.is_default),
            'notify_onbatt': bool(self.notify_onbatt),
            'notify_online': bool(self.notify_online),
            'notify_lowbatt': bool(self.notify_lowbatt),
            'notify_commok': bool(self.notify_commok),
            'notify_commbad': bool(self.notify_commbad),
            'notify_shutdown': bool(self.notify_shutdown),
            'notify_replbatt': bool(self.notify_replbatt),
            'notify_nocomm': bool(self.notify_nocomm),
            'notify_noparent': bool(self.notify_noparent),
            'created_at': utc_to_local(self.created_at).isoformat() if self.created_at else None,
            'updated_at': utc_to_local(self.updated_at).isoformat() if self.updated_at else None,
        }


def init_model(model_base, secret_key=None, db_logger=None):
    """
    Initialize the TelegramConfig model with the SQLAlchemy base.

    Args:
        model_base: SQLAlchemy declarative base class
        secret_key: Optional key for encrypting sensitive data
        db_logger: Logger for database operations

    Returns:
        The initialized TelegramConfig model class
    """
    global logger, SECRET_KEY

    if db_logger:
        logger = db_logger
    else:
        import logging
        logger = logging.getLogger('database')

    if secret_key:
        SECRET_KEY = secret_key
        if isinstance(SECRET_KEY, str):
            SECRET_KEY = SECRET_KEY.encode()
        logger.info("🔑 Using provided secret key for Telegram encryption")
    else:
        try:
            from flask import current_app

            if current_app and current_app.config.get('SECRET_KEY'):
                SECRET_KEY = current_app.config.get('SECRET_KEY')
                if isinstance(SECRET_KEY, str):
                    SECRET_KEY = SECRET_KEY.encode()
                logger.info("🔑 Using SECRET_KEY from Flask config for Telegram encryption")
            else:
                logger.warning("⚠️ SECRET_KEY not found in Flask config for Telegram")
        except Exception as exc:
            logger.warning(f"⚠️ Could not load SECRET_KEY from Flask config for Telegram: {exc}")

    class TelegramConfigModel(model_base, TelegramConfig):
        __table_args__ = {'extend_existing': True}

    return TelegramConfigModel
