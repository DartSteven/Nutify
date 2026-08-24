"""OIDC configuration source selection and database lifecycle."""

from __future__ import annotations

from datetime import datetime
import os
from typing import Any, Mapping

from flask import has_app_context
import pytz

from .oidc_config import DEFAULT_SCOPES, OIDCSettings, load_oidc_settings
from .oidc_crypto import configuration_fingerprint
from .oidc_discovery import OIDCDiscoveryError, discover_provider, register_dynamic_client


ENVIRONMENT_SOURCE = 'environment'
DATABASE_SOURCE = 'database'
VALID_SOURCES = frozenset({ENVIRONMENT_SOURCE, DATABASE_SOURCE})
MASKED_SECRET = '********'
ENV_REQUIRED_KEYS = ('OIDC_ISSUER', 'OIDC_CLIENT_ID', 'OIDC_CLIENT_SECRET', 'OIDC_REDIRECT_URI')


class OIDCConfigError(Exception):
    """OIDC configuration cannot be saved or activated safely."""


def _truthy(value: Any) -> bool:
    return str(value or '').strip().lower() in {'1', 'true', 'yes', 'on'}


def configuration_source(environ: Mapping[str, str] | None = None) -> str:
    source = os.environ if environ is None else environ
    explicit = str(source.get('OIDC_CONFIG_SOURCE', '') or '').strip().lower()
    if explicit:
        return explicit if explicit in VALID_SOURCES else 'invalid'
    if _truthy(source.get('OIDC_ENABLED')) or any(str(source.get(key, '') or '').strip() for key in ENV_REQUIRED_KEYS):
        return ENVIRONMENT_SOURCE
    return DATABASE_SOURCE


def _models():
    if not has_app_context():
        return None, None
    try:
        from core.db.ups import db
        return db, getattr(getattr(db, 'ModelClasses', None), 'OIDCConfig', None)
    except Exception:
        return None, None


def get_record(create: bool = False):
    db, model = _models()
    if db is None or model is None:
        return None
    try:
        record = model.query.order_by(model.id.asc()).first()
    except Exception:
        return None
    if record is None and create:
        record = model(id=1)
        db.session.add(record)
        db.session.flush()
    return record


def _csv(value: Any) -> str:
    if isinstance(value, (list, tuple, set)):
        parts = [str(item).strip() for item in value]
    else:
        parts = str(value or '').split(',')
    return ','.join(dict.fromkeys(part for part in parts if part))


def _record_mapping(record, enabled_override: bool | None = None) -> dict[str, str]:
    enabled = bool(record.enabled) if enabled_override is None else bool(enabled_override)
    return {
        'OIDC_ENABLED': 'true' if enabled else 'false',
        'OIDC_ISSUER': record.issuer or '',
        'OIDC_CLIENT_ID': record.client_id or '',
        'OIDC_CLIENT_SECRET': record.client_secret or '',
        'OIDC_REDIRECT_URI': record.redirect_uri or '',
        'OIDC_SCOPES': record.scopes or ' '.join(DEFAULT_SCOPES),
        'OIDC_USERNAME_CLAIM': record.username_claim or 'preferred_username',
        'OIDC_GROUPS_CLAIM': record.groups_claim or 'groups',
        'OIDC_ADMIN_GROUP': record.admin_groups or '',
        'OIDC_USER_GROUP': record.user_groups or '',
        'OIDC_ALLOW_ALL_USERS': 'true' if record.allow_all_users else 'false',
        'OIDC_PROVIDER_NAME': record.provider_name or 'SSO',
        'OIDC_BUTTON_LABEL': record.button_label or '',
        'OIDC_AUTO_REDIRECT': 'true' if record.auto_redirect else 'false',
        'OIDC_ALLOW_INSECURE_HTTP': 'true' if _truthy(os.getenv('OIDC_ALLOW_INSECURE_HTTP')) else 'false',
    }


def load_effective_settings(environ: Mapping[str, str] | None = None) -> OIDCSettings:
    source = configuration_source(environ)
    if source == ENVIRONMENT_SOURCE:
        return load_oidc_settings(os.environ if environ is None else environ)
    if source == DATABASE_SOURCE:
        record = get_record()
        return load_oidc_settings(_record_mapping(record) if record else {})
    settings = load_oidc_settings({'OIDC_ENABLED': 'true'})
    return OIDCSettings(**{**settings.__dict__, 'errors': ('OIDC_CONFIG_SOURCE is invalid',)})


def load_database_draft_settings() -> OIDCSettings:
    record = get_record()
    return load_oidc_settings(_record_mapping(record, enabled_override=True) if record else {})


def _fingerprint_values(record) -> dict[str, Any]:
    return {
        'issuer': record.issuer,
        'client_id': record.client_id,
        'client_secret': record.client_secret,
        'redirect_uri': record.redirect_uri,
        'scopes': record.scopes,
        'username_claim': record.username_claim,
        'groups_claim': record.groups_claim,
        'admin_groups': record.admin_groups,
        'user_groups': record.user_groups,
        'allow_all_users': bool(record.allow_all_users),
    }


