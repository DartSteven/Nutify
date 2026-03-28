"""Utilities for Nutify callback token used by remote NOTIFYCMD bridges."""

from __future__ import annotations

import os
import secrets
from pathlib import Path

from flask import current_app

from core.logger import web_logger as logger
from core.settings import INSTANCE_PATH


TOKEN_ENV_KEY = "NUT_EVENT_API_TOKEN"
TOKEN_FILENAME = "nut_event_api_token"


def _configured_from_app_or_env() -> str:
    """Return token from Flask config or environment, if present."""
    token = str(current_app.config.get(TOKEN_ENV_KEY) or "").strip()
    if token:
        return token
    return str(os.environ.get(TOKEN_ENV_KEY) or "").strip()


def _token_file_path() -> Path:
    """Return token file path under instance directory."""
    instance_path = str(current_app.config.get("INSTANCE_PATH") or INSTANCE_PATH)
    instance_dir = Path(instance_path)
    instance_dir.mkdir(parents=True, exist_ok=True)
    return instance_dir / TOKEN_FILENAME


def _read_token_from_file(path: Path) -> str:
    """Read token from disk."""
    try:
        token = path.read_text(encoding="utf-8").strip()
        if token:
            return token
    except Exception as exc:
        logger.warning(f"Could not read callback token file {path}: {exc}")
    return ""


def _write_token_to_file(path: Path, token: str):
    """Persist token with restrictive permissions."""
    path.write_text(token, encoding="utf-8")
    try:
        os.chmod(path, 0o600)
    except Exception as exc:
        logger.debug(f"Could not chmod callback token file {path}: {exc}")


def get_configured_event_api_token() -> str:
    """Return existing callback token without creating a new one."""
    token = _configured_from_app_or_env()
    if token:
        return token

    path = _token_file_path()
    token = _read_token_from_file(path)
    if token:
        # Cache token in app config for quick reuse.
        current_app.config[TOKEN_ENV_KEY] = token
    return token


def ensure_event_api_token() -> str:
    """Return callback token, creating one when missing."""
    token = get_configured_event_api_token()
    if token:
        return token

    token = secrets.token_urlsafe(32)
    path = _token_file_path()
    try:
        _write_token_to_file(path, token)
        logger.info(f"Generated callback token file for remote NOTIFYCMD: {path}")
    except Exception as exc:
        logger.error(f"Could not write callback token file {path}: {exc}")
        return ""

    current_app.config[TOKEN_ENV_KEY] = token
    return token

