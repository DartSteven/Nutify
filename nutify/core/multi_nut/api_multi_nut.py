"""REST API for Multi-NUT configuration and monitoring."""

from __future__ import annotations

import json

from flask import Blueprint, current_app, jsonify, request

from core.auth import require_admin, require_auth_json
from core.db.ups import db
from core.logger import system_logger as system_logger
from core.logger import web_logger as logger

from .analytics import build_multi_target_report, build_target_dashboard, list_targets_overview
from .active_target import (
    clear_active_target,
    get_active_target,
    get_request_or_active_target_id,
    set_active_target_id,
)
from .connection import normalize_metrics, run_upsc_command, test_target_connection
from .polling import get_multi_nut_runtime_state
from .renamer import build_catalog_rows, build_source_list, save_target_mappings, target_mapping_sources
from .storage import (
    create_target,
    delete_target,
    get_latest_target_snapshot,
    get_target_with_policy,
    list_targets,
    load_target_history,
    record_target_snapshot,
    record_target_error_snapshot,
    set_primary_target,
    update_target,
    utc_now,
)

api_multi_nut = Blueprint('api_multi_nut', __name__, url_prefix='/api/multi-nut')

def _json_error(message: str, status: int = 400):
    return jsonify({'success': False, 'error': message}), status

def _update_target_test_status(target, success: bool, message: str | None = None):
    target.last_test_status = success
    target.last_test_error = None if success else (str(message)[:1000] if message else None)
    db.session.commit()

def _resolve_renamer_target_id(payload_or_args) -> int:
    explicit_target_id = None
    if isinstance(payload_or_args, dict):
        try:
            explicit_target_id = int(payload_or_args.get('target_id'))
        except (TypeError, ValueError):
            explicit_target_id = None
    elif payload_or_args is not None and hasattr(payload_or_args, 'get'):
        explicit_target_id = payload_or_args.get('target_id', type=int)

    if explicit_target_id:
        return int(explicit_target_id)

    active_target_id = get_request_or_active_target_id()
    if active_target_id:
        return int(active_target_id)

    enabled_targets = list_targets(include_disabled=False)
    if enabled_targets:
        return int(enabled_targets[0]['id'])

    raise ValueError('No enabled targets available')

def _extract_keys_from_snapshot(snapshot: dict) -> list[str]:
    keys = set()
    for key_name in ('raw_json', 'data_json'):
        payload = snapshot.get(key_name)
        if not payload:
            continue
        try:
            parsed = json.loads(payload)
        except Exception:
            continue
        if isinstance(parsed, dict):
            keys.update(str(item).strip() for item in parsed.keys() if str(item).strip())
    return sorted(keys)

def _collect_target_source_keys(target) -> tuple[list[str], str]:
    success, raw_payload, _error = run_upsc_command(
        ups_name=target.ups_name,
        host=target.host,
        port=target.port,
        command_path=target.command_path,
        timeout=8,
        target_id=target.id,
    )
    if success and raw_payload:
        return build_source_list(raw_payload), 'live_upsc'

    snapshot = get_latest_target_snapshot(target.id)
    if snapshot:
        snapshot_keys = _extract_keys_from_snapshot(snapshot)
        if snapshot_keys:
            return snapshot_keys, 'latest_snapshot'

    return [], 'none'

@api_multi_nut.route('/state', methods=['GET'])
@require_auth_json
def multi_nut_state():
    """Return runtime state used by top bar and routing logic."""
    state = get_multi_nut_runtime_state()
    state['profile'] = state.get('monitoring_profile', 'single')
    active_target_id = get_request_or_active_target_id()
    state['active_target_id'] = active_target_id
    return jsonify({'success': True, 'data': state})

@api_multi_nut.route('/active-target', methods=['GET'])
@require_auth_json
def get_active_target_route():
    """Return current active dashboard target."""
    target = get_active_target()
    return jsonify(
        {
            'success': True,
            'data': {
                'target': target,
                'target_id': int(target['id']) if target else None,
            },
        }
    )

@api_multi_nut.route('/active-target', methods=['POST'])
@require_auth_json
def set_active_target_route():
    """Set current active dashboard target."""
    payload = request.get_json(silent=True) or {}
    target_id = payload.get('target_id')
    try:
        target = set_active_target_id(int(target_id))
        return jsonify({'success': True, 'data': {'target': target, 'target_id': int(target['id'])}})
    except Exception as exc:
        return _json_error(str(exc), 400)

@api_multi_nut.route('/active-target', methods=['DELETE'])
@require_auth_json
def clear_active_target_route():
    """Clear active dashboard target selection."""
    clear_active_target()
    return jsonify({'success': True, 'data': {'target_id': None}})

@api_multi_nut.route('/targets', methods=['GET'])
@require_auth_json
def get_targets():
    """List configured targets and policies."""
    include_disabled = request.args.get('include_disabled', 'true').lower() == 'true'
    data = list_targets(include_disabled=include_disabled)
    return jsonify({'success': True, 'data': data})

