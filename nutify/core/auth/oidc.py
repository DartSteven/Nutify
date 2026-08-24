"""Secure OIDC Authorization Code flow backed by Authlib."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from typing import Any, Dict, Iterable, Tuple
import unicodedata

from flask import current_app

from .oidc_config import OIDCSettings, load_oidc_settings, public_oidc_config

try:
    from authlib.integrations.flask_client import OAuth
except ImportError:  # pragma: no cover - deployment dependency guard
    OAuth = None


EXTENSION_KEY = 'nutify_oidc'
CLIENT_NAME = 'nutify_oidc'
TEST_CLIENT_NAME = 'nutify_oidc_test'
ADMIN_ROLE = 'administrator'
USER_ROLE = 'user'


class OIDCError(Exception):
    """Base error for safe OIDC failures."""


class OIDCAccessDenied(OIDCError):
    """Identity is valid but not authorized for Nutify."""


@dataclass(frozen=True)
class OIDCClaims:
    issuer: str
    subject: str
    username: str
    email: str
    role: str
    groups: Tuple[str, ...]


def _runtime_state() -> dict:
    state = current_app.extensions.get(EXTENSION_KEY)
    if not isinstance(state, dict):
        raise OIDCError('OIDC runtime is not initialized')
    return state


def get_settings(test_mode: bool = False) -> OIDCSettings:
    key = 'test_settings' if test_mode else 'settings'
    settings = _runtime_state().get(key)
    if not isinstance(settings, OIDCSettings):
        raise OIDCError('OIDC test configuration is unavailable' if test_mode else 'OIDC configuration is unavailable')
    return settings


def init_oidc_module(app, oidc_logger=None) -> None:
    """Initialize or reload effective and administrator-test OIDC clients."""
    reload_oidc_module(app, oidc_logger)


def _register_client(oauth, name: str, settings: OIDCSettings) -> None:
    oauth.register(
        name=name,
        client_id=settings.client_id,
        client_secret=settings.client_secret,
        server_metadata_url=f'{settings.issuer.rstrip("/")}/.well-known/openid-configuration',
        client_kwargs={
            'scope': settings.scope_string,
            'code_challenge_method': 'S256',
        },
    )


def reload_oidc_module(app, oidc_logger=None) -> None:
    """Atomically rebuild Authlib clients after source or database changes."""
    from .oidc_store import DATABASE_SOURCE, configuration_source, load_database_draft_settings, load_effective_settings

    previous = app.extensions.get(EXTENSION_KEY, {})
    active_logger = oidc_logger or previous.get('logger')
    settings = load_effective_settings()
    test_settings = load_database_draft_settings() if configuration_source() == DATABASE_SOURCE else None
    state = {'settings': settings, 'test_settings': test_settings, 'oauth': None, 'logger': active_logger}
    app.extensions[EXTENSION_KEY] = state

    requested_settings = [candidate for candidate in (settings, test_settings) if candidate and candidate.requested]
    if not requested_settings:
        return
    for candidate in requested_settings:
        if not candidate.ready and active_logger:
            for error in candidate.errors:
                active_logger.error('OIDC configuration rejected: %s', error)
    if OAuth is None:
        if active_logger:
            active_logger.error('OIDC requested but Authlib is unavailable')
        state['settings'] = OIDCSettings(
            **{**settings.__dict__, 'ready': False, 'auto_redirect': False}
        )
        if test_settings:
            state['test_settings'] = OIDCSettings(
                **{**test_settings.__dict__, 'ready': False, 'auto_redirect': False}
            )
        return

    oauth = OAuth(app)
    if settings.ready:
        _register_client(oauth, CLIENT_NAME, settings)
    if test_settings and test_settings.ready:
        _register_client(oauth, TEST_CLIENT_NAME, test_settings)
    state['oauth'] = oauth
    if active_logger and settings.ready:
        active_logger.info('OIDC initialized for provider %s', settings.provider_name)


def is_oidc_enabled() -> bool:
    try:
        state = _runtime_state()
        return bool(state['settings'].ready and state.get('oauth'))
    except OIDCError:
        return False


def is_auto_redirect() -> bool:
    return is_oidc_enabled() and get_settings().auto_redirect


def is_oidc_test_available() -> bool:
    try:
        state = _runtime_state()
        settings = get_settings(test_mode=True)
        return bool(settings.ready and state.get('oauth'))
    except OIDCError:
        return False


def get_public_config() -> dict:
    try:
        return public_oidc_config(get_settings())
    except OIDCError:
        return public_oidc_config(load_oidc_settings({}))


def _client(test_mode: bool = False):
    state = _runtime_state()
    settings = get_settings(test_mode)
    if not settings.ready or not state.get('oauth'):
        raise OIDCError('OIDC is not available')
    client = state['oauth'].create_client(TEST_CLIENT_NAME if test_mode else CLIENT_NAME)
    if client is None:
        raise OIDCError('OIDC client is not registered')
    return client


def begin_login(test_mode: bool = False):
    """Start state/nonce/PKCE-protected authorization."""
    settings = get_settings(test_mode)
    return _client(test_mode).authorize_redirect(settings.redirect_uri)


def _claim_text(claims: Dict[str, Any], name: str) -> str:
    value = claims.get(name)
    return value.strip() if isinstance(value, str) else ''


def _normalized_groups(value: Any) -> Tuple[str, ...]:
    if isinstance(value, str):
        raw: Iterable[Any] = value.split(',')
    elif isinstance(value, (list, tuple, set)):
        raw = value
    else:
        raw = ()
    return tuple(dict.fromkeys(str(item).strip() for item in raw if str(item).strip()))


def _resolve_role(settings: OIDCSettings, groups: Tuple[str, ...]) -> str:
    memberships = {group.casefold() for group in groups}
    if memberships.intersection(settings.admin_groups):
        return ADMIN_ROLE
    if memberships.intersection(settings.user_groups) or settings.allow_all_users:
        return USER_ROLE
    raise OIDCAccessDenied('OIDC identity is not in an authorized group')


def _fallback_username(issuer: str, subject: str) -> str:
    digest = hashlib.sha256(f'{issuer}\0{subject}'.encode('utf-8')).hexdigest()[:20]
    return f'oidc-{digest}'


def _normalized_username(value: str) -> str:
    candidate = unicodedata.normalize('NFKC', value).strip()
    if any(unicodedata.category(character).startswith('C') for character in candidate):
        return ''
    return candidate[:100]


def _resolve_username(settings: OIDCSettings, claims: Dict[str, Any], issuer: str, subject: str) -> str:
    candidate_names = [settings.username_claim, 'preferred_username']
    for name in dict.fromkeys(candidate_names):
        candidate = _normalized_username(_claim_text(claims, name))
        if candidate:
            return candidate
    email = _normalized_username(_claim_text(claims, 'email'))
    if email and claims.get('email_verified') is True:
        return email
    return _fallback_username(issuer, subject)


def _merge_verified_userinfo(client, token: dict, id_claims: Dict[str, Any], subject: str) -> Dict[str, Any]:
    """Merge UserInfo only after mandatory subject equality validation."""
    metadata = getattr(client, 'server_metadata', {}) or {}
    if not metadata.get('userinfo_endpoint'):
        return dict(id_claims)
    try:
        userinfo = dict(client.userinfo(token=token) or {})
    except Exception:
        return dict(id_claims)
    if not userinfo:
        return dict(id_claims)
    if _claim_text(userinfo, 'sub') != subject:
        raise OIDCError('OIDC UserInfo subject does not match ID token subject')
    merged = dict(id_claims)
    merged.update(userinfo)
    return merged


def complete_login(test_mode: bool = False) -> OIDCClaims:
    """Exchange callback code and return validated, authorized identity claims."""
    settings = get_settings(test_mode)
    client = _client(test_mode)
    try:
        token = client.authorize_access_token()
    except Exception as exc:
        raise OIDCError('OIDC token exchange or state validation failed') from exc

    id_claims = dict(token.get('userinfo') or {})
    issuer = _claim_text(id_claims, 'iss')
    subject = _claim_text(id_claims, 'sub')
    if not issuer or issuer != settings.issuer:
        raise OIDCError('OIDC issuer does not match configured issuer')
    if not subject:
        raise OIDCError('OIDC subject claim is missing')

    claims = _merge_verified_userinfo(client, token, id_claims, subject)
    groups = _normalized_groups(claims.get(settings.groups_claim))
    role = _resolve_role(settings, groups)
    username = _resolve_username(settings, claims, issuer, subject)
    email = _claim_text(claims, 'email') if claims.get('email_verified') is True else ''
    return OIDCClaims(issuer, subject, username, email[:320], role, groups)
