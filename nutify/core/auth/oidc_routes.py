"""OIDC login, callback, test, and safe public configuration routes."""

import html
import json

from flask import Response, current_app, flash, jsonify, redirect, session, url_for

from . import is_auth_disabled, is_authenticated, is_login_configured, login_authenticated_user, require_admin
from .oidc import (
    OIDCAccessDenied,
    OIDCError,
    begin_login,
    complete_login,
    get_public_config,
    is_oidc_enabled,
    is_oidc_test_available,
    reload_oidc_module,
)
from .oidc_identity import OIDCAccountDisabled, OIDCIdentityError, OIDCUsernameConflict, provision_oidc_user
from .oidc_store import OIDCConfigError, current_fingerprint, get_record, mark_browser_verified
from .security import rate_limit
from core.logger import web_logger as logger


def _local_login_url() -> str:
    return url_for('auth.login', local='1')


def _test_result(success: bool, message: str) -> Response:
    payload = json.dumps({'type': 'nutify-oidc-test', 'success': bool(success), 'message': message})
    title = 'SSO test successful' if success else 'SSO test failed'
    safe_title = html.escape(title)
    safe_message = html.escape(message)
    body = f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{safe_title}</title><style>
body{{margin:0;min-height:100vh;display:grid;place-items:center;background:#0d1728;color:#e8f0fb;font-family:ui-sans-serif,sans-serif}}
main{{width:min(420px,calc(100% - 32px));padding:34px;border:1px solid #30435f;border-radius:22px;background:#142238;box-shadow:0 24px 70px #0008}}
h1{{margin:0 0 12px;color:{'#74e1a5' if success else '#ff9c9c'}}}p{{line-height:1.55;color:#b8c7dc}}a{{color:#62c9ff}}
</style></head><body><main><h1>{safe_title}</h1><p>{safe_message}</p><p>This window can be closed.</p>
<a href="/settings?view=system&amp;tab=authentication">Return to Authentication settings</a></main>
<script>if(window.opener){{window.opener.postMessage({payload},window.location.origin);setTimeout(()=>window.close(),700);}}</script>
</body></html>'''
    return Response(body, content_type='text/html; charset=utf-8')


def register_oidc_routes(blueprint) -> None:
    """Register public OIDC login/config/callback endpoints."""

    @blueprint.get('/oidc/login')
    @rate_limit('20 per minute')
    def oidc_login():
        if is_auth_disabled():
            return redirect(url_for('index'))
        if not is_login_configured():
            return redirect(url_for('auth.setup'))
        if is_authenticated():
            return redirect(url_for('index'))
        if not is_oidc_enabled():
            flash('Single sign-on is unavailable or incorrectly configured.', 'error')
            return redirect(_local_login_url())
        try:
            return begin_login()
        except OIDCError:
            logger.warning('OIDC authorization could not be started')
            flash('Single sign-on is currently unavailable.', 'error')
            return redirect(_local_login_url())

    @blueprint.get('/oidc/callback')
    @rate_limit('20 per minute')
    def oidc_callback():
        if is_auth_disabled():
            return redirect(url_for('index'))
        test_fingerprint = str(session.pop('oidc_test_fingerprint', '') or '')
        if test_fingerprint:
            try:
                claims = complete_login(test_mode=True)
                mark_browser_verified(test_fingerprint)
                reload_oidc_module(current_app._get_current_object(), logger)
                logger.info('OIDC browser verification succeeded for provider role=%s', claims.role)
                return _test_result(True, 'Provider login, token validation, group policy, and callback succeeded.')
            except (OIDCAccessDenied, OIDCError, OIDCConfigError):
                logger.warning('OIDC browser verification failed')
                return _test_result(False, 'Provider login or Nutify authorization validation failed.')
        if not is_login_configured() or not is_oidc_enabled():
            return redirect(_local_login_url())
        try:
            claims = complete_login()
            user = provision_oidc_user(claims)
            login_authenticated_user(user, auth_method='oidc')
            logger.info('Successful OIDC login for local user id=%s', user.id)
            return redirect(url_for('index'))
        except OIDCUsernameConflict:
            logger.warning('OIDC login rejected due to local username collision')
            flash('SSO username conflicts with an existing local account. Contact an administrator.', 'error')
        except OIDCAccountDisabled:
            logger.warning('OIDC login rejected because linked account is disabled')
            flash('This SSO account is disabled.', 'error')
        except OIDCAccessDenied:
            logger.warning('OIDC login rejected by group policy')
            flash('Your SSO account is not authorized for Nutify.', 'error')
        except (OIDCError, OIDCIdentityError):
            logger.warning('OIDC callback validation failed')
            flash('Single sign-on failed. Please try again.', 'error')
        return redirect(_local_login_url())

    @blueprint.get('/api/oidc')
    def api_oidc_config():
        return jsonify(get_public_config())

    @blueprint.get('/oidc/test/login')
    @require_admin
    @rate_limit('10 per minute')
    def oidc_test_login():
        record = get_record()
        if not record or record.discovery_status != 'valid' or not is_oidc_test_available():
            return _test_result(False, 'Save the configuration and complete provider discovery first.')
        session['oidc_test_fingerprint'] = current_fingerprint(record)
        try:
            return begin_login(test_mode=True)
        except OIDCError:
            session.pop('oidc_test_fingerprint', None)
            return _test_result(False, 'Single Sign-On browser test could not be started.')

    from .oidc_admin_routes import register_oidc_admin_routes

    register_oidc_admin_routes(blueprint)
