"""
API routes for webhook configuration and management.
"""

from flask import Blueprint, request, jsonify
from core.auth import require_admin
from core.logger import webhook_logger as logger

def create_blueprint():
    """Create and return the blueprint to avoid circular imports"""
    webhook_bp = Blueprint('webhook', __name__)
    
    @webhook_bp.route('/api/webhook/configs', methods=['GET'])
    @require_admin
    def get_webhook_configs():
        logger.info("API: Fetching all webhook configurations")
        from core.extranotifs.webhook.db import get_configs_from_db
        configs = get_configs_from_db()
        return jsonify({"success": True, "configs": configs})
    
    @webhook_bp.route('/api/webhook/config/<int:config_id>', methods=['GET', 'DELETE', 'POST'])
    @require_admin
    def webhook_config_endpoint(config_id):
        if request.method == 'GET':
            logger.info(f"API: Fetching webhook configuration {config_id}")
            from core.extranotifs.webhook.db import get_config_by_id
            config = get_config_by_id(config_id)
            if config:
                return jsonify({"success": True, "config": config})
            logger.warning(f"API: Webhook configuration {config_id} not found")
            return jsonify({"success": False, "message": "Configuration not found"}), 404
        elif request.method == 'DELETE':
            logger.info(f"API: Deleting webhook configuration {config_id}")
            from core.extranotifs.webhook.db import delete_config
            result = delete_config(config_id)
            if result.get("success"):
                logger.info(f"API: Webhook configuration {config_id} deleted successfully")
            else:
                logger.error(f"API: Error deleting webhook configuration {config_id}: {result.get('message')}")
            return jsonify(result)
        elif request.method == 'POST':
            logger.info(f"API: Updating webhook configuration {config_id}")
            from core.extranotifs.webhook.db import save_config
            from core.extranotifs.webhook.db import get_config_by_id
            
            # Get existing config
            existing_config = get_config_by_id(config_id)
            if not existing_config:
                logger.warning(f"API: Webhook configuration {config_id} not found for update")
                return jsonify({"success": False, "message": "Configuration not found"}), 404
                
            # Prepare update data - merged with only the fields from the request
            update_data = request.json
            update_data['id'] = config_id  # Ensure ID is set
            
            # Save the updated config
            result = save_config(update_data)
            if result.get("success"):
                logger.info(f"API: Webhook configuration {config_id} updated successfully")
            else:
                logger.error(f"API: Error updating webhook configuration {config_id}: {result.get('message')}")
            return jsonify(result)
    
    @webhook_bp.route('/api/webhook/config', methods=['POST'])
    @require_admin
    def save_webhook_config():
        logger.info("API: Saving webhook configuration")
        from core.extranotifs.webhook.db import save_config
        config_data = request.json
        result = save_config(config_data)
        if result.get("success"):
            logger.info(f"API: Webhook configuration saved successfully: {result.get('config', {}).get('id')}")
        else:
            logger.error(f"API: Error saving webhook configuration: {result.get('message')}")
        return jsonify(result)
    
    @webhook_bp.route('/api/webhook/config/<int:config_id>/default', methods=['POST'])
    @require_admin
    def set_default_webhook_config(config_id):
        logger.info(f"API: Setting webhook configuration {config_id} as default")
        from core.extranotifs.webhook.db import set_default_config
        result = set_default_config(config_id)
        return jsonify(result)
    
    @webhook_bp.route('/api/webhook/test', methods=['POST'])
    @require_admin
    def test_webhook():
        event_type = request.args.get('event_type')
        logger.info(f"API: Testing webhook with event type {event_type}")
        from core.extranotifs.webhook.webhook import test_notification
        config_data = request.json or {}
        if isinstance(config_data, dict) and request.args.get('target_id'):
            config_data['target_id'] = request.args.get('target_id')
        result = test_notification(config_data, event_type)
        if result.get("success"):
            logger.info(f"API: Webhook test completed successfully")
        else:
            logger.error(f"API: Webhook test failed: {result.get('message')}")
        return jsonify(result)
    
    @webhook_bp.route('/api/webhook/test/<int:config_id>', methods=['POST'])
    @require_admin
    def test_webhook_config(config_id):
        event_type = request.args.get('event_type')
        logger.info(f"API: Testing webhook configuration {config_id} with event type {event_type}")
        from core.extranotifs.webhook.db import get_config_by_id
        from core.extranotifs.webhook.webhook import test_notification
        
        config = get_config_by_id(config_id, include_secrets=True)
        
        if not config:
            logger.warning(f"API: Webhook configuration {config_id} not found for testing")
            return jsonify({"success": False, "message": "Configuration not found"}), 404

        if isinstance(config, dict) and request.args.get('target_id'):
            config['target_id'] = request.args.get('target_id')
        
        result = test_notification(config, event_type)
        if result.get("success"):
            logger.info(f"API: Webhook test for configuration {config_id} completed successfully")
        else:
            logger.error(f"API: Webhook test for configuration {config_id} failed: {result.get('message')}")
        return jsonify(result)
    
    @webhook_bp.route('/api/webhook/send', methods=['POST'])
    @require_admin
    def send_webhook_notification():
        """Send a webhook notification manually for testing"""
        data = request.json
        event_type = data.get('event_type')
        ups_name = data.get('ups_name')
        
        logger.info(f"API: Manually sending webhook notification for event {event_type}")
        
        from core.extranotifs.webhook.webhook import send_event_notification
        
        if not event_type:
            logger.warning("API: Event type missing in webhook send request")
            return jsonify({"success": False, "message": "Event type is required"}), 400
            
        result = send_event_notification(event_type, ups_name)
        if result.get("success"):
            logger.info(f"API: Webhook notification sent successfully for event {event_type}")
        else:
            logger.error(f"API: Error sending webhook notification for event {event_type}: {result.get('message')}")
        return jsonify(result)

    @webhook_bp.route('/api/webhook/settings', methods=['GET'])
    @require_admin
    def get_webhook_settings():
        from core.extranotifs.webhook.db import get_notification_settings

        settings = get_notification_settings(target_id=request.args.get('target_id', type=int))
        return jsonify({"success": True, "settings": settings})

    @webhook_bp.route('/api/webhook/setting', methods=['POST'])
    @require_admin
    def save_webhook_setting():
        from core.extranotifs.webhook.db import save_notification_setting

        result = save_notification_setting(
            request.json or {},
            target_id=request.args.get('target_id', type=int),
        )
        return jsonify(result)
    
    return webhook_bp 
