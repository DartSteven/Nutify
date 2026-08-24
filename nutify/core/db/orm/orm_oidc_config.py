"""Database-backed OpenID Connect configuration model."""

from __future__ import annotations

from datetime import datetime

import pytz
from sqlalchemy import Boolean, Column, DateTime, Integer, LargeBinary, String, Text

from core.auth.oidc_crypto import decrypt_secret, encrypt_secret


class OIDCConfig:
    """Singleton administrator-managed OIDC configuration."""

    __tablename__ = 'auth_oidc_config'

    id = Column(Integer, primary_key=True)
    enabled = Column(Boolean, nullable=False, default=False)
    issuer = Column(String(500), nullable=False, default='')
    client_id = Column(String(255), nullable=False, default='')
    _client_secret = Column('client_secret', LargeBinary, nullable=True)
    redirect_uri = Column(String(500), nullable=False, default='')
    scopes = Column(String(500), nullable=False, default='openid profile email groups')
    username_claim = Column(String(120), nullable=False, default='preferred_username')
    groups_claim = Column(String(120), nullable=False, default='groups')
    admin_groups = Column(Text, nullable=False, default='')
    user_groups = Column(Text, nullable=False, default='')
    allow_all_users = Column(Boolean, nullable=False, default=False)
    allow_private_network = Column(Boolean, nullable=False, default=False)
    provider_name = Column(String(80), nullable=False, default='SSO')
    button_label = Column(String(120), nullable=False, default='Sign in with SSO')
    auto_redirect = Column(Boolean, nullable=False, default=False)
    discovery_status = Column(String(20), nullable=False, default='untested')
    discovery_error = Column(String(255), nullable=False, default='')
    discovery_issuer = Column(String(500), nullable=False, default='')
    registration_supported = Column(Boolean, nullable=False, default=False)
    discovery_checked_at = Column(DateTime(timezone=True), nullable=True)
    verified_fingerprint = Column(String(64), nullable=False, default='')
    verified_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(pytz.UTC), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(pytz.UTC),
        onupdate=lambda: datetime.now(pytz.UTC),
        nullable=False,
    )

    @property
    def client_secret(self) -> str:
        return decrypt_secret(self._client_secret)

    @client_secret.setter
    def client_secret(self, value: str) -> None:
        self._client_secret = encrypt_secret(value) if value else None

    @property
    def has_client_secret(self) -> bool:
        return bool(self._client_secret)


def init_model(model_base, db_logger=None):
    class OIDCConfigModel(model_base, OIDCConfig):
        __table_args__ = ({'extend_existing': True},)

    if db_logger:
        db_logger.info('Initialized OIDC configuration ORM model')
    return OIDCConfigModel
