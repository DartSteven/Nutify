"""Socket.IO transport configuration shared by every runtime instance."""

from __future__ import annotations

import os
from typing import Callable, List, Optional
from urllib.parse import urlsplit


SOCKETIO_ALLOWED_ORIGINS_ENV = 'SOCKETIO_ALLOWED_ORIGINS'


def _normalize_origin(value: str) -> str:
    origin = str(value or '').strip()
    parsed = urlsplit(origin)
    if (
        parsed.scheme not in {'http', 'https'}
        or not parsed.netloc
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path not in {'', '/'}
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError(
            f"Invalid {SOCKETIO_ALLOWED_ORIGINS_ENV} origin {origin!r}; "
            "use comma-separated http(s) origins without paths"
        )
    return f'{parsed.scheme.lower()}://{parsed.netloc.lower()}'


def get_socketio_allowed_origins() -> Optional[List[str]]:
    """Return configured proxy origins, or None for strict same-origin checks."""
    raw_value = os.environ.get(SOCKETIO_ALLOWED_ORIGINS_ENV, '').strip()
    if not raw_value:
        return None

    origins: List[str] = []
    for value in raw_value.split(','):
        if not value.strip():
            continue
        if value.strip() == '*':
            raise ValueError(
                f"{SOCKETIO_ALLOWED_ORIGINS_ENV}=* is not allowed; configure explicit origins"
            )
        normalized = _normalize_origin(value)
        if normalized not in origins:
            origins.append(normalized)

    return origins or None


def _request_origins(environ: dict) -> List[str]:
    candidates: List[str] = []
    scheme = str(environ.get('wsgi.url_scheme') or '').strip()
    host = str(environ.get('HTTP_HOST') or '').strip()
    if scheme and host:
        candidates.append(f'{scheme}://{host}')

    forwarded_proto = str(environ.get('HTTP_X_FORWARDED_PROTO') or '').split(',')[0].strip()
    forwarded_host = str(environ.get('HTTP_X_FORWARDED_HOST') or '').split(',')[0].strip()
    if forwarded_proto or forwarded_host:
        candidates.append(f'{forwarded_proto or scheme}://{forwarded_host or host}')

    normalized: List[str] = []
    for candidate in candidates:
        try:
            origin = _normalize_origin(candidate)
        except ValueError:
            continue
        if origin not in normalized:
            normalized.append(origin)
    return normalized


def build_socketio_origin_validator() -> Optional[Callable[[str, dict], bool]]:
    """Extend strict request-origin checks with configured public proxy origins."""
    configured_origins = get_socketio_allowed_origins()
    if not configured_origins:
        return None

    def is_allowed(origin: str, environ: dict) -> bool:
        try:
            normalized_origin = _normalize_origin(origin)
        except ValueError:
            return False
        allowed_origins = set(configured_origins)
        allowed_origins.update(_request_origins(environ))
        return normalized_origin in allowed_origins

    return is_allowed


def socketio_server_options() -> dict:
    """Build Flask-SocketIO options without weakening default origin checks."""
    return {'cors_allowed_origins': build_socketio_origin_validator()}
