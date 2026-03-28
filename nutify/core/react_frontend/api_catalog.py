"""Dynamic API catalog helpers for the hidden React API explorer page."""

from __future__ import annotations

from datetime import datetime, timezone
import inspect
from typing import Any

from flask import current_app
from werkzeug.routing import Rule

from core.auth.api_guard import classify_route_access

_METHOD_ORDER = {
    'GET': 0,
    'POST': 1,
    'PUT': 2,
    'PATCH': 3,
    'DELETE': 4,
}

_GROUP_LABELS = {
    'auth': 'Authentication',
    'battery': 'Battery',
    'data': 'Monitoring Data',
    'energy': 'Energy',
    'events': 'Events',
    'frontend': 'Frontend Runtime',
    'main': 'Dashboard',
    'mail': 'Mail',
    'multi-nut': 'Multi-NUT',
    'ntfy': 'Ntfy',
    'nut_config': 'Setup Wizard',
    'options': 'Options',
    'power': 'Power',
    'report': 'Reports',
    'scheduler': 'Scheduler',
    'settings': 'Settings',
    'table': 'Tables',
    'telegram': 'Telegram',
    'upscmd': 'UPS Commands',
    'upsrw': 'UPS Variables',
    'voltage': 'Voltage',
    'webhook': 'Webhook',
}


def build_api_catalog() -> dict[str, Any]:
    """Build a grouped catalog of all registered API routes."""
    groups: dict[str, dict[str, Any]] = {}

    for route in _collect_routes():
        group = groups.setdefault(
            route['group_key'],
            {
                'key': route['group_key'],
                'label': route['group_label'],
                'routes': [],
            },
        )
        group['routes'].append(route)

    ordered_groups = sorted(
        groups.values(),
        key=lambda group: (group['label'].lower(), group['key']),
    )

    for group in ordered_groups:
        group['routes'].sort(key=lambda route: (route['path'], route['methods']))
        group['route_count'] = len(group['routes'])

    return {
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'total_routes': sum(group['route_count'] for group in ordered_groups),
        'total_groups': len(ordered_groups),
        'groups': ordered_groups,
    }


def _collect_routes() -> list[dict[str, Any]]:
    routes: list[dict[str, Any]] = []

    for rule in current_app.url_map.iter_rules():
        if not _is_api_rule(rule):
            continue

        methods = _normalize_methods(rule.methods)
        if not methods:
            continue

        view = current_app.view_functions.get(rule.endpoint)
        base_view = inspect.unwrap(view) if view else None
        summary = _build_summary(rule, base_view)
        group_key = _resolve_group_key(rule.rule)
        access_kind, access_label, access_detail = _resolve_access_metadata(
            path=rule.rule,
            methods=methods,
            view=view,
            base_view=base_view,
        )

        routes.append(
            {
                'path': rule.rule,
                'methods': methods,
                'endpoint': rule.endpoint,
                'module': getattr(base_view, '__module__', ''),
                'function_name': getattr(base_view, '__name__', ''),
                'summary': summary,
                'group_key': group_key,
                'group_label': _format_group_label(group_key),
                'path_params': sorted(rule.arguments),
                'supports_get': 'GET' in methods,
                'access_kind': access_kind,
                'access_label': access_label,
                'access_detail': access_detail,
            }
        )

    return sorted(routes, key=lambda route: (route['group_label'].lower(), route['path']))


def _is_api_rule(rule: Rule) -> bool:
    path = str(rule.rule or '').strip()
    if not path or path == '/api':
        return False

    if path.startswith('/frontend-dist/'):
        return False

    if rule.endpoint == 'static':
        return False

    segments = [segment for segment in path.split('/') if segment]
    return 'api' in segments


def _normalize_methods(methods: set[str] | None) -> list[str]:
    normalized = [method for method in (methods or set()) if method not in {'HEAD', 'OPTIONS'}]
    return sorted(normalized, key=lambda method: (_METHOD_ORDER.get(method, 99), method))


def _build_summary(rule: Rule, view: Any) -> str:
    docstring = inspect.getdoc(view) if view else ''
    if docstring:
        first_line = docstring.splitlines()[0].strip()
        if first_line:
            return first_line.rstrip('.')

    endpoint = str(rule.endpoint or '').replace('.', ' ')
    if endpoint:
        return endpoint.replace('_', ' ').strip().title()

    return f"API route for {rule.rule}"


def _resolve_group_key(path: str) -> str:
    segments = [segment for segment in path.split('/') if segment]
    if not segments:
        return 'core'

    try:
        api_index = segments.index('api')
    except ValueError:
        return segments[0]

    if api_index > 0:
        return segments[api_index - 1]

    if api_index + 1 < len(segments):
        return segments[api_index + 1]

    return 'core'


def _format_group_label(group_key: str) -> str:
    if group_key in _GROUP_LABELS:
        return _GROUP_LABELS[group_key]

    chunks = group_key.replace('_', '-').split('-')
    formatted_chunks = []
    for chunk in chunks:
        if chunk.lower() in {'api', 'ups', 'nut', 'ntfy'}:
            formatted_chunks.append(chunk.upper())
        else:
            formatted_chunks.append(chunk.capitalize())
    return ' '.join(formatted_chunks) or 'Core'


def _resolve_access_metadata(path: str, methods: list[str], view: Any, base_view: Any) -> tuple[str, str, str]:
    """Classify route access policy from decorator metadata or route-specific markers."""
    for candidate in _iter_wrapped_callables(view):
        kind = str(getattr(candidate, '_nutify_auth_kind', '') or '').strip().lower()
        if not kind:
            continue

        detail = str(getattr(candidate, '_nutify_auth_detail', '') or '').strip()
        if kind == 'admin':
            return 'admin', 'Admin only', 'Requires authenticated admin session'
        if kind == 'permission':
            page_name = detail or 'restricted'
            return 'permission', f'Permission: {page_name}', 'Requires authenticated user with page permission'
        if kind == 'session':
            label = 'Private (session)'
            if detail:
                return 'session', label, detail
            return 'session', label, 'Requires authenticated user session'
        if kind == 'token':
            header_name = detail or 'token'
            return 'token', f'Token: {header_name}', 'Requires callback token header'

    if _looks_like_token_route(base_view):
        return 'token', 'Token', 'Requires callback token header'

    guarded_classification = classify_route_access(path, methods)
    if guarded_classification:
        return guarded_classification

    return 'public', 'Public', 'No login required'


def _iter_wrapped_callables(view: Any):
    seen_ids: set[int] = set()
    current = view
    while current is not None and id(current) not in seen_ids:
        seen_ids.add(id(current))
        yield current
        current = getattr(current, '__wrapped__', None)


def _looks_like_token_route(view: Any) -> bool:
    if not view:
        return False

    try:
        source = inspect.getsource(view)
    except (OSError, TypeError):
        return False

    return 'X-Nutify-Token' in source or '_is_event_token_valid' in source
