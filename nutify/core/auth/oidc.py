"""OpenID Connect (OIDC) single sign-on for Nutify.

This module adds a generic, provider-agnostic OIDC Authorization Code flow on
top of the existing local username/password login. It works with any spec
compliant provider (Authentik, Keycloak, Authelia, Zitadel, ...) discovered via
the ``.well-known/openid-configuration`` document.

SSO is strictly additive: local login keeps working and the primary admin
(user id 1) always remains a fallback. Users returned by the provider are
auto-provisioned locally, and their Nutify role is derived from a configurable
group claim (group -> role mapping).

Configuration is entirely environment driven:

    OIDC_ENABLED          Enable the SSO flow (1/true/yes/on).
    OIDC_ISSUER           Provider issuer URL (discovery base).
    OIDC_CLIENT_ID        Registered client id.
    OIDC_CLIENT_SECRET    Registered client secret.
    OIDC_SCOPES           Requested scopes (default: "openid profile email groups").
    OIDC_REDIRECT_URI     Explicit callback URL override (behind a proxy).
    OIDC_USERNAME_CLAIM   Preferred username claim (default: preferred_username).
    OIDC_GROUPS_CLAIM     Claim holding group membership (default: groups).
    OIDC_ADMIN_GROUP      Group(s) mapped to the administrator role (comma-separated).
    OIDC_USER_GROUP       Optional group(s) mapped to the user role (comma-separated).
                          When set, only members of the admin or user group may sign
                          in (everyone else is rejected). When left empty, every
                          authenticated user who is not an admin becomes a user.
    OIDC_PROVIDER_NAME    Display name used on the login button.
    OIDC_BUTTON_LABEL     Explicit login button label override.
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

from flask import url_for

try:
    from authlib.integrations.flask_client import OAuth
except Exception:  # pragma: no cover - optional dependency guard
    OAuth = None


# These will be set during initialization
logger = None
_oauth = None
_registered = False

# Internal name of the registered Authlib client.
OIDC_CLIENT_NAME = 'nutify_oidc'

DEFAULT_SCOPES = 'openid profile email groups'
DEFAULT_USERNAME_CLAIM = 'preferred_username'
DEFAULT_GROUPS_CLAIM = 'groups'
DEFAULT_ROLE = 'user'
ADMIN_ROLE = 'administrator'


class OidcError(Exception):
    """Raised when an OIDC login cannot be completed."""


def _get_env(name: str, default: str = '') -> str:
    """Return a trimmed environment variable value."""
    return os.getenv(name, default).strip()


def _get_env_flag(name: str) -> bool:
    """Check if an environment variable is set to a truthy value."""
    value = os.getenv(name, '').strip().lower()
    return value in {'1', 'true', 'yes', 'on'}


def _get_scopes() -> str:
    """Return the requested OAuth scopes, always including ``openid``."""
    scopes = _get_env('OIDC_SCOPES', DEFAULT_SCOPES) or DEFAULT_SCOPES
    parts = [part for part in scopes.replace(',', ' ').split() if part]
    if 'openid' not in parts:
        parts.insert(0, 'openid')
    return ' '.join(parts)


def _split_groups(raw: str) -> List[str]:
    """Split a comma-separated group list into lowercase names."""
    return [group.strip().lower() for group in raw.split(',') if group.strip()]


def _get_admin_groups() -> List[str]:
    """Return the groups mapped to the administrator role (case-insensitive)."""
    return _split_groups(_get_env('OIDC_ADMIN_GROUP'))


def _get_user_groups() -> List[str]:
    """Return the groups mapped to the user role (case-insensitive).

    Empty by default. When configured, it also gates access: users who are in
    neither the admin nor the user group are rejected.
    """
    return _split_groups(_get_env('OIDC_USER_GROUP'))


def is_oidc_configured() -> bool:
    """Check whether the mandatory OIDC settings are present."""
    return bool(
        _get_env('OIDC_ISSUER')
        and _get_env('OIDC_CLIENT_ID')
        and _get_env('OIDC_CLIENT_SECRET')
    )


def is_oidc_enabled() -> bool:
    """Check whether OIDC SSO is enabled, configured and usable."""
    return bool(OAuth) and _get_env_flag('OIDC_ENABLED') and is_oidc_configured()


def get_public_config() -> Dict[str, Any]:
    """Return SSO details that are safe to expose to the frontend.

    Never includes the client secret or issuer internals.
    """
    enabled = is_oidc_enabled()
    provider_name = _get_env('OIDC_PROVIDER_NAME', 'SSO') or 'SSO'
    button_label = _get_env('OIDC_BUTTON_LABEL') or f'Sign in with {provider_name}'
    return {
        'enabled': enabled,
        'login_url': '/auth/oidc/login',
        'provider_name': provider_name,
        'button_label': button_label,
    }


def init_oidc_module(app, oidc_logger=None) -> None:
    """Initialize the OIDC module and register the provider client.

    Registration is lazy about network access: Authlib only fetches the
    provider metadata on the first login attempt, so a down provider never
    blocks application startup.

    Args:
        app: Flask application instance.
        oidc_logger: Logger instance for authentication operations.
    """
    global _oauth, _registered, logger
    logger = oidc_logger

    if app.extensions.get('nutify_oidc_initialized'):
        return

    if OAuth is None:
        if logger:
            logger.warning("🔐 OIDC SSO unavailable (authlib not installed)")
        return

    if not is_oidc_enabled():
        if logger:
            logger.info("🔐 OIDC SSO disabled (set OIDC_ENABLED and issuer/client config to enable)")
        return

    issuer = _get_env('OIDC_ISSUER').rstrip('/')
    _oauth = OAuth(app)
    _oauth.register(
        name=OIDC_CLIENT_NAME,
        client_id=_get_env('OIDC_CLIENT_ID'),
        client_secret=_get_env('OIDC_CLIENT_SECRET'),
        server_metadata_url=f'{issuer}/.well-known/openid-configuration',
        client_kwargs={'scope': _get_scopes()},
    )
    _registered = True
    app.extensions['nutify_oidc_initialized'] = True

    if logger:
        logger.info(f"🔐 OIDC SSO initialized (issuer: {issuer})")


def _get_client():
    """Return the registered Authlib client or raise if SSO is not ready."""
    if not _oauth or not _registered:
        raise OidcError('OIDC SSO is not initialized')
    client = _oauth.create_client(OIDC_CLIENT_NAME)
    if client is None:
        raise OidcError('OIDC client is not registered')
    return client


def _resolve_redirect_uri() -> str:
    """Resolve the callback URL, honoring an explicit proxy override."""
    override = _get_env('OIDC_REDIRECT_URI')
    if override:
        return override
    return url_for('auth.oidc_callback', _external=True)


def begin_login():
    """Start the Authorization Code flow by redirecting to the provider."""
    if not is_oidc_enabled():
        raise OidcError('OIDC SSO is not enabled')
    client = _get_client()
    redirect_uri = _resolve_redirect_uri()
    if logger:
        logger.info(f"🔐 Starting OIDC login (redirect_uri: {redirect_uri})")
    return client.authorize_redirect(redirect_uri)


def _extract_username(claims: Dict[str, Any]) -> str:
    """Pick a username from the token claims using a configurable priority."""
    preferred = _get_env('OIDC_USERNAME_CLAIM', DEFAULT_USERNAME_CLAIM) or DEFAULT_USERNAME_CLAIM
    for key in (preferred, 'preferred_username', 'email', 'sub'):
        value = claims.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ''


def _extract_groups(claims: Dict[str, Any]) -> List[str]:
    """Normalize the group claim into a list of strings."""
    groups_claim = _get_env('OIDC_GROUPS_CLAIM', DEFAULT_GROUPS_CLAIM) or DEFAULT_GROUPS_CLAIM
    raw = claims.get(groups_claim)
    if raw is None:
        return []
    if isinstance(raw, str):
        return [part.strip() for part in raw.replace(',', ' ').split() if part.strip()]
    if isinstance(raw, (list, tuple, set)):
        return [str(item).strip() for item in raw if str(item).strip()]
    return []


def resolve_role(groups: List[str]) -> Optional[str]:
    """Map provider groups to a Nutify role.

    Rules (admin always wins):
        * member of an admin group          -> ``administrator``
        * member of a user group            -> ``user``
        * no user group configured          -> ``user`` (everyone is let in)
        * user group configured, no match   -> ``None`` (access rejected)

    Returns:
        The resolved role, or ``None`` when the user is not a member of any
        authorized group and must be rejected.
    """
    member_of = {group.lower() for group in groups}
    if set(_get_admin_groups()) & member_of:
        return ADMIN_ROLE

    user_groups = set(_get_user_groups())
    if not user_groups:
        # No user group configured: every authenticated user becomes a user.
        return DEFAULT_ROLE
    if user_groups & member_of:
        return DEFAULT_ROLE
    # A user group is configured but the user is in none of the allowed groups.
    return None


def _merge_userinfo(client, token: Dict[str, Any]) -> Dict[str, Any]:
    """Combine id_token claims with the userinfo endpoint (best effort).

    Some providers only expose group membership from the userinfo endpoint,
    so we enrich the id_token claims when possible without failing the login.
    """
    claims: Dict[str, Any] = dict(token.get('userinfo') or {})
    try:
        endpoint_claims = client.userinfo(token=token)
        if endpoint_claims:
            claims.update(dict(endpoint_claims))
    except Exception as exc:  # pragma: no cover - provider dependent
        if logger:
            logger.debug(f"🔐 OIDC userinfo endpoint not used: {str(exc)}")
    return claims


def complete_login() -> Dict[str, Any]:
    """Finish the callback: exchange the code and resolve the SSO identity.

    Returns:
        dict: ``{'username': str, 'role': str, 'groups': list}``.

    Raises:
        OidcError: If the flow fails or no username claim is present.
    """
    if not is_oidc_enabled():
        raise OidcError('OIDC SSO is not enabled')

    client = _get_client()
    try:
        token = client.authorize_access_token()
    except Exception as exc:
        if logger:
            logger.warning(f"🔐 OIDC token exchange failed: {str(exc)}")
        raise OidcError('OIDC token exchange failed') from exc

    claims = _merge_userinfo(client, token)
    username = _extract_username(claims)
    if not username:
        if logger:
            logger.warning("🔐 OIDC login rejected: no usable username claim")
        raise OidcError('No username claim returned by the provider')

    groups = _extract_groups(claims)
    role = resolve_role(groups)
    if role is None:
        if logger:
            logger.warning(
                f"🔐 OIDC login rejected: user '{username}' is not a member of "
                f"any authorized group"
            )
        raise OidcError('User is not a member of an authorized group')

    if logger:
        logger.info(f"🔐 OIDC login resolved user '{username}' to role '{role}'")

    return {'username': username, 'role': role, 'groups': groups}
