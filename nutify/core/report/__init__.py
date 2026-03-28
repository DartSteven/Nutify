"""Report Package.

Defines package exports and module-level initialization helpers.
"""

from core.report.report import report_manager
from core.report.api_report import api_report
from core.report.routes_report import routes_report

__all__ = [
    'report_manager',
    'api_report',
    'routes_report'
] 