"""
Database Models Entry Point.
This module serves as the main entry point for initializing SQLAlchemy ORM models.
All model definitions have been moved to the core.db.orm package.
"""

import pytz

# Import the centralized ModelClasses
from core.db.model_classes import init_model_classes

# Will be set in init_models
db = None

def get_db_timezone():
    """
    Returns UTC timezone for database operations.
    Database always stores dates in UTC, regardless of display timezone.
    
    Returns:
        function: A function that returns pytz.UTC
    """
    return lambda: pytz.UTC

def init_models(db_instance, timezone_getter=None):
    """
    Initialize the SQLAlchemy models
    
    Args:
        db_instance: SQLAlchemy database instance
        timezone_getter: Function to get the timezone (provided for backward compatibility but not used)
        
    Returns:
        dict: Dictionary of initialized model classes
    """
    global db
    db = db_instance
    
    # Check if we already have a ModelClasses namespace stored on db
    if hasattr(db, 'ModelClasses'):
        from core.logger import database_logger as logger
        logger.debug("📚 ORM models already initialized, returning existing models")
        # Return a dictionary of the existing models
        models_dict = {name: getattr(db.ModelClasses, name) for name in dir(db.ModelClasses) 
                      if not name.startswith('__')}
        return models_dict
    
    # Log key information
    from core.logger import database_logger as logger
    logger.info("📚 Initializing ORM models")
    
    # Initialize ModelClasses using UTC for database operations
    models = init_model_classes(db, get_db_timezone())
    
    # Create a dictionary of models for backwards compatibility
    models_dict = {
        'UPSEvent': models.UPSEvent,
        'VariableConfig': models.VariableConfig,
        'UPSCommand': models.UPSCommand,
        'UPSVariable': models.UPSVariable,
        'MailConfig': models.MailConfig,
        'NtfyConfig': models.NtfyConfig,
        'TelegramConfig': models.TelegramConfig,
        'WebhookConfig': models.WebhookConfig,
        'NotificationSettings': models.NotificationSettings,
        'ReportSchedule': models.ReportSchedule,
        'MasterControl': models.MasterControl,
        'LoginAuth': models.LoginAuth,
        'UPSMonitorTarget': models.UPSMonitorTarget,
        'UPSMonitorPolicy': models.UPSMonitorPolicy,
        'UPSMonitorData': models.UPSMonitorData,
        'UPSMonitorRollup': models.UPSMonitorRollup,
        'UPSMonitorTargetProfile': models.UPSMonitorTargetProfile,
        'UPSMonitorVariableMapping': models.UPSMonitorVariableMapping,
    }
    
    # Log summary
    logger.info(f"✅ Created {len(models_dict)} ORM models successfully")
    
    # Make models available via ModelClasses attached to db
    db.ModelClasses = models
    
    # Tables will be created automatically by Flask-SQLAlchemy
    # or by the database integrity system during application startup.
    
    return models_dict 
