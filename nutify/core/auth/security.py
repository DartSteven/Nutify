"""Authentication security extensions for Nutify."""

from __future__ import annotations

from functools import wraps
from typing import Any, Callable

from flask import flash, jsonify, redirect, request, url_for

try:
    from flask_wtf.csrf import CSRFError, CSRFProtect
except Exception:  # pragma: no cover - optional dependency guard
    CSRFError = None
    CSRFProtect = None

try:
    from flask_limiter import Limiter
    from flask_limiter.util import get_remote_address
except Exception:  # pragma: no cover - optional dependency guard
    Limiter = None
    get_remote_address = None


csrf = CSRFProtect() if CSRFProtect else None
limiter = (
    Limiter(
        key_func=get_remote_address,
        default_limits=[],
        storage_uri='memory://',
        headers_enabled=True,
    )
    if Limiter and get_remote_address
    else None
)

_logger = None


def init_auth_security(app, auth_logger=None):
    """Initialize auth-oriented security controls."""
    global _logger
    _logger = auth_logger

    if app.extensions.get('nutify_auth_security_initialized'):
        return

    app.config.setdefault('WTF_CSRF_ENABLED', True)
    app.config.setdefault('WTF_CSRF_TIME_LIMIT', 3600)
    # Keep global CSRF checks disabled by default and enforce explicitly on auth routes.
    app.config.setdefault('WTF_CSRF_CHECK_DEFAULT', False)

    if csrf:
        csrf.init_app(app)
        if _logger:
            _logger.info("🔐 CSRF protection initialized")
    elif _logger:
        _logger.warning("🔐 CSRF protection unavailable (flask-wtf not installed)")

    if limiter:
        limiter.init_app(app)
        if _logger:
            _logger.info("🔐 Request limiter initialized")
    elif _logger:
        _logger.warning("🔐 Request limiter unavailable (flask-limiter not installed)")

    @app.before_request
    def _protect_auth_forms():
        if request.method in {'GET', 'HEAD', 'OPTIONS', 'TRACE'}:
            return None
        if request.blueprint != 'auth':
            return None
        # Keep API compatibility: do not enforce CSRF on JSON auth APIs yet.
        if request.path.startswith('/auth/api/'):
            return None
        if csrf:
            csrf.protect()
        return None

    if CSRFError:

        @app.errorhandler(CSRFError)
        def _handle_csrf_error(error):
            message = 'Security token invalid or expired. Please retry.'
            if request.is_json or request.path.startswith('/auth/api/'):
                return jsonify({'error': message}), 400
            flash(message, 'error')
            return redirect(request.referrer or url_for('auth.login'))

    app.extensions['nutify_auth_security_initialized'] = True


def rate_limit(limit_value: str, **limit_kwargs):
    """Decorator wrapper that becomes a no-op if limiter is unavailable."""

    def decorator(func: Callable[..., Any]):
        if not limiter:
            return func
        return limiter.limit(limit_value, **limit_kwargs)(func)

    return decorator
