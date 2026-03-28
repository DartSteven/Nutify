"""Centralized API security guard for session and admin enforcement.

This module applies a single request-level security policy for API routes
so that endpoints are not left public by omission.
"""

from __future__ import annotations

from collections.abc import Iterable

from flask import jsonify, request

from . import is_admin, is_auth_disabled, is_authenticated, is_login_configured


_PUBLIC_ALWAYS_PATHS = frozenset(
    {
        '/api/frontend/bootstrap',
        '/api/nut_event',
    }
)

_SETUP_BOOTSTRAP_PATHS = frozenset(
    {
        '/api/options/options-from-initial-setup',
        '/nut_config/api/restart',
        '/nut_config/api/delete-config',
    }
)

_SETUP_BOOTSTRAP_PREFIXES = (
    '/nut_config/api/setup/',
)

_GUARDED_PREFIXES = (
    '/api/',
    '/nut_config/api/',
)

_ADMIN_ONLY_PREFIXES = (
    '/api/advanced/',
    '/api/nut/',
    '/api/log/',
    '/api/options/database/',
    '/api/options/logs',
    '/api/database/',
    '/api/settings/mail',
    '/api/logs/',
    '/api/ntfy/',
    '/api/telegram/',
    '/api/webhook/',
    '/nut_config/api/',
)

_ADMIN_ONLY_EXACT = frozenset(
    {
        '/api/restart',
        '/api/settings',
        '/api/settings/reload',
        '/api/settings/log',
        '/api/upsrw/set',
        '/api/upsrw/clear-history',
        '/api/logs',
    }
)


def _is_guarded_path(path: str) -> bool:
    normalized = str(path or '').strip()
    if not normalized:
        return False
    return normalized.startswith(_GUARDED_PREFIXES)


def _is_setup_bootstrap_path(path: str) -> bool:
    normalized = str(path or '').strip()
    if not normalized:
        return False
    if normalized in _SETUP_BOOTSTRAP_PATHS:
        return True
    return normalized.startswith(_SETUP_BOOTSTRAP_PREFIXES)


def _is_admin_only_path(path: str, methods: Iterable[str] | None = None) -> bool:
    normalized = str(path or '').strip()
    if not normalized:
        return False

    if normalized in _ADMIN_ONLY_EXACT:
        return True
    if normalized.startswith(_ADMIN_ONLY_PREFIXES):
        return True

    method_set = {str(method or '').upper() for method in (methods or ())}
    if normalized == '/api/options/options-from-initial-setup':
        return bool(method_set - {'', 'GET', 'HEAD', 'OPTIONS'})

    return False


def classify_route_access(path: str, methods: Iterable[str] | None):
    """Return access metadata inferred from centralized guard rules."""
    normalized_path = str(path or '').strip()
    normalized_methods = {str(method or '').upper() for method in (methods or ())}

    if normalized_path in _PUBLIC_ALWAYS_PATHS:
        if normalized_path == '/api/nut_event':
            return (
                'token',
                'Token: X-Nutify-Token',
                'Requires callback token header and rejects unsigned callbacks',
            )
        return ('public', 'Public', 'Required for pre-login frontend bootstrap flow')

    if _is_guarded_path(normalized_path):
        if _is_admin_only_path(normalized_path, normalized_methods):
            return ('admin', 'Admin only', 'Requires authenticated admin session')
        if _is_setup_bootstrap_path(normalized_path):
            return (
                'session',
                'Private (session)',
                'Public only during first setup, then protected by authenticated session',
            )
        return ('session', 'Private (session)', 'Requires authenticated user session')

    return None


def register_api_request_guard(app):
    """Register centralized API protection guard once."""
    if app.extensions.get('nutify_api_guard_initialized'):
        return

    @app.before_request
    def _enforce_api_security():
        request_path = str(request.path or '').strip()
        if not _is_guarded_path(request_path):
            return None

        if request_path in _PUBLIC_ALWAYS_PATHS:
            return None

        if is_auth_disabled():
            return None

        login_ready = is_login_configured()
        if not login_ready:
            if _is_setup_bootstrap_path(request_path):
                return None
            return jsonify({'error': 'Login system not configured'}), 503

        if not is_authenticated():
            return jsonify({'error': 'Authentication required'}), 401

        if _is_admin_only_path(request_path, {request.method}):
            if not is_admin():
                return jsonify({'error': 'Admin privileges required'}), 403

        return None

    app.extensions['nutify_api_guard_initialized'] = True
