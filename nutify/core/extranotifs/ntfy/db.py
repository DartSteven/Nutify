"""Database access helpers for Ntfy configurations."""

from __future__ import annotations

import logging

from core.notifications import normalize_render_mode
from core.multi_nut.target_scope import resolve_settings_target_id

logger = logging.getLogger(__name__)

_EVENT_TYPES = [
    'ONLINE',
    'ONBATT',
    'LOWBATT',
    'COMMOK',
    'COMMBAD',
    'SHUTDOWN',
    'REPLBATT',
    'NOCOMM',
    'NOPARENT',
]


def _normalize_event_type(value) -> str:
    event_type = str(value or '').strip().upper()
    if event_type == 'FSD':
        return 'SHUTDOWN'
    return event_type


def get_ntfy_model():
    """Return NtfyConfig model from the central db registry."""
    try:
        from app import db
    except Exception as exc:
        logger.error(f"Error loading db in Ntfy module: {exc}")
        return None

    if hasattr(db, 'ModelClasses') and hasattr(db.ModelClasses, 'NtfyConfig'):
        return db.ModelClasses.NtfyConfig

    logger.warning("NtfyConfig model is not available in db.ModelClasses")
    return None


def get_notification_model():
    """Return NotificationSettings model from the central db registry."""
    try:
        from app import db
    except Exception as exc:
        logger.error(f"Error loading db in Ntfy module: {exc}")
        return None

    if hasattr(db, 'ModelClasses') and hasattr(db.ModelClasses, 'NotificationSettings'):
        return db.ModelClasses.NotificationSettings

    logger.warning("NotificationSettings model is not available in db.ModelClasses")
    return None


def _global_query(model):
    query = model.query
    if hasattr(model, 'target_id'):
        query = query.filter(model.target_id.is_(None))
    return query


def _notification_scoped_query(notification_model, target_id=None):
    scoped_target_id = resolve_settings_target_id(target_id)
    query = notification_model.query
    if hasattr(notification_model, 'target_id'):
        if scoped_target_id is None:
            query = query.filter(notification_model.target_id.is_(None))
        else:
            query = query.filter(notification_model.target_id == int(scoped_target_id))
    return query, scoped_target_id


def _set_default_global(model, current_config_id):
    query = _global_query(model)
    query.filter(model.id != int(current_config_id)).update({'is_default': False}, synchronize_session=False)


def _resolve_notification_row(notification_model, event_type, target_id=None, create_missing=False):
    from app import db

    query, scoped_target_id = _notification_scoped_query(notification_model, target_id)
    row = query.filter(notification_model.event_type == str(event_type).upper()).first()
    if row or not create_missing:
        return row, scoped_target_id

    row = notification_model(
        event_type=str(event_type).upper(),
        enabled=False,
        id_email=None,
        ntfy_enabled=False,
        id_ntfy=None,
        telegram_enabled=False,
        id_telegram=None,
        webhook_enabled=False,
        id_webhook=None,
    )
    if hasattr(row, 'target_id'):
        row.target_id = scoped_target_id
    db.session.add(row)
    db.session.flush()
    return row, scoped_target_id


def get_configs_from_db(target_id=None):
    """Return all global Ntfy configurations."""
    try:
        model = get_ntfy_model()
        if not model:
            return []

        configs = _global_query(model).order_by(model.is_default.desc(), model.id.asc()).all()
        return [config.to_dict() for config in configs]
    except Exception as exc:
        logger.error(f"Error fetching Ntfy configurations: {exc}")
        return []


def get_config_by_id(config_id, target_id=None):
    """Return one global Ntfy configuration by id."""
    try:
        model = get_ntfy_model()
        if not model:
            return None

        config = _global_query(model).filter(model.id == int(config_id)).first()
        return config.to_dict() if config else None
    except Exception as exc:
        logger.error(f"Error fetching Ntfy configuration {config_id}: {exc}")
        return None


