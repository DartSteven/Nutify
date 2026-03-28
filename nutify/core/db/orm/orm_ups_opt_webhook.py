"""
Webhook Configuration ORM Model.
This module defines the SQLAlchemy ORM model for the ups_opt_webhook table.
"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime, LargeBinary, Text
import pytz
from flask import current_app
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
    
    This function always tries to get the most current SECRET_KEY from Flask's current_app.
    If that fails, it will fall back to the global SECRET_KEY set during model initialization.
    
    Returns:
        Fernet: An encryption key derived from SECRET_KEY
        
    Raises:
        RuntimeError: If SECRET_KEY is not available
    """
    # Always try to get the SECRET_KEY from Flask's current_app first
    try:
        from flask import current_app
        if current_app and current_app.config.get('SECRET_KEY'):
            secret_key = current_app.config.get('SECRET_KEY')
            if isinstance(secret_key, str):
                secret_key = secret_key.encode()
            if logger:
                logger.debug("Using SECRET_KEY from Flask's current_app.config")
            
            # Generate the Fernet key
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=b'fixed-salt',  # Using fixed salt for consistency
                iterations=100000,
            )
            key = base64.urlsafe_b64encode(kdf.derive(secret_key))
            return Fernet(key)
    except Exception as e:
        if logger:
            logger.debug(f"Could not get SECRET_KEY from current_app, error: {str(e)}")
            logger.debug("Falling back to global SECRET_KEY")
    
    # Fall back to global SECRET_KEY
    global SECRET_KEY
    if not SECRET_KEY:
        # Raise an error as we require a secret key for encryption
        if logger:
            logger.error("SECRET_KEY is not set for data encryption")
            logger.error("Make sure SECRET_KEY is set in environment variables (docker-compose.yaml)")
        raise RuntimeError("SECRET_KEY is not available. Data encryption is disabled.")

    # Generate the Fernet key
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=b'fixed-salt',  # Using fixed salt for consistency
        iterations=100000,
    )
    key = base64.urlsafe_b64encode(kdf.derive(SECRET_KEY))
    return Fernet(key)

