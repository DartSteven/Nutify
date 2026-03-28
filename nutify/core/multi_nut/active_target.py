"""Session-scoped active Multi-NUT target helpers."""

from __future__ import annotations

import json
from typing import Dict, Optional

from flask import has_request_context, request, session

from core.logger import system_logger as logger

from .storage import get_monitoring_profile, list_targets
from .storage_snapshots import extract_metric, get_latest_target_snapshot


ACTIVE_TARGET_SESSION_KEY = "active_multi_target_id"


def _safe_int(value) -> Optional[int]:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _profile_supports_target_selection() -> bool:
    try:
        profile = str(get_monitoring_profile() or "single").strip().lower()
        return profile in {"single", "multi"}
    except Exception as exc:
        logger.debug(f"Failed to read monitoring profile for active target: {exc}")
        return False


def _enabled_targets_by_id() -> Dict[int, Dict[str, object]]:
    targets = list_targets(include_disabled=False)
    return {int(item["id"]): item for item in targets if "id" in item}


def clear_active_target() -> None:
    """Clear active target selection from session."""
    if not has_request_context():
        return
    session.pop(ACTIVE_TARGET_SESSION_KEY, None)


def resolve_active_target_id(
    request_override: bool = True,
    fallback_to_primary: bool = True,
) -> Optional[int]:
    """
    Resolve active target id from request/session.

    Resolution order:
    1. `target_id` query param (when enabled)
    2. session value
    3. primary enabled target (optional fallback)
    """
    if not has_request_context():
        return None

    if not _profile_supports_target_selection():
        clear_active_target()
        return None

    targets_map = _enabled_targets_by_id()
    if not targets_map:
        clear_active_target()
        return None

    if request_override:
        requested = _safe_int(request.args.get("target_id"))
        if requested in targets_map:
            session[ACTIVE_TARGET_SESSION_KEY] = requested
            return requested

    session_target_id = _safe_int(session.get(ACTIVE_TARGET_SESSION_KEY))
    if session_target_id in targets_map:
        return session_target_id

    if not fallback_to_primary:
        return None

    primary = next(
        (item for item in targets_map.values() if bool(item.get("is_primary"))),
        None,
    )
    fallback = int(primary["id"]) if primary else int(next(iter(targets_map.keys())))
    session[ACTIVE_TARGET_SESSION_KEY] = fallback
    return fallback


def set_active_target_id(target_id: int) -> Dict[str, object]:
    """Set active target id in session if valid/enabled."""
    if not has_request_context():
        raise ValueError("No request context available")
    if not _profile_supports_target_selection():
        raise ValueError("Active target selection is unavailable in current profile")

    normalized_id = _safe_int(target_id)
    if normalized_id is None:
        raise ValueError("target_id must be an integer")

    targets_map = _enabled_targets_by_id()
    target = targets_map.get(normalized_id)
    if not target:
        raise ValueError("Target not found or disabled")

    session[ACTIVE_TARGET_SESSION_KEY] = normalized_id
    return target


def get_active_target() -> Optional[Dict[str, object]]:
    """Return active target object for current request."""
    active_id = resolve_active_target_id(request_override=True, fallback_to_primary=True)
    if active_id is None:
        return None

    targets_map = _enabled_targets_by_id()
    return targets_map.get(active_id)


def get_request_or_active_target_id() -> Optional[int]:
    """
    Resolve target id for APIs/pages.

    If a valid `target_id` query arg exists, it is used and persisted.
    Otherwise uses session active target in multi profile.
    """
    return resolve_active_target_id(request_override=True, fallback_to_primary=True)


def get_active_target_snapshot_payload() -> Optional[Dict[str, object]]:
    """Return normalized snapshot payload for the active target."""
    target = get_active_target()
    if not target:
        return None

    target_id = int(target["id"])
    snapshot = get_latest_target_snapshot(target_id)
    if not snapshot:
        return {
            "target": target,
            "latest": None,
            "metrics": {},
        }

    metrics = {}
    for key in (
        "ups_status",
        "battery_charge",
        "battery_runtime",
        "ups_load",
        "ups_realpower",
        "input_voltage",
        "device_model",
        "device_serial",
        "device_mfr",
        "ups_realpower_nominal",
        "battery_voltage",
    ):
        value = extract_metric(snapshot, key)
        if value is not None:
            metrics[key] = value

    # Keep full raw map for APIs/pages that need additional keys.
    raw_json = snapshot.get("data_json")
    if raw_json:
        try:
            raw_payload = json.loads(raw_json)
            if isinstance(raw_payload, dict):
                for key, value in raw_payload.items():
                    metrics.setdefault(key, value)
        except Exception:
            pass

    return {
        "target": target,
        "latest": snapshot,
        "metrics": metrics,
    }
