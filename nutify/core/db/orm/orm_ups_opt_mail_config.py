"""
Mail Configuration ORM Model.
This module defines the SQLAlchemy ORM model for the ups_opt_mail_config table.
"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime, LargeBinary
from cryptography.fernet import Fernet
import base64
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import pytz
from flask import current_app

# These will be set during initialization
db = None
SECRET_KEY = None  # This is now only a fallback value
logger = None

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
            logger.error("SECRET_KEY is not set for password encryption")
            logger.error("Make sure SECRET_KEY is set in environment variables (docker-compose.yaml)")
        raise RuntimeError("SECRET_KEY is not available. Password encryption is disabled.")

    # Generate the Fernet key
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=b'fixed-salt',  # Using fixed salt for consistency
        iterations=100000,
    )
    key = base64.urlsafe_b64encode(kdf.derive(SECRET_KEY))
    return Fernet(key)

class MailConfig:
    """Model for email configuration"""
    __tablename__ = 'ups_opt_mail_config'
    
    id = Column(Integer, primary_key=True)
    target_id = Column(Integer, nullable=True, index=True)
    smtp_server = Column(String(255), nullable=False)
    smtp_port = Column(Integer, nullable=False)
    username = Column(String(255))
    _password = Column('password', LargeBinary)
    enabled = Column(Boolean, default=False)
    provider = Column(String(50))  # Email provider
    tls = Column(Boolean, default=True)
    tls_starttls = Column(Boolean, default=True)
    render_mode = Column(String(20), nullable=False, default='graphic')
    is_default = Column(Boolean, default=False)  # Whether this is the default configuration
    to_email = Column(String(255))  # Email address for receiving test emails and notifications
    _from_email = Column('from_email', String(255))  # Email address used as sender (especially for Amazon SES)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(pytz.UTC))
    updated_at = Column(DateTime(timezone=True), 
                      default=lambda: datetime.now(pytz.UTC),
                      onupdate=lambda: datetime.now(pytz.UTC))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        logger.debug(f"📅 Creating MailConfig")
        logger.debug(f"📅 Created at will use UTC: {datetime.now(pytz.UTC)}")

    @property
    def password(self):
        """
        Decrypts the password.
        Manages decryption errors gracefully if SECRET_KEY has changed since password was stored.
        """
        if self._password is None:
            if logger:
                logger.debug(f"Password is None for mail config ID {getattr(self, 'id', 'unknown')}")
            return None
        
        try:
            if logger:
                logger.debug(f"Attempting to decrypt password for mail config ID {getattr(self, 'id', 'unknown')}")
            f = get_encryption_key()
            decrypted = f.decrypt(self._password).decode()
            if logger:
                logger.debug(f"Password decryption successful for mail config ID {getattr(self, 'id', 'unknown')}")
            return decrypted
        except Exception as e:
            # Log the decryption error but don't crash the application
            if logger:
                logger.error(f"⚠️ Password decryption failed for mail config ID {getattr(self, 'id', 'unknown')}. Error: {str(e)}")
                logger.error(f"⚠️ SECRET_KEY mismatch likely. Current key hash: {hash(SECRET_KEY) if SECRET_KEY else 'None'}")
                logger.warning("You will need to set a new password since decryption with current SECRET_KEY failed")
            return None  # Return None to indicate password is unusable but not crash

    @password.setter
    def password(self, value):
        """Encrypts the password"""
        if value is None:
            self._password = None
        else:
            f = get_encryption_key()
            self._password = f.encrypt(value.encode())
            
    @property
    def from_email(self):
        """Returns the explicit from_email if set, otherwise falls back to username"""
        return self._from_email if hasattr(self, '_from_email') and self._from_email else self.username
        
    @from_email.setter
    def from_email(self, value):
        """Sets the from_email field"""
        self._from_email = value
        
    @property
    def from_name(self):
        """Returns the username's local part as the from_name"""
        if self.username and '@' in self.username:
            return self.username.split('@')[0]
        return self.username
        
    @classmethod
    def get_default(cls, target_id=None):
        """Get the default global mail configuration."""
        query = cls.query
        if hasattr(cls, 'target_id'):
            query = query.filter(cls.target_id.is_(None))
        return query.filter_by(is_default=True).first() or query.order_by(cls.id.asc()).first()

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
    Initialize the MailConfig model with the SQLAlchemy base.
    
    Args:
        model_base: SQLAlchemy declarative base class
        secret_key: Optional key for encrypting passwords (will use settings.get_secret_key if not provided)
        db_logger: Logger for database operations
        
    Returns:
        The initialized MailConfig model class
    """
    global db, SECRET_KEY, logger
    db = model_base
    
    # Set secret key and logger if provided
    if secret_key:
        SECRET_KEY = secret_key
    else:
        try:
            from core.settings import get_secret_key
            SECRET_KEY = get_secret_key()
            if logger:
                logger.info("✅ Retrieved SECRET_KEY from settings for password encryption")
        except Exception as e:
            if logger:
                logger.warning(f"⚠️ Could not get SECRET_KEY from settings: {e}")
    
    if db_logger:
        logger = db_logger
    else:
        import logging
        logger = logging.getLogger('database')
    
    class MailConfigModel(model_base, MailConfig):
        """ORM model for mail configuration"""
        __table_args__ = {'extend_existing': True}
    
    return MailConfigModel 
