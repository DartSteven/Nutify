"""
UPS monitor policy ORM model.

This model stores per-target polling and storage policies for Multi-NUT.
"""

from datetime import datetime

import pytz
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text


logger = None


class UPSMonitorPolicy:
    """Model for per-target Multi-NUT policy."""

    __tablename__ = 'ups_monitor_policies'

    id = Column(Integer, primary_key=True)
    target_id = Column(
        Integer,
        ForeignKey('ups_monitor_targets.id', ondelete='CASCADE'),
        nullable=False,
        unique=True,
        index=True,
    )

    db_strategy = Column(String(20), nullable=False, default='shared')
    shard_granularity = Column(String(10), nullable=False, default='month')
    separate_db_path = Column(String(255), nullable=True)

    polling_interval = Column(Integer, nullable=False, default=5)
    retention_days = Column(Integer, nullable=False, default=0)
    notify_scope = Column(String(20), nullable=False, default='global')

    last_polled_at = Column(DateTime(timezone=True), nullable=True)
    last_success_at = Column(DateTime(timezone=True), nullable=True)
    last_error = Column(Text, nullable=True)

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
            'target_id': self.target_id,
            'db_strategy': self.db_strategy,
            'shard_granularity': self.shard_granularity,
            'separate_db_path': self.separate_db_path,
            'polling_interval': self.polling_interval,
            'retention_days': self.retention_days,
            'notify_scope': self.notify_scope,
            'last_polled_at': self.last_polled_at.isoformat() if self.last_polled_at else None,
            'last_success_at': self.last_success_at.isoformat() if self.last_success_at else None,
            'last_error': self.last_error,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }



def init_model(model_base, db_logger=None):
    """Initialize model with SQLAlchemy base."""
    global logger

    if db_logger:
        logger = db_logger

    class UPSMonitorPolicyModel(model_base, UPSMonitorPolicy):
        __table_args__ = {'extend_existing': True}

    return UPSMonitorPolicyModel
