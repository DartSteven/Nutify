"""
UPS monitor target ORM model.

This model stores NUT targets configured for Multi-NUT monitoring.
"""

from datetime import datetime

import pytz
from sqlalchemy import Boolean, Column, DateTime, Float, Integer, String, Text


logger = None


class UPSMonitorTarget:
    """Model for configured Multi-NUT targets."""

    __tablename__ = 'ups_monitor_targets'

    id = Column(Integer, primary_key=True)
    name = Column(String(120), nullable=False, unique=True)
    ups_name = Column(String(120), nullable=False)
    host = Column(String(255), nullable=False)
    port = Column(Integer, nullable=False, default=3493)
    nut_mode = Column(String(20), nullable=False, default='netclient')
    command_path = Column(String(255), nullable=False)
    source = Column(String(30), nullable=False, default='wizard')

    enabled = Column(Boolean, nullable=False, default=True)
    is_primary = Column(Boolean, nullable=False, default=False)
    location_enabled = Column(Boolean, nullable=False, default=False)
    location = Column(String(255), nullable=False, default='')
    location_country = Column(String(120), nullable=False, default='')
    location_region = Column(String(120), nullable=False, default='')
    location_city = Column(String(120), nullable=False, default='')
    location_postal_code = Column(String(40), nullable=False, default='')
    location_address = Column(String(255), nullable=False, default='')
    location_latitude = Column(Float, nullable=True)
    location_longitude = Column(Float, nullable=True)

    last_test_status = Column(Boolean, nullable=True)
    last_test_error = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(pytz.UTC))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(pytz.UTC),
        onupdate=lambda: datetime.now(pytz.UTC),
    )

    def to_dict(self):
        """Convert model to API-friendly dictionary."""
        return {
            'id': self.id,
            'name': self.name,
            'ups_name': self.ups_name,
            'host': self.host,
            'port': self.port,
            'nut_mode': self.nut_mode,
            'command_path': self.command_path,
            'source': self.source,
            'enabled': self.enabled,
            'is_primary': self.is_primary,
            'location_enabled': self.location_enabled,
            'location': self.location,
            'location_country': self.location_country,
            'location_region': self.location_region,
            'location_city': self.location_city,
            'location_postal_code': self.location_postal_code,
            'location_address': self.location_address,
            'location_latitude': float(self.location_latitude) if self.location_latitude is not None else None,
            'location_longitude': float(self.location_longitude) if self.location_longitude is not None else None,
            'last_test_status': self.last_test_status,
            'last_test_error': self.last_test_error,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }



def init_model(model_base, db_logger=None):
    """Initialize model with SQLAlchemy base."""
    global logger

    if db_logger:
        logger = db_logger

    class UPSMonitorTargetModel(model_base, UPSMonitorTarget):
        __table_args__ = {'extend_existing': True}

    return UPSMonitorTargetModel
