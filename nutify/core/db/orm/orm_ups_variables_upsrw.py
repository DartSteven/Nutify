"""
UPS Variable ORM Model.
This module defines the SQLAlchemy ORM model for the ups_variables_upsrw table.
"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime
import pytz
from flask import current_app

# These will be set during initialization
db = None

class UPSVariable:
    """Model to track changes to UPS variables"""
    __tablename__ = 'ups_variables_upsrw'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    old_value = Column(String(255))
    new_value = Column(String(255), nullable=False)
    timestamp_utc = Column(DateTime, default=lambda: datetime.now(pytz.UTC))
    success = Column(Boolean, default=True)
    target_id = Column(Integer, nullable=True, index=True)

def init_model(model_base):
    """
    Initialize the UPSVariable model with the SQLAlchemy base.
    
    Args:
        model_base: SQLAlchemy declarative base class
        
    Returns:
        The initialized UPSVariable model class
    """
    global db
    db = model_base
    
    class UPSVariableModel(model_base, UPSVariable):
        """ORM model for UPS variable tracking"""
        __table_args__ = {'extend_existing': True}
    
    return UPSVariableModel 
