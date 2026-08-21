"""
Authentication Module

This module provides authentication functionality for the Nutify application.
It handles login/logout, session management, and authentication decorators.
"""

from functools import wraps
from flask import session, request, jsonify, redirect, url_for
from typing import Optional, Dict, Any
import os
import secrets
try:
    from flask_login import (
        LoginManager,
        current_user as flask_current_user,
        login_user as flask_login_user,
        logout_user as flask_logout_user,
    )
except Exception:  # pragma: no cover - optional dependency guard
    LoginManager = None
    flask_current_user = None
    flask_login_user = None
    flask_logout_user = None

# These will be set during initialization
LoginAuth = None
logger = None
login_manager = LoginManager() if LoginManager else None
_user_loader_registered = False


def _mark_auth_metadata(func, kind: str, detail: str = ''):
    """Attach auth metadata so runtime route introspection can classify access rules."""
    setattr(func, '_nutify_auth_kind', str(kind or '').strip())
    setattr(func, '_nutify_auth_detail', str(detail or '').strip())
    return func


def _ensure_user_loader_registered() -> None:
    """Register a safe Flask-Login user_loader (works even before DB auth model is ready)."""
    global _user_loader_registered
    if not login_manager or _user_loader_registered:
        return

    @login_manager.user_loader
    def _load_user_by_id(user_id):
        if not LoginAuth:
            return None
        try:
            return LoginAuth.query.filter_by(id=int(user_id), is_active=True).first()
        except Exception:
            return None

    _user_loader_registered = True


def _get_env_flag(name: str) -> bool:
    """Check if an environment variable is set to a truthy value."""
    value = os.getenv(name, '').strip().lower()
    return value in {'1', 'true', 'yes', 'on'}

def is_auth_disabled() -> bool:
    """Check if authentication is disabled via environment variable."""
    return _get_env_flag('DISABLE_AUTH')

def init_auth_module(login_model, auth_logger=None):
    """
    Initialize the authentication module with the LoginAuth model and logger.
    
    Args:
        login_model: The LoginAuth model class
        auth_logger: Logger instance for authentication operations
    """
    global LoginAuth, logger
    LoginAuth = login_model
    logger = auth_logger

    _ensure_user_loader_registered()

    if logger:
        logger.info("🔐 Authentication module initialized")


def _sync_session_from_user(user) -> None:
    """Keep legacy session fields in sync with authenticated user."""
    if not user:
        return
    session['user_id'] = user.id
    session['username'] = user.username
    session['last_login'] = user.last_login.isoformat() if user.last_login else None
    session['role'] = getattr(user, 'role', 'administrator' if user.id == 1 else 'user')
    session.permanent = True

def is_authenticated() -> bool:
    """
    Check if the current user is authenticated.
    
    Returns:
        bool: True if user is authenticated, False otherwise
    """
    if is_auth_disabled():
        return True
    try:
        if flask_current_user is not None and getattr(flask_current_user, 'is_authenticated', False):
            _sync_session_from_user(flask_current_user)
            return True
    except Exception:
        pass
    return 'user_id' in session and 'username' in session

def get_current_user() -> Optional[Dict[str, Any]]:
    """
    Get the current authenticated user information.
    
    Returns:
        dict: User information if authenticated, None otherwise
    """
    if is_auth_disabled():
        return {
            'id': 1,
            'username': 'admin',
            'last_login': None,
            'role': 'administrator'
        }
    try:
        if flask_current_user is not None and getattr(flask_current_user, 'is_authenticated', False):
            _sync_session_from_user(flask_current_user)
    except Exception:
        pass
    if not is_authenticated():
        return None
    
    return {
        'id': session.get('user_id'),
        'username': session.get('username'),
        'last_login': session.get('last_login'),
        'role': session.get('role', 'administrator' if session.get('user_id') == 1 else 'user')
    }

