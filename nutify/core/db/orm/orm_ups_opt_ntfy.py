"""
Ntfy Configuration ORM Model.
This module defines the SQLAlchemy ORM model for the ups_opt_ntfy table.
"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime, LargeBinary
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

class NtfyConfig:
    """Model for Ntfy configuration"""
    __tablename__ = 'ups_opt_ntfy'
    
    id = Column(Integer, primary_key=True)
    target_id = Column(Integer, nullable=True, index=True)
    server_type = Column(String(50), nullable=False, default='ntfy.sh')
    server = Column(String(255), nullable=False, default='https://ntfy.sh')
    _topic = Column('topic', LargeBinary)
    use_auth = Column(Boolean, default=False)
    _username = Column('username', LargeBinary)
    _password = Column('password', LargeBinary)
    priority = Column(Integer, default=3)
    use_tags = Column(Boolean, default=False)
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
    updated_at = Column(DateTime(timezone=True), 
                       default=lambda: datetime.now(pytz.UTC),
                       onupdate=lambda: datetime.now(pytz.UTC))
    
    @property
    def topic(self):
        """
        Decrypts the topic.
        Manages decryption errors gracefully if SECRET_KEY has changed since topic was stored.
        """
        if self._topic is None:
            if logger:
                logger.debug(f"Topic is None for ntfy config ID {getattr(self, 'id', 'unknown')}")
            return None
        
        try:
            if logger:
                logger.debug(f"Attempting to decrypt topic for ntfy config ID {getattr(self, 'id', 'unknown')}")
            f = get_encryption_key()
            decrypted = f.decrypt(self._topic).decode()
            if logger:
                logger.debug(f"Topic decryption successful for ntfy config ID {getattr(self, 'id', 'unknown')}")
            return decrypted
        except Exception as e:
            # Log the decryption error but don't crash the application
            if logger:
                logger.error(f"⚠️ Topic decryption failed for ntfy config ID {getattr(self, 'id', 'unknown')}. Error: {str(e)}")
                logger.error(f"⚠️ SECRET_KEY mismatch likely. Current key hash: {hash(SECRET_KEY) if SECRET_KEY else 'None'}")
                logger.warning("You will need to set a new topic since decryption with current SECRET_KEY failed")
            return None  # Return None to indicate topic is unusable but not crash

    @topic.setter
    def topic(self, value):
        """Encrypts the topic"""
        if value is None:
            self._topic = None
        else:
            f = get_encryption_key()
            self._topic = f.encrypt(value.encode())
    
    @property
    def username(self):
        """
        Decrypts the username.
        Manages decryption errors gracefully if SECRET_KEY has changed since username was stored.
        """
        if self._username is None:
            if logger:
                logger.debug(f"Username is None for ntfy config ID {getattr(self, 'id', 'unknown')}")
            return None
        
        try:
            if logger:
                logger.debug(f"Attempting to decrypt username for ntfy config ID {getattr(self, 'id', 'unknown')}")
            f = get_encryption_key()
            decrypted = f.decrypt(self._username).decode()
            if logger:
                logger.debug(f"Username decryption successful for ntfy config ID {getattr(self, 'id', 'unknown')}")
            return decrypted
        except Exception as e:
            # Log the decryption error but don't crash the application
            if logger:
                logger.error(f"⚠️ Username decryption failed for ntfy config ID {getattr(self, 'id', 'unknown')}. Error: {str(e)}")
                logger.error(f"⚠️ SECRET_KEY mismatch likely. Current key hash: {hash(SECRET_KEY) if SECRET_KEY else 'None'}")
                logger.warning("You will need to set a new username since decryption with current SECRET_KEY failed")
            return None  # Return None to indicate username is unusable but not crash

    @username.setter
    def username(self, value):
        """Encrypts the username"""
        if value is None:
            self._username = None
        else:
            f = get_encryption_key()
            self._username = f.encrypt(value.encode())
    
    @property
    def password(self):
        """
        Decrypts the password.
        Manages decryption errors gracefully if SECRET_KEY has changed since password was stored.
        """
        if self._password is None:
            if logger:
                logger.debug(f"Password is None for ntfy config ID {getattr(self, 'id', 'unknown')}")
            return None
        
        try:
            if logger:
                logger.debug(f"Attempting to decrypt password for ntfy config ID {getattr(self, 'id', 'unknown')}")
            f = get_encryption_key()
            decrypted = f.decrypt(self._password).decode()
            if logger:
                logger.debug(f"Password decryption successful for ntfy config ID {getattr(self, 'id', 'unknown')}")
            return decrypted
        except Exception as e:
            # Log the decryption error but don't crash the application
            if logger:
                logger.error(f"⚠️ Password decryption failed for ntfy config ID {getattr(self, 'id', 'unknown')}. Error: {str(e)}")
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
    
    def to_dict(self):
        """Convert model to dictionary"""
        # Convert UTC timestamps to local timezone for display
        from core.db.ups.utils import utc_to_local
        
        return {
            'id': self.id,
            'target_id': self.target_id,
            'server_type': self.server_type,
            'server': self.server,
            'topic': self.topic,
            'use_auth': self.use_auth,
            'username': self.username,
            'password': '********' if self.password else '',
            'priority': self.priority,
            'use_tags': self.use_tags,
            'render_mode': self.render_mode or 'graphic',
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
    Initialize the NtfyConfig model with the SQLAlchemy base.
    
    Args:
        model_base: SQLAlchemy declarative base class
        secret_key: Optional key for encrypting sensitive data
        db_logger: Logger for database operations
        
    Returns:
        The initialized NtfyConfig model class
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
    
    class NtfyConfigModel(model_base, NtfyConfig):
        """ORM model for Ntfy configuration"""
        __table_args__ = {'extend_existing': True}
    
    return NtfyConfigModel 
