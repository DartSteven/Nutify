"""Nutify Application Entrypoint.

Bootstraps Flask, initializes core modules, and starts the Nutify web application.
"""

# Prevent resource tracker warnings
import os
# Set environment variable to disable resource tracker
os.environ["PYTHONWARNINGS"] = "ignore::UserWarning:multiprocessing.resource_tracker"
import warnings
# Filter out resource tracker warnings directly
warnings.filterwarnings("ignore", category=UserWarning, module="multiprocessing.resource_tracker")

####### FROM HERE - MACOS DEVELOPMENT COMPATIBILITY - REMOVE IN PRODUCTION #######
####### FROM HERE - MACOS DEVELOPMENT COMPATIBILITY - REMOVE IN PRODUCTION #######
####### FROM HERE - MACOS DEVELOPMENT COMPATIBILITY - REMOVE IN PRODUCTION #######
####### FROM HERE - MACOS DEVELOPMENT COMPATIBILITY - REMOVE IN PRODUCTION #######
####### FROM HERE - MACOS DEVELOPMENT COMPATIBILITY - REMOVE IN PRODUCTION #######
#######
#######
####### core/nut/nut_daemon.py will do the monkey patching #######
import eventlet
import sys

# Check for macOS and apply compatibility fixes BEFORE monkey patching
if sys.platform == 'darwin':
    try:
        # Force poll hub instead of kqueue on macOS
        import eventlet.hubs
        eventlet.hubs.use_hub('poll')
        
        # Configure debug settings
        import eventlet.debug
        eventlet.debug.hub_prevent_multiple_readers(False)
        
        # Set environment variables for macOS
        os.environ['EVENTLET_MONKEY_PATCH'] = '1'
        os.environ['MULTIPROCESSING_FORK_DISABLE'] = '1'
        os.environ['OBJC_DISABLE_INITIALIZE_FORK_SAFETY'] = 'YES'
        
        print("Applied macOS compatibility settings before monkey patching")
    except Exception as e:
        print(f"Error applying macOS compatibility settings: {e}")

# Now we can monkey patch
eventlet.monkey_patch()

# Import the full macos compatibility module for additional fixes
try:
    from core.macos import configure_macos_compatibility
    configure_macos_compatibility()
except ImportError:
    # Module not found, likely in production where it's not needed
    pass
####### TO HERE - MACOS DEVELOPMENT COMPATIBILITY - REMOVE IN PRODUCTION #######
####### TO HERE - MACOS DEVELOPMENT COMPATIBILITY - REMOVE IN PRODUCTION #######
####### TO HERE - MACOS DEVELOPMENT COMPATIBILITY - REMOVE IN PRODUCTION #######
####### TO HERE - MACOS DEVELOPMENT COMPATIBILITY - REMOVE IN PRODUCTION #######
####### TO HERE - MACOS DEVELOPMENT COMPATIBILITY - REMOVE IN PRODUCTION #######


# Global timezone cache - initialized to UTC by default
import pytz
import logging
from pathlib import Path

# Initialize basic logging to capture timezone initialization
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
timezone_logger = logging.getLogger('timezone')

# Default to UTC initially
CACHE_TIMEZONE = pytz.timezone('UTC')

def initialize_timezone():
    """
    Initialize the global CACHE_TIMEZONE from database.
    Must be called before any other operation that requires timezone information.
    """
    global CACHE_TIMEZONE
    timezone_logger.info("Initializing global timezone cache")
    
    # Find the instance path and database name
    base_dir = Path(__file__).resolve().parent
    instance_path = os.path.join(base_dir, 'instance')
    db_name = 'nutify.db.sqlite'
    db_path = os.path.join(instance_path, db_name)
    
    timezone_str = 'UTC'

    # Check if database exists and has data
    if os.path.exists(db_path) and os.path.getsize(db_path) > 0:
        try:
            from core.settings.settings import get_target_timezone

            timezone_str = get_target_timezone() or 'UTC'
            timezone_logger.info(f"🌏 Loaded timezone from target-scoped variable config: {timezone_str}")
        except Exception as e:
            timezone_logger.error(f"Error loading timezone from database: {str(e)}")
            timezone_logger.info("Using default timezone: UTC")
    else:
        timezone_logger.info("Database not found or empty, using default timezone: UTC")

    try:
        CACHE_TIMEZONE = pytz.timezone(timezone_str)
    except Exception:
        CACHE_TIMEZONE = pytz.UTC
    timezone_logger.info(f"CACHE_TIMEZONE initialized to: {CACHE_TIMEZONE.zone}")

# Initialize timezone immediately
initialize_timezone()

from flask import Flask, render_template, request, jsonify, send_from_directory, redirect, url_for
from flask_socketio import SocketIO, emit
import datetime
import sys
import threading
import time
from flask_talisman import Talisman
import json
from sqlalchemy import text, inspect

# Import the new NUT config module
from core.nut_config import check_nut_config_files, is_nut_configured
from core.nut_config.routes import register_routes as register_nut_config_routes
from core.nut_config.api_nut_config import register_api_routes as register_nut_config_api_routes

# Import the new NUT daemon module for managing NUT services
from core.nut import register_api_routes as register_nut_daemon_api_routes

# Import the new NUT daemon module for managing NUT services
from core.nut.nut_daemon import (
    start_nut_services,
    NUTConfigError,
    NUTStartupError,
    NUTShutdownError,
    get_nut_mode
)

# Import nut_parser for NUT configuration file parsing
from core.db.nut_parser import get_ups_connection_params, refresh_config

# Import db_patch for database schema patching
from core.db.db_patch import (
    check_timestamp_columns,
    ensure_provider_render_mode_schema,
    ensure_target_scope_schema,
)

# Check for NUT configuration files without exiting
is_nut_configured, missing_nut_files = check_nut_config_files()

