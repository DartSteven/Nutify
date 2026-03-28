"""
Notification Settings ORM Model.
This module defines the SQLAlchemy ORM model for the ups_opt_notification table.
"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime, UniqueConstraint
import pytz
from core.db.ups import db as app_db

# These will be set during initialization
db = None
logger = None

class NotificationSettings:
    """Model for notification settings"""
    __tablename__ = 'ups_opt_notification'
    __table_args__ = (
        UniqueConstraint('target_id', 'event_type', name='uq_notification_target_event'),
    )
    
    id = Column(Integer, primary_key=True)
    target_id = Column(Integer, nullable=True, index=True)
    event_type = Column(String(50), nullable=False)
    enabled = Column(Boolean, default=True)
    id_email = Column(Integer, nullable=True)
    ntfy_enabled = Column(Boolean, default=False)
    id_ntfy = Column(Integer, nullable=True)
    telegram_enabled = Column(Boolean, default=False)
    id_telegram = Column(Integer, nullable=True)
    webhook_enabled = Column(Boolean, default=False)
    id_webhook = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(pytz.UTC))
    updated_at = Column(DateTime(timezone=True), 
                       default=lambda: datetime.now(pytz.UTC),
                       onupdate=lambda: datetime.now(pytz.UTC))
    
    def to_dict(self):
        """Convert to dictionary"""
        # Convert UTC timestamps to local timezone for display
        from core.db.ups.utils import utc_to_local
        
        return {
            'id': self.id,
            'target_id': self.target_id,
            'event_type': self.event_type,
            'enabled': self.enabled,
            'id_email': self.id_email,
            'ntfy_enabled': bool(getattr(self, 'ntfy_enabled', False)),
            'id_ntfy': getattr(self, 'id_ntfy', None),
            'telegram_enabled': bool(getattr(self, 'telegram_enabled', False)),
            'id_telegram': getattr(self, 'id_telegram', None),
            'webhook_enabled': bool(getattr(self, 'webhook_enabled', False)),
            'id_webhook': getattr(self, 'id_webhook', None),
            'created_at': utc_to_local(self.created_at).isoformat() if self.created_at else None,
            'updated_at': utc_to_local(self.updated_at).isoformat() if self.updated_at else None
        }
    
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

    @classmethod
    def _scoped_query(cls, target_id=None):
        query = app_db.session.query(cls)
        if not hasattr(cls, 'target_id'):
            return query
        if target_id is None:
            return query.filter(cls.target_id.is_(None))
        return query.filter(cls.target_id == int(target_id))
    
    @classmethod
    def init_notification_settings(cls, target_id=None):
        """Initialize notification settings with default values if not exists"""
        try:
            # Get available event types
            from core.mail.mail import EmailNotifier
            
            # Import the SQLAlchemy db instance from the core app
            from core.db.ups import db as app_db
            
            logger.info("Starting NotificationSettings initialization")
            
            # Check if settings already exist
            settings = cls._scoped_query(target_id).all()
            if settings:
                logger.info(f"Notification settings already exist: {len(settings)} found")
                return False
                
            logger.info("No notification settings found, creating defaults")
            
            # Create default settings
            added_count = 0
            for event_type in EmailNotifier.EVENT_TYPES:
                setting = cls(event_type=event_type, enabled=False)
                if hasattr(setting, 'target_id'):
                    setting.target_id = target_id
                app_db.session.add(setting)
                added_count += 1
                
            logger.info(f"Added {added_count} notification settings")
            
            # Commit the transaction
            try:
                app_db.session.commit()
                logger.info("Default notification settings created and committed")
                return True
            except Exception as e:
                # If error occurs during commit due to transaction issues, try a different approach
                if "transaction is already begun" in str(e):
                    logger.debug("Transaction already begun, trying to flush instead")
                    app_db.session.flush()
                    logger.info("Default notification settings flushed to session")
                    return True
                else:
                    # Another type of error, propagate it
                    app_db.session.rollback()
                    logger.error(f"Error during commit: {str(e)}")
                    raise
            
        except Exception as e:
            # Ensure we rollback any open transaction
            try:
                app_db.session.rollback()
            except:
                pass
                
            logger.error(f"Error initializing notification settings: {str(e)}")
            return False

def init_model(model_base, db_instance, db_logger=None):
    """
    Initialize the NotificationSettings model with the SQLAlchemy base.
    
    Args:
        model_base: SQLAlchemy declarative base class
        db_instance: SQLAlchemy database instance
        db_logger: Logger for database operations
        
    Returns:
        The initialized NotificationSettings model class
    """
    global db, logger
    db = db_instance
    
    if db_logger:
        logger = db_logger
    else:
        import logging
        logger = logging.getLogger('database')

    base_table_args = getattr(NotificationSettings, '__table_args__', ())
    if isinstance(base_table_args, tuple):
        table_args = (*base_table_args, {'extend_existing': True})
    elif isinstance(base_table_args, dict):
        table_args = {**base_table_args, 'extend_existing': True}
    else:
        table_args = {'extend_existing': True}
    
    class NotificationSettingsModel(model_base, NotificationSettings):
        """ORM model for notification settings"""
        __table_args__ = table_args
    
    return NotificationSettingsModel
