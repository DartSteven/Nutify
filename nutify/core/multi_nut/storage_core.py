"""Core target and policy storage helpers for Multi-NUT."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import pytz
from sqlalchemy import create_engine, text

from core.db.nut_parser import get_nut_mode, get_ups_connection_params
from core.db.ups import db
from core.logger import system_logger as logger
from core.settings import DB_URI, INSTANCE_PATH, UPSC_BIN, get_workspace_monitoring_profile as get_workspace_profile_setting

PROFILE_SINGLE = 'single'
PROFILE_MULTI = 'multi'



def utc_now() -> datetime:
    """Return current UTC datetime."""
    return datetime.now(pytz.UTC)



def coerce_int(value, fallback: int, minimum: int, maximum: int) -> int:
    """Safely cast integer with clamped bounds."""
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return fallback
    return max(minimum, min(maximum, parsed))


def coerce_optional_coordinate(value, minimum: float, maximum: float):
    """Safely cast optional float coordinate with bounds."""
    if value in (None, ''):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if parsed < minimum or parsed > maximum:
        return None
    return parsed



def normalize_mode(mode: Optional[str]) -> str:
    """Normalize NUT mode to supported values."""
    normalized = str(mode or '').strip().lower()
    if normalized in {'standalone', 'netserver', 'netclient'}:
        return normalized
    return 'netclient'



def normalize_db_strategy(strategy: Optional[str]) -> str:
    """Normalize DB strategy (shared-only phase)."""
    return 'shared'



def normalize_shard_granularity(value: Optional[str]) -> str:
    """Normalize shard granularity for sharded strategy."""
    normalized = str(value or '').strip().lower()
    if normalized in {'day', 'month'}:
        return normalized
    return 'month'


def normalize_notify_scope(value: Optional[str]) -> str:
    """Normalize per-target notification routing scope."""
    normalized = str(value or '').strip().lower()
    if normalized in {'global', 'mail', 'ntfy', 'telegram', 'webhook', 'none'}:
        return normalized
    return 'global'


def normalize_monitoring_profile(value: Optional[str]) -> str:
    """Normalize workspace profile."""
    normalized = str(value or '').strip().lower()
    if normalized == PROFILE_MULTI:
        return PROFILE_MULTI
    return PROFILE_SINGLE


def compose_location_string(address: str, city: str, region: str, postal_code: str, country: str) -> str:
    """Compose one readable location string for target rows."""
    return ', '.join(
        part.strip()
        for part in [address, city, region, postal_code, country]
        if str(part or '').strip()
    )


def extract_location_payload(payload: Dict[str, object]) -> Dict[str, object]:
    """Normalize optional structured location fields from target payload."""
    location_enabled = bool(payload.get('location_enabled', False))
    if not location_enabled:
        return {
            'location_enabled': False,
            'location': '',
            'location_country': '',
            'location_region': '',
            'location_city': '',
            'location_postal_code': '',
            'location_address': '',
            'location_latitude': None,
            'location_longitude': None,
        }

    location_country = str(payload.get('location_country') or '').strip()
    location_region = str(payload.get('location_region') or '').strip()
    location_city = str(payload.get('location_city') or '').strip()
    location_postal_code = str(payload.get('location_postal_code') or '').strip()
    location_address = str(payload.get('location_address') or payload.get('location') or '').strip()
    location_latitude = coerce_optional_coordinate(payload.get('location_latitude'), -90.0, 90.0)
    location_longitude = coerce_optional_coordinate(payload.get('location_longitude'), -180.0, 180.0)
    location = compose_location_string(
        location_address,
        location_city,
        location_region,
        location_postal_code,
        location_country,
    )

    return {
        'location_enabled': True,
        'location': location,
        'location_country': location_country,
        'location_region': location_region,
        'location_city': location_city,
        'location_postal_code': location_postal_code,
        'location_address': location_address,
        'location_latitude': location_latitude,
        'location_longitude': location_longitude,
    }


def get_monitoring_profile() -> str:
    """Read workspace monitoring profile from master-control settings."""
    try:
        profile = get_workspace_profile_setting()
        return normalize_monitoring_profile(profile)
    except Exception as exc:
        logger.debug(f"Failed to load monitoring profile from settings: {exc}")

    return PROFILE_SINGLE



def _get_or_init_model_space():
    """Return db.ModelClasses, initializing it lazily when missing."""
    model_space = getattr(db, 'ModelClasses', None)
    if model_space is not None:
        return model_space

    try:
        from core.db.models import init_models
        from core.db.ups import register_models_from_modelclasses

        init_models(db)
        model_space = getattr(db, 'ModelClasses', None)
        if model_space is not None:
            try:
                register_models_from_modelclasses(model_space)
            except Exception as register_exc:
                logger.debug(f"Could not register lazy-loaded ModelClasses globally: {register_exc}")
            logger.info("Initialized db.ModelClasses lazily for Multi-NUT storage access")
            return model_space
    except Exception as exc:
        logger.error(f"Failed to initialize db.ModelClasses lazily: {exc}")

    return None


def models():
    """Return Multi-NUT model classes from ModelClasses."""
    model_space = _get_or_init_model_space()
    if model_space is None:
        raise RuntimeError('ModelClasses not available on db')
    required = ['UPSMonitorTarget', 'UPSMonitorPolicy', 'UPSMonitorData']
    missing = [name for name in required if not hasattr(model_space, name)]
    if missing:
        raise RuntimeError(f'Missing Multi-NUT models: {missing}')

    ensure_target_location_columns()
    return model_space.UPSMonitorTarget, model_space.UPSMonitorPolicy, model_space.UPSMonitorData


def _resolve_sql_engine():
    """Resolve usable SQL engine both inside and outside Flask app context."""
    try:
        return db.engine, False
    except Exception:
        return create_engine(DB_URI), True


def ensure_target_location_columns():
    """Ensure optional target location columns exist for compatibility."""
    engine = None
    dispose_engine = False
    try:
        engine, dispose_engine = _resolve_sql_engine()

        with engine.begin() as conn:
            existing_tables = {
                row[0]
                for row in conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'")).fetchall()
            }
            if 'ups_monitor_targets' not in existing_tables:
                return

            table_info = conn.execute(text("PRAGMA table_info(ups_monitor_targets)")).fetchall()
            if not table_info:
                return
            existing_columns = {row[1] for row in table_info}
            if 'location_enabled' not in existing_columns:
                conn.execute(
                    text(
                        "ALTER TABLE ups_monitor_targets "
                        "ADD COLUMN location_enabled BOOLEAN NOT NULL DEFAULT 0"
                    )
                )
            if 'location' not in existing_columns:
                conn.execute(
                    text(
                        "ALTER TABLE ups_monitor_targets "
                        "ADD COLUMN location VARCHAR(255) NOT NULL DEFAULT ''"
                    )
                )
            if 'location_country' not in existing_columns:
                conn.execute(
                    text(
                        "ALTER TABLE ups_monitor_targets "
                        "ADD COLUMN location_country VARCHAR(120) NOT NULL DEFAULT ''"
                    )
                )
            if 'location_region' not in existing_columns:
                conn.execute(
                    text(
                        "ALTER TABLE ups_monitor_targets "
                        "ADD COLUMN location_region VARCHAR(120) NOT NULL DEFAULT ''"
                    )
                )
            if 'location_city' not in existing_columns:
                conn.execute(
                    text(
                        "ALTER TABLE ups_monitor_targets "
                        "ADD COLUMN location_city VARCHAR(120) NOT NULL DEFAULT ''"
                    )
                )
            if 'location_postal_code' not in existing_columns:
                conn.execute(
                    text(
                        "ALTER TABLE ups_monitor_targets "
                        "ADD COLUMN location_postal_code VARCHAR(40) NOT NULL DEFAULT ''"
                    )
                )
            if 'location_address' not in existing_columns:
                conn.execute(
                    text(
                        "ALTER TABLE ups_monitor_targets "
                        "ADD COLUMN location_address VARCHAR(255) NOT NULL DEFAULT ''"
                    )
                )
            if 'location_latitude' not in existing_columns:
                conn.execute(
                    text(
                        "ALTER TABLE ups_monitor_targets "
                        "ADD COLUMN location_latitude FLOAT"
                    )
                )
            if 'location_longitude' not in existing_columns:
                conn.execute(
                    text(
                        "ALTER TABLE ups_monitor_targets "
                        "ADD COLUMN location_longitude FLOAT"
                    )
                )
    except Exception as exc:
        logger.debug(f"Could not ensure location columns on ups_monitor_targets: {exc}")
    finally:
        if dispose_engine and engine is not None:
            try:
                engine.dispose()
            except Exception:
                pass



def make_default_target_name(base_name: str, existing_names: set[str]) -> str:
    """Create unique target name."""
    candidate = base_name
    index = 2
    while candidate in existing_names:
        candidate = f"{base_name} {index}"
        index += 1
    return candidate



def default_polling_interval() -> int:
    """Read fallback polling interval from VariableConfig."""
    engine = None
    dispose_engine = False
    try:
        engine, dispose_engine = _resolve_sql_engine()

        with engine.connect() as conn:
            existing_tables = {
                row[0]
                for row in conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'")).fetchall()
            }
            if 'ups_opt_variable_config' not in existing_tables:
                return 1

            if 'ups_monitor_targets' in existing_tables:
                primary_target_row = conn.execute(
                    text(
                        "SELECT id FROM ups_monitor_targets "
                        "ORDER BY is_primary DESC, id ASC LIMIT 1"
                    )
                ).fetchone()
                if primary_target_row and primary_target_row[0] is not None:
                    scoped_row = conn.execute(
                        text(
                            "SELECT polling_interval FROM ups_opt_variable_config "
                            "WHERE target_id = :target_id ORDER BY id DESC LIMIT 1"
                        ),
                        {'target_id': int(primary_target_row[0])},
                    ).fetchone()
                    if scoped_row and scoped_row[0] is not None:
                        return coerce_int(scoped_row[0], 1, 1, 60)

            # Legacy fallback for old databases still using global (NULL scope) row.
            global_row = conn.execute(
                text(
                    "SELECT polling_interval FROM ups_opt_variable_config "
                    "WHERE target_id IS NULL ORDER BY id DESC LIMIT 1"
                )
            ).fetchone()
            if global_row and global_row[0] is not None:
                return coerce_int(global_row[0], 1, 1, 60)
    except Exception as exc:
        logger.debug(f"Could not read default polling interval from VariableConfig: {exc}")
    finally:
        if dispose_engine and engine is not None:
            try:
                engine.dispose()
            except Exception:
                pass
    return 1



def default_separate_db_path(target_id: int) -> str:
    """Return default SQLite path for separate strategy."""
    instance_dir = Path(INSTANCE_PATH)
    instance_dir.mkdir(parents=True, exist_ok=True)
    return str(instance_dir / f"multi_target_{target_id}.sqlite")



def apply_policy_values(policy, payload: Dict[str, object], target_id: int):
    """Apply and normalize policy values from payload."""
    # Shared-only phase for Multi-NUT persistence.
    # Future strategy support (sharded/separate) intentionally disabled.
    policy.db_strategy = 'shared'
    policy.shard_granularity = 'month'
    policy.polling_interval = coerce_int(payload.get('polling_interval', policy.polling_interval), 1, 1, 60)
    policy.retention_days = coerce_int(payload.get('retention_days', policy.retention_days), 0, 0, 3650)
    policy.notify_scope = normalize_notify_scope(payload.get('notify_scope', policy.notify_scope))

    policy.separate_db_path = None



def ensure_policy_for_target(target_id: int):
    """Ensure policy exists for a target."""
    _, Policy, _ = models()
    policy = Policy.query.filter_by(target_id=target_id).first()
    if policy:
        return policy

    policy = Policy(
        target_id=target_id,
        db_strategy='shared',
        shard_granularity='month',
        polling_interval=default_polling_interval(),
        retention_days=0,
        notify_scope='global',
    )
    db.session.add(policy)
    db.session.flush()
    return policy



def bootstrap_primary_target() -> Dict[str, object]:
    """Create and maintain the implicit primary target from current NUT config."""
    Target, Policy, _ = models()

    targets = Target.query.order_by(Target.id.asc()).all()
    if targets:
        primary_targets = [item for item in targets if item.is_primary]
        if not primary_targets:
            targets[0].is_primary = True
        elif len(primary_targets) > 1:
            first = primary_targets[0].id
            Target.query.filter(Target.id != first, Target.is_primary.is_(True)).update(
                {'is_primary': False},
                synchronize_session=False,
            )

        for target in Target.query.all():
            ensure_policy_for_target(target.id)

        db.session.commit()
        return {'created': False, 'message': 'Primary target already available'}

    params = get_ups_connection_params() or {}
    ups_name = params.get('name') or 'ups'
    host = params.get('host') or '127.0.0.1'

    target = Target(
        name='Primary UPS',
        ups_name=str(ups_name),
        host=str(host),
        port=3493,
        nut_mode=normalize_mode(get_nut_mode()),
        command_path=UPSC_BIN,
        source='bootstrap',
        enabled=True,
        is_primary=True,
    )
    db.session.add(target)
    db.session.flush()

    policy = Policy(
        target_id=target.id,
        db_strategy='shared',
        shard_granularity='month',
        polling_interval=default_polling_interval(),
        retention_days=0,
        notify_scope='global',
    )
    db.session.add(policy)
    db.session.commit()

    logger.info(f"✅ Created primary Multi-NUT target: {target.ups_name}@{target.host}")
    return {'created': True, 'target_id': target.id}



def list_targets(include_disabled: bool = True) -> List[Dict[str, object]]:
    """List all configured targets with their policy."""
    Target, Policy, _ = models()
    query = Target.query
    if not include_disabled:
        query = query.filter(Target.enabled.is_(True))

    targets = query.order_by(Target.is_primary.desc(), Target.name.asc()).all()
    policies = {
        policy.target_id: policy
        for policy in Policy.query.filter(Policy.target_id.in_([t.id for t in targets])).all()
    } if targets else {}

    serialized = []
    for target in targets:
        item = target.to_dict()
        policy = policies.get(target.id) or ensure_policy_for_target(target.id)
        item['policy'] = policy.to_dict()
        serialized.append(item)

    db.session.commit()
    return serialized



def get_target_with_policy(target_id: int):
    """Fetch target and its policy."""
    Target, Policy, _ = models()
    target = Target.query.get(int(target_id))
    if not target:
        return None, None
    policy = Policy.query.filter_by(target_id=target.id).first() or ensure_policy_for_target(target.id)
    db.session.commit()
    return target, policy



def set_single_primary(target_id: int):
    """Mark one target as primary and clear others."""
    Target, _, _ = models()
    Target.query.update({'is_primary': False}, synchronize_session=False)
    Target.query.filter_by(id=target_id).update({'is_primary': True}, synchronize_session=False)



def create_target(payload: Dict[str, object]) -> Dict[str, object]:
    """Create a new Multi-NUT target."""
    Target, Policy, _ = models()

    ups_name = str(payload.get('ups_name', '')).strip()
    host = str(payload.get('host', '')).strip()
    if not ups_name or not host:
        raise ValueError('ups_name and host are required')

    existing_names = {item.name for item in Target.query.all()}
    preferred_name = str(payload.get('name', '')).strip() or f"{ups_name}@{host}"
    target_name = make_default_target_name(preferred_name, existing_names)
    location_values = extract_location_payload(payload)

    target = Target(
        name=target_name,
        ups_name=ups_name,
        host=host,
        port=coerce_int(payload.get('port', 3493), 3493, 1, 65535),
        nut_mode=normalize_mode(payload.get('nut_mode')),
        command_path=str(payload.get('command_path') or UPSC_BIN).strip() or UPSC_BIN,
        source='wizard',
        enabled=bool(payload.get('enabled', True)),
        is_primary=bool(payload.get('is_primary', False)),
        location_enabled=bool(location_values['location_enabled']),
        location=str(location_values['location']),
        location_country=str(location_values['location_country']),
        location_region=str(location_values['location_region']),
        location_city=str(location_values['location_city']),
        location_postal_code=str(location_values['location_postal_code']),
        location_address=str(location_values['location_address']),
        location_latitude=location_values['location_latitude'],
        location_longitude=location_values['location_longitude'],
    )
    db.session.add(target)
    db.session.flush()

    policy = Policy(
        target_id=target.id,
        db_strategy='shared',
        shard_granularity='month',
        polling_interval=default_polling_interval(),
        retention_days=0,
        notify_scope='global',
    )
    apply_policy_values(policy, payload, target.id)
    db.session.add(policy)

    if target.is_primary:
        set_single_primary(target.id)

    db.session.commit()

    return {
        'target': target.to_dict(),
        'policy': policy.to_dict(),
    }



def update_target(target_id: int, payload: Dict[str, object]) -> Dict[str, object]:
    """Update an existing target."""
    target, policy = get_target_with_policy(target_id)
    if not target:
        raise ValueError('Target not found')

    if 'name' in payload:
        requested_name = str(payload.get('name') or '').strip()
        if requested_name and requested_name != target.name:
            Target, _, _ = models()
            duplicate = Target.query.filter(Target.name == requested_name, Target.id != target.id).first()
            if duplicate:
                raise ValueError('Target name already exists')
            target.name = requested_name

    for field in ['ups_name', 'host', 'command_path']:
        if field in payload and payload.get(field):
            setattr(target, field, str(payload.get(field)).strip())

    if (
        'location_enabled' in payload
        or 'location' in payload
        or 'location_country' in payload
        or 'location_region' in payload
        or 'location_city' in payload
        or 'location_postal_code' in payload
        or 'location_address' in payload
        or 'location_latitude' in payload
        or 'location_longitude' in payload
    ):
        merged_payload = {
            'location_enabled': payload.get('location_enabled', target.location_enabled),
            'location': payload.get('location', target.location),
            'location_country': payload.get('location_country', getattr(target, 'location_country', '')),
            'location_region': payload.get('location_region', getattr(target, 'location_region', '')),
            'location_city': payload.get('location_city', getattr(target, 'location_city', '')),
            'location_postal_code': payload.get('location_postal_code', getattr(target, 'location_postal_code', '')),
            'location_address': payload.get('location_address', getattr(target, 'location_address', '')),
            'location_latitude': payload.get('location_latitude', getattr(target, 'location_latitude', None)),
            'location_longitude': payload.get('location_longitude', getattr(target, 'location_longitude', None)),
        }
        location_values = extract_location_payload(merged_payload)
        target.location_enabled = bool(location_values['location_enabled'])
        target.location = str(location_values['location'])
        target.location_country = str(location_values['location_country'])
        target.location_region = str(location_values['location_region'])
        target.location_city = str(location_values['location_city'])
        target.location_postal_code = str(location_values['location_postal_code'])
        target.location_address = str(location_values['location_address'])
        target.location_latitude = location_values['location_latitude']
        target.location_longitude = location_values['location_longitude']

    if 'port' in payload:
        target.port = coerce_int(payload.get('port'), target.port or 3493, 1, 65535)

    if 'nut_mode' in payload:
        target.nut_mode = normalize_mode(payload.get('nut_mode'))

    if 'enabled' in payload:
        target.enabled = bool(payload.get('enabled'))

    if 'is_primary' in payload and bool(payload.get('is_primary')):
        set_single_primary(target.id)

    apply_policy_values(policy, payload, target.id)
    db.session.commit()

    return {
        'target': target.to_dict(),
        'policy': policy.to_dict(),
    }



def set_primary_target(target_id: int) -> Dict[str, object]:
    """Set given target as primary."""
    target, _ = get_target_with_policy(target_id)
    if not target:
        raise ValueError('Target not found')

    set_single_primary(target.id)
    db.session.commit()

    return {'success': True, 'target_id': target.id}



def delete_target(target_id: int) -> Dict[str, object]:
    """Delete a target and its stored data."""
    target, _ = get_target_with_policy(target_id)
    if not target:
        raise ValueError('Target not found')
    if target.is_primary:
        raise ValueError('Primary target cannot be deleted')

    deleted_target_id = target.id

    Target, Policy, Data = models()
    Policy.query.filter_by(target_id=target.id).delete(synchronize_session=False)
    Data.query.filter_by(target_id=target.id).delete(synchronize_session=False)
    Target.query.filter_by(id=target.id).delete(synchronize_session=False)
    db.session.commit()

    return {'success': True, 'deleted_target_id': deleted_target_id}



def enabled_targets_count() -> int:
    """Count enabled targets."""
    Target, _, _ = models()
    return Target.query.filter_by(enabled=True).count()



def has_multiple_enabled_targets() -> bool:
    """Check if at least two targets are active."""
    return enabled_targets_count() > 1



def get_enabled_targets(exclude_primary: bool = False):
    """Return enabled targets with policy objects."""
    Target, Policy, _ = models()
    query = Target.query.filter_by(enabled=True)
    if exclude_primary:
        query = query.filter(Target.is_primary.is_(False))

    targets = query.order_by(Target.id.asc()).all()
    policies = {
        policy.target_id: policy
        for policy in Policy.query.filter(Policy.target_id.in_([t.id for t in targets])).all()
    } if targets else {}

    results = []
    for target in targets:
        policy = policies.get(target.id) or ensure_policy_for_target(target.id)
        results.append((target, policy))

    db.session.commit()
    return results