# Import only the essential components when in setup mode
from core.settings import (
    DEBUG_MODE, SERVER_PORT, SERVER_HOST,
    DB_NAME, LOG_LEVEL, LOG_FILE, LOG_FILE_ENABLED,
    LOG_FORMAT, LOG_LEVEL_DEBUG, LOG_LEVEL_INFO,
    INSTANCE_PATH, DB_URI, LOG_WERKZEUG,
    SSL_ENABLED, SSL_CERT, SSL_KEY, UPSC_BIN, init_application_timezone,
    get_workspace_monitoring_profile as get_workspace_profile_setting,
    get_target_timezone as get_target_timezone_setting,
)
# Import both loggers correctly
from core.logger import system_logger
from core.logger import system_logger as logger
from werkzeug.serving import WSGIRequestHandler
from core.template_loader import configure_template_loader
from core.auth.api_guard import register_api_request_guard

RUNTIME_STATUS_HEALTHY = 'healthy'
RUNTIME_STATUS_DEGRADED = 'degraded'
RUNTIME_STATUS_CRITICAL = 'critical'
RUNTIME_STATUS_UNCONFIGURED = 'unconfigured'

_app_runtime_state_lock = threading.Lock()
_app_runtime_state = {
    'status': RUNTIME_STATUS_UNCONFIGURED,
    'message': 'Application setup is required.',
    'updated_at': datetime.datetime.now(pytz.UTC).isoformat(),
}


def set_app_runtime_state(status, message):
    """Update global runtime state exposed to templates and APIs."""
    normalized = status if status in {
        RUNTIME_STATUS_HEALTHY,
        RUNTIME_STATUS_DEGRADED,
        RUNTIME_STATUS_CRITICAL,
        RUNTIME_STATUS_UNCONFIGURED,
    } else RUNTIME_STATUS_CRITICAL

    with _app_runtime_state_lock:
        _app_runtime_state['status'] = normalized
        _app_runtime_state['message'] = message
        _app_runtime_state['updated_at'] = datetime.datetime.now(pytz.UTC).isoformat()


def get_app_runtime_state():
    """Return a copy of the current runtime state."""
    with _app_runtime_state_lock:
        return dict(_app_runtime_state)

# Function to check if the database and tables exist
def check_database_and_tables():
    """Check if the database file exists and is non-empty."""
    logger.info("🔍 Checking if database file exists...")
    db_path = os.path.join(INSTANCE_PATH, DB_NAME)
    
    # Check if database file exists
    if not os.path.exists(db_path):
        logger.warning(f"❌ Database file does not exist: {db_path}")
        return False
    
    # Check if database file is empty
    if os.path.getsize(db_path) == 0:
        logger.warning(f"❌ Database file is empty: {db_path}")
        return False
        
    logger.info("✅ Database file exists and is not empty")
    return True

# Check if all conditions are met for full app initialization
is_db_initialized = check_database_and_tables()
is_fully_configured = is_nut_configured and is_db_initialized

if is_fully_configured:
    set_app_runtime_state(
        RUNTIME_STATUS_HEALTHY,
        "Nutify is configured. Runtime service checks are in progress."
    )
else:
    set_app_runtime_state(
        RUNTIME_STATUS_UNCONFIGURED,
        "Nutify requires initial setup to enable full monitoring."
    )

# Initialize global settings from database only if we're fully configured
initial_server_name = "Nutify Setup"  # Default name for setup mode
if is_fully_configured:
    from core.settings.settings import get_server_name
    try:
        initial_server_name = get_server_name()
        logger.info(f"Server name initialized to: {initial_server_name}")
    except Exception as e:
        logger.error(f"❌ Cannot initialize server_name from database: {str(e)}")
        is_fully_configured = False  # If we can't get the server name, fall back to setup mode
        set_app_runtime_state(
            RUNTIME_STATUS_UNCONFIGURED,
            f"Initial setup metadata could not be loaded: {str(e)}"
        )

# Only import the rest of the components if fully configured
if is_fully_configured:
    from core.db.ups import (
        db,
        configure_ups,
    )
    from core.db.initializer import init_database
    from core.routes import register_routes
    from core.api import register_api_routes
    from core.energy.api_energy import register_api_routes as register_energy_api_routes
    from core.battery.api_battery import register_api_routes as register_battery_api_routes
    from core.advanced.api_advanced import register_api_routes as register_advanced_api_routes
    from core.mail import init_notification_settings
    from core.mail.api_mail import register_mail_api_routes
    from core.report import api_report, routes_report
    from core.settings.api_settings import api_settings
    from core.settings.routes_settings import routes_settings
    from core.logger import routes_logger, api_logger
    from core.socket import socketio
    from core.upsmon import api_upsmon, routes_upsmon
    from core.scheduler import scheduler, register_scheduler_routes
    from core.logger.api_logger import api_logger
    from core.logger.routes_logger import routes_logger
    from core.db.model_classes import register_models_for_global_access
    from core.multi_nut import (
        get_multi_polling_sleep_seconds,
        poll_multi_targets_once,
        register_api_routes as register_multi_nut_api_routes,
        register_routes as register_multi_nut_routes,
    )
    from core.options.api_options import api_options
    from core.options.routes_options import routes_options
else:
    # Create a minimal socketio instance when in setup mode
    from flask_socketio import SocketIO
    socketio = SocketIO()
    logger.warning("🔧 Starting in SETUP MODE - some components are not fully configured")
    if not is_nut_configured:
        logger.warning("⚠️ NUT configuration is missing or incomplete")
    if not is_db_initialized:
        logger.warning("⚠️ Database or required tables are missing")

# Configuring logging
log_format = LOG_FORMAT
handlers = [logging.StreamHandler()]

if LOG_FILE_ENABLED:
    handlers.append(logging.FileHandler(LOG_FILE))

