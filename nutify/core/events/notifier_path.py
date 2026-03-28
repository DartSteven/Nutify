"""Events Module.

Implements core runtime logic and helpers used by this feature.
"""

import os
from pathlib import Path


def _ensure_executable(path: Path) -> None:
    """Best-effort: ensure notifier script can be executed directly by upsmon."""
    try:
        current_mode = path.stat().st_mode
        path.chmod(current_mode | 0o111)
    except Exception:
        pass


def _ensure_tmp_symlink(target: Path) -> Path:
    """
    Return a stable symlink path without spaces for NOTIFYCMD.

    Some development paths contain spaces (for example macOS workspaces).
    A fixed symlink in /tmp avoids command parsing issues in upsmon.
    """
    # Use a stable short path instead of platform-specific random temp folders.
    link_path = Path("/tmp/nutify_ups_notifier.py")
    try:
        if link_path.exists() or link_path.is_symlink():
            try:
                if link_path.is_symlink() and link_path.resolve() == target.resolve():
                    return link_path
            except Exception:
                pass
            link_path.unlink()
        link_path.symlink_to(target)
    except Exception:
        return target
    return link_path


def get_ups_notifier_command_path():
    """Return the absolute command path used by upsmon NOTIFYCMD."""
    override = str(os.environ.get("NUTIFY_NOTIFYCMD") or "").strip()
    if override:
        return override

    notifier_path = Path(__file__).resolve().parent / "ups_notifier.py"
    _ensure_executable(notifier_path)

    if " " in str(notifier_path):
        notifier_path = _ensure_tmp_symlink(notifier_path)

    return str(notifier_path)