def save_config(config_data, target_id=None):
    """Create or update a global Ntfy configuration."""
    try:
        from app import db

        model = get_ntfy_model()
        if not model:
            return {"success": False, "message": "NtfyConfig model not available"}

        config_id = config_data.get('id')
        if config_id:
            config = _global_query(model).filter(model.id == int(config_id)).first()
            if not config:
                return {"success": False, "message": "Configuration not found"}

            if config_data.get('password') == '********':
                config_data.pop('password', None)

            config.server_type = config_data.get('server_type', config.server_type)
            config.server = config_data.get('server', config.server)
            config.topic = config_data.get('topic', config.topic)
            config.use_auth = bool(config_data.get('use_auth', config.use_auth))
            config.username = config_data.get('username', config.username)
            if 'password' in config_data:
                config.password = config_data.get('password')
            config.priority = config_data.get('priority', config.priority)
            config.use_tags = bool(config_data.get('use_tags', config.use_tags))
            config.render_mode = normalize_render_mode(config_data.get('render_mode', config.render_mode))
            if hasattr(config, 'target_id'):
                config.target_id = None

            if config_data.get('is_default'):
                _set_default_global(model, config.id)
                config.is_default = True

            db.session.commit()
            return {"success": True, "config": get_config_by_id(config.id)}

        new_config = model(
            target_id=None,
            server_type=config_data.get('server_type', 'ntfy.sh'),
            server=config_data.get('server', 'https://ntfy.sh'),
            topic=config_data.get('topic', ''),
            use_auth=bool(config_data.get('use_auth', False)),
            username=config_data.get('username', ''),
            password=config_data.get('password', ''),
            priority=config_data.get('priority', 3),
            use_tags=bool(config_data.get('use_tags', False)),
            render_mode=normalize_render_mode(config_data.get('render_mode')),
            is_default=bool(config_data.get('is_default', False)),
        )
        db.session.add(new_config)
        db.session.flush()

        count_global = _global_query(model).count()
        if count_global == 1:
            new_config.is_default = True
        elif config_data.get('is_default'):
            _set_default_global(model, new_config.id)

        db.session.commit()
        return {"success": True, "config": get_config_by_id(new_config.id)}
    except Exception as exc:
        from app import db

        db.session.rollback()
        logger.error(f"Error saving Ntfy configuration: {exc}")
        return {"success": False, "message": str(exc)}


def delete_config(config_id, target_id=None):
    """Delete a global Ntfy configuration."""
    try:
        from app import db

        model = get_ntfy_model()
        if not model:
            return {"success": False, "message": "NtfyConfig model not available"}

        config = _global_query(model).filter(model.id == int(config_id)).first()
        if not config:
            return {"success": False, "message": "Configuration not found"}

        was_default = bool(config.is_default)

        notification_model = get_notification_model()
        if notification_model is not None and hasattr(notification_model, 'id_ntfy'):
            rows = notification_model.query.filter(notification_model.id_ntfy == int(config_id)).all()
            for row in rows:
                row.id_ntfy = None
                if hasattr(row, 'ntfy_enabled'):
                    row.ntfy_enabled = False

        db.session.delete(config)
        db.session.commit()

        if was_default:
            remaining = _global_query(model).order_by(model.id.asc()).first()
            if remaining:
                remaining.is_default = True
                db.session.commit()

        return {"success": True}
    except Exception as exc:
        from app import db

        db.session.rollback()
        logger.error(f"Error deleting Ntfy configuration {config_id}: {exc}")
        return {"success": False, "message": str(exc)}


def set_default_config(config_id, target_id=None):
    """Set a global Ntfy configuration as default."""
    try:
        from app import db

        model = get_ntfy_model()
        if not model:
            return {"success": False, "message": "NtfyConfig model not available"}

        config = _global_query(model).filter(model.id == int(config_id)).first()
        if not config:
            return {"success": False, "message": "Configuration not found"}

        _set_default_global(model, config.id)
        config.is_default = True
        db.session.commit()
        return {"success": True}
    except Exception as exc:
        from app import db

        db.session.rollback()
        logger.error(f"Error setting default Ntfy configuration {config_id}: {exc}")
        return {"success": False, "message": str(exc)}