# Flask initialization
app = Flask(__name__, instance_path=INSTANCE_PATH)
configure_template_loader(app)

# Make CACHE_TIMEZONE available as an application attribute
app.CACHE_TIMEZONE = CACHE_TIMEZONE
app.get_runtime_state = get_app_runtime_state

# Flask configuration
app.config['TEMPLATES_AUTO_RELOAD'] = True
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0

# Always set SECRET_KEY from environment, even during setup mode
secret_key_env = os.getenv('SECRET_KEY')
if secret_key_env:
    app.config['SECRET_KEY'] = secret_key_env
    # Log the first 5 characters of the key for debugging
    key_preview = secret_key_env[:5] if len(secret_key_env) > 5 else "[empty]"
    logger.info(f"✅ SECRET_KEY set in app config from environment (first 5 chars: {key_preview}...)")
    
    # Verify key length for additional debugging
    if len(secret_key_env) < 16:
        logger.warning(f"⚠️ SECRET_KEY is shorter than recommended (length: {len(secret_key_env)})")
else:
    # SECRET_KEY MUST be set in environment (docker-compose.yaml)
    logger.warning("⚠️ No SECRET_KEY found in environment!")
    logger.warning("⚠️ SECRET_KEY must be set in environment variables or docker-compose.yaml")
    logger.warning("⚠️ Encryption features will be disabled until SECRET_KEY is properly set")

app.events_log = []

# Initialize baseline auth/session security for both setup and full runtime.
try:
    from core.auth import setup_session_config
    from core.auth.security import init_auth_security
    from core.auth.oidc import init_oidc_module

    setup_session_config(app)
    init_auth_security(app, logger)
    init_oidc_module(app, logger)
except Exception as auth_bootstrap_error:
    logger.warning(f"⚠️ Early auth security bootstrap failed: {auth_bootstrap_error}")


def get_workspace_monitoring_profile():
    """Return workspace monitoring profile (single/multi)."""
    if not is_fully_configured:
        return 'single'

    try:
        return get_workspace_profile_setting()
    except Exception as exc:
        logger.debug(f"Could not load monitoring profile from settings: {exc}")

    try:
        from core.multi_nut.storage import get_monitoring_profile
        return get_monitoring_profile()
    except Exception as exc:
        logger.debug(f"Falling back to single profile: {exc}")
        return 'single'


@app.context_processor
def inject_multi_nut_state():
    """Expose Multi-NUT status to all dashboard templates."""
    runtime_state = get_app_runtime_state()
    monitoring_profile = get_workspace_monitoring_profile()
    base_payload = {
        'app_runtime_status': runtime_state.get('status', RUNTIME_STATUS_UNCONFIGURED),
        'app_runtime_message': runtime_state.get('message', ''),
        'app_runtime_updated_at': runtime_state.get('updated_at', ''),
        'monitoring_profile': monitoring_profile,
    }

    if not is_fully_configured:
        base_payload.update({
            'monitoring_profile': 'single',
            'multi_nut_enabled': False,
            'multi_nut_target_count': 0,
        })
        return base_payload

    try:
        from core.multi_nut.polling import get_multi_nut_runtime_state
        from core.multi_nut.active_target import get_active_target, get_request_or_active_target_id

        state = get_multi_nut_runtime_state()
        resolved_profile = str(state.get('monitoring_profile', monitoring_profile) or monitoring_profile).strip().lower()
        if resolved_profile not in {'single', 'multi'}:
            resolved_profile = 'single'

        active_target_id = get_request_or_active_target_id()
        active_target = get_active_target()

        base_payload.update({
            'monitoring_profile': resolved_profile,
            'multi_nut_enabled': resolved_profile == 'multi' and bool(state.get('multi_enabled', False)),
            'multi_nut_target_count': int(state.get('enabled_targets', 0)),
            'active_target_id': active_target_id,
            'active_target': active_target,
        })
        return base_payload
    except Exception:
        base_payload.update({
            'monitoring_profile': monitoring_profile,
            'multi_nut_enabled': False,
            'multi_nut_target_count': 0,
            'active_target_id': None,
            'active_target': None,
        })
        return base_payload

# Talisman configuration
Talisman(app, 
    force_https=SSL_ENABLED,
    content_security_policy=None
)

# Define a function to ensure database permissions (only used when fully configured)
def ensure_database_permissions():
    """Ensure the database file has proper permissions for the nut user"""
    try:
        logger.info("Checking database file permissions...")
        # Get the database path
        db_path = os.path.join(INSTANCE_PATH, DB_NAME)
        
        # Check if database file exists
        if os.path.exists(db_path):
            # Get current owner and permissions if possible
            try:
                import pwd
                import grp
                stat_info = os.stat(db_path)
                uid = stat_info.st_uid
                gid = stat_info.st_gid
                mode = stat_info.st_mode
                
                # Try to get nut user and group IDs
                try:
                    nut_uid = pwd.getpwnam('nut').pw_uid
                    nut_gid = grp.getgrnam('nut').gr_gid
                    
                    # Log current permissions
                    logger.info(f"Database permissions - Current: uid={uid}, gid={gid}, mode={mode:o}")
                    logger.info(f"Target permissions: uid={nut_uid}, gid={nut_gid}, mode=664")
                    
                    # Fix ownership and permissions if needed
                    if uid != nut_uid or gid != nut_gid:
                        os.chown(db_path, nut_uid, nut_gid)
                        logger.info(f"Changed database ownership to nut:nut")
                    
                    # Fix permissions if needed (664 = rw-rw-r--)
                    if (mode & 0o777) != 0o664:
                        os.chmod(db_path, 0o664)
                        logger.info(f"Changed database permissions to 664")
                    
                    # Also check for SQLite journal files
                    for ext in ["-journal", "-wal", "-shm"]:
                        journal_file = f"{db_path}{ext}"
                        if os.path.exists(journal_file):
                            os.chown(journal_file, nut_uid, nut_gid)
                            os.chmod(journal_file, 0o664)
                            logger.info(f"Fixed permissions for {journal_file}")
                    
                except (KeyError, PermissionError) as e:
                    # Couldn't get nut user or don't have permission to change
                    logger.warning(f"Failed to set database permissions: {str(e)}")
            except ImportError:
                # pwd/grp modules not available (non-Unix OS), just try chmod
                try:
                    os.chmod(db_path, 0o664)
                    logger.info("Set database permissions to 664 (owner unchanged)")
                except Exception as e:
                    logger.warning(f"Failed to set database permissions: {str(e)}")
        else:
            logger.info(f"Database file doesn't exist yet at {db_path}")
            # Ensure the directory has proper permissions
            db_dir = os.path.dirname(db_path)
            if not os.path.exists(db_dir):
                os.makedirs(db_dir, exist_ok=True)
                logger.info(f"Created database directory: {db_dir}")
            
            # Set directory permissions
            try:
                os.chmod(db_dir, 0o775)  # rwxrwxr-x
                logger.info(f"Set database directory permissions to 775")
            except Exception as e:
                logger.warning(f"Failed to set directory permissions: {str(e)}")
    except Exception as e:
        logger.error(f"Error checking database permissions: {str(e)}")