def is_admin() -> bool:
    """
    Check if the current user is an admin.
    Admin is determined by role/is_admin flags.
    
    Returns:
        bool: True if current user is admin, False otherwise
    """
    if is_auth_disabled():
        return True

    if not is_authenticated():
        return False

    # Fast path from session role.
    session_role = str(session.get('role', '')).strip().lower()
    if session_role == 'administrator':
        return True

    # Authoritative check from database.
    user_id = session.get('user_id')
    if not user_id or not LoginAuth:
        return False

    try:
        user = LoginAuth.query.filter_by(id=user_id, is_active=True).first()
        if not user:
            return False

        role = str(getattr(user, 'role', '')).strip().lower()
        is_admin_flag = bool(getattr(user, 'is_admin', False))
        is_user_admin = role == 'administrator' or is_admin_flag

        # Keep session role aligned with DB.
        if is_user_admin and session_role != 'administrator':
            session['role'] = 'administrator'
        elif not is_user_admin and session_role == 'administrator':
            session['role'] = role or 'user'

        return is_user_admin
    except Exception as exc:
        if logger:
            logger.error(f"🔐 Error checking admin role: {str(exc)}")
        return False

def login_user(username: str, password: str) -> bool:
    """
    Authenticate and login a user.
    
    Args:
        username: Username for authentication
        password: Password for authentication
        
    Returns:
        bool: True if login successful, False otherwise
    """
    if not LoginAuth:
        if logger:
            logger.error("🔐 LoginAuth model not initialized")
        return False
    
    user = LoginAuth.authenticate_user(username, password)
    if user:
        if flask_login_user is not None:
            flask_login_user(user, remember=False)
        _sync_session_from_user(user)
        
        if logger:
            logger.info(f"🔐 User {username} logged in successfully")
        return True
    
    if logger:
        logger.warning(f"🔐 Failed login attempt for user: {username}")
    return False

def login_oidc_user(username: str, role: str = 'user'):
    """Provision and log in a user authenticated through OIDC SSO.

    The user is created locally on first login (without a usable local
    password) and its role is aligned with the provider group mapping on
    every login. Local login and the primary admin fallback are unaffected.

    Args:
        username: Username reported by the identity provider.
        role: Role derived from the provider group mapping.

    Returns:
        The provisioned LoginAuth user on success, otherwise None.
    """
    if not LoginAuth:
        if logger:
            logger.error("🔐 LoginAuth model not initialized")
        return None

    try:
        user = LoginAuth.get_or_create_oidc_user(username, role)
    except Exception as exc:
        if logger:
            logger.error(f"🔐 Failed to provision SSO user {username}: {str(exc)}")
        return None

    if flask_login_user is not None:
        flask_login_user(user, remember=False)
    _sync_session_from_user(user)

    if logger:
        logger.info(f"🔐 SSO user {username} logged in successfully")
    return user

def logout_user() -> None:
    """Logout the current user by clearing the session."""
    username = session.get('username', 'unknown')
    if flask_logout_user is not None:
        try:
            flask_logout_user()
        except Exception:
            pass
    session.clear()
    
    if logger:
        logger.info(f"🔐 User {username} logged out")

def require_auth(f):
    """
    Decorator to require authentication for a route.
    
    Args:
        f: The function to decorate
        
    Returns:
        The decorated function
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if is_auth_disabled():
            return f(*args, **kwargs)

        # First check if login system is configured
        if not is_login_configured():
            if request.is_json:
                return jsonify({'error': 'Login system not configured'}), 503
            else:
                return redirect(url_for('auth.setup'))
        
        if not is_authenticated():
            if request.is_json:
                return jsonify({'error': 'Authentication required'}), 401
            else:
                return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return _mark_auth_metadata(decorated_function, 'session')

def require_auth_json(f):
    """
    Decorator to require authentication for JSON API routes.
    
    Args:
        f: The function to decorate
        
    Returns:
        The decorated function
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if is_auth_disabled():
            return f(*args, **kwargs)

        # First check if login system is configured
        if not is_login_configured():
            return jsonify({'error': 'Login system not configured'}), 503
        
        if not is_authenticated():
            return jsonify({'error': 'Authentication required'}), 401
        return f(*args, **kwargs)
    return _mark_auth_metadata(decorated_function, 'session', 'JSON session auth')

