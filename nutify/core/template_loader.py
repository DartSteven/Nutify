"""Shared Flask Jinja template loader configuration."""

from __future__ import annotations

from pathlib import Path

from flask import Flask
from jinja2 import ChoiceLoader, FileSystemLoader


def _resolve_app_root(app_root: str | Path | None = None) -> Path:
    """Resolve Nutify app root directory."""
    if app_root is not None:
        return Path(app_root).resolve()
    return Path(__file__).resolve().parents[1]


def resolve_template_search_paths(app_root: str | Path | None = None) -> list[str]:
    """Return existing template search paths in priority order."""
    root = _resolve_app_root(app_root)
    frontend_server_templates = root / "frontend" / "server_templates"
    legacy_templates = root / "templates"

    ordered_paths: list[Path] = [frontend_server_templates, legacy_templates]
    existing = [str(path) for path in ordered_paths if path.exists() and path.is_dir()]
    return existing


def configure_template_loader(app: Flask, app_root: str | Path | None = None) -> None:
    """Configure Jinja to load templates from frontend server templates first."""
    if app.extensions.get("nutify_template_loader_configured"):
        return

    template_paths = resolve_template_search_paths(app_root)
    if not template_paths:
        app.extensions["nutify_template_loader_configured"] = True
        return

    loaders: list[object] = [FileSystemLoader(template_paths)]
    if app.jinja_loader is not None:
        loaders.append(app.jinja_loader)

    app.jinja_loader = ChoiceLoader(loaders)
    app.extensions["nutify_template_loader_configured"] = True