# Only configure the full app if fully configured
if is_fully_configured:
    # Basic Flask app configuration
    app.config['INSTANCE_PATH'] = INSTANCE_PATH
    app.config['SQLALCHEMY_DATABASE_URI'] = DB_URI
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['JSONIFY_PRETTYPRINT_REGULAR'] = True
    app.config['JSON_SORT_KEYS'] = False
    app.json.compact = False

    # Ensure database has proper permissions before initializing
    ensure_database_permissions()

    # Initialize database only once
    db.init_app(app)
    
    # Process NUT configuration first
    with app.app_context():
        # Configure UPS
        try:
            # Check for UPS configuration in NUT configuration files
            logger.info("Checking for UPS configuration in NUT configuration files...")
            params = get_ups_connection_params()
            logger.debug(f"🔍 DEBUG - UPS connection params from NUT files: {params}")
            
            if params and 'host' in params and 'name' in params:
                # Configure UPS with values from configuration files
                host = params['host']
                name = params['name']
                logger.info(f"Found UPS configuration in NUT files: {name}@{host}")
                configure_ups(host, name, UPSC_BIN, 10, source="nut_files")  # Set default timeout to 10s
                logger.info(f"✅ UPS configured from NUT files: {host}:{name}")
            else:
                # No configuration found in NUT files
                logger.warning("⚠️ No UPS configuration found in NUT files")
                logger.warning("⚠️ Continuing startup in degraded mode without active primary UPS binding")
                set_app_runtime_state(
                    RUNTIME_STATUS_DEGRADED,
                    "Primary UPS binding is missing from NUT files. Multi-target monitoring can continue."
                )
        except Exception as e:
            logger.error(f"❌ Error configuring UPS: {str(e)}")
            logger.warning("⚠️ Continuing startup in degraded mode after UPS configuration error")
            set_app_runtime_state(
                RUNTIME_STATUS_DEGRADED,
                f"Primary UPS configuration failed: {str(e)}"
            )

    # Initialize the rest of the components
    socketio.init_app(
        app,
        async_mode='eventlet',
    )
    
    # Helper function to register blueprint only if not already registered
    def register_blueprint_if_not_exists(app, blueprint):
        if blueprint.name not in app.blueprints:
            app.register_blueprint(blueprint)
    
    register_routes(app)
    register_multi_nut_routes(app)
    register_api_routes(app)
    register_multi_nut_api_routes(app)
    register_energy_api_routes(app)
    register_battery_api_routes(app)
    register_advanced_api_routes(app)
    register_scheduler_routes(app)
    register_blueprint_if_not_exists(app, api_logger)
    register_blueprint_if_not_exists(app, routes_logger)
    register_blueprint_if_not_exists(app, api_report)
    register_blueprint_if_not_exists(app, routes_report)
    register_blueprint_if_not_exists(app, api_settings)
    register_blueprint_if_not_exists(app, routes_settings)
    register_blueprint_if_not_exists(app, api_upsmon)
    register_blueprint_if_not_exists(app, routes_upsmon)
    register_blueprint_if_not_exists(app, api_options)
    register_blueprint_if_not_exists(app, routes_options)
else:
    # Minimal configuration for setup mode
    socketio.init_app(
        app,
        async_mode='eventlet',
    )
    
    # Add a route redirect with authentication check
    @app.route('/')
    @app.route('/index')
    def redirect_to_welcome():
        """Redirect based on setup and authentication status"""
        try:
            # STEP 1: Check if NUT is configured FIRST
            if not is_nut_configured:
                # NUT not configured, redirect to NUT setup
                logger.info("🔧 NUT not configured - redirecting to NUT setup")
                return redirect(url_for('nut_config.welcome'))
            
            # STEP 2: Check if database is initialized
            if not is_db_initialized:
                # Database not initialized, redirect to NUT setup to complete setup
                logger.info("🔧 Database not initialized - redirecting to NUT setup")
                return redirect(url_for('nut_config.welcome'))
            
            # STEP 3: Only after NUT and DB are ready, check authentication
            from core.auth import is_login_configured, is_authenticated
            
            if not is_login_configured():
                # Login not configured, redirect to login setup
                logger.info("🔐 Login not configured - redirecting to login setup")
                return redirect(url_for('auth.setup'))
            elif not is_authenticated():
                # Login configured but user not authenticated
                logger.info("🔐 User not authenticated - redirecting to login")
                return redirect(url_for('auth.login'))
            else:
                # Everything is configured and user is authenticated
                logger.info("✅ Fully configured and authenticated - redirecting to main dashboard")
                return redirect(url_for('dashboard_index'))
        except Exception as e:
            # If authentication system fails, fall back to welcome page
            logger.error(f"Authentication system error: {str(e)}")
            return redirect(url_for('nut_config.welcome'))

