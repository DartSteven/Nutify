"""
UPS Command History ORM Model.
This module defines the SQLAlchemy ORM model for the ups_variables_upscmd table.
"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text
import pytz
from flask import current_app

# These will be set during initialization
db = None

class UPSCommand:
    """Model for UPS commands history"""
    __tablename__ = 'ups_variables_upscmd'
    
    id = Column(Integer, primary_key=True)
    command = Column(String(100), nullable=False)
    timestamp = Column(DateTime, nullable=False, default=lambda: datetime.now(pytz.UTC))
    success = Column(Boolean, nullable=False)
    output = Column(Text)
    target_id = Column(Integer, nullable=True, index=True)
    
    def to_dict(self):
        """Converts the object to a dictionary"""
        return {
            'id': self.id,
            'command': self.command,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
            'success': self.success,
            'output': self.output,
            'target_id': self.target_id,
        }

def init_model(model_base):
    """
    Initialize the UPSCommand model with the SQLAlchemy base.
    
    Args:
        model_base: SQLAlchemy declarative base class
        
    Returns:
        The initialized UPSCommand model class
    """
    global db
    db = model_base
    
    class UPSCommandModel(model_base, UPSCommand):
        """ORM model for UPS command history"""
        __table_args__ = {'extend_existing': True}
    
    return UPSCommandModel 
