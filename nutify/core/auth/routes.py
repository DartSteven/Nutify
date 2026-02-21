"""
Authentication Routes

This module provides Flask routes for user authentication including login, logout,
initial setup, and admin panel.
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, current_app
from . import (
    login_user,
    logout_user,
    is_authenticated,
    get_current_user,
    is_login_configured,
    is_admin,
    is_auth_disabled,
    require_admin
)
from datetime import datetime
import pytz
from core.logger import web_logger as logger

# Create blueprint
auth_bp = Blueprint('auth', __name__, url_prefix='/auth')

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """Login page and handler"""
    if is_auth_disabled():
        if not is_login_configured():
            flash('Authentication is disabled. Create an admin user first.', 'info')
            return redirect(url_for('auth.setup'))
        flash('Authentication is disabled', 'info')
        return redirect(url_for('index'))
    # If already authenticated, redirect to main page
    if is_authenticated():
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        
        if not username or not password:
            flash('Username and password are required', 'error')
            return render_template('auth/login.html')
        
        if login_user(username, password):
            logger.info(f"🔐 Successful login for user: {username}")
            next_page = request.args.get('next')
            return redirect(next_page) if next_page else redirect(url_for('index'))
        else:
            flash('Invalid username or password', 'error')
            logger.warning(f"🔐 Failed login attempt for user: {username}")
    
    return render_template('auth/login.html')

@auth_bp.route('/logout')
def logout():
    """Logout handler"""
    if is_auth_disabled():
        return redirect(url_for('index'))
    logout_user()
    flash('You have been logged out', 'success')
    return redirect(url_for('auth.login'))

@auth_bp.route('/setup', methods=['GET', 'POST'])
def setup():
    """Initial setup page for creating the first user"""
    if is_auth_disabled() and is_login_configured():
        flash('Authentication is disabled', 'info')
        return redirect(url_for('index'))
    # If login is already configured, redirect to login
    if is_login_configured():
        return redirect(url_for('auth.login'))
    
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        
        # Validation
        if not username or not password or not confirm_password:
            flash('All fields are required', 'error')
            return render_template('auth/setup.html')
        
        if len(username) < 3:
            flash('Username must be at least 3 characters long', 'error')
            return render_template('auth/setup.html')
        
        if len(password) < 6:
            flash('Password must be at least 6 characters long', 'error')
            return render_template('auth/setup.html')
        
        if password != confirm_password:
            flash('Passwords do not match', 'error')
            return render_template('auth/setup.html')
        
        try:
            # Create the first user
            from . import LoginAuth
            if LoginAuth is None:
                flash('Authentication system not initialized', 'error')
                logger.error("🔐 LoginAuth model is None - authentication system not properly initialized")
                return render_template('auth/setup.html')
            
            user = LoginAuth.create_user(username, password, role='administrator', is_admin=True)
            
            # Automatically log in the user after setup (unless auth is disabled)
            if is_auth_disabled():
                flash('Login system configured successfully!', 'success')
                logger.info(f"🔐 Initial setup completed - created user: {username}")
                return redirect(url_for('index'))
            if login_user(username, password):
                flash('Login system configured successfully! You are now logged in.', 'success')
                logger.info(f"🔐 Initial setup completed - created and logged in user: {username}")
                return redirect(url_for('index'))
            flash('Login system configured successfully! You can now log in.', 'success')
            logger.info(f"🔐 Initial setup completed - created user: {username}")
            return redirect(url_for('auth.login'))
        except Exception as e:
            flash(f'Error creating user: {str(e)}', 'error')
            logger.error(f"🔐 Error during initial setup: {str(e)}")
    
    return render_template('auth/setup.html')

@auth_bp.route('/admin', methods=['GET', 'POST'])
def admin():
    """Admin panel for managing login credentials"""
    if is_auth_disabled():
        flash('Authentication is disabled', 'info')
        return redirect(url_for('index'))
    # Check if user is authenticated
    if not is_authenticated():
        return redirect(url_for('auth.login', next=request.url))
    
    current_user = get_current_user()
    
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'change_password':
            current_password = request.form.get('current_password', '')
            new_password = request.form.get('new_password', '')
            confirm_new_password = request.form.get('confirm_new_password', '')
            
            # Validation
            if not current_password or not new_password or not confirm_new_password:
                flash('All fields are required', 'error')
                return render_template('auth/admin.html', current_user=current_user)
            
            if new_password != confirm_new_password:
                flash('New passwords do not match', 'error')
                return render_template('auth/admin.html', current_user=current_user)
            
            if len(new_password) < 6:
                flash('New password must be at least 6 characters long', 'error')
                return render_template('auth/admin.html', current_user=current_user)
            
            # Verify current password
            from . import LoginAuth
            if LoginAuth is None:
                flash('Authentication system not initialized', 'error')
                return render_template('auth/admin.html', current_user=current_user)
                
            user = LoginAuth.get_active_user(current_user['username'])
            if not user or not user.check_password(current_password):
                flash('Current password is incorrect', 'error')
                return render_template('auth/admin.html', current_user=current_user)
            
            # Update password
            if LoginAuth.update_user_password(current_user['username'], new_password):
                flash('Password updated successfully', 'success')
                logger.info(f"🔐 Password updated for user: {current_user['username']}")
            else:
                flash('Error updating password', 'error')
                logger.error(f"🔐 Failed to update password for user: {current_user['username']}")
        
        elif action == 'change_username':
            new_username = request.form.get('new_username', '').strip()
            password = request.form.get('password', '')
            
            # Validation
            if not new_username or not password:
                flash('Username and password are required', 'error')
                return render_template('auth/admin.html', current_user=current_user)
            
            if len(new_username) < 3:
                flash('Username must be at least 3 characters long', 'error')
                return render_template('auth/admin.html', current_user=current_user)
            
            # Verify password
            from . import LoginAuth
            if LoginAuth is None:
                flash('Authentication system not initialized', 'error')
                return render_template('auth/admin.html', current_user=current_user)
                
            user = LoginAuth.get_active_user(current_user['username'])
            if not user or not user.check_password(password):
                flash('Password is incorrect', 'error')
                return render_template('auth/admin.html', current_user=current_user)
            
            # Check if new username already exists
            if LoginAuth.get_active_user(new_username):
                flash('Username already exists', 'error')
                return render_template('auth/admin.html', current_user=current_user)
            
            # Update username
            try:
                user.username = new_username
                from core.db.ups import db
                db.session.commit()
                
                # Update session
                from flask import session
                session['username'] = new_username
                
                flash('Username updated successfully', 'success')
                logger.info(f"🔐 Username updated from {current_user['username']} to {new_username}")
                
                # Update current_user for template
                current_user['username'] = new_username
                
            except Exception as e:
                from core.db.ups import db
                db.session.rollback()
                flash(f'Error updating username: {str(e)}', 'error')
                logger.error(f"🔐 Error updating username: {str(e)}")
    
    return render_template('auth/admin.html', current_user=current_user)

@auth_bp.route('/api/status')
def api_status():
    """API endpoint to check authentication status"""
    current_user = get_current_user()
    permissions = {}
    user_role = None
    

    if is_auth_disabled():
        permissions = {
            'home': True,
            'energy': True,
            'power': True,
            'battery': True,
            'voltage': True,
            'info': True,
            'command': True,
            'settings': True,
            'events': True,
            'options': True
        }

    # If user is authenticated, get their permissions and role
    if not is_auth_disabled() and is_authenticated() and current_user:
        try:
            from . import LoginAuth
            if LoginAuth:
                user = LoginAuth.query.filter_by(id=current_user['id'], is_active=True).first()
                if user:
                    permissions = user.get_permissions()
                    # Get the actual role from database or use fallback
                    user_role = getattr(user, 'role', 'admin' if user.id == 1 else 'viewer')
        except Exception as e:
            logger.error(f"🔐 Error getting user permissions: {str(e)}")
    
    # Update current_user with role if available
    if current_user and user_role:
        current_user['role'] = user_role
    
    return jsonify({
        'is_authenticated': is_authenticated(),
        'is_configured': is_login_configured(),
        'current_user': current_user,
        'is_admin': is_admin(),
        'permissions': permissions,
        'auth_disabled': is_auth_disabled()
    })

@auth_bp.route('/api/login', methods=['POST'])
def api_login():
    """API endpoint for login"""
    if is_auth_disabled():
        return jsonify({'error': 'Authentication is disabled'}), 403
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Invalid request data'}), 400
    
    username = data.get('username', '').strip()
    password = data.get('password', '')
    
    if not username or not password:
        return jsonify({'error': 'Username and password are required'}), 400
    
    if login_user(username, password):
        return jsonify({
            'success': True,
            'message': 'Login successful',
            'user': get_current_user()
        })
    else:
        return jsonify({'error': 'Invalid username or password'}), 401

@auth_bp.route('/api/logout', methods=['POST'])
def api_logout():
    """API endpoint for logout"""
    if is_auth_disabled():
        return jsonify({
            'success': True,
            'message': 'Authentication disabled - no logout required',
            'redirect_url': url_for('index')
        })
    logout_user()
    return jsonify({
        'success': True,
        'message': 'Logout successful',
        'redirect_url': url_for('auth.login')
    })

@auth_bp.route('/api/change-password', methods=['POST'])
def api_change_password():
    """API endpoint for changing password"""
    if is_auth_disabled():
        return jsonify({'error': 'Authentication is disabled'}), 403
    if not is_authenticated():
        return jsonify({'error': 'Authentication required'}), 401
    
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Invalid request data'}), 400
    
    current_password = data.get('current_password', '')
    new_password = data.get('new_password', '')
    
    if not current_password or not new_password:
        return jsonify({'error': 'Current password and new password are required'}), 400
    
    if len(new_password) < 6:
        return jsonify({'error': 'New password must be at least 6 characters long'}), 400
    
    try:
        from . import LoginAuth
        if LoginAuth is None:
            return jsonify({'error': 'Authentication system not initialized'}), 500
        
        current_user = get_current_user()
        user = LoginAuth.get_active_user(current_user['username'])
        
        if not user or not user.check_password(current_password):
            return jsonify({'error': 'Current password is incorrect'}), 400
        
        if LoginAuth.update_user_password(current_user['username'], new_password):
            logger.info(f"🔐 Password updated for user: {current_user['username']}")
            return jsonify({'success': True, 'message': 'Password updated successfully'})
        else:
            return jsonify({'error': 'Failed to update password'}), 500
            
    except Exception as e:
        logger.error(f"🔐 Error changing password: {str(e)}")
        return jsonify({'error': 'An error occurred while updating password'}), 500

@auth_bp.route('/api/change-username', methods=['POST'])
def api_change_username():
    """API endpoint for changing username"""
    if is_auth_disabled():
        return jsonify({'error': 'Authentication is disabled'}), 403
    if not is_authenticated():
        return jsonify({'error': 'Authentication required'}), 401
    
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Invalid request data'}), 400
    
    new_username = data.get('new_username', '').strip()
    password = data.get('password', '')
    
    if not new_username or not password:
        return jsonify({'error': 'New username and password are required'}), 400
    
    if len(new_username) < 3:
        return jsonify({'error': 'Username must be at least 3 characters long'}), 400
    
    try:
        from . import LoginAuth
        if LoginAuth is None:
            return jsonify({'error': 'Authentication system not initialized'}), 500
        
        current_user = get_current_user()
        user = LoginAuth.get_active_user(current_user['username'])
        
        if not user or not user.check_password(password):
            return jsonify({'error': 'Password is incorrect'}), 400
        
        # Check if new username already exists
        if LoginAuth.get_active_user(new_username):
            return jsonify({'error': 'Username already exists'}), 400
        
        # Update username
        user.username = new_username
        from core.db.ups import db
        db.session.commit()
        
        # Update session
        from flask import session
        session['username'] = new_username
        
        logger.info(f"🔐 Username updated from {current_user['username']} to {new_username}")
        return jsonify({
            'success': True, 
            'message': 'Username updated successfully',
            'new_username': new_username
        })
        
    except Exception as e:
        from core.db.ups import db
        db.session.rollback()
        logger.error(f"🔐 Error changing username: {str(e)}")
        return jsonify({'error': 'An error occurred while updating username'}), 500

@auth_bp.route('/api/admin/users', methods=['GET'])
@require_admin
def api_admin_get_users():
    """API endpoint to get all users (admin only)"""
    try:
        from . import LoginAuth
        if LoginAuth is None:
            return jsonify({'error': 'Authentication system not initialized'}), 500
        
        users = LoginAuth.query.filter_by(is_active=True).all()
        users_data = []
        
        for user in users:
            users_data.append({
                'id': user.id,
                'username': user.username,
                'role': getattr(user, 'role', 'admin' if user.id == 1 else 'viewer'),
                'is_admin': user.id == 1,  # First user is admin
                'last_login': user.last_login.isoformat() if user.last_login else None,
                'created_at': user.created_at.isoformat() if user.created_at else None
            })
        
        return jsonify({'success': True, 'users': users_data})
        
    except Exception as e:
        logger.error(f"🔐 Error fetching users: {str(e)}")
        return jsonify({'error': 'An error occurred while fetching users'}), 500

@auth_bp.route('/api/admin/users', methods=['POST'])
@require_admin
def api_admin_create_user():
    """API endpoint to create a new user (admin only)"""
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Invalid request data'}), 400
    
    username = data.get('username', '').strip()
    password = data.get('password', '')
    role = data.get('role', 'viewer')
    
    if not username or not password or not role:
        return jsonify({'error': 'Username, password and role are required'}), 400
    
    if len(username) < 3:
        return jsonify({'error': 'Username must be at least 3 characters long'}), 400
    
    if len(password) < 6:
        return jsonify({'error': 'Password must be at least 6 characters long'}), 400
    
    if role not in ['administrator', 'user']:
        return jsonify({'error': 'Invalid role specified'}), 400
    
    try:
        from . import LoginAuth
        if LoginAuth is None:
            return jsonify({'error': 'Authentication system not initialized'}), 500
        
        # Check if username already exists
        if LoginAuth.get_active_user(username):
            return jsonify({'error': 'Username already exists'}), 400
        
        # Create new user with specified role
        is_admin = role == 'administrator'
        user = LoginAuth.create_user(username, password, role=role, is_admin=is_admin)
        
        role_text = role.capitalize()
        logger.info(f"🔐 Admin created new {role_text}: {username}")
        
        return jsonify({
            'success': True,
            'message': f'User created successfully as {role_text}',
            'user': {
                'id': user.id,
                'username': user.username,
                'role': getattr(user, 'role', 'viewer'),
                'is_admin': getattr(user, 'is_admin', user.id == 1),
                'created_at': user.created_at.isoformat() if user.created_at else None
            }
        })
        
    except Exception as e:
        logger.error(f"🔐 Error creating user: {str(e)}")
        return jsonify({'error': 'An error occurred while creating user'}), 500

@auth_bp.route('/api/admin/users/<int:user_id>/password', methods=['PUT'])
@require_admin
def api_admin_update_user_password(user_id):
    """API endpoint to update user password (admin only)"""
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Invalid request data'}), 400
    
    new_password = data.get('new_password', '')
    
    if not new_password:
        return jsonify({'error': 'New password is required'}), 400
    
    if len(new_password) < 6:
        return jsonify({'error': 'New password must be at least 6 characters long'}), 400
    
    try:
        from . import LoginAuth
        if LoginAuth is None:
            return jsonify({'error': 'Authentication system not initialized'}), 500
        
        # Get user by ID
        user = LoginAuth.query.filter_by(id=user_id, is_active=True).first()
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        # Update password
        if LoginAuth.update_user_password(user.username, new_password):
            logger.info(f"🔐 Admin updated password for user: {user.username}")
            return jsonify({'success': True, 'message': 'Password updated successfully'})
        else:
            return jsonify({'error': 'Failed to update password'}), 500
            
    except Exception as e:
        logger.error(f"🔐 Error updating user password: {str(e)}")
        return jsonify({'error': 'An error occurred while updating password'}), 500

@auth_bp.route('/api/admin/users/<int:user_id>/role', methods=['PUT'])
@require_admin
def api_admin_update_user_role(user_id):
    """API endpoint to update user role (admin only)"""
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Invalid request data'}), 400
    
    new_role = data.get('role', '')
    
    if not new_role:
        return jsonify({'error': 'Role is required'}), 400
    
    if new_role not in ['administrator', 'user']:
        return jsonify({'error': 'Invalid role specified'}), 400
    
    try:
        from . import LoginAuth
        if LoginAuth is None:
            return jsonify({'error': 'Authentication system not initialized'}), 500
        
        # Get user by ID
        user = LoginAuth.query.filter_by(id=user_id, is_active=True).first()
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        # Don't allow changing role of user ID 1 (main admin)
        if user_id == 1:
            return jsonify({'error': 'Cannot change role of primary administrator'}), 400
        
        # Update role
        user.role = new_role
        user.is_admin = (new_role == 'administrator')
        
        from core.db.ups import db
        db.session.commit()
        
        logger.info(f"🔐 Admin updated role for user {user.username} to {new_role}")
        return jsonify({'success': True, 'message': 'Role updated successfully'})
        
    except Exception as e:
        from core.db.ups import db
        db.session.rollback()
        logger.error(f"🔐 Error updating user role: {str(e)}")
        return jsonify({'error': 'An error occurred while updating role'}), 500

@auth_bp.route('/api/admin/users/<int:user_id>', methods=['DELETE'])
@require_admin
def api_admin_delete_user(user_id):
    """API endpoint to delete user (admin only)"""
    # Prevent admin from deleting themselves
    current_user = get_current_user()
    if current_user and current_user['id'] == user_id:
        return jsonify({'error': 'Cannot delete your own account'}), 400
    
    # Prevent deleting the first user (admin)
    if user_id == 1:
        return jsonify({'error': 'Cannot delete the main admin account'}), 400
    
    try:
        from . import LoginAuth
        if LoginAuth is None:
            return jsonify({'error': 'Authentication system not initialized'}), 500
        
        # Get user by ID
        user = LoginAuth.query.filter_by(id=user_id, is_active=True).first()
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        # Permanently delete user
        if LoginAuth.delete_user(user.username):
            logger.info(f"🔐 Admin deleted user: {user.username}")
            return jsonify({'success': True, 'message': 'User deleted successfully'})
        else:
            return jsonify({'error': 'Failed to delete user'}), 500
            
    except Exception as e:
        logger.error(f"🔐 Error deleting user: {str(e)}")
        return jsonify({'error': 'An error occurred while deleting user'}), 500

@auth_bp.route('/api/admin/users/<int:user_id>/permissions', methods=['GET'])
@require_admin
def api_admin_get_user_permissions(user_id):
    """API endpoint to get user page permissions (admin only)"""
    try:
        from . import LoginAuth
        if LoginAuth is None:
            return jsonify({'error': 'Authentication system not initialized'}), 500
        
        # Get user by ID
        user = LoginAuth.query.filter_by(id=user_id, is_active=True).first()
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        # Get user permissions from database or defaults
        permissions = user.get_permissions()
        user_role = getattr(user, 'role', 'viewer')
        
        return jsonify({
            'success': True,
            'permissions': permissions,
            'user_role': user_role
        })
        
    except Exception as e:
        logger.error(f"🔐 Error fetching user permissions: {str(e)}")
        return jsonify({'error': 'An error occurred while fetching user permissions'}), 500

@auth_bp.route('/api/admin/users/<int:user_id>/permissions', methods=['POST'])
@require_admin
def api_admin_update_user_permissions(user_id):
    """API endpoint to update user page permissions (admin only)"""
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Invalid request data'}), 400
    
    permissions = data.get('permissions', {})
    if not isinstance(permissions, dict):
        return jsonify({'error': 'Permissions must be a dictionary'}), 400
    
    # Validate permission keys
    valid_pages = ['home', 'energy', 'power', 'battery', 'voltage', 'info', 'command', 'settings', 'events', 'options']
    for page in permissions.keys():
        if page not in valid_pages:
            return jsonify({'error': f'Invalid page permission: {page}'}), 400
    
    try:
        from . import LoginAuth
        if LoginAuth is None:
            return jsonify({'error': 'Authentication system not initialized'}), 500
        
        # Get user by ID
        user = LoginAuth.query.filter_by(id=user_id, is_active=True).first()
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        # Save permissions to database
        user.set_permissions(permissions)
        user.updated_at = datetime.now(pytz.UTC)
        
        from core.db.ups import db
        db.session.commit()
        
        logger.info(f"🔐 Admin updated permissions for user {user.username}: {permissions}")
        
        return jsonify({
            'success': True,
            'message': 'User permissions updated successfully',
            'permissions': permissions
        })
        
    except Exception as e:
        from core.db.ups import db
        db.session.rollback()
        logger.error(f"🔐 Error updating user permissions: {str(e)}")
        return jsonify({'error': 'An error occurred while updating user permissions'}), 500

@auth_bp.route('/api/admin/users/<int:user_id>/options-tabs', methods=['GET'])
@require_admin
def api_admin_get_user_options_tabs(user_id):
    """API endpoint to get user options tabs permissions (admin only)"""
    try:
        from . import LoginAuth
        if LoginAuth is None:
            return jsonify({'error': 'Authentication system not initialized'}), 500
        
        # Get user by ID
        user = LoginAuth.query.filter_by(id=user_id, is_active=True).first()
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        # Get user options tabs from database or defaults
        options_tabs = user.get_options_tabs()
        user_role = getattr(user, 'role', 'viewer')
        
        return jsonify({
            'success': True,
            'options_tabs': options_tabs,
            'user_role': user_role
        })
        
    except Exception as e:
        logger.error(f"🔐 Error fetching user options tabs: {str(e)}")
        return jsonify({'error': 'An error occurred while fetching user options tabs'}), 500

@auth_bp.route('/api/admin/users/<int:user_id>/options-tabs', methods=['POST'])
@require_admin
def api_admin_update_user_options_tabs(user_id):
    """API endpoint to update user options tabs permissions (admin only)"""
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Invalid request data'}), 400
    
    options_tabs = data.get('options_tabs', {})
    if not isinstance(options_tabs, dict):
        return jsonify({'error': 'Options tabs must be a dictionary'}), 400
    
    # Validate tab keys
    valid_tabs = ['email', 'extranotifs', 'webhook', 'powerflow', 'database', 'log', 'advanced', 'admin']
    for tab in options_tabs.keys():
        if tab not in valid_tabs:
            return jsonify({'error': f'Invalid options tab: {tab}'}), 400
    
    try:
        from . import LoginAuth
        if LoginAuth is None:
            return jsonify({'error': 'Authentication system not initialized'}), 500
        
        # Get user by ID
        user = LoginAuth.query.filter_by(id=user_id, is_active=True).first()
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        # Save options tabs to database
        user.set_options_tabs(options_tabs)
        user.updated_at = datetime.now(pytz.UTC)
        
        from core.db.ups import db
        db.session.commit()
        
        logger.info(f"🔐 Admin updated options tabs for user {user.username}: {options_tabs}")
        
        return jsonify({
            'success': True,
            'message': 'User options tabs updated successfully',
            'options_tabs': options_tabs
        })
        
    except Exception as e:
        from core.db.ups import db
        db.session.rollback()
        logger.error(f"🔐 Error updating user options tabs: {str(e)}")
        return jsonify({'error': 'An error occurred while updating user options tabs'}), 500

def register_auth_routes(app):
    """Register authentication routes with the Flask app"""
    app.register_blueprint(auth_bp)
    logger.info("🔐 Authentication routes registered")
