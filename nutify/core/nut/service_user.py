"""Resolve the operating-system account used by NUT daemons."""

import os
import re


_USERNAME_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_.-]{0,31}$")


def get_nut_service_user() -> str:
    """Return a validated NUT service account from runtime configuration."""
    username = str(os.getenv("NUT_SERVICE_USER", "root") or "").strip()
    if not _USERNAME_PATTERN.fullmatch(username):
        raise ValueError("NUT_SERVICE_USER must be a valid operating-system username")
    return username
