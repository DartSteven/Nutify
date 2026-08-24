"""Extranotifs Module.

Implements core runtime logic and helpers used by this feature.
"""

from flask import Blueprint, request, jsonify
from core.auth import require_admin

def create_blueprint():
    """Create and return the blueprint to avoid circular imports"""
    ntfy_bp = Blueprint('ntfy', __name__)
    
    @ntfy_bp.route('/api/ntfy/configs', methods=['GET'])
    @require_admin
    def get_ntfy_configs():
        from core.extranotifs.ntfy.db import get_configs_from_db
        configs = get_configs_from_db()
        return jsonify({"success": True, "configs": configs})
    
    @ntfy_bp.route('/api/ntfy/config/<int:config_id>', methods=['GET'])
    @require_admin
    def get_ntfy_config(config_id):
        from core.extranotifs.ntfy.db import get_config_by_id
        config = get_config_by_id(config_id)
        if config:
            return jsonify({"success": True, "config": config})
        return jsonify({"success": False, "message": "Configuration not found"}), 404
    
    @ntfy_bp.route('/api/ntfy/config', methods=['POST'])
    @require_admin
    def save_ntfy_config():
        from core.extranotifs.ntfy.db import save_config
        config_data = request.json
        result = save_config(config_data)
        return jsonify(result)
    
    @ntfy_bp.route('/api/ntfy/config/<int:config_id>', methods=['DELETE'])
    @require_admin
    def delete_ntfy_config(config_id):
        from core.extranotifs.ntfy.db import delete_config
        result = delete_config(config_id)
        return jsonify(result)
    
    @ntfy_bp.route('/api/ntfy/config/<int:config_id>/default', methods=['POST'])
    @require_admin
    def set_default_ntfy_config(config_id):
        from core.extranotifs.ntfy.db import set_default_config
        result = set_default_config(config_id)
        return jsonify(result)
    
    @ntfy_bp.route('/api/ntfy/test', methods=['POST'])
    @require_admin
    def test_ntfy():
        from core.extranotifs.ntfy.ntfy import test_notification
        config_data = request.json
        if isinstance(config_data, dict) and request.args.get('target_id'):
            config_data['target_id'] = request.args.get('target_id')
        result = test_notification(config_data)
        return jsonify(result)
    
    @ntfy_bp.route('/api/ntfy/test/<int:config_id>', methods=['POST'])
    @require_admin
    def test_ntfy_config(config_id):
        from core.extranotifs.ntfy.db import get_config_by_id
        from core.extranotifs.ntfy.ntfy import test_notification
        
        event_type = request.args.get('event_type')
        config = get_config_by_id(config_id)
        if isinstance(config, dict) and request.args.get('target_id'):
            config['target_id'] = request.args.get('target_id')
        
        if not config:
            return jsonify({"success": False, "message": "Configuration not found"}), 404
        
        result = test_notification(config, event_type)
        return jsonify(result)
    
    @ntfy_bp.route('/api/ntfy/settings', methods=['GET'])
    @require_admin
    def get_ntfy_settings():
        from core.extranotifs.ntfy.db import get_notification_settings
        settings = get_notification_settings()
        return jsonify({"success": True, "settings": settings})
    
    @ntfy_bp.route('/api/ntfy/setting', methods=['POST'])
    @require_admin
    def save_ntfy_setting():
        from core.extranotifs.ntfy.db import save_notification_setting
        setting_data = request.json
        result = save_notification_setting(setting_data)
        return jsonify(result)
    
    return ntfy_bp 