class WebhookConfig:
    """Model for Webhook configuration"""
    __tablename__ = 'ups_opt_webhook'
    
    id = Column(Integer, primary_key=True)
    target_id = Column(Integer, nullable=True, index=True)
    display_name = Column(String(50), nullable=False)
    _url = Column('url', LargeBinary, nullable=False)
    server_type = Column(String(20), default='custom', nullable=False)
    request_method = Column(String(10), default='POST', nullable=False)
    content_type = Column(String(50), default='application/json', nullable=False)
    auth_type = Column(String(20), default='none', nullable=False)
    _auth_username = Column('auth_username', LargeBinary)
    _auth_password = Column('auth_password', LargeBinary)
    _auth_token = Column('auth_token', LargeBinary)
    custom_headers = Column(Text)
    custom_payload = Column(Text)
    custom_params = Column(Text)
    render_mode = Column(String(20), nullable=False, default='graphic')
    include_ups_data = Column(Boolean, default=True)
    verify_ssl = Column(Boolean, default=True)
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
    updated_at = Column(DateTime(timezone=True), 
                      default=lambda: datetime.now(pytz.UTC),
                      onupdate=lambda: datetime.now(pytz.UTC))
    
    @property
    def url(self):
        """
        Decrypts the URL.
        Manages decryption errors gracefully if SECRET_KEY has changed since URL was stored.
        """
        if self._url is None:
            if logger:
                logger.debug(f"URL is None for webhook config ID {getattr(self, 'id', 'unknown')}")
            return None
        
        try:
            if logger:
                logger.debug(f"Attempting to decrypt URL for webhook config ID {getattr(self, 'id', 'unknown')}")
            f = get_encryption_key()
            decrypted = f.decrypt(self._url).decode()
            if logger:
                logger.debug(f"URL decryption successful for webhook config ID {getattr(self, 'id', 'unknown')}")
            return decrypted
        except Exception as e:
            # Log the decryption error but don't crash the application
            if logger:
                logger.error(f"⚠️ URL decryption failed for webhook config ID {getattr(self, 'id', 'unknown')}. Error: {str(e)}")
                logger.error(f"⚠️ SECRET_KEY mismatch likely. Current key hash: {hash(SECRET_KEY) if SECRET_KEY else 'None'}")
                logger.warning("You will need to set a new URL since decryption with current SECRET_KEY failed")
            return None  # Return None to indicate URL is unusable but not crash

    @url.setter
    def url(self, value):
        """Encrypts the URL"""
        if value is None:
            self._url = None
        else:
            f = get_encryption_key()
            self._url = f.encrypt(value.encode())
    
    @property
    def auth_username(self):
        """
        Decrypts the auth_username.
        Manages decryption errors gracefully if SECRET_KEY has changed since auth_username was stored.
        """
        if self._auth_username is None:
            if logger:
                logger.debug(f"Auth username is None for webhook config ID {getattr(self, 'id', 'unknown')}")
            return None
        
        try:
            if logger:
                logger.debug(f"Attempting to decrypt auth username for webhook config ID {getattr(self, 'id', 'unknown')}")
            f = get_encryption_key()
            decrypted = f.decrypt(self._auth_username).decode()
            if logger:
                logger.debug(f"Auth username decryption successful for webhook config ID {getattr(self, 'id', 'unknown')}")
            return decrypted
        except Exception as e:
            # Log the decryption error but don't crash the application
            if logger:
                logger.error(f"⚠️ Auth username decryption failed for webhook config ID {getattr(self, 'id', 'unknown')}. Error: {str(e)}")
                logger.error(f"⚠️ SECRET_KEY mismatch likely. Current key hash: {hash(SECRET_KEY) if SECRET_KEY else 'None'}")
                logger.warning("You will need to set a new auth username since decryption with current SECRET_KEY failed")
            return None  # Return None to indicate auth_username is unusable but not crash

    @auth_username.setter
    def auth_username(self, value):
        """Encrypts the auth_username"""
        if value is None:
            self._auth_username = None
        else:
            f = get_encryption_key()
            self._auth_username = f.encrypt(value.encode())
    
    @property
    def auth_password(self):
        """
        Decrypts the auth_password.
        Manages decryption errors gracefully if SECRET_KEY has changed since auth_password was stored.
        """
        if self._auth_password is None:
            if logger:
                logger.debug(f"Auth password is None for webhook config ID {getattr(self, 'id', 'unknown')}")
            return None
        
        try:
            if logger:
                logger.debug(f"Attempting to decrypt auth password for webhook config ID {getattr(self, 'id', 'unknown')}")
            f = get_encryption_key()
            decrypted = f.decrypt(self._auth_password).decode()
            if logger:
                logger.debug(f"Auth password decryption successful for webhook config ID {getattr(self, 'id', 'unknown')}")
            return decrypted
        except Exception as e:
            # Log the decryption error but don't crash the application
            if logger:
                logger.error(f"⚠️ Auth password decryption failed for webhook config ID {getattr(self, 'id', 'unknown')}. Error: {str(e)}")
                logger.error(f"⚠️ SECRET_KEY mismatch likely. Current key hash: {hash(SECRET_KEY) if SECRET_KEY else 'None'}")
                logger.warning("You will need to set a new auth password since decryption with current SECRET_KEY failed")
            return None  # Return None to indicate auth_password is unusable but not crash

    @auth_password.setter
    def auth_password(self, value):
        """Encrypts the auth_password"""
        if value is None:
            self._auth_password = None
        else:
            f = get_encryption_key()
            self._auth_password = f.encrypt(value.encode())
    
    @property
    def auth_token(self):
        """
        Decrypts the auth_token.
        Manages decryption errors gracefully if SECRET_KEY has changed since auth_token was stored.
        """
        if self._auth_token is None:
            if logger:
                logger.debug(f"Auth token is None for webhook config ID {getattr(self, 'id', 'unknown')}")
            return None
        
        try:
            if logger:
                logger.debug(f"Attempting to decrypt auth token for webhook config ID {getattr(self, 'id', 'unknown')}")
            f = get_encryption_key()
            decrypted = f.decrypt(self._auth_token).decode()
            if logger:
                logger.debug(f"Auth token decryption successful for webhook config ID {getattr(self, 'id', 'unknown')}")
            return decrypted
        except Exception as e:
            # Log the decryption error but don't crash the application
            if logger:
                logger.error(f"⚠️ Auth token decryption failed for webhook config ID {getattr(self, 'id', 'unknown')}. Error: {str(e)}")
                logger.error(f"⚠️ SECRET_KEY mismatch likely. Current key hash: {hash(SECRET_KEY) if SECRET_KEY else 'None'}")
                logger.warning("You will need to set a new auth token since decryption with current SECRET_KEY failed")
            return None  # Return None to indicate auth_token is unusable but not crash

    @auth_token.setter
    def auth_token(self, value):
        """Encrypts the auth_token"""
        if value is None:
            self._auth_token = None
        else:
            f = get_encryption_key()
            self._auth_token = f.encrypt(value.encode())
    
    def to_dict(self):
        """Convert model to dictionary"""
        # Convert UTC timestamps to local timezone for display
        from core.db.ups.utils import utc_to_local
        
        # Truncate URL for display if too long
        url = self.url
        url_display = url
        if url and len(url) > 40:
            url_display = url[:37] + '...'
        
        return {
            'id': self.id,
            'target_id': self.target_id,
            'name': self.display_name,  # Add 'name' field mapped to display_name for frontend compatibility
            'display_name': self.display_name,
            'url': url,
            'url_display': url_display,
            'server_type': self.server_type,
            'request_method': self.request_method,
            'content_type': self.content_type,
            'auth_type': self.auth_type,
            'auth_username': self.auth_username,
            'auth_password': '********' if self.auth_password else '',
            'auth_token': '********' if self.auth_token else '',
            'custom_headers': self.custom_headers,
            'custom_payload': self.custom_payload,
            'custom_params': self.custom_params,
            'render_mode': self.render_mode or 'graphic',
            'include_ups_data': self.include_ups_data,
            'verify_ssl': self.verify_ssl,
            'is_default': self.is_default,
            'notify_onbatt': self.notify_onbatt,
            'notify_online': self.notify_online,
            'notify_lowbatt': self.notify_lowbatt,
            'notify_commok': self.notify_commok,
            'notify_commbad': self.notify_commbad,
            'notify_shutdown': self.notify_shutdown,
            'notify_replbatt': self.notify_replbatt,
            'notify_nocomm': self.notify_nocomm,
            'notify_noparent': self.notify_noparent,
            'created_at': utc_to_local(self.created_at).isoformat() if self.created_at else None,
            'updated_at': utc_to_local(self.updated_at).isoformat() if self.updated_at else None
        }
    
    def is_event_enabled(self, event_type):
        """Check if notification for event type is enabled"""
        event_map = {
            'ONBATT': self.notify_onbatt,
            'ONLINE': self.notify_online,
            'LOWBATT': self.notify_lowbatt,
            'COMMOK': self.notify_commok,
            'COMMBAD': self.notify_commbad,
            'SHUTDOWN': self.notify_shutdown,
            'REPLBATT': self.notify_replbatt,
            'NOCOMM': self.notify_nocomm,
            'NOPARENT': self.notify_noparent
        }
        return event_map.get(event_type, False)
    
    @classmethod
    def utc_to_local(cls, utc_dt):
        """
        Convert a UTC datetime to the configured local timezone.
        
        Args:
            utc_dt: UTC datetime object
            
        Returns:
            datetime: Local timezone datetime object
        """
        from core.db.ups.utils import utc_to_local as utils_utc_to_local
        return utils_utc_to_local(utc_dt)
    
    @classmethod
    def local_to_utc(cls, local_dt):
        """
        Convert a local timezone datetime to UTC.
        
        Args:
            local_dt: Local timezone datetime object
            
        Returns:
            datetime: UTC datetime object
        """
        from core.db.ups.utils import local_to_utc as utils_local_to_utc
        return utils_local_to_utc(local_dt)

