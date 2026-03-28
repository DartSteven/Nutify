"""Mail API Module.

Defines API endpoints and response handlers for this feature domain.
"""

from flask import jsonify, request, current_app
from datetime import datetime
from ..db.ups import db, data_lock
from .mail import (
    test_email_config, save_mail_config,
    test_notification, get_current_email_settings
)
from .provider import (
    get_all_providers, get_provider_config, get_provider_list,
    add_provider, update_provider, remove_provider
)
from core.logger import web_logger as logger
from core.multi_nut.target_scope import apply_target_scope, resolve_settings_target_id


def _mail_scoped_query(mail_model, target_id=None):
    query = mail_model.query
    if hasattr(mail_model, "target_id"):
        query = query.filter(mail_model.target_id.is_(None))
    return query, None


def _notification_scoped_query(notification_model, target_id=None):
    scoped_target_id = resolve_settings_target_id(target_id)
    return apply_target_scope(notification_model, notification_model.query, scoped_target_id), scoped_target_id


def _schedule_scoped_query(schedule_model, target_id=None):
    scoped_target_id = resolve_settings_target_id(target_id)
    return apply_target_scope(schedule_model, schedule_model.query, scoped_target_id), scoped_target_id

def register_mail_api_routes(app):
    """Register all email-related API routes."""
    
    @app.route('/api/settings/mail', methods=['GET'])
    def get_mail_config():
        """Return the current email configuration for the active target scope."""
        try:
            logger.debug("Fetching mail config...")
            MailConfig = db.ModelClasses.MailConfig
            query, scoped_target_id = _mail_scoped_query(MailConfig)
            logger.debug(f"Mail scope target_id={scoped_target_id}")
            config = query.order_by(MailConfig.is_default.desc(), MailConfig.id.asc()).first()
            logger.debug(f"Found config: {config}")
            
            if not config:
                logger.info("No mail config found")
                return jsonify({
                    'success': True,
                    'data': None
                })
            
            return jsonify({
                'success': True,
                'data': {
                    'id': config.id,
                    'smtp_server': config.smtp_server or '',
                    'smtp_port': config.smtp_port or '',
                    'username': config.username or '',
                    'enabled': bool(config.enabled),
                    'provider': config.provider or '',
                    'render_mode': getattr(config, 'render_mode', 'graphic') or 'graphic',
                    'tls': bool(config.tls),
                    'tls_starttls': bool(config.tls_starttls),
                    'to_email': config.to_email or ''
                }
            })
        except Exception as e:
            logger.error(f"Error getting mail config: {str(e)}", exc_info=True)
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/settings/mail/providers', methods=['GET'])
    def get_mail_providers():
        """Get all available email providers"""
        try:
            providers = get_all_providers()
            return jsonify({
                'success': True,
                'providers': providers
            })
        except Exception as e:
            logger.error(f"Error getting mail providers: {str(e)}")
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/settings/mail/providers/<provider>', methods=['GET'])
    def get_mail_provider(provider):
        """Get configuration for a specific email provider"""
        try:
            provider_config = get_provider_config(provider)
            if not provider_config:
                return jsonify({'success': False, 'error': 'Provider not found'}), 404
                
            return jsonify({
                'success': True,
                'data': provider_config
            })
        except Exception as e:
            logger.error(f"Error getting mail provider: {str(e)}")
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/settings/mail/providers', methods=['POST'])
    def add_mail_provider():
        """Add a new email provider"""
        try:
            data = request.get_json()
            if not data or 'name' not in data or 'config' not in data:
                return jsonify({'success': False, 'error': 'Missing required fields'}), 400
                
            success = add_provider(data['name'], data['config'])
            if not success:
                return jsonify({'success': False, 'error': 'Failed to add provider'}), 400
                
            return jsonify({
                'success': True,
                'message': 'Provider added successfully'
            })
        except Exception as e:
            logger.error(f"Error adding mail provider: {str(e)}")
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/settings/mail/providers/<provider>', methods=['PUT'])
    def update_mail_provider(provider):
        """Update an existing email provider"""
        try:
            data = request.get_json()
            if not data:
                return jsonify({'success': False, 'error': 'No data provided'}), 400
                
            success = update_provider(provider, data)
            if not success:
                return jsonify({'success': False, 'error': 'Provider not found'}), 404
                
            return jsonify({
                'success': True,
                'message': 'Provider updated successfully'
            })
        except Exception as e:
            logger.error(f"Error updating mail provider: {str(e)}")
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/settings/mail/providers/<provider>', methods=['DELETE'])
    def delete_mail_provider(provider):
        """Delete an email provider"""
        try:
            success = remove_provider(provider)
            if not success:
                return jsonify({'success': False, 'error': 'Provider not found'}), 404
                
            return jsonify({
                'success': True,
                'message': 'Provider deleted successfully'
            })
        except Exception as e:
            logger.error(f"Error deleting mail provider: {str(e)}")
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/settings/mail/test', methods=['POST'])
    def test_mail_config():
        """Test email configuration"""
        try:
            config_data = request.get_json()
            
            # Create sanitized copy for logging
            sanitized_data = config_data.copy()
            if 'smtp_password' in sanitized_data:
                sanitized_data['smtp_password'] = '********'
            if 'password' in sanitized_data:
                sanitized_data['password'] = '********'
                
            logger.debug(f"Testing mail config: {sanitized_data}")
            
            # Map form field names to database field names
            if 'smtp_username' in config_data:
                config_data['username'] = config_data.pop('smtp_username')
            
            if 'smtp_password' in config_data:
                config_data['password'] = config_data.pop('smtp_password')
            
            if 'use_tls' in config_data:
                config_data['tls'] = config_data.pop('use_tls')
            
            if 'use_starttls' in config_data:
                config_data['tls_starttls'] = config_data.pop('use_starttls')
            
            if 'email_provider' in config_data:
                config_data['provider'] = config_data.pop('email_provider')

            config_data['target_id'] = None
            
            # Check if this provider requires a specific sender email
            from core.mail.provider import email_providers
            provider = config_data.get('provider', '')
            provider_key = str(provider or '').strip().lower()
            provider_info = email_providers.get(provider_key, {})
            requires_sender_email = provider_info.get('requires_sender_email', False)
                
            # Only enforce specific from_email for providers that require it
            if requires_sender_email and ('from_email' not in config_data or not config_data['from_email']):
                return jsonify({
                    'success': False,
                    'message': f'Provider {provider} requires a valid verified sender email address in the From Email field'
                })
            
            # Use username as from_email only if not explicitly provided
            if 'username' in config_data and ('from_email' not in config_data or not config_data['from_email']):
                config_data['from_email'] = config_data['username']
                config_data['from_name'] = config_data['username'].split('@')[0] if '@' in config_data['username'] else ''
            
            # Verify to_email is present for test
            if 'to_email' not in config_data or not config_data['to_email']:
                return jsonify({
                    'success': False,
                    'message': 'Please provide an email address to receive the test email'
                })
            
            success, message = test_email_config(config_data)
            return jsonify({
                'success': success,
                'message': message
            })
        except Exception as e:
            logger.error(f"Error testing mail config: {str(e)}")
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/settings/mail', methods=['POST'])
    def save_mail_settings():
        """Save email configuration"""
        try:
            # Get and sanitize data immediately
            config_data = request.get_json()
            sanitized_data = config_data.copy()
            if 'smtp_password' in sanitized_data:
                sanitized_data['smtp_password'] = '********'
            if 'password' in sanitized_data:
                sanitized_data['password'] = '********'
                
            logger.debug(f"Received mail config data: {sanitized_data}")
            
            # Check if this is just an enabled status update
            if config_data.get('update_enabled_only', False):
                # For enabled status updates, we only need the ID and enabled status
                if 'id' not in config_data or 'enabled' not in config_data:
                    return jsonify({'success': False, 'error': 'ID and enabled status are required for status updates'}), 400
                    
                # Perform just the enabled status update
                try:
                    MailConfig = db.ModelClasses.MailConfig
                    query, _ = _mail_scoped_query(MailConfig)
                    config = query.filter(MailConfig.id == int(config_data['id'])).first()
                    
                    if not config:
                        return jsonify({'success': False, 'error': f"Configuration with ID {config_data['id']} not found"}), 404
                        
                    # Update only the enabled status
                    config.enabled = config_data['enabled']
                    db.session.commit()
                    
                    return jsonify({
                        'success': True,
                        'message': f"Configuration {'enabled' if config_data['enabled'] else 'disabled'} successfully",
                        'config_id': config_data['id']
                    })
                except Exception as e:
                    db.session.rollback()
                    logger.error(f"Error updating enabled status: {str(e)}")
                    return jsonify({'success': False, 'error': str(e)}), 500
            
            # Regular save operation (not just enabled status update)
            # Map form field names to database field names
            if 'smtp_username' in config_data:
                config_data['username'] = config_data.pop('smtp_username')
            
            if 'smtp_password' in config_data:
                config_data['password'] = config_data.pop('smtp_password')
            
            if 'use_tls' in config_data:
                config_data['tls'] = config_data.pop('use_tls')
            
            if 'use_starttls' in config_data:
                config_data['tls_starttls'] = config_data.pop('use_starttls')
            
            if 'email_provider' in config_data:
                config_data['provider'] = config_data.pop('email_provider')

            config_data['target_id'] = None
            
            # Save to_email field
            if 'to_email' in config_data:
                logger.debug(f"Saving to_email: {config_data['to_email']}")
            
            # Check if this provider requires a specific sender email
            from core.mail.provider import email_providers
            provider = config_data.get('provider', '')
            provider_key = str(provider or '').strip().lower()
            provider_info = email_providers.get(provider_key, {})
            requires_sender_email = provider_info.get('requires_sender_email', False)
                
            # Only enforce specific from_email for providers that require it
            if requires_sender_email and ('from_email' not in config_data or not config_data['from_email']):
                return jsonify({
                    'success': False,
                    'message': f'Provider {provider} requires a valid verified sender email address in the From Email field'
                }), 400
            
            # Use username as from_email only if not explicitly provided
            if 'username' in config_data and ('from_email' not in config_data or not config_data['from_email']):
                config_data['from_email'] = config_data['username']
                config_data['from_name'] = config_data['username'].split('@')[0] if '@' in config_data['username'] else ''
            
            # If no ID is provided, create a new configuration
            is_new_config = 'id' not in config_data
            scoped_target_id = None
            config_data['target_id'] = None
            if is_new_config:
                # Find the next available ID by checking for gaps
                MailConfig = db.ModelClasses.MailConfig
                
                # Get all existing IDs
                existing_ids = db.session.query(MailConfig.id).order_by(MailConfig.id).all()
                existing_ids = [item[0] for item in existing_ids]
                
                # Find the first available ID starting from 1
                next_id = 1
                while next_id in existing_ids:
                    next_id += 1
                
                config_data['id'] = next_id
                logger.debug(f"Creating new mail config with next available ID: {config_data['id']}")
                
                # Set enabled to True by default for new configurations
                if 'enabled' not in config_data:
                    config_data['enabled'] = True
                    logger.debug("Setting enabled=True for new configuration")
            
            success, result = save_mail_config(config_data)
            
            if not success:
                return jsonify({'success': False, 'error': result}), 500
                
            return jsonify({
                'success': True,
                'message': 'Mail configuration saved successfully',
                'config_id': result
            })
        except Exception as e:
            logger.error(f"Error saving mail config: {str(e)}")
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/settings/mail', methods=['DELETE'])
    def delete_mail_settings():
        """Delete the email configuration in the active target scope."""
        try:
            # Get the current configuration
            MailConfig = db.ModelClasses.MailConfig
            query, _ = _mail_scoped_query(MailConfig)
            config = query.order_by(MailConfig.id.asc()).first()
            
            if not config:
                return jsonify({'success': False, 'error': 'No configuration found'}), 404
                
            # Delete the configuration
            db.session.delete(config)
            db.session.commit()
            
            return jsonify({
                'success': True,
                'message': 'Mail configuration deleted successfully'
            })
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error deleting mail config: {str(e)}")
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/settings/nutify', methods=['GET'])
    def get_nutify_settings():
        """Return notification settings."""
        try:
            NotificationSettings = db.ModelClasses.NotificationSettings
            query, scoped_target_id = _notification_scoped_query(NotificationSettings)
            settings = query.order_by(NotificationSettings.event_type.asc()).all()

            if not settings:
                NotificationSettings.init_notification_settings(scoped_target_id)
                query, _ = _notification_scoped_query(NotificationSettings, scoped_target_id)
                settings = query.order_by(NotificationSettings.event_type.asc()).all()
            
            # Prepare the response
            response = []
            for setting in settings:
                response.append({
                    'id': setting.id,
                    'target_id': getattr(setting, 'target_id', None),
                    'event_type': setting.event_type,
                    'enabled': setting.enabled,
                    'id_email': setting.id_email
                })
                
            return jsonify({
                'success': True,
                'target_id': scoped_target_id,
                'data': response
            })
        except Exception as e:
            logger.error(f"Error getting nutify settings: {str(e)}", exc_info=True)
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/settings/nutify', methods=['POST'])
    def update_nutify_settings():
        """Update notification settings."""
        try:
            data = request.json
            updated = []
            
            with data_lock:
                NotificationSettings = db.ModelClasses.NotificationSettings
                query, scoped_target_id = _notification_scoped_query(NotificationSettings)
                for setting in data:
                    event_type = str(setting['event_type'])
                    nutify = query.filter(NotificationSettings.event_type == event_type).first()
                    
                    if nutify:
                        # Update existing setting
                        nutify.enabled = setting['enabled']
                        nutify.id_email = setting.get('id_email')
                    else:
                        # Create new setting
                        new_setting = NotificationSettings(
                            event_type=event_type,
                            enabled=setting['enabled'],
                            id_email=setting.get('id_email')
                        )
                        if hasattr(new_setting, 'target_id'):
                            new_setting.target_id = scoped_target_id
                        db.session.add(new_setting)
                        
                    updated.append(event_type)
                    
                db.session.commit()
                
            return jsonify({
                'success': True,
                'target_id': scoped_target_id,
                'data': {
                    'updated': updated
                }
            })
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error updating nutify settings: {str(e)}", exc_info=True)
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/settings/nutify/single', methods=['POST'])
    def update_single_nutify_setting():
        """Update one notification setting."""
        try:
            data = request.json
            
            # Validate required fields
            required_fields = ['event_type', 'enabled']
            for field in required_fields:
                if field not in data:
                    return jsonify({
                        'success': False,
                        'error': f"Missing required field: {field}"
                    }), 400
                    
            event_type = data['event_type']
            enabled = data['enabled']
            id_email = data.get('id_email')
            
            with data_lock:
                NotificationSettings = db.ModelClasses.NotificationSettings
                query, scoped_target_id = _notification_scoped_query(NotificationSettings)
                nutify = query.filter(NotificationSettings.event_type == event_type).first()
                
                if nutify:
                    # Update existing setting
                    nutify.enabled = enabled
                    nutify.id_email = id_email
                else:
                    # Create new setting
                    new_setting = NotificationSettings(
                        event_type=event_type,
                        enabled=enabled,
                        id_email=id_email
                    )
                    if hasattr(new_setting, 'target_id'):
                        new_setting.target_id = scoped_target_id
                    db.session.add(new_setting)
                    
                db.session.commit()
                
            return jsonify({
                'success': True,
                'target_id': scoped_target_id,
                'data': {
                    'event_type': event_type,
                    'enabled': enabled,
                    'id_email': id_email
                }
            })
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error updating single nutify setting: {str(e)}", exc_info=True)
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/settings/mail/<int:config_id>', methods=['DELETE'])
    def delete_mail_config(config_id):
        """Delete an email configuration and all associated records"""
        try:
            MailConfig = db.ModelClasses.MailConfig
            query, _ = _mail_scoped_query(MailConfig)
            config = query.filter(MailConfig.id == int(config_id)).first()
            
            if not config:
                return jsonify({'success': False, 'error': f"Configuration with ID {config_id} not found"}), 404
                
            with data_lock:
                # 1. Delete associated notification settings
                NotificationSettings = db.ModelClasses.NotificationSettings
                notification_settings = NotificationSettings.query.filter(
                    NotificationSettings.id_email == config_id
                ).all()
                
                logger.info(f"Found {len(notification_settings)} notification settings associated with mail config ID {config_id}")
                
                # Update notification settings to use null id_email
                for setting in notification_settings:
                    logger.info(f"Resetting id_email to null for notification setting: {setting.event_type}")
                    setting.id_email = None
                    setting.enabled = False
                
                # 2. Delete associated report schedules
                if hasattr(db.ModelClasses, 'ReportSchedule'):
                    ReportSchedule = db.ModelClasses.ReportSchedule
                    schedule_query = ReportSchedule.query
                    
                    # Find and log report schedules that use this mail_config_id
                    config_schedules = schedule_query.filter(ReportSchedule.mail_config_id == config_id).all()
                    
                    # Log details before deletion
                    if config_schedules:
                        logger.info(f"Found {len(config_schedules)} report schedules with mail_config_id={config_id}")
                        for schedule in config_schedules:
                            logger.info(f"Will delete report schedule ID {schedule.id} with mail_config_id={config_id}")
                            logger.info(f"Schedule details: time={schedule.time}, days={schedule.days}, reports={schedule.reports}")
                            db.session.delete(schedule)
                    else:
                        logger.info(f"No report schedules found with mail_config_id={config_id}")

                    # Commit changes after deleting schedules
                    db.session.commit()
                    
                    # Verify deletion
                    remaining = schedule_query.filter(ReportSchedule.mail_config_id == config_id).count()
                    if remaining > 0:
                        logger.warning(f"After deletion, still found {remaining} schedules with mail_config_id={config_id}")
                    else:
                        logger.info("All associated report schedules successfully deleted")
                        
                else:
                    logger.warning("ReportSchedule model not available, skipping report schedule cleanup")
                
                # 3. Delete the email configuration itself
                logger.info(f"Deleting mail configuration with ID {config_id}")
                db.session.delete(config)
                db.session.commit()
                
                # 4. Check if this was the last email configuration and reset sequence if needed
                remaining_configs = query.count()
                logger.info(f"📧 {remaining_configs} email configurations remaining after deletion")
                
                if remaining_configs == 0:
                    logger.info("🔄 All email configurations have been deleted, will reset sequence for new configurations")
                    
                    # Reset the SQLite sequence for the mail config table
                    try:
                        # Import text function from SQLAlchemy
                        from sqlalchemy import text
                        
                        # First check if sqlite_sequence table exists
                        result = db.session.execute(
                            text("SELECT name FROM sqlite_master WHERE type='table' AND name='sqlite_sequence'")
                        ).fetchone()
                        
                        if result:
                            # Check if our table is in the sequence table
                            sequence_result = db.session.execute(
                                text("SELECT seq FROM sqlite_sequence WHERE name = 'ups_opt_mail_config'")
                            ).fetchone()
                            
                            if sequence_result:
                                current_seq = sequence_result[0]
                                logger.info(f"🔍 Current sequence value for ups_opt_mail_config: {current_seq}")
                                
                                # Reset the sequence to 0 so next ID will be 1
                                db.session.execute(
                                    text("UPDATE sqlite_sequence SET seq = 0 WHERE name = 'ups_opt_mail_config'")
                                )
                                db.session.commit()
                                logger.info("✅ Successfully reset sequence to 0 - next email configuration will use ID 1")
                            else:
                                logger.info("ℹ️ Table ups_opt_mail_config not found in sqlite_sequence")
                        else:
                            logger.info("ℹ️ sqlite_sequence table not found - auto-increment will start from 1")
                    except Exception as e:
                        logger.warning(f"⚠️ Could not reset sequence counter: {str(e)}")
                        logger.debug(f"🔍 DEBUG - Sequence reset exception details: {e.__class__.__name__}")
                
            return jsonify({'success': True})
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error deleting mail config: {str(e)}", exc_info=True)
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/settings/mail/all', methods=['GET'])
    def get_all_mail_configs():
        """Return all email configurations in the active target scope."""
        try:
            logger.debug("Fetching all mail configs...")
            MailConfig = db.ModelClasses.MailConfig
            query, scoped_target_id = _mail_scoped_query(MailConfig)
            logger.debug(f"Mail list scope target_id={scoped_target_id}")
            configs = query.order_by(MailConfig.id.asc()).all()
            logger.debug(f"Found {len(configs)} configurations")
            
            result = []
            for config in configs:
                result.append({
                    'id': config.id,
                    'smtp_server': config.smtp_server or '',
                    'smtp_port': config.smtp_port or '',
                    'username': config.username or '',
                    'enabled': bool(config.enabled),
                    'provider': config.provider or '',
                    'render_mode': getattr(config, 'render_mode', 'graphic') or 'graphic',
                    'tls': bool(config.tls),
                    'tls_starttls': bool(config.tls_starttls),
                    'to_email': config.to_email or ''
                })
            
            return jsonify({
                'success': True,
                'data': result
            })
        except Exception as e:
            logger.error(f"Error getting all mail configs: {str(e)}", exc_info=True)
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/settings/mail/<int:config_id>/test', methods=['POST'])
    def test_specific_mail_config(config_id):
        """Test a specific email configuration"""
        try:
            # Get the configuration
            MailConfig = db.ModelClasses.MailConfig
            query, _ = _mail_scoped_query(MailConfig)
            config = query.filter(MailConfig.id == int(config_id)).first()
            if not config:
                return jsonify({
                    'success': False,
                    'message': 'Configuration not found'
                }), 404
            
            # Get the test email address and other parameters
            data = request.get_json()
            to_email = data.get('to_email')
            event_type = data.get('event_type')
            is_test = data.get('is_test', False)
            
            if not to_email:
                return jsonify({
                    'success': False,
                    'message': 'Please provide an email address to receive the test email'
                })
            
            # If event_type is provided, test a notification
            if event_type:
                # Create test data
                test_data = {
                    'id_email': config_id,
                    'is_test': True,
                    'to_email': to_email,
                    'target_id': getattr(config, 'target_id', None),
                }
                
                # Call the test function
                success, message = test_notification(event_type, test_data)
                
                return jsonify({
                    'success': success,
                    'message': message
                })
            
            # Get provider info to check if it requires specific sender email
            from core.mail.provider import email_providers
            provider_info = email_providers.get(config.provider, {})
            requires_sender_email = provider_info.get('requires_sender_email', False)
            
            # Get the password safely with proper error handling
            try:
                password = config.password
                if password is None:
                    logger.error(f"Password decryption failed for config ID {config_id}")
                    return jsonify({
                        'success': False,
                        'message': 'Stored password cannot be decrypted with the current SECRET_KEY. Please edit the configuration and enter a new password.'
                    })
                logger.debug(f"Successfully decrypted password for config ID {config_id}")
            except Exception as e:
                logger.error(f"Exception when decrypting password for config ID {config_id}: {str(e)}")
                return jsonify({
                    'success': False,
                    'message': f'Error decrypting password: {str(e)}. Please edit the configuration and enter a new password.'
                })
            
            # Make sure from_email is properly set
            from_email = config.from_email
            if not from_email and requires_sender_email:
                return jsonify({
                    'success': False,
                    'message': f'Provider {config.provider} requires a verified sender email. Please edit the configuration and enter a From Email address.'
                })
            
            # Otherwise, test a regular email
            test_config = {
                'smtp_server': config.smtp_server,
                'smtp_port': config.smtp_port,
                'username': config.username,
                'password': password,  # Use the decrypted password directly
                'provider': config.provider,
                'tls': config.tls,
                'tls_starttls': config.tls_starttls,
                'from_email': from_email,
                'from_name': from_email.split('@')[0] if from_email and '@' in from_email else config.username.split('@')[0] if '@' in config.username else '',
                'to_email': to_email
            }
            
            logger.debug(f"Testing email configuration (ID: {config_id}) with username: {config.username}, SMTP: {config.smtp_server}:{config.smtp_port}")
            
            # Test the configuration
            success, message = test_email_config(test_config)
            
            # Update the last test date and status
            with data_lock:
                db.session.commit()
            
            return jsonify({
                'success': success,
                'message': message
            })
        except Exception as e:
            logger.error(f"Error testing mail config: {str(e)}", exc_info=True)
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/settings/mail/<int:config_id>', methods=['GET'])
    def get_specific_mail_config(config_id):
        """Get a specific email configuration"""
        try:
            MailConfig = db.ModelClasses.MailConfig
            query, _ = _mail_scoped_query(MailConfig)
            config = query.filter(MailConfig.id == int(config_id)).first()
            if not config:
                return jsonify({
                    'success': False,
                    'message': 'Configuration not found'
                }), 404
            
            return jsonify({
                'success': True,
                'config': {
                    'id': config.id,
                    'smtp_server': config.smtp_server or '',
                    'smtp_port': config.smtp_port or '',
                    'username': config.username or '',
                    'enabled': bool(config.enabled),
                    'provider': config.provider or '',
                    'render_mode': getattr(config, 'render_mode', 'graphic') or 'graphic',
                    'tls': bool(config.tls),
                    'tls_starttls': bool(config.tls_starttls),
                    'to_email': config.to_email or ''
                }
            })
        except Exception as e:
            logger.error(f"Error getting mail config: {str(e)}")
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/settings/mail/<int:config_id>', methods=['PUT'])
    def update_specific_mail_config(config_id):
        """Update a specific email configuration"""
        try:
            # Get and sanitize data immediately
            config_data = request.get_json()
            sanitized_data = config_data.copy()
            if 'smtp_password' in sanitized_data:
                sanitized_data['smtp_password'] = '********'
            if 'password' in sanitized_data:
                sanitized_data['password'] = '********'
                
            logger.debug(f"Updating mail config ID {config_id} with data: {sanitized_data}")
            
            # Verify configuration exists
            MailConfig = db.ModelClasses.MailConfig
            query, scoped_target_id = _mail_scoped_query(MailConfig)
            config = query.filter(MailConfig.id == int(config_id)).first()
            if not config:
                return jsonify({
                    'success': False,
                    'message': f'Configuration with ID {config_id} not found'
                }), 404
            
            # Map form field names to database field names
            if 'smtp_username' in config_data:
                config_data['username'] = config_data.pop('smtp_username')
            
            if 'smtp_password' in config_data:
                config_data['password'] = config_data.pop('smtp_password')
            
            if 'use_tls' in config_data:
                config_data['tls'] = config_data.pop('use_tls')
            
            if 'use_starttls' in config_data:
                config_data['tls_starttls'] = config_data.pop('use_starttls')
            
            if 'email_provider' in config_data:
                config_data['provider'] = config_data.pop('email_provider')
            
            # Check if this provider requires a specific sender email
            from core.mail.provider import email_providers
            provider = config_data.get('provider', config.provider)
            provider_info = email_providers.get(provider, {})
            requires_sender_email = provider_info.get('requires_sender_email', False)
            
            # Only enforce specific from_email for providers that require it
            if requires_sender_email and ('from_email' not in config_data or not config_data['from_email']):
                return jsonify({
                    'success': False,
                    'message': f'Provider {provider} requires a valid verified sender email address in the From Email field'
                }), 400
            
            # Always make sure ID is present in config_data for the save_mail_config function
            config_data['id'] = config_id
            config_data['target_id'] = None
            
            # Pass to the save function for actual saving
            success, result = save_mail_config(config_data)
            
            if not success:
                return jsonify({'success': False, 'error': result}), 500
                
            return jsonify({
                'success': True,
                'message': 'Mail configuration updated successfully',
                'config_id': result
            })
        except Exception as e:
            logger.error(f"Error updating mail config: {str(e)}", exc_info=True)
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/settings/nutify/by-email/<int:email_id>', methods=['GET'])
    def get_nutify_settings_by_email(email_id):
        """Retrieve notification settings for a specific email ID"""
        try:
            MailConfig = db.ModelClasses.MailConfig
            scoped_query, _ = _mail_scoped_query(MailConfig)
            scoped_config = scoped_query.filter(MailConfig.id == int(email_id)).first()
            if not scoped_config:
                return jsonify({'success': False, 'error': 'Email configuration not found'}), 404

            NotificationSettings = db.ModelClasses.NotificationSettings
            notification_query, scoped_target_id = _notification_scoped_query(NotificationSettings)
            
            # Find all settings that use this email ID
            settings = notification_query.filter(NotificationSettings.id_email == email_id).all()
            
            # Prepare the response
            response = []
            for setting in settings:
                response.append({
                    'id': setting.id,
                    'target_id': getattr(setting, 'target_id', None),
                    'event_type': setting.event_type,
                    'enabled': setting.enabled,
                    'id_email': setting.id_email
                })
                
            return jsonify({
                'success': True,
                'target_id': scoped_target_id,
                'settings': response
            })
        except Exception as e:
            logger.error(f"Error getting notification settings by email ID: {str(e)}", exc_info=True)
            return jsonify({'success': False, 'error': str(e)}), 500 
