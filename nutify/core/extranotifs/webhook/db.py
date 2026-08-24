"""Database access helpers for webhook configurations."""

from __future__ import annotations

import json

from core.extranotifs.webhook import get_webhook_model as get_webhook_model_from_init
from core.logger import webhook_logger as logger
from core.notifications import normalize_render_mode
from core.multi_nut.target_scope import resolve_settings_target_id

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


def get_webhook_model():
    """Return WebhookConfig model from the central db registry."""
    return get_webhook_model_from_init()


def get_notification_model():
    """Return NotificationSettings model from central db registry."""
    try:
        from app import db
    except Exception as exc:
        logger.error(f"Error loading db in Webhook module: {exc}")
        return None

    if hasattr(db, 'ModelClasses') and hasattr(db.ModelClasses, 'NotificationSettings'):
        return db.ModelClasses.NotificationSettings

    logger.warning("NotificationSettings model not available in db.ModelClasses")
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


def _config_to_dict(config, include_secrets=False):
    """Serialize a webhook config, exposing secrets only to runtime callers."""
    data = config.to_dict()
    if include_secrets:
        data['auth_password'] = str(config.auth_password or '')
        data['auth_token'] = str(config.auth_token or '')
    return data


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
    """Return all global webhook configurations."""
    try:
        model = get_webhook_model()
        if not model:
            logger.error("WebhookConfig model not available")
            return []

        configs = _global_query(model).order_by(model.is_default.desc(), model.id.asc()).all()
        return [config.to_dict() for config in configs]
    except Exception as exc:
        logger.error(f"Error fetching webhook configurations: {exc}")
        return []


def get_config_by_id(config_id, target_id=None, include_secrets=False):
    """Return one global webhook configuration."""
    try:
        model = get_webhook_model()
        if not model:
            logger.error("WebhookConfig model not available")
            return None

        config = _global_query(model).filter(model.id == int(config_id)).first()
        return _config_to_dict(config, include_secrets=include_secrets) if config else None
    except Exception as exc:
        logger.error(f"Error fetching webhook configuration {config_id}: {exc}")
        return None


def get_default_config(target_id=None, include_secrets=False):
    """Return default global webhook configuration."""
    try:
        model = get_webhook_model()
        if not model:
            logger.error("WebhookConfig model not available")
            return None

        config = _global_query(model).filter_by(is_default=True).first() or _global_query(model).order_by(model.id.asc()).first()
        return _config_to_dict(config, include_secrets=include_secrets) if config else None
    except Exception as exc:
        logger.error(f"Error fetching default webhook configuration: {exc}")
        return None


