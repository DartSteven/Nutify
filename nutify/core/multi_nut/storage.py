"""Facade exports for Multi-NUT storage and analytics."""

from .storage_core import (
    apply_policy_values,
    bootstrap_primary_target,
    coerce_int,
    create_target,
    default_polling_interval,
    default_separate_db_path,
    delete_target,
    enabled_targets_count,
    ensure_policy_for_target,
    get_enabled_targets,
    get_monitoring_profile,
    get_target_with_policy,
    has_multiple_enabled_targets,
    list_targets,
    models,
    normalize_db_strategy,
    normalize_mode,
    normalize_notify_scope,
    normalize_shard_granularity,
    set_primary_target,
    update_target,
    utc_now,
)
from .storage_snapshots import (
    extract_metric,
    get_latest_target_snapshot,
    infer_error_status,
    load_target_history,
    mark_poll_error,
    parse_iso_timestamp,
    record_target_error_snapshot,
    record_target_snapshot,
    should_poll_target,
)


# Lazy wrappers avoid circular imports between analytics <-> active_target <-> storage facade.
def list_targets_overview(*args, **kwargs):
    from .analytics import list_targets_overview as _impl

    return _impl(*args, **kwargs)


def build_target_dashboard(*args, **kwargs):
    from .analytics import build_target_dashboard as _impl

    return _impl(*args, **kwargs)


def build_multi_target_report(*args, **kwargs):
    from .analytics import build_multi_target_report as _impl

    return _impl(*args, **kwargs)


def get_powerflow_settings(*args, **kwargs):
    from .analytics import get_powerflow_settings as _impl

    return _impl(*args, **kwargs)


__all__ = [
    'apply_policy_values',
    'bootstrap_primary_target',
    'build_target_dashboard',
    'build_multi_target_report',
    'coerce_int',
    'create_target',
    'default_polling_interval',
    'default_separate_db_path',
    'delete_target',
    'enabled_targets_count',
    'ensure_policy_for_target',
    'extract_metric',
    'get_enabled_targets',
    'infer_error_status',
    'get_monitoring_profile',
    'get_latest_target_snapshot',
    'get_powerflow_settings',
    'get_target_with_policy',
    'has_multiple_enabled_targets',
    'list_targets',
    'list_targets_overview',
    'load_target_history',
    'mark_poll_error',
    'models',
    'normalize_db_strategy',
    'normalize_mode',
    'normalize_notify_scope',
    'normalize_shard_granularity',
    'parse_iso_timestamp',
    'record_target_error_snapshot',
    'record_target_snapshot',
    'set_primary_target',
    'should_poll_target',
    'update_target',
    'utc_now',
]
