"""Domain-separated encryption helpers for OIDC configuration secrets."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
from typing import Any, Mapping

from cryptography.fernet import Fernet
from flask import current_app, has_app_context


_ENCRYPTION_CONTEXT = b'nutify:oidc-config:encryption:v1'
_FINGERPRINT_CONTEXT = b'nutify:oidc-config:fingerprint:v1'


def _secret_key() -> bytes:
    value = current_app.config.get('SECRET_KEY') if has_app_context() else os.getenv('SECRET_KEY')
    if not value:
        raise RuntimeError('SECRET_KEY is required for OIDC configuration encryption')
    return value if isinstance(value, bytes) else str(value).encode('utf-8')


def _fernet() -> Fernet:
    derived = hmac.new(_secret_key(), _ENCRYPTION_CONTEXT, hashlib.sha256).digest()
    return Fernet(base64.urlsafe_b64encode(derived))


def encrypt_secret(value: str) -> bytes:
    text = str(value or '')
    if not text:
        raise ValueError('OIDC client secret cannot be empty')
    return _fernet().encrypt(text.encode('utf-8'))


def decrypt_secret(value: bytes | None) -> str:
    if not value:
        return ''
    return _fernet().decrypt(value).decode('utf-8')


def configuration_fingerprint(values: Mapping[str, Any]) -> str:
    canonical = json.dumps(values, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode('utf-8')
    return hmac.new(_secret_key(), _FINGERPRINT_CONTEXT + canonical, hashlib.sha256).hexdigest()