def save_config(config_data, target_id=None):
    """Create or update one global webhook configuration."""
    try:
        from app import db

        model = get_webhook_model()
        if not model:
            logger.error("WebhookConfig model not available")
            return {"success": False, "message": "WebhookConfig model not available"}

        config_id = config_data.get('id')

        if config_id:
            config = _global_query(model).filter(model.id == int(config_id)).first()
            if not config:
                return {"success": False, "message": "Configuration not found"}

            if config_data.get('auth_password') == '********':
                config_data.pop('auth_password', None)
            if config_data.get('auth_token') == '********':
                config_data.pop('auth_token', None)

            if 'custom_headers' in config_data and isinstance(config_data['custom_headers'], dict):
                config_data['custom_headers'] = json.dumps(config_data['custom_headers'])

            config.display_name = config_data.get('name', config.display_name)
            config.url = config_data.get('url', config.url)
            config.server_type = config_data.get('server_type', config.server_type or 'custom')
            config.auth_type = config_data.get('auth_type', config.auth_type)
            config.auth_username = config_data.get('auth_username', config.auth_username)
            if 'auth_password' in config_data:
                config.auth_password = config_data.get('auth_password')
            if 'auth_token' in config_data:
                config.auth_token = config_data.get('auth_token')
            config.content_type = config_data.get('content_type', config.content_type)
            if 'custom_headers' in config_data:
                config.custom_headers = config_data.get('custom_headers')
            config.render_mode = normalize_render_mode(config_data.get('render_mode', config.render_mode))
            config.include_ups_data = bool(config_data.get('include_ups_data', config.include_ups_data))
            config.verify_ssl = bool(config_data.get('verify_ssl', config.verify_ssl))

            if hasattr(config, 'target_id'):
                config.target_id = None

            if config_data.get('is_default'):
                _set_default_global(model, config.id)
                config.is_default = True

            db.session.commit()
            return {"success": True, "config": get_config_by_id(config.id)}

        if 'custom_headers' in config_data and isinstance(config_data['custom_headers'], dict):
            config_data['custom_headers'] = json.dumps(config_data['custom_headers'])

        new_config = model(
            target_id=None,
            display_name=config_data.get('name', 'New Webhook'),
            url=config_data.get('url', ''),
            server_type=config_data.get('server_type', 'custom'),
            auth_type=config_data.get('auth_type', 'none'),
            auth_username=config_data.get('auth_username', ''),
            auth_password=config_data.get('auth_password', ''),
            auth_token=config_data.get('auth_token', ''),
            content_type=config_data.get('content_type', 'application/json'),
            custom_headers=config_data.get('custom_headers', ''),
            render_mode=normalize_render_mode(config_data.get('render_mode')),
            include_ups_data=bool(config_data.get('include_ups_data', True)),
            verify_ssl=bool(config_data.get('verify_ssl', False)),
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
        logger.error(f"Error saving webhook configuration: {exc}")
        return {"success": False, "message": str(exc)}


def delete_config(config_id, target_id=None):
    """Delete one global webhook configuration."""
    try:
        from app import db

        model = get_webhook_model()
        if not model:
            return {"success": False, "message": "WebhookConfig model not available"}

        config = _global_query(model).filter(model.id == int(config_id)).first()
        if not config:
            return {"success": False, "message": "Configuration not found"}

        was_default = bool(config.is_default)

        notification_model = get_notification_model()
        if notification_model is not None and hasattr(notification_model, 'id_webhook'):
            rows = notification_model.query.filter(notification_model.id_webhook == int(config_id)).all()
            for row in rows:
                row.id_webhook = None
                if hasattr(row, 'webhook_enabled'):
                    row.webhook_enabled = False

        db.session.delete(config)
        db.session.commit()

        if was_default:
            remaining = _global_query(model).order_by(model.id.asc()).first()
            if remaining:
                remaining.is_default = True
                db.session.commit()

        return {"success": True, "message": "Configuration deleted successfully"}
    except Exception as exc:
        logger.error(f"Error deleting webhook configuration: {exc}")
        return {"success": False, "message": str(exc)}


def set_default_config(config_id, target_id=None):
    """Set one global webhook configuration as default."""
    try:
        from app import db

        model = get_webhook_model()
        if not model:
            return {"success": False, "message": "WebhookConfig model not available"}

        config = _global_query(model).filter(model.id == int(config_id)).first()
        if not config:
            return {"success": False, "message": "Configuration not found"}

        _set_default_global(model, config.id)
        config.is_default = True
        db.session.commit()
        return {"success": True, "message": "Default configuration updated successfully"}
    except Exception as exc:
        logger.error(f"Error setting default webhook configuration: {exc}")
        return {"success": False, "message": str(exc)}


def save_notification_setting(setting_data, target_id=None):
    """Save per-event webhook routing in selected target scope."""
    try:
        from app import db

        model = get_webhook_model()
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

        if hasattr(row, 'id_webhook'):
            row.id_webhook = selected_id
        if hasattr(row, 'webhook_enabled'):
            row.webhook_enabled = bool(enabled and selected_id)

        db.session.commit()
        return {
            "success": True,
            "target_id": scoped_target_id,
            "message": f"Notification for {event_type} updated",
        }
    except Exception as exc:
        from app import db

        db.session.rollback()
        logger.error(f"Error saving webhook notification setting: {exc}")
        return {"success": False, "message": str(exc)}


def get_notification_settings(target_id=None):
    """Return event-to-config webhook routing map for selected target scope."""
    try:
        notification_model = get_notification_model()
        if not notification_model:
            return {}

        query, _ = _notification_scoped_query(notification_model, target_id)
        scoped_rows = query.all()
        rows = {
            str(row.event_type or '').upper(): row
            for row in scoped_rows
            if str(row.event_type or '').strip()
        }
        # Compatibility fallback: old databases may have target-scoped rows even in single profile.
        if not rows and target_id is not None and hasattr(notification_model, 'target_id'):
            try:
                legacy_rows = (
                    notification_model.query
                    .filter(notification_model.target_id == int(target_id))
                    .all()
                )
                rows = {
                    str(row.event_type or '').upper(): row
                    for row in legacy_rows
                    if str(row.event_type or '').strip()
                }
            except Exception:
                pass

        settings = {}
        for event_type in _EVENT_TYPES:
            row = rows.get(event_type)
            enabled = bool(getattr(row, 'webhook_enabled', False)) if row else False
            config_id = getattr(row, 'id_webhook', None) if row else None
            settings[event_type] = {
                'enabled': bool(enabled and config_id),
                'config_id': str(config_id) if (enabled and config_id) else '',
                'event_type': event_type,
            }
        return settings
    except Exception as exc:
        logger.error(f"Error getting webhook notification settings: {exc}")
        return {}


def get_enabled_configs_for_event(event_type, target_id=None):
    """Return selected webhook config for one event in selected target scope."""
    try:
        model = get_webhook_model()
        if not model:
            logger.error("WebhookConfig model not available")
            return []

        event_key = _normalize_event_type(event_type)
        settings = get_notification_settings(target_id=target_id)
        event_setting = settings.get(event_key, {})
        config_id = event_setting.get('config_id')

        if event_setting.get('enabled') and config_id:
            config = _global_query(model).filter(model.id == int(config_id)).first()
            if config:
                return [_config_to_dict(config, include_secrets=True)]
            else:
                logger.warning(f"Webhook config id={config_id} not found for event {event_key}")
        return []
    except Exception as exc:
        logger.error(f"Error getting webhook configs for event {event_type}: {exc}")
        return []
