"""API routes for Telegram configuration and management."""

from flask import Blueprint, request, jsonify
from core.auth import require_admin


def create_blueprint():
    """Create and return Telegram blueprint."""
    telegram_bp = Blueprint('telegram', __name__)

    @telegram_bp.route('/api/telegram/configs', methods=['GET'])
    @require_admin
    def get_telegram_configs():
        from core.extranotifs.telegram.db import get_configs_from_db

        configs = get_configs_from_db()
        return jsonify({"success": True, "configs": configs})

    @telegram_bp.route('/api/telegram/config/<int:config_id>', methods=['GET'])
    @require_admin
    def get_telegram_config(config_id):
        from core.extranotifs.telegram.db import get_config_by_id

        config = get_config_by_id(config_id)
        if config:
            return jsonify({"success": True, "config": config})
        return jsonify({"success": False, "message": "Configuration not found"}), 404

    @telegram_bp.route('/api/telegram/config', methods=['POST'])
    @require_admin
    def save_telegram_config():
        from core.extranotifs.telegram.db import save_config

        result = save_config(request.json or {})
        return jsonify(result)

    @telegram_bp.route('/api/telegram/config/<int:config_id>', methods=['DELETE'])
    @require_admin
    def delete_telegram_config(config_id):
        from core.extranotifs.telegram.db import delete_config

        result = delete_config(config_id)
        return jsonify(result)

    @telegram_bp.route('/api/telegram/config/<int:config_id>/default', methods=['POST'])
    @require_admin
    def set_default_telegram_config(config_id):
        from core.extranotifs.telegram.db import set_default_config

        result = set_default_config(config_id)
        return jsonify(result)

    @telegram_bp.route('/api/telegram/test', methods=['POST'])
    @require_admin
    def test_telegram():
        from core.extranotifs.telegram.telegram import test_notification

        event_type = request.args.get('event_type')
        config = request.json or {}
        if isinstance(config, dict) and request.args.get('target_id'):
            config['target_id'] = request.args.get('target_id')
        result = test_notification(config, event_type=event_type)
        return jsonify(result)

    @telegram_bp.route('/api/telegram/test/<int:config_id>', methods=['POST'])
    @require_admin
    def test_telegram_config(config_id):
        from core.extranotifs.telegram.db import get_config_by_id
        from core.extranotifs.telegram.telegram import test_notification

        config = get_config_by_id(config_id, include_secrets=True)
        if not config:
            return jsonify({"success": False, "message": "Configuration not found"}), 404

        event_type = request.args.get('event_type')
        if isinstance(config, dict) and request.args.get('target_id'):
            config['target_id'] = request.args.get('target_id')
        result = test_notification(config, event_type=event_type)
        return jsonify(result)

    @telegram_bp.route('/api/telegram/settings', methods=['GET'])
    @require_admin
    def get_telegram_settings():
        from core.extranotifs.telegram.db import get_notification_settings

        settings = get_notification_settings()
        return jsonify({"success": True, "settings": settings})

    @telegram_bp.route('/api/telegram/setting', methods=['POST'])
    @require_admin
    def save_telegram_setting():
        from core.extranotifs.telegram.db import save_notification_setting

        result = save_notification_setting(request.json or {})
        return jsonify(result)

    return telegram_bp
