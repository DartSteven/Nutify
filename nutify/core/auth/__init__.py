"""
Authentication Module

This module provides authentication functionality for the Nutify application.
It handles login/logout, session management, and authentication decorators.
"""

from functools import wraps
from flask import session, request, jsonify, redirect, url_for, current_app, render_template
from typing import Optional, Dict, Any
import os
import secrets

# These will be set during initialization
LoginAuth = None
logger = None

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
    
    if logger:
        logger.info("🔐 Authentication module initialized")

def is_authenticated() -> bool:
    """
    Check if the current user is authenticated.
    
    Returns:
        bool: True if user is authenticated, False otherwise
    """
    if is_auth_disabled():
        return True
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
    if not is_authenticated():
        return None
    
    return {
        'id': session.get('user_id'),
        'username': session.get('username'),
        'last_login': session.get('last_login'),
        'role': session.get('role', 'admin' if session.get('user_id') == 1 else 'viewer')
    }

def is_admin() -> bool:
    """
    Check if the current user is an admin.
    Admin is determined by being the first user created (ID = 1).
    
    Returns:
        bool: True if current user is admin, False otherwise
    """
    if is_auth_disabled():
        return True

    if not is_authenticated():
        return False
    
    user_id = session.get('user_id')
    if not user_id:
        return False
    
    # Admin is the first user created (ID = 1)
    return user_id == 1

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
        session['user_id'] = user.id
        session['username'] = user.username
        session['last_login'] = user.last_login.isoformat() if user.last_login else None
        session['role'] = getattr(user, 'role', 'admin' if user.id == 1 else 'viewer')
        session.permanent = True
        
        if logger:
            logger.info(f"🔐 User {username} logged in successfully")
        return True
    
    if logger:
        logger.warning(f"🔐 Failed login attempt for user: {username}")
    return False

def logout_user() -> None:
    """Logout the current user by clearing the session."""
    username = session.get('username', 'unknown')
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
    return decorated_function

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
    return decorated_function

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
    return decorated_function

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
                        return render_template('auth/access_denied.html', page_name=page_name.capitalize()), 403
                
                user = LoginAuth.query.filter_by(id=current_user['id'], is_active=True).first()
                if not user:
                    if logger:
                        logger.warning(f"🔐 User {current_user['id']} not found or inactive for {page_name}")
                    if request.is_json:
                        return jsonify({'error': 'User not found'}), 403
                    else:
                        return render_template('auth/access_denied.html', page_name=page_name.capitalize()), 403
                
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
                    # Render access denied page
                    return render_template('auth/access_denied.html', page_name=page_name.capitalize()), 403
                    
            except Exception as e:
                if logger:
                    logger.error(f"🔐 Exception checking permissions for {page_name}: {str(e)}")
                    import traceback
                    logger.error(f"🔐 Traceback: {traceback.format_exc()}")
                
                if request.is_json:
                    return jsonify({'error': 'Error checking permissions'}), 500
                else:
                    # Show access denied instead of redirect on error
                    return render_template('auth/access_denied.html', page_name=page_name.capitalize()), 403
        
        return decorated_function
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
    
    if logger:
        logger.info("🔐 Session configuration completed") 