def get_default_config(target_id=None):
    """Return the default global Ntfy configuration."""
    try:
        model = get_ntfy_model()
        if not model:
            return None

        config = _global_query(model).filter_by(is_default=True).first() or _global_query(model).order_by(model.id.asc()).first()
        return config.to_dict() if config else None
    except Exception as exc:
        logger.error(f"Error getting default Ntfy configuration: {exc}")
        return None


def is_event_notification_enabled(event_type, target_id=None):
    """Check if Ntfy is enabled for one event in the selected target scope."""
    settings = get_notification_settings(target_id=target_id)
    item = settings.get(_normalize_event_type(event_type), {})
    return bool(item.get('enabled'))


def save_notification_setting(setting_data, target_id=None):
    """Save per-event Ntfy routing in the selected target scope."""
    try:
        from app import db

        model = get_ntfy_model()
        notification_model = get_notification_model()
        if not model or not notification_model:
            return {"success": False, "message": "Notification models not available"}

        event_type = _normalize_event_type(setting_data.get('event_type'))
        enabled = bool(setting_data.get('enabled', False))
        config_id = setting_data.get('config_id')

        if event_type not in _EVENT_TYPES:
            return {"success": False, "message": f"Unsupported event type: {event_type}"}

        selected_id = None
        if enabled:
            try:
                selected_id = int(config_id)
            except (TypeError, ValueError):
                return {"success": False, "message": "Configuration ID is required when enabling notification"}

            exists = _global_query(model).filter(model.id == selected_id).first()
            if not exists:
                return {"success": False, "message": f"Configuration ID {selected_id} not found"}

        row, scoped_target_id = _resolve_notification_row(
            notification_model,
            event_type,
            target_id=target_id,
            create_missing=True,
        )

        if hasattr(row, 'id_ntfy'):
            row.id_ntfy = selected_id
        if hasattr(row, 'ntfy_enabled'):
            row.ntfy_enabled = bool(enabled and selected_id)

        db.session.commit()
        return {
            "success": True,
            "target_id": scoped_target_id,
            "message": f"Notification for {event_type} updated",
        }
    except Exception as exc:
        from app import db

        db.session.rollback()
        logger.error(f"Error saving Ntfy notification setting: {exc}")
        return {"success": False, "message": str(exc)}


def get_notification_settings(target_id=None):
    """Return event-to-config Ntfy routing map for the selected target scope."""
    try:
        notification_model = get_notification_model()
        if not notification_model:
            return {}

        query, _ = _notification_scoped_query(notification_model, target_id)
        rows = {
            str(row.event_type or '').upper(): row
            for row in query.all()
            if str(row.event_type or '').strip()
        }

        settings = {}
        for event_type in _EVENT_TYPES:
            row = rows.get(event_type)
            enabled = bool(getattr(row, 'ntfy_enabled', False)) if row else False
            config_id = getattr(row, 'id_ntfy', None) if row else None
            settings[event_type] = {
                'enabled': bool(enabled and config_id),
                'config_id': str(config_id) if (enabled and config_id) else '',
                'event_type': event_type,
            }
        return settings
    except Exception as exc:
        logger.error(f"Error getting Ntfy notification settings: {exc}")
        return {}


def get_config_for_event(event_type, target_id=None):
    """Return the selected Ntfy config for an event in one target scope."""
    settings = get_notification_settings(target_id=target_id)
    event_key = _normalize_event_type(event_type)
    event_setting = settings.get(event_key, {})
    config_id = event_setting.get('config_id')
    if not event_setting.get('enabled') or not config_id:
        return None

    try:
        return get_config_by_id(int(config_id), target_id=target_id)
    except (TypeError, ValueError):
        return None
