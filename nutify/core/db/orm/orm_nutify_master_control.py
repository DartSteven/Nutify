"""
Nutify Master Control ORM model.
Stores instance-level metadata only (server name and workspace profile).
"""

from datetime import datetime
from typing import Any, Dict, Optional

import pytz
from sqlalchemy import Boolean, Column, DateTime, Integer, String

logger = None
_MODEL_CACHE: Dict[int, type] = {}

PROFILE_SINGLE = "single"
PROFILE_MULTI = "multi"
VALID_MONITORING_PROFILES = {PROFILE_SINGLE, PROFILE_MULTI}


def normalize_monitoring_profile(value: Optional[str]) -> str:
    """Normalize monitoring profile to supported values."""
    normalized = str(value or "").strip().lower()
    if normalized in VALID_MONITORING_PROFILES:
        return normalized
    return PROFILE_SINGLE


class NutifyMasterControl:
    """ORM model for instance-level Nutify metadata."""

    __tablename__ = "nutify_master_control"

    id = Column(Integer, primary_key=True)
    server_name = Column(String(100), nullable=False, default="Nutify")
    monitoring_profile = Column(String(20), nullable=False, default=PROFILE_SINGLE)
    is_configured = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(pytz.UTC))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(pytz.UTC),
        onupdate=lambda: datetime.now(pytz.UTC),
    )

    @classmethod
    def get_current_config(cls) -> Optional["NutifyMasterControl"]:
        """Return configured row first, then latest row."""
        configured = (
            cls.query.filter_by(is_configured=True)
            .order_by(cls.updated_at.desc(), cls.id.desc())
            .first()
        )
        if configured:
            return configured

        return cls.query.order_by(cls.updated_at.desc(), cls.id.desc()).first()

    @classmethod
    def get_server_name(cls) -> str:
        """Return server name from DB with strict behavior."""
        config = cls.get_current_config()
        if config and str(config.server_name or "").strip():
            return str(config.server_name).strip()
        raise Exception("No server_name found in nutify_master_control")

    @classmethod
    def get_monitoring_profile(cls) -> str:
        """Return normalized workspace profile."""
        config = cls.get_current_config()
        if not config:
            return PROFILE_SINGLE
        return normalize_monitoring_profile(getattr(config, "monitoring_profile", None))

    @classmethod
    def is_setup_complete(cls) -> bool:
        """Return True when at least one configured row exists."""
        try:
            return cls.query.filter_by(is_configured=True).count() > 0
        except Exception:
            return False

    @classmethod
    def create_or_update(cls, config_data: Dict[str, Any]) -> "NutifyMasterControl":
        """Create or update the single canonical row."""
        session = cls.query.session
        config = cls.query.order_by(cls.updated_at.desc(), cls.id.desc()).first()

        if config is None:
            config = cls()
            session.add(config)

        if "server_name" in config_data:
            config.server_name = str(config_data.get("server_name") or "Nutify").strip() or "Nutify"
        if "monitoring_profile" in config_data:
            config.monitoring_profile = normalize_monitoring_profile(config_data.get("monitoring_profile"))
        if "is_configured" in config_data:
            config.is_configured = bool(config_data.get("is_configured"))

        session.commit()
        return config


def init_model(model_base, db_logger=None):
    """Initialize ORM class bound to provided SQLAlchemy base."""
    global logger
    logger = db_logger

    cache_key = id(model_base)
    if cache_key in _MODEL_CACHE:
        return _MODEL_CACHE[cache_key]

    class NutifyMasterControlModel(model_base, NutifyMasterControl):
        """Bound ORM model for nutify_master_control."""

        __table_args__ = {"extend_existing": True}

    _MODEL_CACHE[cache_key] = NutifyMasterControlModel
    return NutifyMasterControlModel