@api_multi_nut.route('/targets/<int:target_id>', methods=['GET'])
@require_auth_json
def get_target(target_id: int):
    """Return single target detail."""
    target, policy = get_target_with_policy(target_id)
    if not target:
        return _json_error('Target not found', 404)

    latest = get_latest_target_snapshot(target_id)
    return jsonify(
        {
            'success': True,
            'data': {
                'target': target.to_dict(),
                'policy': policy.to_dict() if policy else None,
                'latest': latest,
            },
        }
    )

@api_multi_nut.route('/targets/test', methods=['POST'])
@require_admin
def test_target():
    """Test target connection before creation/update."""
    payload = request.get_json(silent=True) or {}
    result = test_target_connection(payload)
    status_code = 200 if result['success'] else 400
    return jsonify(result), status_code

@api_multi_nut.route('/targets', methods=['POST'])
@require_admin
def create_target_route():
    """Create a new Multi-NUT target using wizard payload."""
    payload = request.get_json(silent=True) or {}

    log_context = (
        f"ups_name={payload.get('ups_name')} "
        f"host={payload.get('host')} "
        f"port={payload.get('port', 3493)}"
    )
    logger.info(f"Multi-NUT create target request received: {log_context}")
    system_logger.info(f"Multi-NUT create target request received: {log_context}")

    result = test_target_connection(payload)
    if not result['success']:
        logger.warning(f"Multi-NUT pre-create test failed: {result['message']} ({log_context})")
        system_logger.warning(f"Multi-NUT pre-create test failed: {result['message']} ({log_context})")
        return _json_error(result['message'])

    try:
        created = create_target(payload)
        target_data = created.get('target') or {}
        created_context = (
            f"id={target_data.get('id')} "
            f"name={target_data.get('name')} "
            f"target={target_data.get('ups_name')}@{target_data.get('host')}:{target_data.get('port')}"
        )
        logger.info(f"Multi-NUT target created successfully: {created_context}")
        system_logger.info(f"Multi-NUT target created successfully: {created_context}")
        return jsonify({'success': True, 'data': created}), 201
    except Exception as exc:
        logger.error(f"Error creating Multi-NUT target: {exc}")
        system_logger.error(f"Error creating Multi-NUT target: {exc}")
        db.session.rollback()
        return _json_error(str(exc))

@api_multi_nut.route('/targets/<int:target_id>', methods=['PUT'])
@require_admin
def update_target_route(target_id: int):
    """Update target and policy."""
    payload = request.get_json(silent=True) or {}
    try:
        updated = update_target(target_id, payload)
        return jsonify({'success': True, 'data': updated})
    except Exception as exc:
        logger.error(f"Error updating target {target_id}: {exc}")
        db.session.rollback()
        return _json_error(str(exc), 404 if 'not found' in str(exc).lower() else 400)

@api_multi_nut.route('/targets/<int:target_id>/toggle', methods=['POST'])
@require_admin
def toggle_target_route(target_id: int):
    """Enable/disable a target."""
    payload = request.get_json(silent=True) or {}
    enabled = bool(payload.get('enabled', True))

    try:
        updated = update_target(target_id, {'enabled': enabled})
        return jsonify({'success': True, 'data': updated})
    except Exception as exc:
        db.session.rollback()
        return _json_error(str(exc), 404 if 'not found' in str(exc).lower() else 400)

@api_multi_nut.route('/targets/<int:target_id>/primary', methods=['POST'])
@require_admin
def set_primary_route(target_id: int):
    """Set target as primary dashboard UPS."""
    try:
        result = set_primary_target(target_id)
        return jsonify({'success': True, 'data': result})
    except Exception as exc:
        db.session.rollback()
        return _json_error(str(exc), 404 if 'not found' in str(exc).lower() else 400)

@api_multi_nut.route('/targets/<int:target_id>/poll-now', methods=['POST'])
@require_admin
def poll_now_route(target_id: int):
    """Force immediate poll for one target."""
    target, policy = get_target_with_policy(target_id)
    if not target:
        return _json_error('Target not found', 404)

    success, raw_payload, error = run_upsc_command(
        ups_name=target.ups_name,
        host=target.host,
        port=target.port,
        command_path=target.command_path,
        timeout=10,
        target_id=target.id,
    )

    if not success:
        try:
            record_target_error_snapshot(
                target=target,
                policy=policy,
                error_message=error,
                timestamp_utc=utc_now(),
            )
        except Exception:
            db.session.rollback()
        _update_target_test_status(target, False, error)
        return _json_error(error)

    metrics = normalize_metrics(raw_payload, target_id=target.id)
    record_target_snapshot(
        target,
        policy,
        metrics,
        timestamp_utc=utc_now(),
        raw_payload=raw_payload,
    )
    _update_target_test_status(target, True)

    return jsonify({'success': True, 'data': {'metrics': metrics}})

