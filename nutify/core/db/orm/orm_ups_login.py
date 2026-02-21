"""
Login Authentication ORM Model.
This module defines the SQLAlchemy ORM model for the orm_login table.
Stores login credentials for user authentication.
"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text
from werkzeug.security import generate_password_hash, check_password_hash
from typing import Optional, Dict, Any
import pytz
import json
from flask import current_app

# These will be set during initialization
db = None
logger = None

class LoginAuth:
    """Model for storing login authentication credentials"""
    __tablename__ = 'orm_login'
    
    id = Column(Integer, primary_key=True)
    username = Column(String(100), nullable=False, unique=True)
    password_hash = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True)
    is_admin = Column(Boolean, default=False)
    role = Column(String(20), default='user')
    permissions = Column(Text, nullable=True)  # JSON string storing page permissions
    options_tabs = Column(Text, nullable=True)  # JSON string storing options tab permissions
    last_login = Column(DateTime(timezone=True), nullable=True)
    # Store all datetimes in UTC
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(pytz.UTC))
    updated_at = Column(DateTime(timezone=True), 
                      default=lambda: datetime.now(pytz.UTC),
                      onupdate=lambda: datetime.now(pytz.UTC))

    def __init__(self, *args, **kwargs):
        # Only call super().__init__ if we have a parent class
        try:
            super().__init__(*args, **kwargs)
        except TypeError:
            # If no parent class, just set attributes directly
            for key, value in kwargs.items():
                setattr(self, key, value)
        
        if logger:
            logger.debug(f"🔐 Creating LoginAuth for username: {getattr(self, 'username', 'unknown')}")

    def set_password(self, password: str) -> None:
        """Set password hash for the user"""
        # Use pbkdf2:sha256 which is more compatible across systems
        self.password_hash = generate_password_hash(password, method='pbkdf2:sha256')
        if logger:
            logger.debug(f"🔐 Password hash set for username: {self.username}")

    def check_password(self, password: str) -> bool:
        """Check if provided password matches the stored hash"""
        result = check_password_hash(self.password_hash, password)
        if logger:
            logger.debug(f"🔐 Password check for username {self.username}: {'✅ SUCCESS' if result else '❌ FAILED'}")
        return result

    def update_last_login(self) -> None:
        """Update the last login timestamp"""
        self.last_login = datetime.now(pytz.UTC)
        if logger:
            logger.debug(f"🔐 Updated last login for username: {self.username}")

    def get_permissions(self) -> Dict[str, bool]:
        """Get user permissions as a dictionary"""
        if self.permissions:
            try:
                return json.loads(self.permissions)
            except json.JSONDecodeError:
                if logger:
                    logger.warning(f"🔐 Invalid permissions JSON for user {self.username}")
                return self.get_default_permissions()
        return self.get_default_permissions()

    def set_permissions(self, permissions: Dict[str, bool]) -> None:
        """Set user permissions from a dictionary"""
        try:
            self.permissions = json.dumps(permissions)
            if logger:
                logger.debug(f"🔐 Updated permissions for user {self.username}")
        except TypeError as e:
            if logger:
                logger.error(f"🔐 Error serializing permissions for user {self.username}: {str(e)}")
            raise

    def get_options_tabs(self) -> Dict[str, bool]:
        """Get user options tabs permissions as a dictionary"""
        if self.options_tabs:
            try:
                return json.loads(self.options_tabs)
            except json.JSONDecodeError:
                if logger:
                    logger.warning(f"🔐 Invalid options_tabs JSON for user {self.username}")
                return self.get_default_options_tabs()
        return self.get_default_options_tabs()

    def set_options_tabs(self, options_tabs: Dict[str, bool]) -> None:
        """Set user options tabs permissions from a dictionary"""
        try:
            self.options_tabs = json.dumps(options_tabs)
            if logger:
                logger.debug(f"🔐 Updated options tabs for user {self.username}")
        except TypeError as e:
            if logger:
                logger.error(f"🔐 Error serializing options tabs for user {self.username}: {str(e)}")
            raise

    def get_default_options_tabs(self) -> Dict[str, bool]:
        """Get default options tabs permissions based on user role"""
        default_tabs = {
            'email': False,
            'extranotifs': False,
            'webhook': False,
            'powerflow': False,
            'database': False,
            'log': False,
            'advanced': False,
            'admin': False
        }
        
        # Role-based default tabs
        if self.role == 'administrator':
            # Administrator can access all tabs
            return {key: True for key in default_tabs.keys()}
        else:
            # All other roles start with no tabs enabled
            return default_tabs

    def get_default_permissions(self) -> Dict[str, bool]:
        """Get default permissions based on user role"""
        # Role-based default permissions
        if self.role == 'administrator':
            # Administrator can access everything
            return {
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
        elif self.role == 'user':
            # User has read-only access, no commands or settings access
            return {
                'home': True,
                'energy': True,
                'power': True,
                'battery': True,
                'voltage': True,
                'info': True,
                'command': False,
                'settings': False,
                'events': True,
                'options': False
            }
        else:
            # Fallback for any unknown role (restrictive)
            return {
                'home': True,
                'energy': True,
                'power': True,
                'battery': True,
                'voltage': True,
                'info': True,
                'command': False,
                'settings': False,
                'events': True,
                'options': False
            }

    def has_permission(self, page: str) -> bool:
        """Check if user has permission to access a specific page"""
        permissions = self.get_permissions()
        return permissions.get(page, False)

    def has_options_tab(self, tab: str) -> bool:
        """Check if user has permission to access a specific options tab"""
        if self.role == 'administrator':
            return True  # Administrator always has access to all tabs
        options_tabs = self.get_options_tabs()
        return options_tabs.get(tab, False)

    def can_access_settings(self) -> bool:
        """Check if user can access settings based on options tabs configuration"""
        if self.role == 'administrator':
            return True  # Administrator always has access
        
        # For non-admin users, check if they have at least one options tab enabled
        options_tabs = self.get_options_tabs()
        return any(options_tabs.values())

    @classmethod
    def get_active_user(cls, username: str) -> Optional['LoginAuth']:
        """Get an active user by username"""
        return cls.query.filter_by(username=username, is_active=True).first()

    @classmethod
    def is_login_configured(cls) -> bool:
        """Check if login system has been configured with at least one active user"""
        try:
            return cls.query.filter_by(is_active=True).count() > 0
        except Exception as e:
            # If table doesn't exist or query fails, login is not configured
            if logger:
                logger.debug(f"🔐 Login configuration check failed (table may not exist): {str(e)}")
            return False

    @classmethod
    def get_first_active_user(cls) -> Optional['LoginAuth']:
        """Get the first active user (for single-user systems)"""
        return cls.query.filter_by(is_active=True).first()

    @classmethod
    def create_user(cls, username: str, password: str, role: str = 'user', is_admin: bool = False) -> 'LoginAuth':
        """
        Create a new user with username, password and role.
        
        Args:
            username: Username for the new user
            password: Plain text password that will be hashed
            role: User role (administrator, user)
            is_admin: Whether user has admin privileges
            
        Returns:
            LoginAuth: The created user instance
        """
        user = cls(username=username, role=role, is_admin=is_admin)
        user.set_password(password)
        
        # Set default permissions based on role
        user.set_permissions(user.get_default_permissions())
        # Set default options tabs based on role
        user.set_options_tabs(user.get_default_options_tabs())
        
        try:
            from core.db.ups import db
            db.session.add(user)
            db.session.commit()
            if logger:
                logger.info(f"🔐 Created new user: {username} with role: {role}")
            return user
        except Exception as e:
            from core.db.ups import db
            db.session.rollback()
            if logger:
                logger.error(f"🔐 Error creating user {username}: {str(e)}")
            raise

    @classmethod
    def update_user_password(cls, username: str, new_password: str) -> bool:
        """
        Update password for an existing user.
        
        Args:
            username: Username of the user to update
            new_password: New plain text password
            
        Returns:
            bool: True if password was updated, False if user not found
        """
        user = cls.get_active_user(username)
        if not user:
            if logger:
                logger.warning(f"🔐 Attempted to update password for non-existent user: {username}")
            return False

        user.set_password(new_password)
        user.updated_at = datetime.now(pytz.UTC)

        try:
            from core.db.ups import db
            db.session.commit()
            if logger:
                logger.info(f"🔐 Updated password for user: {username}")
            return True
        except Exception as e:
            from core.db.ups import db
            db.session.rollback()
            if logger:
                logger.error(f"🔐 Error updating password for user {username}: {str(e)}")
            return False

    @classmethod
    def reset_admin_password(cls, new_password: str, username: Optional[str] = None) -> bool:
        """
        Reset the admin password by updating or creating the primary admin user.

        Args:
            new_password: New plain text password
            username: Optional username to set for the admin user

        Returns:
            bool: True if password was reset successfully, False otherwise
        """
        if not new_password:
            if logger:
                logger.warning("🔐 Admin password reset requested with empty password")
            return False

        try:
            user = cls.query.filter_by(id=1).first()
            if not user and username:
                user = cls.query.filter_by(username=username).first()

            if not user:
                user = cls(
                    username=username or 'admin',
                    role='administrator',
                    is_admin=True,
                    is_active=True
                )
                user.set_password(new_password)
                user.set_permissions(user.get_default_permissions())
                user.set_options_tabs(user.get_default_options_tabs())

                from core.db.ups import db
                db.session.add(user)
                db.session.commit()
                if logger:
                    logger.info("🔐 Created primary admin user via password reset")
                return True

            user.set_password(new_password)
            if username:
                user.username = username
            user.is_active = True
            user.is_admin = True
            user.role = 'administrator'
            if not user.permissions:
                user.set_permissions(user.get_default_permissions())
            if not user.options_tabs:
                user.set_options_tabs(user.get_default_options_tabs())
            user.updated_at = datetime.now(pytz.UTC)

            from core.db.ups import db
            db.session.commit()
            if logger:
                logger.info("🔐 Reset password for primary admin user")
            return True
        except Exception as e:
            from core.db.ups import db
            db.session.rollback()
            if logger:
                logger.error(f"🔐 Error resetting admin password: {str(e)}")
            return False
    @classmethod
    def authenticate_user(cls, username: str, password: str) -> Optional['LoginAuth']:
        """
        Authenticate user with username and password.
        
        Args:
            username: Username to authenticate
            password: Plain text password
            
        Returns:
            LoginAuth: User instance if authentication successful, None otherwise
        """
        user = cls.get_active_user(username)
        if user and user.check_password(password):
            user.update_last_login()
            try:
                from core.db.ups import db
                db.session.commit()
                if logger:
                    logger.info(f"🔐 Successful authentication for user: {username}")
                return user
            except Exception as e:
                from core.db.ups import db
                db.session.rollback()
                if logger:
                    logger.error(f"🔐 Error updating last login for user {username}: {str(e)}")
                return user  # Return user even if last login update fails
        else:
            if logger:
                logger.warning(f"🔐 Failed authentication attempt for user: {username}")
            return None

    @classmethod
    def deactivate_user(cls, username: str) -> bool:
        """
        Deactivate a user (soft delete).
        
        Args:
            username: Username to deactivate
            
        Returns:
            bool: True if user was deactivated, False if user not found
        """
        user = cls.get_active_user(username)
        if not user:
            return False
        
        user.is_active = False
        user.updated_at = datetime.now(pytz.UTC)
        
        try:
            from core.db.ups import db
            db.session.commit()
            if logger:
                logger.info(f"🔐 Deactivated user: {username}")
            return True
        except Exception as e:
            from core.db.ups import db
            db.session.rollback()
            if logger:
                logger.error(f"🔐 Error deactivating user {username}: {str(e)}")
            return False
    
    @classmethod
    def delete_user(cls, username: str) -> bool:
        """
        Permanently delete a user from the database.
        
        Args:
            username: Username to delete
            
        Returns:
            bool: True if user was deleted, False if user not found
        """
        user = cls.query.filter_by(username=username).first()
        if not user:
            return False
        
        try:
            from core.db.ups import db
            db.session.delete(user)
            db.session.commit()
            if logger:
                logger.info(f"🔐 Permanently deleted user: {username}")
            return True
        except Exception as e:
            from core.db.ups import db
            db.session.rollback()
            if logger:
                logger.error(f"🔐 Error deleting user {username}: {str(e)}")
            return False

    def to_dict(self) -> dict:
        """Convert user to dictionary (without password hash)"""
        return {
            'id': self.id,
            'username': self.username,
            'is_active': self.is_active,
            'last_login': self.last_login.isoformat() if self.last_login else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

    def __repr__(self):
        return f'<LoginAuth {self.username}>'


def init_model(model_base, db_logger=None):
    """
    Initialize the LoginAuth model with the provided base class and logger.
    
    Args:
        model_base: SQLAlchemy model base class
        db_logger: Logger instance for database operations
        
    Returns:
        LoginAuth: The initialized model class
    """
    global logger
    logger = db_logger
    
    class LoginAuthModel(model_base, LoginAuth):
        """ORM model for login authentication"""
        __table_args__ = {'extend_existing': True}
    
    if logger:
        logger.info("🔐 Initialized LoginAuth ORM model")
    
    return LoginAuthModel