# Register NUT configuration routes regardless of configuration status
register_nut_config_routes(app)
register_nut_config_api_routes(app)
register_nut_daemon_api_routes(app)

# Register authentication routes
from core.auth.routes import register_auth_routes
register_auth_routes(app)

# Register centralized API security guard after auth routes are available.
register_api_request_guard(app)

# Ensure callback token exists so event callbacks are never accepted fail-open.
try:
    from core.events.callback_token import ensure_event_api_token

    with app.app_context():
        callback_token = ensure_event_api_token()
        if callback_token:
            logger.info("✅ Event callback token initialized")
        else:
            logger.warning("⚠️ Event callback token is empty; callback endpoints will reject requests")
except Exception as callback_token_error:
    logger.error(f"❌ Failed to initialize event callback token: {callback_token_error}")

# Register React frontend bootstrap API
from core.react_frontend import register_react_frontend_api
register_react_frontend_api(app)

# Werkzeug log control
if isinstance(LOG_WERKZEUG, bool):
    use_werkzeug = LOG_WERKZEUG
else:
    use_werkzeug = True

if not use_werkzeug:
    logging.getLogger('werkzeug').disabled = True

@app.template_filter('isoformat')
def isoformat_filter(value):
    """Converts a datetime object to ISO string with timezone"""
    if isinstance(value, datetime.datetime):
        if value.tzinfo is None:
            value = CACHE_TIMEZONE.localize(value)
        return value.astimezone(CACHE_TIMEZONE).isoformat()
    return value

# Only define and start the polling thread if NUT is configured
if is_fully_configured:
    def polling_thread():
        """Thread for UPS data polling"""
        failures = 0
        
        # Import the internal checker to monitor UPS connection
        from core.db.internal_checker import start_connection_monitoring
        
        # Start connection monitoring
        start_connection_monitoring()
        logger.info("🔄 UPS connection monitoring started for polling thread")

        def _read_polling_interval_seconds():
            """Read polling interval from VariableConfig with safe fallback."""
            try:
                if hasattr(db, 'ModelClasses') and hasattr(db.ModelClasses, 'VariableConfig'):
                    model_class = db.ModelClasses.VariableConfig
                else:
                    from core.db.ups import VariableConfig
                    model_class = VariableConfig

                query = model_class.query
                if hasattr(model_class, 'target_id'):
                    query = query.filter(model_class.target_id.is_(None))
                config = query.order_by(model_class.id.desc()).first()
                interval_value = config.polling_interval if config else 1
            except Exception as exc:
                logger.error(f"Error getting polling interval: {str(exc)}. Using default of 1 second.")
                interval_value = 1
            return max(1, min(60, int(interval_value or 1)))
        
        while True:
            try:
                with app.app_context():
                    try:
                        poll_multi_targets_once(timeout=10)
                        failures = 0
                    except Exception as poll_exc:
                        failures += 1
                        logger.warning(f"⚠️ Unified target polling error: {poll_exc}")

                    sleep_seconds = get_multi_polling_sleep_seconds(
                        default_interval=_read_polling_interval_seconds()
                    )
                    time.sleep(sleep_seconds)
                    
            except Exception as e:
                logger.error(f"Unexpected error in polling thread: {str(e)}")
                failures += 1
                time.sleep(min(300, 2 ** failures))

# Disables Werkzeug log if LOG_LEVEL is OFF
if LOG_LEVEL == 'OFF':
    log = logging.getLogger('werkzeug')
    log.setLevel(logging.ERROR)
    WSGIRequestHandler.log = lambda *args, **kwargs: None

