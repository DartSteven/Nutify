"""
Unified UPS model access helpers.

This module keeps legacy call sites working while enforcing a single
time-series source: ups_monitor_data (target-scoped snapshots).
"""

from __future__ import annotations

from typing import Dict, Optional, Type

from core.logger import database_logger as logger


def _resolve_db(db_instance=None):
    if db_instance is not None:
        return db_instance
    from core.db.ups import db as global_db
    return global_db


def _resolve_monitor_model(db_instance=None):
    database = _resolve_db(db_instance)

    model = None
    if hasattr(database, 'ModelClasses'):
        model = getattr(database.ModelClasses, 'UPSMonitorData', None)
    if model is not None:
        return model

    # Late fallback when ModelClasses is not fully initialized yet.
    from core.db.orm.orm_ups_monitor_data import init_model as init_monitor_data_model

    model = init_monitor_data_model(database.Model, logger)
    if hasattr(database, 'ModelClasses'):
        database.ModelClasses.UPSMonitorData = model
    return model


def get_ups_model(db_instance=None):
    """
    Legacy-compatible dynamic model accessor.
    Returns the unified UPSMonitorData model.
    """
    return _resolve_monitor_model(db_instance)


def get_static_model(db_instance=None):
    """
    Legacy-compatible static model accessor.
    Static data is also read from UPSMonitorData snapshots.
    """
    return _resolve_monitor_model(db_instance)


def create_dynamic_model(db_instance=None):
    """Compatibility alias for legacy callers."""
    return _resolve_monitor_model(db_instance)


def create_static_model(db_instance=None):
    """Compatibility alias for legacy callers."""
    return _resolve_monitor_model(db_instance)


def initialize_static_data(db_instance=None):
    """
    Legacy no-op: static bootstrap table has been removed.
    """
    logger.info("Skipping legacy initialize_static_data (using unified ups_monitor_data only)")
    return True


def initialize_static_data_if_needed(db_instance=None):
    """
    Legacy no-op: static bootstrap table has been removed.
    """
    logger.info("Skipping legacy initialize_static_data_if_needed (using unified ups_monitor_data only)")
    return True


def insert_initial_dynamic_data(db_instance=None):
    """
    Legacy no-op: dynamic bootstrap table has been removed.
    """
    logger.info("Skipping legacy insert_initial_dynamic_data (using unified ups_monitor_data only)")
    return True


def get_available_ups_variables() -> Dict[str, object]:
    """
    Keep old API shape for callers that only need an available-variable map.
    """
    try:
        from core.db.ups.data import get_available_variables

        return get_available_variables() or {}
    except Exception as exc:
        logger.warning(f"Unable to load available UPS variables from NUT: {exc}")
        return {}


def is_static_field(field_name: str) -> bool:
    """
    Compatibility helper retained for callers that branch on static fields.
    """
    name = str(field_name or '').strip().replace('_', '.').lower()
    static_prefixes = (
        'device.',
        'driver.',
        'battery.type',
        'battery.date',
        'battery.mfr.date',
        'ups.model',
        'ups.mfr',
        'ups.serial',
        'ups.vendorid',
        'ups.productid',
    )
    return name.startswith(static_prefixes)

