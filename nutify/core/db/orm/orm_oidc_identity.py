"""Stable OpenID Connect identity bindings."""

from datetime import datetime

import pytz
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, UniqueConstraint


class OIDCIdentity:
    """Bind one local OIDC-only user to immutable provider issuer and subject."""

    __tablename__ = 'auth_oidc_identities'

    id = Column(Integer, primary_key=True)
    user_id = Column(
        Integer,
        ForeignKey('orm_login.id', ondelete='CASCADE'),
        nullable=False,
        unique=True,
        index=True,
    )
    issuer = Column(String(500), nullable=False)
    subject = Column(String(255), nullable=False)
    provider_username = Column(String(100), nullable=False)
    email = Column(String(320), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(pytz.UTC), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(pytz.UTC),
        onupdate=lambda: datetime.now(pytz.UTC),
        nullable=False,
    )
    last_login_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        UniqueConstraint('issuer', 'subject', name='uq_oidc_identity_issuer_subject'),
    )

    def to_dict(self) -> dict:
        return {
            'user_id': self.user_id,
            'issuer': self.issuer,
            'subject': self.subject,
            'provider_username': self.provider_username,
            'email': self.email,
            'last_login_at': self.last_login_at.isoformat() if self.last_login_at else None,
        }


def init_model(model_base, db_logger=None):
    """Initialize model with project SQLAlchemy base."""
    class OIDCIdentityModel(model_base, OIDCIdentity):
        __table_args__ = OIDCIdentity.__table_args__ + ({'extend_existing': True},)

    if db_logger:
        db_logger.info('Initialized OIDC identity ORM model')
    return OIDCIdentityModel
