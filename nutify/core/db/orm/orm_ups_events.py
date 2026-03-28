"""
UPS Events ORM Model.
This module defines the SQLAlchemy ORM model for the ups_events table.
"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text
import pytz
from flask import current_app

# These will be set during initialization
db = None

class UPSEvent:
    """Model for UPS events"""
    __tablename__ = 'ups_events'  # Changed table name from ups_events_socket
    
    id = Column(Integer, primary_key=True)
    timestamp_utc = Column(DateTime(timezone=True), nullable=False, 
                        default=lambda: datetime.now(pytz.UTC))
    timestamp_utc_begin = Column(DateTime(timezone=True), 
                              default=lambda: datetime.now(pytz.UTC))
    timestamp_utc_end = Column(DateTime(timezone=True))
    ups_name = Column(String(255))
    event_type = Column(String(50))
    event_message = Column(Text)
    source_ip = Column(String(45))
    acknowledged = Column(Boolean, default=False)
    target_id = Column(Integer, nullable=True, index=True)
    
    def to_dict(self):
        """Convert to dictionary"""
        # Convert UTC timestamps to local timezone for display
        from core.db.ups.utils import utc_to_local
        
        result = {
            'id': self.id,
            'timestamp_utc': self.timestamp_utc.isoformat() if self.timestamp_utc else None,
            'timestamp_utc_begin': self.timestamp_utc_begin.isoformat() if self.timestamp_utc_begin else None,
            'timestamp_utc_end': self.timestamp_utc_end.isoformat() if self.timestamp_utc_end else None,
            'ups_name': self.ups_name,
            'event_type': self.event_type,
            'event_message': self.event_message,
            'source_ip': self.source_ip,
            'acknowledged': self.acknowledged,
            'target_id': self.target_id,
        }
        return result
    
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

def init_model(model_base):
    """
    Initialize the UPSEvent model with the SQLAlchemy base.
    
    Args:
        model_base: SQLAlchemy declarative base class
        
    Returns:
        The initialized UPSEvent model class
    """
    global db
    db = model_base
    
    class UPSEventModel(model_base, UPSEvent):
        """ORM model for UPS events"""
        __table_args__ = {'extend_existing': True}
        
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            
            # Set the timestamp in UTC if not provided
            if 'timestamp_utc' not in kwargs and 'timestamp_utc_begin' not in kwargs:
                now = datetime.now(pytz.UTC)
                self.timestamp_utc = now
                self.timestamp_utc_begin = now
    
    return UPSEventModel 
