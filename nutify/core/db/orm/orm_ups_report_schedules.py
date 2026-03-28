"""
Report Schedule ORM Model.
This module defines the SQLAlchemy ORM model for the ups_report_schedules table.
"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime
import pytz
from flask import current_app

# These will be set during initialization
logger = None

class ReportSchedule:
    """Model for report schedules"""
    __tablename__ = 'ups_report_schedules'
    
    id = Column(Integer, primary_key=True)
    target_id = Column(Integer, nullable=True, index=True)
    time = Column(String(5), nullable=False)  # Format: HH:MM
    days = Column(String(20), nullable=False)  # Format: 0,1,2,3,4,5,6 or * for all days
    reports = Column(String(200), nullable=False)  # Comma-separated list of report types
    email = Column(String(255))  # Email to send report to
    mail_config_id = Column(Integer)  # ID of the mail configuration to use
    period_type = Column(String(10), nullable=False, default='daily')  # yesterday, last_week, last_month, range
    from_date = Column(DateTime(timezone=True))  # Start date for 'range' period_type
    to_date = Column(DateTime(timezone=True))  # End date for 'range' period_type
    enabled = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), 
                      default=lambda: datetime.now(pytz.UTC))
    updated_at = Column(DateTime(timezone=True), 
                      default=lambda: datetime.now(pytz.UTC),
                      onupdate=lambda: datetime.now(pytz.UTC))
    
    def to_dict(self):
        """Convert model to dictionary"""
        from core.db.ups.utils import utc_to_local
        
        # Split reports by comma and remove any duplicates
        reports = []
        if self.reports:
            for report in self.reports.split(','):
                if report and report not in reports:
                    reports.append(report)
        
        return {
            'id': self.id,
            'target_id': self.target_id,
            'time': self.time,
            'days': [int(d) for d in self.days.split(',') if d.isdigit()],
            'reports': reports,
            'email': self.email,
            'mail_config_id': self.mail_config_id,
            'period_type': self.period_type,
            'from_date': utc_to_local(self.from_date).isoformat() if self.from_date else None,
            'to_date': utc_to_local(self.to_date).isoformat() if self.to_date else None,
            'enabled': self.enabled,
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

def init_model(model_base, db_logger=None):
    """
    Initialize the ReportSchedule model with the SQLAlchemy base.
    
    Args:
        model_base: SQLAlchemy declarative base class
        db_logger: Logger for database operations
        
    Returns:
        The initialized ReportSchedule model class
    """
    global logger
    
    if db_logger:
        logger = db_logger
    else:
        import logging
        logger = logging.getLogger('database')
    
    class ReportScheduleModel(model_base, ReportSchedule):
        """ORM model for report schedules"""
        __table_args__ = {'extend_existing': True}
    
    return ReportScheduleModel 
