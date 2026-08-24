"""Secure OIDC account provisioning and lifecycle helpers."""

from __future__ import annotations

from datetime import datetime
import secrets
import unicodedata

import pytz
from sqlalchemy.exc import IntegrityError

from .oidc import OIDCClaims


class OIDCIdentityError(Exception):
    """Base identity persistence error."""


class OIDCUsernameConflict(OIDCIdentityError):
    """Provider username collides with an unrelated local account."""


class OIDCAccountDisabled(OIDCIdentityError):
    """Linked local account was disabled by an administrator."""


def _models():
    from core.db.ups import db

    models = getattr(db, 'ModelClasses', None)
    login_model = getattr(models, 'LoginAuth', None)
    identity_model = getattr(models, 'OIDCIdentity', None)
    if login_model is None or identity_model is None:
        raise OIDCIdentityError('OIDC database models are unavailable')
    return db, login_model, identity_model


def _casefold_username_collision(login_model, username: str):
    wanted = unicodedata.normalize('NFKC', username).casefold()
    return next(
        (
            user
            for user in login_model.query.all()
            if unicodedata.normalize('NFKC', str(user.username)).casefold() == wanted
        ),
        None,
    )


def _set_role(user, role: str) -> None:
    if user.role == role and bool(user.is_admin) == (role == 'administrator'):
        return
    user.role = role
    user.is_admin = role == 'administrator'
    user.set_permissions(user.get_default_permissions())
    user.set_options_tabs(user.get_default_options_tabs())


def provision_oidc_user(claims: OIDCClaims):
    """Resolve only by issuer/sub; never auto-link by mutable username."""
    db, LoginAuth, OIDCIdentity = _models()
    now = datetime.now(pytz.UTC)
    identity = OIDCIdentity.query.filter_by(issuer=claims.issuer, subject=claims.subject).first()

    if identity:
        user = LoginAuth.query.filter_by(id=identity.user_id).first()
        if user is None:
            raise OIDCIdentityError('OIDC identity references a missing local account')
        if not user.is_active:
            raise OIDCAccountDisabled('OIDC account is disabled')
        _set_role(user, claims.role)
        identity.provider_username = claims.username
        identity.email = claims.email or None
        identity.last_login_at = now
        user.update_last_login()
        db.session.commit()
        return user

    if _casefold_username_collision(LoginAuth, claims.username):
        raise OIDCUsernameConflict('OIDC username conflicts with an existing account')

    user = LoginAuth(
        username=claims.username,
        password_hash=f'!oidc:{secrets.token_urlsafe(32)}',
        role=claims.role,
        is_admin=claims.role == 'administrator',
        is_active=True,
    )
    user.set_permissions(user.get_default_permissions())
    user.set_options_tabs(user.get_default_options_tabs())
    user.update_last_login()
    try:
        db.session.add(user)
        db.session.flush()
        identity = OIDCIdentity(
            user_id=user.id,
            issuer=claims.issuer,
            subject=claims.subject,
            provider_username=claims.username,
            email=claims.email or None,
            last_login_at=now,
        )
        db.session.add(identity)
        db.session.commit()
        return user
    except IntegrityError as exc:
        db.session.rollback()
        raise OIDCIdentityError('OIDC identity could not be provisioned safely') from exc
    except Exception:
        db.session.rollback()
        raise


def is_oidc_user(user_id: int) -> bool:
    _, _, OIDCIdentity = _models()
    return OIDCIdentity.query.filter_by(user_id=int(user_id)).first() is not None


def delete_oidc_identity(user_id: int) -> None:
    """Stage linked identity deletion in same transaction as local user deletion."""
    db, _, OIDCIdentity = _models()
    identity = OIDCIdentity.query.filter_by(user_id=int(user_id)).first()
    if identity:
        db.session.delete(identity)


def auth_source(user_id: int) -> str:
    return 'oidc' if is_oidc_user(user_id) else 'local'
