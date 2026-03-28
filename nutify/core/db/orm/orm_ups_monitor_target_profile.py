"""
UPS monitor target profile ORM model.

Stores low-churn text metadata per target to avoid duplicating the same values
on each minute snapshot row.
"""

from datetime import datetime

import pytz
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, UniqueConstraint


logger = None


PROFILE_TEXT_FIELDS = (
    'input_sensitivity',
    'device_model',
    'device_serial',
    'device_mfr',
    'battery_type',
    'battery_date',
    'battery_mfr_date',
)


class UPSMonitorTargetProfile:
    """Model for low-churn per-target metadata."""

    __tablename__ = 'ups_monitor_target_profiles'

    id = Column(Integer, primary_key=True)
    target_id = Column(
        Integer,
        ForeignKey('ups_monitor_targets.id', ondelete='CASCADE'),
        nullable=False,
        unique=True,
        index=True,
    )

    input_sensitivity = Column(String(255), nullable=True)
    device_model = Column(String(255), nullable=True)
    device_serial = Column(String(255), nullable=True)
    device_mfr = Column(String(255), nullable=True)
    battery_type = Column(String(255), nullable=True)
    battery_date = Column(String(255), nullable=True)
    battery_mfr_date = Column(String(255), nullable=True)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(pytz.UTC))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(pytz.UTC),
        onupdate=lambda: datetime.now(pytz.UTC),
    )

    __table_args__ = (
        UniqueConstraint('target_id', name='uq_target_profile_target'),
    )

    def to_dict(self):
        return {
            'target_id': self.target_id,
            'input_sensitivity': self.input_sensitivity,
            'device_model': self.device_model,
            'device_serial': self.device_serial,
            'device_mfr': self.device_mfr,
            'battery_type': self.battery_type,
            'battery_date': self.battery_date,
            'battery_mfr_date': self.battery_mfr_date,
        }


def init_model(model_base, db_logger=None):
    """Initialize model with SQLAlchemy base."""
    global logger
    if db_logger:
        logger = db_logger

    class UPSMonitorTargetProfileModel(model_base, UPSMonitorTargetProfile):
        __table_args__ = UPSMonitorTargetProfile.__table_args__ + ({'extend_existing': True},)

    return UPSMonitorTargetProfileModel

