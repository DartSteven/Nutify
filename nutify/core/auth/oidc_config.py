"""Environment-backed, fail-closed OpenID Connect configuration."""

from __future__ import annotations

from dataclasses import dataclass
import ipaddress
import os
from typing import Mapping, Optional, Tuple
from urllib.parse import SplitResult, urlsplit


TRUTHY_VALUES = frozenset({'1', 'true', 'yes', 'on'})
DEFAULT_SCOPES = ('openid', 'profile', 'email', 'groups')


@dataclass(frozen=True)
class OIDCSettings:
    """Validated OIDC runtime settings."""

    requested: bool
    ready: bool
    issuer: str
    client_id: str
    client_secret: str
    redirect_uri: str
    scopes: Tuple[str, ...]
    username_claim: str
    groups_claim: str
    admin_groups: Tuple[str, ...]
    user_groups: Tuple[str, ...]
    allow_all_users: bool
    provider_name: str
    button_label: str
    auto_redirect: bool
    errors: Tuple[str, ...]

    @property
    def scope_string(self) -> str:
        return ' '.join(self.scopes)


def _value(environ: Mapping[str, str], name: str, default: str = '') -> str:
    return str(environ.get(name, default) or '').strip()


def _flag(environ: Mapping[str, str], name: str) -> bool:
    return _value(environ, name).lower() in TRUTHY_VALUES


def _groups(raw: str) -> Tuple[str, ...]:
    return tuple(dict.fromkeys(part.strip().casefold() for part in raw.split(',') if part.strip()))


def _scopes(raw: str) -> Tuple[str, ...]:
    values = [part for part in raw.replace(',', ' ').split() if part]
    if 'openid' not in values:
        values.insert(0, 'openid')
    return tuple(dict.fromkeys(values))


def _is_loopback_host(hostname: Optional[str]) -> bool:
    host = str(hostname or '').strip().rstrip('.').casefold()
    if host == 'localhost' or host.endswith('.localhost'):
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def _parse_url(value: str) -> Optional[SplitResult]:
    try:
        parsed = urlsplit(value)
        parsed.port  # Force validation of malformed/non-numeric ports.
        return parsed
    except ValueError:
        return None


def _validate_url(name: str, value: str, allow_local_http: bool) -> Optional[str]:
    if not value:
        return f'{name} is required'
    parsed = _parse_url(value)
    if parsed is None:
        return f'{name} must be a valid absolute URL'
    if parsed.scheme not in {'http', 'https'} or not parsed.hostname:
        return f'{name} must be an absolute HTTP(S) URL'
    if parsed.username or parsed.password or parsed.fragment:
        return f'{name} must not contain credentials or a fragment'
    if parsed.scheme != 'https' and not (allow_local_http and _is_loopback_host(parsed.hostname)):
        return f'{name} must use HTTPS (HTTP is allowed only for local test providers)'
    return None


def load_oidc_settings(environ: Optional[Mapping[str, str]] = None) -> OIDCSettings:
    """Load settings from environment and disable OIDC when validation fails."""
    source = os.environ if environ is None else environ
    requested = _flag(source, 'OIDC_ENABLED')
    issuer = _value(source, 'OIDC_ISSUER')
    client_id = _value(source, 'OIDC_CLIENT_ID')
    client_secret = _value(source, 'OIDC_CLIENT_SECRET')
    redirect_uri = _value(source, 'OIDC_REDIRECT_URI')
    scopes = _scopes(_value(source, 'OIDC_SCOPES', ' '.join(DEFAULT_SCOPES)))
    username_claim = _value(source, 'OIDC_USERNAME_CLAIM', 'preferred_username')
    groups_claim = _value(source, 'OIDC_GROUPS_CLAIM', 'groups')
    admin_groups = _groups(_value(source, 'OIDC_ADMIN_GROUP'))
    user_groups = _groups(_value(source, 'OIDC_USER_GROUP'))
    allow_all_users = _flag(source, 'OIDC_ALLOW_ALL_USERS')
    allow_local_http = _flag(source, 'OIDC_ALLOW_INSECURE_HTTP')
    provider_name = _value(source, 'OIDC_PROVIDER_NAME', 'SSO')[:80] or 'SSO'
    button_label = _value(source, 'OIDC_BUTTON_LABEL')[:120] or f'Sign in with {provider_name}'

    errors = []
    if requested:
        for key, value in (('OIDC_CLIENT_ID', client_id), ('OIDC_CLIENT_SECRET', client_secret)):
            if not value:
                errors.append(f'{key} is required')
        for key, value in (('OIDC_ISSUER', issuer), ('OIDC_REDIRECT_URI', redirect_uri)):
            error = _validate_url(key, value, allow_local_http)
            if error:
                errors.append(error)
        parsed_issuer = _parse_url(issuer)
        parsed_redirect = _parse_url(redirect_uri)
        if parsed_issuer and parsed_issuer.query:
            errors.append('OIDC_ISSUER must not contain a query string')
        if parsed_redirect and not parsed_redirect.path.endswith('/auth/oidc/callback'):
            errors.append('OIDC_REDIRECT_URI must end with /auth/oidc/callback')
        if not username_claim or not groups_claim:
            errors.append('OIDC username and groups claim names must not be empty')
        if not admin_groups and not user_groups and not allow_all_users:
            errors.append(
                'Configure OIDC_ADMIN_GROUP or OIDC_USER_GROUP, or explicitly set OIDC_ALLOW_ALL_USERS=true'
            )

    ready = requested and not errors
    return OIDCSettings(
        requested=requested,
        ready=ready,
        issuer=issuer,
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri=redirect_uri,
        scopes=scopes,
        username_claim=username_claim,
        groups_claim=groups_claim,
        admin_groups=admin_groups,
        user_groups=user_groups,
        allow_all_users=allow_all_users,
        provider_name=provider_name,
        button_label=button_label,
        auto_redirect=ready and _flag(source, 'OIDC_AUTO_REDIRECT'),
        errors=tuple(errors),
    )


def public_oidc_config(settings: OIDCSettings) -> dict:
    """Return only non-sensitive values needed by login UI."""
    return {
        'enabled': settings.ready,
        'configuration_error': settings.requested and not settings.ready,
        'auto_redirect': settings.auto_redirect,
        'login_url': '/auth/oidc/login',
        'provider_name': settings.provider_name,
        'button_label': settings.button_label,
    }
