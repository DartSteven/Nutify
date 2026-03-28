"""Report Routes Module.

Registers HTTP routes and page handlers for this feature domain.
"""

from datetime import datetime

from flask import Blueprint, flash, redirect, request, url_for

from core.logger import report_logger as logger
from core.multi_nut.target_scope import resolve_settings_target_id
from core.react_frontend import serve_react_index
from core.report.report import report_manager

routes_report = Blueprint('routes_report', __name__)


@routes_report.route('/reports')
def reports_page():
    return serve_react_index()


@routes_report.route('/reports/new')
def new_report_page():
    return serve_react_index()


@routes_report.route('/reports/edit/<int:schedule_id>')
def edit_report_page(schedule_id):
    _ = schedule_id
    return serve_react_index()


@routes_report.route('/reports/generate')
def generate_report_page():
    return serve_react_index()


@routes_report.route('/reports/view')
def view_report():
    """Generate and display a report based on query parameters."""
    try:
        from_date_str = request.args.get('from_date')
        to_date_str = request.args.get('to_date')
        report_type = request.args.get('report_type', 'custom')

        if not from_date_str or not to_date_str:
            flash('From date and to date are required to generate a report.', 'danger')
            return redirect(url_for('routes_report.generate_report_page'))

        try:
            from_date = datetime.fromisoformat(from_date_str.replace('Z', '+00:00'))
            to_date = datetime.fromisoformat(to_date_str.replace('Z', '+00:00'))
        except ValueError as exc:
            flash(f'Invalid date format: {str(exc)}', 'danger')
            return redirect(url_for('routes_report.generate_report_page'))

        target_id = resolve_settings_target_id(request.args.get('target_id'))
        result = report_manager.generate_report(from_date, to_date, report_type, target_id=target_id)

        if result.get('status') == 'success':
            return result.get('html')

        flash(result.get('message', 'Failed to generate report'), 'danger')
        return redirect(url_for('routes_report.generate_report_page'))
    except Exception as exc:
        logger.error(f"Error viewing report: {str(exc)}", exc_info=True)
        flash(f'An error occurred generating the report: {str(exc)}', 'danger')
        return redirect(url_for('routes_report.generate_report_page'))