@api_multi_nut.route('/renamer/catalog', methods=['GET'])
@require_auth_json
def renamer_catalog_route():
    """Return canonical catalog with suggested/current source mappings."""
    try:
        target_id = _resolve_renamer_target_id(request.args)
    except ValueError as exc:
        return _json_error(str(exc), 404)

    target, _policy = get_target_with_policy(target_id)
    if not target:
        return _json_error('Target not found', 404)

    source_keys, source_origin = _collect_target_source_keys(target)
    rows = build_catalog_rows(target_id=target.id, available_source_keys=source_keys)

    return jsonify(
        {
            'success': True,
            'data': {
                'target_id': target.id,
                'target': target.to_dict(),
                'source_origin': source_origin,
                'source_keys': source_keys,
                'rows': rows,
                'mapping_count': len(target_mapping_sources(target.id)),
            },
        }
    )

@api_multi_nut.route('/renamer/mappings', methods=['POST'])
@require_admin
def save_renamer_mappings_route():
    """Save canonical variable mappings for one target."""
    payload = request.get_json(silent=True) or {}
    try:
        target_id = _resolve_renamer_target_id(payload)
    except ValueError as exc:
        return _json_error(str(exc), 404)

    target, _policy = get_target_with_policy(target_id)
    if not target:
        return _json_error('Target not found', 404)

    mappings_payload = payload.get('mappings', {})
    if not isinstance(mappings_payload, dict):
        return _json_error('mappings must be a dictionary', 400)

    replace = bool(payload.get('replace', True))
    save_target_mappings(
        target_id=target.id,
        mapping_by_canonical=mappings_payload,
        replace=replace,
    )

    return jsonify(
        {
            'success': True,
            'data': {
                'target_id': target.id,
                'mapping_count': len(target_mapping_sources(target.id)),
            },
        }
    )

@api_multi_nut.route('/targets/<int:target_id>', methods=['DELETE'])
@require_admin
def delete_target_route(target_id: int):
    """Delete non-primary target."""
    try:
        result = delete_target(target_id)
        return jsonify({'success': True, 'data': result})
    except Exception as exc:
        db.session.rollback()
        return _json_error(str(exc), 404 if 'not found' in str(exc).lower() else 400)

@api_multi_nut.route('/overview', methods=['GET'])
@require_auth_json
def overview_route():
    """Return compact overview for all active targets."""
    hours = request.args.get('hours', type=int, default=24)
    data = list_targets_overview(hours=hours)
    return jsonify({'success': True, 'data': data})

@api_multi_nut.route('/targets/<int:target_id>/history', methods=['GET'])
@require_auth_json
def history_route(target_id: int):
    """Return target history series payload."""
    hours = request.args.get('hours', type=int, default=24)
    limit = request.args.get('limit', type=int, default=5000)
    data = load_target_history(target_id, hours=hours, limit=limit)
    return jsonify({'success': True, 'data': data})

@api_multi_nut.route('/targets/<int:target_id>/dashboard', methods=['GET'])
@require_auth_json
def dashboard_route(target_id: int):
    """Return dashboard payload for one target."""
    target, policy = get_target_with_policy(target_id)
    if not target:
        return _json_error('Target not found', 404)

    hours = request.args.get('hours', type=int, default=24)
    dashboard = build_target_dashboard(target_id, hours=hours)

    return jsonify(
        {
            'success': True,
            'data': {
                'target': target.to_dict(),
                'policy': policy.to_dict() if policy else None,
                **dashboard,
            },
        }
    )

@api_multi_nut.route('/report', methods=['GET'])
@require_auth_json
def report_route():
    """Return Multi-NUT report payload for one target or all targets."""
    hours = request.args.get('hours', type=int, default=24)
    scope = str(request.args.get('scope', 'selected') or 'selected').strip().lower()
    download = str(request.args.get('download', 'false') or 'false').strip().lower() == 'true'

    if scope not in {'selected', 'all'}:
        return _json_error('scope must be selected or all', 400)

    selected_target_id = request.args.get('target_id', type=int)
    if scope == 'selected' and selected_target_id is None:
        targets = list_targets(include_disabled=False)
        if not targets:
            return _json_error('No enabled targets available', 404)
        selected_target_id = targets[0]['id']

    try:
        report_payload = build_multi_target_report(
            hours=hours,
            target_id=(None if scope == 'all' else selected_target_id),
        )
    except ValueError as exc:
        return _json_error(str(exc), 404)

    if download:
        target_suffix = 'all' if scope == 'all' else f"target_{selected_target_id}"
        filename = f"multi_nut_report_{target_suffix}_{hours}h.json"
        response = current_app.response_class(
            response=json.dumps(report_payload, ensure_ascii=True, indent=2),
            status=200,
            mimetype='application/json',
        )
        response.headers['Content-Disposition'] = f'attachment; filename={filename}'
        return response

    return jsonify({'success': True, 'data': report_payload})

def register_api_routes(app):
    """Register API blueprint."""
    if api_multi_nut.name not in app.blueprints:
        app.register_blueprint(api_multi_nut)