def current_fingerprint(record=None) -> str:
    target = record or get_record()
    return configuration_fingerprint(_fingerprint_values(target)) if target else ''


def _serialize_record(record) -> dict[str, Any]:
    verified = bool(record and record.verified_fingerprint and record.verified_fingerprint == current_fingerprint(record))
    return {
        'configured': bool(record and record.issuer and record.client_id and record.has_client_secret),
        'enabled': bool(record.enabled) if record else False,
        'issuer': record.issuer if record else '',
        'client_id': record.client_id if record else '',
        'client_secret': MASKED_SECRET if record and record.has_client_secret else '',
        'has_client_secret': bool(record and record.has_client_secret),
        'redirect_uri': record.redirect_uri if record else '',
        'scopes': record.scopes if record else ' '.join(DEFAULT_SCOPES),
        'username_claim': record.username_claim if record else 'preferred_username',
        'groups_claim': record.groups_claim if record else 'groups',
        'admin_groups': record.admin_groups if record else '',
        'user_groups': record.user_groups if record else '',
        'allow_all_users': bool(record.allow_all_users) if record else False,
        'allow_private_network': bool(record.allow_private_network) if record else False,
        'provider_name': record.provider_name if record else 'SSO',
        'button_label': record.button_label if record else 'Sign in with SSO',
        'auto_redirect': bool(record.auto_redirect) if record else False,
        'discovery_status': record.discovery_status if record else 'untested',
        'discovery_error': record.discovery_error if record else '',
        'registration_supported': bool(record.registration_supported) if record else False,
        'verified': verified,
        'verified_at': record.verified_at.isoformat() if record and record.verified_at else None,
    }


def admin_configuration(environ: Mapping[str, str] | None = None) -> dict[str, Any]:
    source = configuration_source(environ)
    if source == ENVIRONMENT_SOURCE:
        env = os.environ if environ is None else environ
        settings = load_oidc_settings(env)
        return {
            'source': source,
            'editable': False,
            'source_error': '',
            **{
                'configured': settings.requested,
                'enabled': settings.ready,
                'issuer': settings.issuer,
                'client_id': settings.client_id,
                'client_secret': MASKED_SECRET if settings.client_secret else '',
                'has_client_secret': bool(settings.client_secret),
                'redirect_uri': settings.redirect_uri,
                'scopes': settings.scope_string,
                'username_claim': settings.username_claim,
                'groups_claim': settings.groups_claim,
                'admin_groups': ','.join(settings.admin_groups),
                'user_groups': ','.join(settings.user_groups),
                'allow_all_users': settings.allow_all_users,
                'allow_private_network': False,
                'provider_name': settings.provider_name,
                'button_label': settings.button_label,
                'auto_redirect': settings.auto_redirect,
                'discovery_status': 'managed',
                'discovery_error': '; '.join(settings.errors),
                'registration_supported': False,
                'verified': settings.ready,
                'verified_at': None,
            },
        }
    if source == 'invalid':
        return {'source': source, 'editable': False, 'source_error': 'OIDC_CONFIG_SOURCE must be database or environment'}
    return {'source': source, 'editable': True, 'source_error': '', **_serialize_record(get_record())}


def save_database_configuration(payload: Mapping[str, Any]):
    if configuration_source() != DATABASE_SOURCE:
        raise OIDCConfigError('OIDC configuration is managed by environment variables')
    db, _ = _models()
    record = get_record(create=True)
    if db is None or record is None:
        raise OIDCConfigError('OIDC database configuration is unavailable')
    previous_issuer = record.issuer
    secret_value = str(payload.get('client_secret') or '').strip()
    if secret_value in {'', MASKED_SECRET}:
        secret_value = record.client_secret
    mapping = {
        'OIDC_ENABLED': 'true',
        'OIDC_ISSUER': str(payload.get('issuer') or '').strip(),
        'OIDC_CLIENT_ID': str(payload.get('client_id') or '').strip(),
        'OIDC_CLIENT_SECRET': secret_value,
        'OIDC_REDIRECT_URI': str(payload.get('redirect_uri') or '').strip(),
        'OIDC_SCOPES': str(payload.get('scopes') or ' '.join(DEFAULT_SCOPES)).strip(),
        'OIDC_USERNAME_CLAIM': str(payload.get('username_claim') or 'preferred_username').strip(),
        'OIDC_GROUPS_CLAIM': str(payload.get('groups_claim') or 'groups').strip(),
        'OIDC_ADMIN_GROUP': _csv(payload.get('admin_groups')),
        'OIDC_USER_GROUP': _csv(payload.get('user_groups')),
        'OIDC_ALLOW_ALL_USERS': 'true' if _truthy(payload.get('allow_all_users')) else 'false',
        'OIDC_PROVIDER_NAME': str(payload.get('provider_name') or 'SSO').strip(),
        'OIDC_BUTTON_LABEL': str(payload.get('button_label') or '').strip(),
        'OIDC_AUTO_REDIRECT': 'true' if _truthy(payload.get('auto_redirect')) else 'false',
        'OIDC_ALLOW_INSECURE_HTTP': 'true' if _truthy(os.getenv('OIDC_ALLOW_INSECURE_HTTP')) else 'false',
    }
    settings = load_oidc_settings(mapping)
    missing_credentials = not settings.client_id and not settings.client_secret
    credential_errors = {'OIDC_CLIENT_ID is required', 'OIDC_CLIENT_SECRET is required'}
    blocking_errors = [error for error in settings.errors if not (missing_credentials and error in credential_errors)]
    if (bool(settings.client_id) != bool(settings.client_secret)) or blocking_errors:
        db.session.rollback()
        if bool(settings.client_id) != bool(settings.client_secret):
            blocking_errors.append('OIDC client ID and client secret must be provided together')
        raise OIDCConfigError('; '.join(blocking_errors))
    old_fingerprint = current_fingerprint(record) if record.has_client_secret else ''
    record.issuer = settings.issuer
    record.client_id = settings.client_id
    record.client_secret = settings.client_secret
    record.redirect_uri = settings.redirect_uri
    record.scopes = settings.scope_string
    record.username_claim = settings.username_claim
    record.groups_claim = settings.groups_claim
    record.admin_groups = ','.join(settings.admin_groups)
    record.user_groups = ','.join(settings.user_groups)
    record.allow_all_users = settings.allow_all_users
    record.allow_private_network = _truthy(payload.get('allow_private_network'))
    record.provider_name = settings.provider_name
    record.button_label = settings.button_label
    record.auto_redirect = settings.auto_redirect
    new_fingerprint = current_fingerprint(record)
    if old_fingerprint != new_fingerprint:
        record.enabled = False
        record.verified_fingerprint = ''
        record.verified_at = None
    if previous_issuer.rstrip('/') != record.issuer.rstrip('/'):
        record.discovery_status = 'untested'
        record.discovery_error = ''
        record.discovery_issuer = ''
        record.registration_supported = False
        record.discovery_checked_at = None
    db.session.commit()
    return record


