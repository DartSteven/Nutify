"""Database access helpers for Telegram configurations."""

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

_VALID_PARSE_MODES = {'HTML', 'MARKDOWN', 'MARKDOWNV2', 'NONE'}


def _normalize_event_type(value) -> str:
    event_type = str(value or '').strip().upper()
    if event_type == 'FSD':
        return 'SHUTDOWN'
    return event_type


def _normalize_parse_mode(value) -> str:
    parse_mode = str(value or '').strip().upper()
    if parse_mode in _VALID_PARSE_MODES:
        return parse_mode
    return 'HTML'


def _normalize_channel_modes(render_mode_value, parse_mode_value):
    render_mode = normalize_render_mode(render_mode_value)
    parse_mode = _normalize_parse_mode(parse_mode_value)
    if render_mode == 'graphic':
        parse_mode = 'HTML'
    return render_mode, parse_mode


def get_telegram_model():
    """Return TelegramConfig model from central db registry."""
    try:
        from app import db
    except Exception as exc:
        logger.error(f"Error loading db in Telegram module: {exc}")
        return None

    if hasattr(db, 'ModelClasses') and hasattr(db.ModelClasses, 'TelegramConfig'):
        return db.ModelClasses.TelegramConfig

    logger.warning("TelegramConfig model is not available in db.ModelClasses")
    return None


def get_notification_model():
    """Return NotificationSettings model from central db registry."""
    try:
        from app import db
    except Exception as exc:
        logger.error(f"Error loading db in Telegram module: {exc}")
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


def _config_to_dict(config, include_secrets=False):
    data = config.to_dict()
    if include_secrets:
        data['bot_token'] = str(config.bot_token or '')
        data['chat_id'] = str(config.chat_id or '')
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


def get_configs_from_db(target_id=None, include_secrets=False):
    """Return all global Telegram configurations."""
    try:
        model = get_telegram_model()
        if not model:
            return []

        rows = _global_query(model).order_by(model.is_default.desc(), model.id.asc()).all()
        return [_config_to_dict(row, include_secrets=include_secrets) for row in rows]
    except Exception as exc:
        logger.error(f"Error fetching Telegram configurations: {exc}")
        return []


def get_config_by_id(config_id, target_id=None, include_secrets=False):
    """Return one global Telegram configuration."""
    try:
        model = get_telegram_model()
        if not model:
            return None

        row = _global_query(model).filter(model.id == int(config_id)).first()
        return _config_to_dict(row, include_secrets=include_secrets) if row else None
    except Exception as exc:
        logger.error(f"Error fetching Telegram configuration {config_id}: {exc}")
        return None