def init_app():
    """Initializes the application"""
    global CACHE_TIMEZONE  # Declare global at the top of the function
    logger.info("💻 Initializing application...")
    startup_issues = []
    
    try:
        with app.app_context():
            # Check if in configuration mode - only proceed if NUT is configured
            if not is_fully_configured:
                logger.info("🔍 Running in setup mode - NUT needs to be configured first")
                logger.info("✅ Skipping initialization until NUT is configured")
                set_app_runtime_state(
                    RUNTIME_STATUS_UNCONFIGURED,
                    "Initial setup is required before monitoring can start."
                )
                logger.info("=" * 60)
                return
            
            # ======== INITIALIZE APPLICATION TIMEZONE ========
            logger.info("")
            logger.info("=" * 60)
            logger.info("=====        INITIALIZING APPLICATION TIMEZONE         =====")
            logger.info("=" * 60)
            
            # Use the global CACHE_TIMEZONE that was initialized at startup
            logger.info(f"🕒 Application display timezone: {CACHE_TIMEZONE.zone}")
            logger.info(f"🕒 Database timezone: UTC (fixed)")
            logger.info("=" * 60)
            
            # Small delay to ensure logs are displayed in order
            time.sleep(0.5)
            
            # ======== STEP 1: ATTEMPT TO START NUT SERVICES ========
            logger.info("")
            logger.info("=" * 60)
            logger.info("=====              STARTING NUT SERVICES               =====")
            logger.info("=" * 60)
            
            try:
                # Get NUT mode before starting services
                nut_mode = get_nut_mode()
                logger.info(f"🔍 Detected NUT mode: {nut_mode}")
                
                # Log which services will be started based on mode
                if nut_mode == 'netclient':
                    logger.info("📡 Operating in NETCLIENT mode - will connect to a remote NUT server")
                    logger.info("🔧 Services that will be started: upsmon (monitor only)")
                elif nut_mode == 'standalone':
                    logger.info("💻 Operating in STANDALONE mode - UPS connected to this machine")
                    logger.info("🔧 Services that will be started: upsdrvctl (drivers), upsd (server), upsmon (monitor)")
                elif nut_mode == 'netserver':
                    logger.info("🖥️ Operating in NETSERVER mode - serving UPS data to network clients")
                    logger.info("🔧 Services that will be started: upsdrvctl (drivers), upsd (server), upsmon (monitor)")
                else:
                    logger.info(f"⚠️ Unknown NUT mode: {nut_mode}")
                
                logger.info("🚀 Starting NUT services (this may take several seconds)...")
                
                # This is now the single check for NUT availability
                start_results = start_nut_services(wait_time=2)
                
                # Display detailed results for each service
                logger.info("📊 NUT services startup results:")
                for service_name, result in start_results.items():
                    success = result['success']
                    error = result.get('error')
                    
                    if success:
                        logger.info(f"  ✅ {service_name}: Started successfully")
                    else:
                        logger.warning(f"  ❌ {service_name}: Failed to start - {error}")
                
                if not all(s['success'] for s in start_results.values()):
                    failed_services = [name for name, info in start_results.items() if not info['success']]
                    logger.warning(f"⚠️ Some NUT services failed to start: {', '.join(failed_services)}")
                    
                    # Check if the failure is critical (depends on mode)
                    critical_failure = False
                    if nut_mode == 'netclient' and 'upsmon' in failed_services:
                        # In netclient mode, let's test if upsc works directly
                        logger.info("In netclient mode, testing if upsc works directly even though upsmon failed...")
                        from core.nut.nut_daemon import get_ups_monitor_config, test_ups_connection
                        ups_name, ups_host = get_ups_monitor_config()
                        
                        if ups_name and ups_host:
                            success, _ = test_ups_connection(ups_name, ups_host)
                            if success:
                                logger.info(f"✅ upsc command works successfully for {ups_name}@{ups_host}")
                                logger.info("Continuing in netclient mode with upsc only (without upsmon)")
                                critical_failure = False
                                
                                # Using only system_logger for this warning, avoiding duplication
                                system_logger.warning(f"⚠️ upsmon failed but upsc works in {nut_mode} mode, continuing anyway")
                            else:
                                logger.error("❌ upsc command also failed - cannot operate in netclient mode")
                                critical_failure = True
                        else:
                            logger.error("❌ Could not determine UPS monitor configuration")
                            critical_failure = True
                    elif (nut_mode == 'standalone' or nut_mode == 'netserver'):
                        # For standalone/netserver, upsd and upsmon are critical
                        if 'upsd' in failed_services or 'upsmon' in failed_services:
                            critical_failure = True
                    
                    if critical_failure:
                        issue = (
                            f"Critical NUT services failed in {nut_mode} mode: "
                            f"{', '.join(failed_services)}. Continuing in degraded runtime mode."
                        )
                        logger.error(f"❗ {issue}")
                        startup_issues.append(issue)
                    else:
                        logger.warning("⚠️ Some non-critical NUT services failed, but continuing anyway...")
                        startup_issues.append(
                            f"Non-critical NUT services failed in {nut_mode} mode: {', '.join(failed_services)}"
                        )
                
                # Validate all running services match expected mode
                if nut_mode == 'netclient':
                    # Only upsmon should be running
                    logger.info("✅ NETCLIENT mode: upsmon running")
                elif nut_mode == 'standalone' or nut_mode == 'netserver':
                    # All services should be running
                    running_services = [name for name, info in start_results.items() if info['success']]
                    logger.info(f"✅ {nut_mode.upper()} mode: Running services - {', '.join(running_services)}")
                
                logger.info("✅ Required NUT services started successfully")
                
                # Add a delay to ensure NUT services are fully started before database initialization
                logger.info("🕒 Waiting for NUT services to fully initialize...")
                time.sleep(5)
                
            except NUTConfigError as e:
                logger.warning(f"⚠️ NUT configuration error: {str(e)}")
                startup_issues.append(f"NUT configuration error during startup: {str(e)}")
            except NUTStartupError as e:
                logger.warning(f"⚠️ NUT startup error: {str(e)}")
                startup_issues.append(f"NUT startup error: {str(e)}")
            except Exception as e:
                logger.error(f"❌ Error starting NUT services: {str(e)}")
                startup_issues.append(f"Unexpected NUT startup error: {str(e)}")

            if startup_issues:
                set_app_runtime_state(RUNTIME_STATUS_DEGRADED, startup_issues[-1])
            else:
                set_app_runtime_state(
                    RUNTIME_STATUS_HEALTHY,
                    "NUT services started successfully."
                )
            
            # ======== STEP 2: INITIALIZE DATABASE ========
            logger.info("")
            logger.info("=" * 60)
            logger.info("=====             DATABASE INITIALIZATION             =====")
            logger.info("=" * 60)
            
            # Import db here to ensure it's only used when NUT is configured
            from core.db.ups import db
            from core.db.initializer import init_database
            from core.db.model_classes import register_models_for_global_access
            
            # Check if database file exists, if not or if it's empty, recreate it
            db_path = os.path.join(INSTANCE_PATH, DB_NAME)
            db_needs_init = not os.path.exists(db_path) or os.path.getsize(db_path) == 0
            
            if db_needs_init:
                logger.info("🔄 Database file not found or empty. Creating new database...")
            else:
                logger.info("🔍 Checking database integrity...")
                try:
                    # Check if tables exist by doing a simple query
                    with db.engine.connect() as conn:
                        # Use Inspector to check if the table exists - pure ORM approach
                        inspector = inspect(db.engine)
                        tables_check = 'ups_variables_upscmd' in inspector.get_table_names()
                        if not tables_check:
                            logger.warning("⚠️ Required tables missing in database. Recreating...")
                            db_needs_init = True
                except Exception as e:
                    logger.warning(f"⚠️ Database check failed: {str(e)}. Will reinitialize database.")
                    db_needs_init = True
            
            # Initialize or reinitialize database if needed
            if db_needs_init:
                logger.info("🔄 (Re)initializing database...")
                db.drop_all()  # Remove any partial tables if they exist
                db.create_all()  # Create all tables from scratch
            
            db_init_success = init_database(app, db)
            if not db_init_success:
                logger.error("❌ Database initialization failed!")
                raise Exception("Database initialization failed")
            
            # Check for and patch timestamp column names if needed
            logger.info("🔄 Checking database timestamp columns...")
            try:
                timestamp_columns_ok = check_timestamp_columns(db, app)
                if timestamp_columns_ok:
                    logger.info("✅ Database timestamp columns are correctly named")
                else:
                    logger.info("✅ Database timestamp columns have been patched")
            except Exception as e:
                logger.error(f"❌ Error checking timestamp columns: {str(e)}")
                logger.warning("⚠️ Continuing with application startup despite timestamp column error")

            # Check and patch target-scoped schema columns/indexes
            logger.info("🔄 Checking target scope schema...")
            try:
                target_scope_ok = ensure_target_scope_schema(db)
                if target_scope_ok:
                    logger.info("✅ Target scope schema is valid")
                else:
                    logger.warning("⚠️ Target scope schema check reported issues")
            except Exception as e:
                logger.error(f"❌ Error checking target scope schema: {str(e)}")
                logger.warning("⚠️ Continuing with application startup despite target scope schema error")

            logger.info("🔄 Checking provider render mode schema...")
            try:
                provider_render_mode_ok = ensure_provider_render_mode_schema(db)
                if provider_render_mode_ok:
                    logger.info("✅ Provider render mode schema is valid")
                else:
                    logger.warning("⚠️ Provider render mode schema check reported issues")
            except Exception as e:
                logger.error(f"❌ Error checking provider render mode schema: {str(e)}")
                logger.warning("⚠️ Continuing with application startup despite provider render mode schema error")
            
            # Make sure all models are registered globally
            if hasattr(db, 'ModelClasses'):
                # Register models for global access
                register_models_for_global_access(db.ModelClasses, db)
                logger.info("✅ All models registered globally via ModelClasses")
                
                # Update CACHE_TIMEZONE if needed based on database value
                try:
                    timezone_str = get_target_timezone_setting()
                    if timezone_str and CACHE_TIMEZONE.zone != timezone_str:
                        logger.info(f"🕒 Updating CACHE_TIMEZONE from database: {timezone_str}")
                        # Update the global variable
                        CACHE_TIMEZONE = pytz.timezone(timezone_str)
                        # Update app attribute too
                        app.CACHE_TIMEZONE = CACHE_TIMEZONE
                        logger.info(f"🕒 CACHE_TIMEZONE updated to: {CACHE_TIMEZONE.zone}")
                except Exception as e:
                    logger.warning(f"⚠️ Could not refresh CACHE_TIMEZONE from database: {str(e)}")
            
            logger.info("✅ Database initialization completed successfully")
            
            # ======== INITIALIZE AUTHENTICATION SYSTEM ========
            logger.info("🔐 Initializing authentication system...")
            try:
                from core.auth import init_auth_module, setup_session_config
                from core.auth.security import init_auth_security
                from core.auth.oidc import init_oidc_module
                
                # Get LoginAuth model from database
                if hasattr(db, 'ModelClasses') and hasattr(db.ModelClasses, 'LoginAuth'):
                    login_model = db.ModelClasses.LoginAuth
                    logger.info("✅ LoginAuth model found in database")
                else:
                    logger.warning("⚠️ LoginAuth model not found in database")
                    login_model = None
                
                # Initialize authentication module
                if login_model:
                    init_auth_module(login_model, logger)
                    setup_session_config(app)
                    init_auth_security(app, logger)
                    init_oidc_module(app, logger)
                    logger.info("✅ Authentication system initialized successfully")
                else:
                    logger.warning("⚠️ Authentication system initialization skipped - model not available")
                
            except Exception as e:
                logger.error(f"❌ Error initializing authentication system: {str(e)}")
                logger.warning("⚠️ Authentication features may not work properly")
            
            logger.info("=" * 60)
            
            # Small delay to ensure logs are displayed in order
            time.sleep(0.5)
                
            # ======== STEP 3: INITIALIZE APPLICATION SERVICES ========
            logger.info("")
            logger.info("=" * 60)

            logger.info("=====            APPLICATION SERVICES PHASE           =====")
            logger.info("=" * 60)
            
            # Explicitly load the encryption key first for mail and other components that need it
            try:
                from core.mail import load_encryption_key
                
                # Try loading the encryption key now that app is fully initialized
                if load_encryption_key():
                    logger.info("✅ Secret key loaded successfully for encryption")
                else:
                    logger.warning("⚠️ SECRET_KEY not found in environment - encryption features will be DISABLED")
                    logger.warning("⚠️ Set SECRET_KEY in environment variables or docker-compose.yaml to enable encryption")
            except Exception as key_error:
                logger.error(f"❌ Error loading encryption key: {str(key_error)}")
                logger.warning("⚠️ Encryption features will be DISABLED")

            # Initialize mail models explicitly after database initialization is complete
            logger.info("📧 Initializing mail models...")
            from core.mail import init_mail_models
            mail_models_initialized = init_mail_models()
            if mail_models_initialized:
                logger.info("✅ Mail models initialized successfully")
            else:
                logger.warning("⚠️ Failed to initialize mail models - notifications may not work properly")
            
            # Mail module is already initialized during import, and notification settings
            # are initialized during database initialization in initializer.py
            logger.info("📧 Mail and notification systems ready")
            
            # Initialize Ntfy model
            logger.info("📱 Initializing Ntfy module...")
            from core.extranotifs.ntfy import get_ntfy_model
            # Get the NtfyConfig model from db.ModelClasses
            get_ntfy_model()
            
            # Register Ntfy blueprint
            from core.extranotifs.ntfy.routes import create_blueprint
            ntfy_bp = create_blueprint()
            app.register_blueprint(ntfy_bp)

            # Initialize Telegram model
            logger.info("✈️ Initializing Telegram module...")
            from core.extranotifs.telegram import get_telegram_model
            # Get the TelegramConfig model from db.ModelClasses
            get_telegram_model()

            # Register Telegram blueprint
            from core.extranotifs.telegram.routes import create_blueprint as create_telegram_blueprint
            telegram_bp = create_telegram_blueprint()
            app.register_blueprint(telegram_bp)
            
            # Initialize Webhook model
            logger.info("🌐 Initializing Webhook module...")
            from core.extranotifs.webhook import get_webhook_model
            # Get the WebhookConfig model from db.ModelClasses
            get_webhook_model()
            
            # Register Webhook blueprint
            try:
                from core.extranotifs.webhook.routes import create_blueprint
                webhook_bp = create_blueprint()
                app.register_blueprint(webhook_bp)
                logger.info("✅ Webhook blueprint registered successfully")
                
                # Explicitly load webhook configurations to ensure persistence
                from core.extranotifs.webhook import load_webhook_configurations
                if load_webhook_configurations():
                    logger.info("✅ Webhook configurations loaded successfully")
                else:
                    logger.warning("⚠️ No webhook configurations found or failed to load")
            except ImportError:
                logger.warning("⚠️ Webhook module not available")
            
            # ======== INITIALIZE CACHE WEBSOCKET ========
            logger.info("📡 Initializing Cache WebSocket...")
            from core.db.ups import init_websocket
            init_websocket(app)
            logger.info("✅ Cache WebSocket initialized successfully")
            
            # ======== INITIALIZE CORE COMPONENTS ========
            logger.info("🧩 Initializing core components...")
            from core.init_modules import initialize_core_components
            core_init_success = initialize_core_components()
            if core_init_success:
                logger.info("✅ Core components initialized successfully")
            else:
                logger.warning("⚠️ Some core components failed to initialize")
            
            logger.info("✅ Application services initialized successfully")
            logger.info("=" * 60)
            
            # Small delay to ensure logs are displayed in order
            time.sleep(0.5)
            
            # ======== STEP 4: START UPS DATA POLLING ========
            logger.info("")
            logger.info("=" * 60)

            logger.info("=====           SCHEDULER AND POLLING PHASE           =====")
            logger.info("=" * 60)
            
            logger.info("📋 Initializing Scheduler...")
            from core.report import report_manager
            report_manager.init_app(app)
            scheduler.init_app(app)
            
            # Verify schedulers loaded
            jobs = scheduler.get_scheduled_jobs()
            logger.info(f"📊 Loaded {len(jobs)} scheduled jobs")
            
            # Start polling thread
            logger.info("🔄 Starting UPS data polling thread...")
            thread = threading.Thread(target=polling_thread, daemon=True)
            thread.start()
            
            logger.info("✅ Scheduler initialized successfully")
            logger.info("=" * 60)
            
        logger.info("")
        logger.info("✅ APPLICATION STARTUP COMPLETE ✅")
    except Exception as e:
        logger.critical(f"❌ FATAL ERROR: Failed to initialize application: {str(e)}")
        raise


