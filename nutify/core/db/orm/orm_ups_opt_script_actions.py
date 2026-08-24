"""Script action ORM model for UPS event-driven local script execution."""

from __future__ import annotations

from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text
from sqlalchemy.sql import func


class ScriptAction:
    """Model for script actions triggered by UPS events."""

    __tablename__ = 'ups_opt_script_actions'

    id = Column(Integer, primary_key=True)
    target_id = Column(Integer, nullable=True, index=True)
    name = Column(String(128), nullable=False)
    enabled = Column(Boolean, default=True, nullable=False)
    trigger_event = Column(String(32), nullable=False, default='LOWBATT')
    battery_threshold = Column(Integer, nullable=False, default=30)
    script_body = Column(Text, nullable=False)
    cooldown_seconds = Column(Integer, nullable=False, default=300)
    condition_active = Column(Boolean, default=False, nullable=False)
    last_executed_at = Column(DateTime(timezone=True), nullable=True)
    last_exit_code = Column(Integer, nullable=True)
    last_output = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    def to_dict(self):
        return {
            'id': int(self.id),
            'target_id': self.target_id,
            'name': str(self.name or ''),
            'enabled': bool(self.enabled),
            'trigger_event': str(self.trigger_event or 'LOWBATT'),
            'battery_threshold': int(self.battery_threshold or 0),
            'script_body': str(self.script_body or ''),
            'cooldown_seconds': int(self.cooldown_seconds or 0),
            'condition_active': bool(self.condition_active),
            'last_executed_at': self.last_executed_at.isoformat() if self.last_executed_at else None,
            'last_exit_code': self.last_exit_code,
            'last_output': str(self.last_output or ''),
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }


def init_model(model_base, _logger=None):
    """Initialize ScriptAction model with the SQLAlchemy base."""

    class ScriptActionModel(model_base, ScriptAction):
        __tablename__ = ScriptAction.__tablename__

    return ScriptActionModel