def save_config(config_data, target_id=None):
    """Create or update one global Telegram configuration."""
    try:
        from app import db

        model = get_telegram_model()
        if not model:
            return {"success": False, "message": "TelegramConfig model not available"}

        config_id = config_data.get('id')

        if config_id:
            config = _global_query(model).filter(model.id == int(config_id)).first()
            if not config:
                return {"success": False, "message": "Configuration not found"}

            config_render_mode, parse_mode = _normalize_channel_modes(
                config_data.get('render_mode', config.render_mode),
                config_data.get('parse_mode', config.parse_mode),
            )

            if config_data.get('bot_token') == '********':
                config_data.pop('bot_token', None)
            if config_data.get('chat_id') == '********':
                config_data.pop('chat_id', None)

            config.display_name = str(config_data.get('name') or config_data.get('display_name') or config.display_name)
            config.parse_mode = parse_mode
            config.disable_web_preview = bool(config_data.get('disable_web_preview', config.disable_web_preview))
            config.render_mode = config_render_mode

            if 'bot_token' in config_data:
                config.bot_token = str(config_data.get('bot_token') or '').strip()
            if 'chat_id' in config_data:
                config.chat_id = str(config_data.get('chat_id') or '').strip()

            if hasattr(config, 'target_id'):
                config.target_id = None

            if config_data.get('is_default'):
                _set_default_global(model, config.id)
                config.is_default = True

            db.session.commit()
            return {"success": True, "config": get_config_by_id(config.id)}

        bot_token = str(config_data.get('bot_token') or '').strip()
        chat_id = str(config_data.get('chat_id') or '').strip()
        if not bot_token:
            return {"success": False, "message": "Telegram bot token is required"}
        if not chat_id:
            return {"success": False, "message": "Telegram chat ID is required"}

        config_render_mode, parse_mode = _normalize_channel_modes(
            config_data.get('render_mode'),
            config_data.get('parse_mode', 'HTML'),
        )

        new_config = model(
            target_id=None,
            display_name=str(config_data.get('name') or config_data.get('display_name') or 'Telegram').strip() or 'Telegram',
            bot_token=bot_token,
            chat_id=chat_id,
            parse_mode=parse_mode,
            disable_web_preview=bool(config_data.get('disable_web_preview', False)),
            render_mode=config_render_mode,
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
        logger.error(f"Error saving Telegram configuration: {exc}")
        return {"success": False, "message": str(exc)}


def delete_config(config_id, target_id=None):
    """Delete one global Telegram configuration."""
    try:
        from app import db

        model = get_telegram_model()
        if not model:
            return {"success": False, "message": "TelegramConfig model not available"}

        config = _global_query(model).filter(model.id == int(config_id)).first()
        if not config:
            return {"success": False, "message": "Configuration not found"}

        was_default = bool(config.is_default)

        notification_model = get_notification_model()
        if notification_model is not None and hasattr(notification_model, 'id_telegram'):
            rows = notification_model.query.filter(notification_model.id_telegram == int(config_id)).all()
            for row in rows:
                row.id_telegram = None
                if hasattr(row, 'telegram_enabled'):
                    row.telegram_enabled = False

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
        logger.error(f"Error deleting Telegram configuration {config_id}: {exc}")
        return {"success": False, "message": str(exc)}


def set_default_config(config_id, target_id=None):
    """Set one global Telegram configuration as default."""
    try:
        from app import db

        model = get_telegram_model()
        if not model:
            return {"success": False, "message": "TelegramConfig model not available"}

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
        logger.error(f"Error setting default Telegram configuration {config_id}: {exc}")
        return {"success": False, "message": str(exc)}


def get_default_config(target_id=None):
    """Return the default global Telegram configuration."""
    try:
        model = get_telegram_model()
        if not model:
            return None

        config = _global_query(model).filter_by(is_default=True).first() or _global_query(model).order_by(model.id.asc()).first()
        return config.to_dict() if config else None
    except Exception as exc:
        logger.error(f"Error getting default Telegram configuration: {exc}")
        return None


def save_notification_setting(setting_data, target_id=None):
    """Save per-event Telegram routing in the selected target scope."""
    try:
        from app import db

        model = get_telegram_model()
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

        if hasattr(row, 'id_telegram'):
            row.id_telegram = selected_id
        if hasattr(row, 'telegram_enabled'):
            row.telegram_enabled = bool(enabled and selected_id)

        db.session.commit()
        return {
            "success": True,
            "target_id": scoped_target_id,
            "message": f"Notification for {event_type} updated",
        }
    except Exception as exc:
        from app import db

        db.session.rollback()
        logger.error(f"Error saving Telegram notification setting: {exc}")
        return {"success": False, "message": str(exc)}


def get_notification_settings(target_id=None):
    """Return event-to-config Telegram routing map for selected target scope."""
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
            enabled = bool(getattr(row, 'telegram_enabled', False)) if row else False
            config_id = getattr(row, 'id_telegram', None) if row else None
            settings[event_type] = {
                'enabled': bool(enabled and config_id),
                'config_id': str(config_id) if (enabled and config_id) else '',
                'event_type': event_type,
            }
        return settings
    except Exception as exc:
        logger.error(f"Error getting Telegram notification settings: {exc}")
        return {}


def get_config_for_event(event_type, target_id=None, include_secrets=False):
    """Return selected Telegram config for one event in selected target scope."""
    settings = get_notification_settings(target_id=target_id)
    event_key = _normalize_event_type(event_type)
    event_setting = settings.get(event_key, {})
    config_id = event_setting.get('config_id')
    if not event_setting.get('enabled') or not config_id:
        return None

    try:
        return get_config_by_id(int(config_id), target_id=target_id, include_secrets=include_secrets)
    except (TypeError, ValueError):
        return None
