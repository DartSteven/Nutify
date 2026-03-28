"""
UPS monitor rollup ORM model.

This table stores materialized, target-scoped aggregates generated from
minute snapshots for fast chart reads on long ranges.
"""

from datetime import datetime

import pytz
from sqlalchemy import (
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)


logger = None


ROLLUP_FLOAT_FIELDS = (
    'ups_load',
    'ups_power',
    'ups_realpower',
    'ups_realpower_nominal',
    'battery_charge',
    'battery_runtime',
    'battery_voltage',
    'battery_temperature',
    'input_voltage',
    'output_voltage',
    'input_transfer_low',
    'input_transfer_high',
)


class UPSMonitorRollup:
    """Model for Multi-NUT time-series materialized rollups."""

    __tablename__ = 'ups_monitor_rollups'

    id = Column(Integer, primary_key=True)
    target_id = Column(
        Integer,
        ForeignKey('ups_monitor_targets.id', ondelete='CASCADE'),
        nullable=False,
        index=True,
    )
    granularity = Column(String(10), nullable=False, index=True)  # minute|hour|day|month|year
    bucket_start_utc = Column(DateTime(timezone=True), nullable=False, index=True)
    bucket_end_utc = Column(DateTime(timezone=True), nullable=False)
    sample_count = Column(Integer, nullable=False, default=0)

    ups_load = Column(Float, nullable=True)
    ups_power = Column(Float, nullable=True)
    ups_realpower = Column(Float, nullable=True)
    ups_realpower_nominal = Column(Float, nullable=True)
    battery_charge = Column(Float, nullable=True)
    battery_runtime = Column(Float, nullable=True)
    battery_voltage = Column(Float, nullable=True)
    battery_temperature = Column(Float, nullable=True)
    input_voltage = Column(Float, nullable=True)
    output_voltage = Column(Float, nullable=True)
    input_transfer_low = Column(Float, nullable=True)
    input_transfer_high = Column(Float, nullable=True)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(pytz.UTC))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(pytz.UTC),
        onupdate=lambda: datetime.now(pytz.UTC),
    )

    __table_args__ = (
        UniqueConstraint('target_id', 'granularity', 'bucket_start_utc', name='uq_rollup_target_gran_bucket'),
        Index('ix_rollup_target_gran_bucket', 'target_id', 'granularity', 'bucket_start_utc'),
    )

    def to_dict(self):
        payload = {
            'id': self.id,
            'target_id': self.target_id,
            'granularity': self.granularity,
            'bucket_start_utc': self.bucket_start_utc.isoformat() if self.bucket_start_utc else None,
            'bucket_end_utc': self.bucket_end_utc.isoformat() if self.bucket_end_utc else None,
            'sample_count': int(self.sample_count or 0),
        }
        for field_name in ROLLUP_FLOAT_FIELDS:
            payload[field_name] = getattr(self, field_name, None)
        return payload


def init_model(model_base, db_logger=None):
    """Initialize model with SQLAlchemy base."""
    global logger
    if db_logger:
        logger = db_logger

    class UPSMonitorRollupModel(model_base, UPSMonitorRollup):
        __table_args__ = UPSMonitorRollup.__table_args__ + ({'extend_existing': True},)

    return UPSMonitorRollupModel

