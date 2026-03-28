"""
UPS monitor variable mapping ORM model.

This model stores per-target canonical variable mappings used by the
Multi-NUT renamer pipeline.
"""

from datetime import datetime

import pytz
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)


logger = None


class UPSMonitorVariableMapping:
    """Model for per-target canonical variable mappings."""

    __tablename__ = 'ups_monitor_variable_mappings'

    id = Column(Integer, primary_key=True)
    target_id = Column(
        Integer,
        ForeignKey('ups_monitor_targets.id', ondelete='CASCADE'),
        nullable=False,
        index=True,
    )
    canonical_key = Column(String(128), nullable=False)
    source_key = Column(String(128), nullable=False)
    mapping_mode = Column(String(20), nullable=False, default='manual')
    is_enabled = Column(Boolean, nullable=False, default=True)

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
            'canonical_key': self.canonical_key,
            'source_key': self.source_key,
            'mapping_mode': self.mapping_mode,
            'is_enabled': self.is_enabled,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }


def init_model(model_base, db_logger=None):
    """Initialize model with SQLAlchemy base."""
    global logger

    if db_logger:
        logger = db_logger

    class UPSMonitorVariableMappingModel(model_base, UPSMonitorVariableMapping):
        __table_args__ = (
            UniqueConstraint('target_id', 'canonical_key', name='uq_target_canonical_mapping'),
            {'extend_existing': True},
        )

    return UPSMonitorVariableMappingModel