def run_discovery(record=None) -> dict[str, Any]:
    db, _ = _models()
    target = record or get_record()
    if db is None or target is None:
        raise OIDCConfigError('Save OIDC configuration before discovery')
    allow_http = _truthy(os.getenv('OIDC_ALLOW_INSECURE_HTTP'))
    try:
        result = discover_provider(
            target.issuer,
            allow_private_network=bool(target.allow_private_network),
            allow_http_loopback=allow_http,
        )
        target.discovery_status = 'valid'
        target.discovery_error = ''
        target.discovery_issuer = result['issuer']
        target.registration_supported = result['registration_supported']
        target.discovery_checked_at = datetime.now(pytz.UTC)
        db.session.commit()
        return result
    except OIDCDiscoveryError as exc:
        target.discovery_status = 'failed'
        target.discovery_error = str(exc)[:255]
        target.discovery_checked_at = datetime.now(pytz.UTC)
        db.session.commit()
        raise OIDCConfigError(str(exc)) from exc


def mark_browser_verified(expected_fingerprint: str) -> None:
    db, _ = _models()
    record = get_record()
    if db is None or record is None or expected_fingerprint != current_fingerprint(record):
        raise OIDCConfigError('OIDC configuration changed during browser verification')
    record.verified_fingerprint = expected_fingerprint
    record.verified_at = datetime.now(pytz.UTC)
    db.session.commit()


def set_enabled(enabled: bool):
    db, _ = _models()
    record = get_record()
    if db is None or record is None:
        raise OIDCConfigError('OIDC configuration does not exist')
    if enabled:
        if record.discovery_status != 'valid':
            raise OIDCConfigError('Provider discovery must succeed before enabling SSO')
        if not record.verified_fingerprint or record.verified_fingerprint != current_fingerprint(record):
            raise OIDCConfigError('A successful browser SSO test is required before enabling SSO')
    record.enabled = bool(enabled)
    db.session.commit()
    return record


def delete_database_configuration() -> None:
    if configuration_source() != DATABASE_SOURCE:
        raise OIDCConfigError('Environment-managed configuration cannot be deleted from the UI')
    db, _ = _models()
    record = get_record()
    if db is not None and record is not None:
        db.session.delete(record)
        db.session.commit()


def dynamic_register_database_configuration(payload: Mapping[str, Any]):
    draft = save_database_configuration(payload)
    issuer = draft.issuer
    redirect_uri = draft.redirect_uri
    allow_private = bool(draft.allow_private_network)
    allow_http = _truthy(os.getenv('OIDC_ALLOW_INSECURE_HTTP'))
    try:
        discovery = discover_provider(
            issuer,
            allow_private_network=allow_private,
            allow_http_loopback=allow_http,
        )
        credentials = register_dynamic_client(
            discovery,
            redirect_uri=redirect_uri,
            client_name=str(payload.get('provider_name') or 'Nutify'),
            initial_access_token=str(payload.get('initial_access_token') or ''),
            allow_private_network=allow_private,
            allow_http_loopback=allow_http,
        )
    except OIDCDiscoveryError as exc:
        raise OIDCConfigError(str(exc)) from exc
    merged = dict(payload)
    merged.update(credentials)
    merged.pop('initial_access_token', None)
    record = save_database_configuration(merged)
    return record, discovery