if __name__ == '__main__':
    warnings.filterwarnings("ignore", message="resource_tracker: There appear to be .* leaked semaphore objects to clean up at shutdown")
    
    # Configure SSL context if enabled
    ssl_context = None
    if SSL_ENABLED:
        if os.path.exists(SSL_CERT) and os.path.exists(SSL_KEY):
            logger.info(f"🔒 SSL enabled with certificate: {SSL_CERT}")
            ssl_context = (SSL_CERT, SSL_KEY)
            
            # Create a wsgi.py file for gunicorn
            wsgi_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'wsgi.py')
            with open(wsgi_path, 'w') as f:
                f.write("""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from app import app, socketio, init_app

# Initialize the application when running with gunicorn
init_app()

if __name__ == '__main__':
    socketio.run(app)
""")
            
            # Start with gunicorn for SSL support
            import subprocess
            logger.info("Starting application with SSL via gunicorn")
            cmd = [
                "gunicorn", 
                "--worker-class", "eventlet", 
                "-w", "1", 
                "--certfile", SSL_CERT, 
                "--keyfile", SSL_KEY,
                "-b", f"{SERVER_HOST}:{SERVER_PORT}", 
                "wsgi:app"
            ]
            logger.info(f"Starting gunicorn with SSL: {' '.join(cmd)}")
            subprocess.Popen(cmd, cwd=os.path.dirname(os.path.abspath(__file__)))
            
            # Keep the main process running to handle signals
            import time
            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                logger.info("Shutting down...")
                sys.exit(0)
        else:
            logger.warning(f"⚠️ SSL certificates not found at {SSL_CERT} and {SSL_KEY}. Running without SSL.")
            ssl_context = None
            # Initialize without SSL since we're not using gunicorn
            init_app()
    else:
        # Initialize without SSL
        init_app()
    
    # Only run socketio directly if not using SSL
    if not SSL_ENABLED or ssl_context is None:
        socketio.run(app, 
            debug=DEBUG_MODE, 
            host=SERVER_HOST, 
            port=SERVER_PORT,
            log_output=use_werkzeug,
            use_reloader=False
        )
