"""Options Package.

Defines package exports and module-level initialization helpers.
"""

from .options import (
    get_database_stats,
    backup_database,
    optimize_database,
    vacuum_database,
    get_log_files,
    get_log_content,
    download_logs,
    get_system_info,
    get_filtered_logs,
    clear_logs,
    get_variable_config,
    get_variable_config_row
)

from .api_options import api_options, api_options_compat
from .routes_options import routes_options

# Export the necessary routes for backward compatibility
from .api_options import (
    api_database_stats,
    handle_get_logs,
    handle_clear_logs,
    api_system_info_compat,
    get_about_image,
    api_optimize_database,
    api_vacuum_database,
    api_backup_database,
    get_variables_settings,
    save_variables_config,
    restart_application,
    update_log_setting,
    download_logs,
    test_email_notification
) 