def require_admin(f):
    """
    Decorator to require admin privileges for a route.
    
    Args:
        f: The function to decorate
        
    Returns:
        The decorated function
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if is_auth_disabled():
            return f(*args, **kwargs)

        # First check if login system is configured
        if not is_login_configured():
            if request.is_json:
                return jsonify({'error': 'Login system not configured'}), 503
            else:
                return redirect(url_for('auth.setup'))
        
        if not is_authenticated():
            if request.is_json:
                return jsonify({'error': 'Authentication required'}), 401
            else:
                return redirect(url_for('auth.login'))
        
        if not is_admin():
            if request.is_json:
                return jsonify({'error': 'Admin privileges required'}), 403
            else:
                return redirect(url_for('auth.login'))
        
        return f(*args, **kwargs)
    return _mark_auth_metadata(decorated_function, 'admin')

def require_permission(page_name):
    """
    Decorator to require specific page permission for a route.
    
    Args:
        page_name: The name of the page permission to check
        
    Returns:
        The decorated function
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if is_auth_disabled():
                return f(*args, **kwargs)

            # First check if login system is configured
            if not is_login_configured():
                if request.is_json:
                    return jsonify({'error': 'Login system not configured'}), 503
                else:
                    return redirect(url_for('auth.setup'))
            
            if not is_authenticated():
                if request.is_json:
                    return jsonify({'error': 'Authentication required'}), 401
                else:
                    return redirect(url_for('auth.login'))
            
            # Admin can access everything
            if is_admin():
                if logger:
                    logger.debug(f"🔐 Admin access granted to {page_name}")
                return f(*args, **kwargs)
            
            # Check user permissions
            current_user = get_current_user()
            if not current_user:
                if logger:
                    logger.warning(f"🔐 No current user found for {page_name} access")
                if request.is_json:
                    return jsonify({'error': 'Authentication required'}), 401
                else:
                    return redirect(url_for('auth.login'))
            
            try:
                # Get user permissions
                if not LoginAuth:
                    if logger:
                        logger.error(f"🔐 LoginAuth not available for {page_name} permission check")
                    if request.is_json:
                        return jsonify({'error': 'Permission system not available'}), 500
                    else:
                        return "Access denied", 403
                
                user = LoginAuth.query.filter_by(id=current_user['id'], is_active=True).first()
                if not user:
                    if logger:
                        logger.warning(f"🔐 User {current_user['id']} not found or inactive for {page_name}")
                    if request.is_json:
                        return jsonify({'error': 'User not found'}), 403
                    else:
                        return "Access denied", 403
                
                if user.has_permission(page_name):
                    if logger:
                        logger.debug(f"🔐 Permission granted: user {user.username} access to {page_name}")
                    return f(*args, **kwargs)
                
                # Access denied - user doesn't have permission
                if logger:
                    logger.info(f"🔐 Access denied: user {user.username} lacks permission for {page_name}")
                
                if request.is_json:
                    return jsonify({'error': f'Access denied to {page_name} page'}), 403
                else:
                    return "Access denied", 403
                    
            except Exception as e:
                if logger:
                    logger.error(f"🔐 Exception checking permissions for {page_name}: {str(e)}")
                    import traceback
                    logger.error(f"🔐 Traceback: {traceback.format_exc()}")
                
                if request.is_json:
                    return jsonify({'error': 'Error checking permissions'}), 500
                else:
                    return "Access denied", 403
        
        return _mark_auth_metadata(decorated_function, 'permission', page_name)
    return decorator

def is_login_configured() -> bool:
    """
    Check if login system is configured.
    
    Returns:
        bool: True if login is configured, False otherwise
    """
    if is_auth_disabled():
        return True

    if not LoginAuth:
        if logger:
            logger.debug("🔐 LoginAuth model not initialized - login not configured")
        return False
    
    try:
        return LoginAuth.is_login_configured()
    except Exception as e:
        if logger:
            logger.debug(f"🔐 Error checking login configuration: {str(e)}")
        return False

def setup_session_config(app):
    """
    Configure Flask session settings for authentication.
    
    Args:
        app: Flask application instance
    """
    # Generate a secret key if not set
    if not app.config.get('SECRET_KEY'):
        app.config['SECRET_KEY'] = secrets.token_hex(32)
        if logger:
            logger.info("🔐 Generated new secret key for session management")
    
    # Configure session settings
    app.config['SESSION_PERMANENT'] = False
    app.config['PERMANENT_SESSION_LIFETIME'] = 24 * 60 * 60  # 24 hours

    if login_manager:
        _ensure_user_loader_registered()
        login_manager.login_view = 'auth.login'
        login_manager.session_protection = 'basic'
        login_manager.init_app(app)
        if logger:
            logger.info("🔐 Flask-Login initialized")
    
    if logger:
        logger.info("🔐 Session configuration completed") 