def init_model(model_base, secret_key=None, db_logger=None):
    """
    Initialize the WebhookConfig model with the SQLAlchemy base.
    
    Args:
        model_base: SQLAlchemy declarative base class
        secret_key: Optional key for encrypting sensitive data
        db_logger: Logger for database operations
        
    Returns:
        The initialized WebhookConfig model class
    """
    global logger, SECRET_KEY
    
    if db_logger:
        logger = db_logger
    else:
        import logging
        logger = logging.getLogger('database')
        
    # Set SECRET_KEY for encryption
    if secret_key:
        SECRET_KEY = secret_key
        if isinstance(SECRET_KEY, str):
            SECRET_KEY = SECRET_KEY.encode()
        logger.info("🔑 Using provided secret key for data encryption")
    else:
        # Try to get SECRET_KEY from Flask config
        try:
            from flask import current_app
            if current_app and current_app.config.get('SECRET_KEY'):
                SECRET_KEY = current_app.config.get('SECRET_KEY')
                if isinstance(SECRET_KEY, str):
                    SECRET_KEY = SECRET_KEY.encode()
                logger.info("🔑 Using secret key from Flask config for data encryption")
            else:
                logger.warning("⚠️ SECRET_KEY not set in Flask config; data encryption disabled")
        except Exception as e:
            logger.warning(f"⚠️ Could not get SECRET_KEY from Flask config: {str(e)}")
            logger.warning("⚠️ Data encryption disabled")
    
    class WebhookConfigModel(model_base, WebhookConfig):
        """ORM model for Webhook configuration"""
        __table_args__ = {'extend_existing': True}
    
    return WebhookConfigModel 
