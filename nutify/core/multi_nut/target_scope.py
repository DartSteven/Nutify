"""Helpers to resolve and apply target scope for Multi-NUT settings."""

from __future__ import annotations

import time
from typing import Optional, Tuple

from flask import current_app, has_app_context, has_request_context
from sqlalchemy import or_

from .active_target import get_request_or_active_target_id
from .storage import get_monitoring_profile

# is_multi_profile() runs once per history sample via get_operation_settings();
# without this every call is a nutify_master_control query. Same TTL as the
# operation settings cache, so a profile switch applies within a few seconds.
_PROFILE_CACHE_TTL_SECONDS = 5.0
_profile_cache: Optional[Tuple[float, bool]] = None


def invalidate_profile_cache() -> None:
    """Drop the cached profile so the next is_multi_profile() re-reads it."""
    global _profile_cache
    _profile_cache = None


def _safe_int(value) -> Optional[int]:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def is_multi_profile() -> bool:
    """Return True when workspace monitoring profile is multi."""
    if not has_app_context():
        return False

    # Setup wizard can run before SQLAlchemy is initialized on the Flask app.
    # In that phase we must not trigger DB-backed profile queries.
    try:
        if current_app.extensions.get('sqlalchemy') is None:
            return False
    except Exception:
        return False

    global _profile_cache
    now = time.monotonic()
    if _profile_cache is not None and _profile_cache[0] > now:
        return _profile_cache[1]

    try:
        profile = str(get_monitoring_profile() or "single").strip().lower()
    except Exception:
        return False
    is_multi = profile == "multi"
    _profile_cache = (now + _PROFILE_CACHE_TTL_SECONDS, is_multi)
    return is_multi


def resolve_settings_target_id(explicit_target_id: Optional[int] = None) -> Optional[int]:
    """
    Resolve target id used to scope settings reads/writes.

    In single profile this always returns None, so settings rows are global.
    In multi profile it resolves from explicit value, then active request/session target.
    """
    if not is_multi_profile():
        return None

    explicit = _safe_int(explicit_target_id)
    if explicit is not None:
        return explicit

    if not has_request_context():
        return None

    return _safe_int(get_request_or_active_target_id())


def apply_target_scope(model_class, query, target_id: Optional[int]):
    """Apply strict target filter to a SQLAlchemy query."""
    if not hasattr(model_class, "target_id"):
        return query

    if target_id is None:
        return query.filter(model_class.target_id.is_(None))

    return query.filter(model_class.target_id == int(target_id))


def apply_target_scope_with_global(model_class, query, target_id: Optional[int]):
    """Apply target filter with optional global fallback rows."""
    if not hasattr(model_class, "target_id"):
        return query

    if target_id is None:
        return query.filter(model_class.target_id.is_(None))

    return query.filter(
        or_(
            model_class.target_id == int(target_id),
            model_class.target_id.is_(None),
        )
    )
