"""
ORM Models Package.
This package contains individual ORM model definitions for each database table.
"""

from core.db.orm.orm_ups_events import UPSEvent, init_model as init_ups_event_model
from core.db.orm.orm_ups_opt_variable_config import VariableConfig, init_model as init_variable_config_model
from core.db.orm.orm_ups_variables_upscmd import UPSCommand, init_model as init_ups_command_model
from core.db.orm.orm_ups_variables_upsrw import UPSVariable, init_model as init_ups_variable_model
from core.db.orm.orm_ups_opt_mail_config import MailConfig, init_model as init_mail_config_model
from core.db.orm.orm_ups_opt_ntfy import NtfyConfig, init_model as init_ntfy_config_model
from core.db.orm.orm_ups_opt_telegram import TelegramConfig, init_model as init_telegram_config_model
from core.db.orm.orm_ups_opt_webhook import WebhookConfig, init_model as init_webhook_config_model
from core.db.orm.orm_ups_opt_notification import NotificationSettings, init_model as init_notification_settings_model
from core.db.orm.orm_ups_report_schedules import ReportSchedule, init_model as init_report_schedule_model
from core.db.orm.orm_nutify_master_control import (
    NutifyMasterControl as MasterControl,
    init_model as init_master_control_model,
)
from core.db.orm.orm_ups_login import LoginAuth, init_model as init_login_model
from core.db.orm.orm_ups_monitor_targets import UPSMonitorTarget, init_model as init_ups_monitor_target_model
from core.db.orm.orm_ups_monitor_policies import UPSMonitorPolicy, init_model as init_ups_monitor_policy_model
from core.db.orm.orm_ups_monitor_data import UPSMonitorData, init_model as init_ups_monitor_data_model
from core.db.orm.orm_ups_monitor_rollups import (
    UPSMonitorRollup,
    init_model as init_ups_monitor_rollup_model,
)
from core.db.orm.orm_ups_monitor_target_profile import (
    UPSMonitorTargetProfile,
    init_model as init_ups_monitor_target_profile_model,
)
from core.db.orm.orm_ups_monitor_variable_mappings import (
    UPSMonitorVariableMapping,
    init_model as init_ups_monitor_variable_mapping_model,
)


# Dictionary to store initialized models
_models = {}

def init_models(db_instance, timezone_getter=None):
    """
    Initialize all ORM models in this package.
    
    Args:
        db_instance: SQLAlchemy database instance
        timezone_getter: DEPRECATED, no longer used - direct CACHE_TIMEZONE is used instead
        
    Returns:
        dict: Dictionary of initialized model classes
    """
    global _models
    
    # Create the base class for all models
    class Base(db_instance.Model):
        """Base model with shared methods"""
        __abstract__ = True
        __table_args__ = {'extend_existing': True}
    
    # Import logger for database operations
    from core.logger import database_logger
    
    # Initialize master-control model first as other modules can depend on it.
    _models['MasterControl'] = init_master_control_model(
        Base,
        database_logger,
    )

    # Load secret key from Flask config for password encryption
    from flask import current_app
    secret_key = current_app.config.get('SECRET_KEY')
    if secret_key:
        secret_key = secret_key.encode()
        database_logger.info("🔑 Using secret key from environment variable for password encryption")
    else:
        database_logger.warning("⚠️ SECRET_KEY not set in Flask config; password encryption disabled")
        secret_key = None
    
    # Initialize UPSEvent model
    _models['UPSEvent'] = init_ups_event_model(Base)
    
    # Initialize VariableConfig model
    _models['VariableConfig'] = init_variable_config_model(Base)
    
    # Initialize UPSCommand model
    _models['UPSCommand'] = init_ups_command_model(Base)
    
    # Initialize UPSVariable model
    _models['UPSVariable'] = init_ups_variable_model(Base)
    
    # Initialize MailConfig model with secret key for password encryption
    _models['MailConfig'] = init_mail_config_model(
        Base, 
        secret_key, 
        database_logger
    )
    
    # Initialize NtfyConfig model
    _models['NtfyConfig'] = init_ntfy_config_model(
        Base,
        database_logger
    )

    # Initialize TelegramConfig model
    _models['TelegramConfig'] = init_telegram_config_model(
        Base,
        secret_key,
        database_logger
    )
    
    # Initialize WebhookConfig model
    _models['WebhookConfig'] = init_webhook_config_model(
        Base,
        database_logger
    )
    
    # Initialize NotificationSettings model
    _models['NotificationSettings'] = init_notification_settings_model(
        Base,
        db_instance,
        database_logger
    )
    
    # Initialize ReportSchedule model
    _models['ReportSchedule'] = init_report_schedule_model(
        Base,
        database_logger
    )
    
    # Initialize LoginAuth model
    _models['LoginAuth'] = init_login_model(
        Base,
        database_logger
    )

    # Initialize Multi-NUT models
    _models['UPSMonitorTarget'] = init_ups_monitor_target_model(
        Base,
        database_logger
    )
    _models['UPSMonitorPolicy'] = init_ups_monitor_policy_model(
        Base,
        database_logger
    )
    _models['UPSMonitorData'] = init_ups_monitor_data_model(
        Base,
        database_logger
    )
    _models['UPSMonitorRollup'] = init_ups_monitor_rollup_model(
        Base,
        database_logger
    )
    _models['UPSMonitorTargetProfile'] = init_ups_monitor_target_profile_model(
        Base,
        database_logger
    )
    _models['UPSMonitorVariableMapping'] = init_ups_monitor_variable_mapping_model(
        Base,
        database_logger
    )
    
    # NUTConfig model has been removed as it's no longer used
    # Configuration is now managed through NUT configuration files
    
    # UPSStaticData and UPSDynamicData models are created dynamically by db_module.py
    # and not part of the standard ORM package
    
    # Return a dictionary of all initialized models
    return _models

# Export public symbols
__all__ = [
    'init_models',
    'UPSEvent',
    'VariableConfig',
    'UPSCommand',
    'UPSVariable',
    'MailConfig',
    'NtfyConfig',
    'TelegramConfig',
    'WebhookConfig',
    'NotificationSettings',
    'ReportSchedule',
    'MasterControl',
    'LoginAuth',
    'UPSMonitorTarget',
    'UPSMonitorPolicy',
    'UPSMonitorData',
    'UPSMonitorRollup',
    'UPSMonitorTargetProfile',
    'UPSMonitorVariableMapping',
    # Removed NUTConfig as it's no longer used
    # Removed UPSStaticData and UPSDynamicData from exports
]
