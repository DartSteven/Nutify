"""Administrator-only OIDC configuration API routes."""

from __future__ import annotations

from flask import current_app, jsonify, request

from . import require_admin
from .oidc import reload_oidc_module
from .oidc_store import (
    OIDCConfigError,
    admin_configuration,
    delete_database_configuration,
    dynamic_register_database_configuration,
    run_discovery,
    save_database_configuration,
    set_enabled,
)
from .security import rate_limit
from core.logger import web_logger as logger


def _reload() -> None:
    reload_oidc_module(current_app._get_current_object(), logger)


def _payload() -> dict:
    value = request.get_json(silent=True)
    return value if isinstance(value, dict) else {}


def register_oidc_admin_routes(blueprint) -> None:
    @blueprint.get('/api/admin/oidc')
    @require_admin
    def oidc_admin_get():
        return jsonify({'success': True, 'data': admin_configuration()})

    @blueprint.put('/api/admin/oidc')
    @require_admin
    @rate_limit('20 per minute')
    def oidc_admin_save():
        try:
            save_database_configuration(_payload())
            _reload()
            return jsonify({'success': True, 'data': admin_configuration()})
        except OIDCConfigError as exc:
            return jsonify({'error': str(exc)}), 400
        except Exception:
            logger.exception('OIDC configuration save failed')
            return jsonify({'error': 'OIDC configuration could not be saved'}), 500

    @blueprint.post('/api/admin/oidc/discover')
    @require_admin
    @rate_limit('10 per minute')
    def oidc_admin_discover():
        try:
            result = run_discovery()
            _reload()
            return jsonify({
                'success': True,
                'data': {
                    'configuration': admin_configuration(),
                    'registration_supported': bool(result.get('registration_supported')),
                    'scopes_supported': result.get('scopes_supported', []),
                    'code_flow_supported': bool(result.get('code_flow_supported')),
                },
            })
        except OIDCConfigError as exc:
            return jsonify({'error': str(exc)}), 400
        except Exception:
            logger.exception('OIDC provider discovery failed')
            return jsonify({'error': 'OIDC provider discovery failed'}), 500

    @blueprint.post('/api/admin/oidc/dynamic-register')
    @require_admin
    @rate_limit('5 per hour')
    def oidc_admin_dynamic_register():
        try:
            record, _ = dynamic_register_database_configuration(_payload())
            run_discovery(record)
            _reload()
            return jsonify({'success': True, 'data': admin_configuration()})
        except (OIDCConfigError, ValueError) as exc:
            return jsonify({'error': str(exc)}), 400
        except Exception:
            logger.exception('OIDC Dynamic Client Registration failed')
            return jsonify({'error': 'Dynamic Client Registration failed'}), 400

    @blueprint.post('/api/admin/oidc/enabled')
    @require_admin
    @rate_limit('20 per minute')
    def oidc_admin_enabled():
        try:
            enabled = bool(_payload().get('enabled'))
            set_enabled(enabled)
            _reload()
            return jsonify({'success': True, 'data': admin_configuration()})
        except OIDCConfigError as exc:
            return jsonify({'error': str(exc)}), 400
        except Exception:
            logger.exception('OIDC enabled state update failed')
            return jsonify({'error': 'OIDC enabled state could not be updated'}), 500

    @blueprint.delete('/api/admin/oidc')
    @require_admin
    @rate_limit('10 per hour')
    def oidc_admin_delete():
        try:
            delete_database_configuration()
            _reload()
            return jsonify({'success': True, 'data': admin_configuration()})
        except OIDCConfigError as exc:
            return jsonify({'error': str(exc)}), 400
        except Exception:
            logger.exception('OIDC configuration delete failed')
            return jsonify({'error': 'OIDC configuration could not be deleted'}), 500
