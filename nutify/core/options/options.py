"""Options Module.

Implements core runtime logic and helpers used by this feature.
"""

import os
import logging
import sqlite3
from datetime import datetime, timedelta
from ..db.ups import db, data_lock
from flask import jsonify, send_file, current_app, request, has_app_context
import shutil
from pathlib import Path
import re
import gzip
from core.settings import LOG_FILE
from sqlalchemy import func, text
import logging.handlers
import json
from types import SimpleNamespace
from typing import Dict, List, Optional
from core.logger import options_logger as logger
from core.multi_nut.target_scope import resolve_settings_target_id

logger.info("🛠️ Initializing options")


def _resolve_active_db():
    """Resolve SQLAlchemy handle bound to the active Flask app context."""
    if not has_app_context():
        return db

    try:
        extension = current_app.extensions.get('sqlalchemy')
    except Exception:
        return db

    if extension is None:
        return db

    if hasattr(extension, 'session') and hasattr(extension, 'Model'):
        return extension

    extension_db = getattr(extension, 'db', None)
    if extension_db is not None and hasattr(extension_db, 'session'):
        return extension_db

    return db


def _get_variable_config_model():
    """Resolve VariableConfig model at runtime (safe after lazy DB init)."""
    db_handle = _resolve_active_db()

    model_space = getattr(db_handle, 'ModelClasses', None)
    model_class = getattr(model_space, 'VariableConfig', None) if model_space else None
    if model_class is not None and hasattr(model_class, 'query'):
        return model_class

    try:
        from core.db import ups as ups_module

        model_class = getattr(ups_module, 'VariableConfig', None)
        if model_class is not None and hasattr(model_class, 'query'):
            return model_class
    except Exception:
        pass

    try:
        from core.db.models import init_models

        timezone_getter = None
        if has_app_context() and hasattr(current_app, 'CACHE_TIMEZONE'):
            timezone_getter = lambda: current_app.CACHE_TIMEZONE

        init_models(db_handle, timezone_getter)
        model_space = getattr(db_handle, 'ModelClasses', None)
        model_class = getattr(model_space, 'VariableConfig', None) if model_space else None
        if model_class is not None and hasattr(model_class, 'query'):
            return model_class
    except Exception as lazy_init_error:
        logger.debug(f"Lazy VariableConfig model initialization failed: {lazy_init_error}")

    return None


def _resolve_sqlite_db_path():
    """Return sqlite database path from Flask configuration."""
    try:
        db_uri = str(current_app.config.get('SQLALCHEMY_DATABASE_URI', '') or '')
    except Exception:
        db_uri = ''

    if db_uri.startswith('sqlite:///'):
        return db_uri.replace('sqlite:///', '', 1)
    return ''


def _get_variable_config_row_sqlite_fallback(resolved_target_id=None, include_global_fallback=True):
    """
    Fallback reader for VariableConfig rows when ORM/session binding is unavailable.

    Returns:
        tuple(row_namespace|None, scope_target_id|None)
    """
    db_path = _resolve_sqlite_db_path()
    if not db_path or not os.path.exists(db_path):
        return None, resolved_target_id

    try:
        with sqlite3.connect(db_path) as connection:
            connection.row_factory = sqlite3.Row

            def _fetchone(sql, params=()):
                return connection.execute(sql, params).fetchone()

            table_exists = _fetchone(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='ups_opt_variable_config'"
            )
            if table_exists is None:
                return None, resolved_target_id

            columns = connection.execute("PRAGMA table_info(ups_opt_variable_config)").fetchall()
            has_target_column = any(str(column['name']) == 'target_id' for column in columns)

            def _as_namespace(row):
                if row is None:
                    return None
                return SimpleNamespace(**{key: row[key] for key in row.keys()})

            if not has_target_column:
                row = _fetchone("SELECT * FROM ups_opt_variable_config ORDER BY id DESC LIMIT 1")
                return _as_namespace(row), resolved_target_id

            if resolved_target_id is None:
                primary_target = _fetchone(
                    """
                    SELECT id
                    FROM ups_monitor_targets
                    WHERE is_primary = 1
                    ORDER BY id ASC
                    LIMIT 1
                    """
                )
                if primary_target is not None:
                    primary_target_id = int(primary_target['id'])
                    row = _fetchone(
                        "SELECT * FROM ups_opt_variable_config WHERE target_id = ? ORDER BY id DESC LIMIT 1",
                        (primary_target_id,),
                    )
                    if row is not None:
                        return _as_namespace(row), primary_target_id

                any_scoped = _fetchone(
                    "SELECT * FROM ups_opt_variable_config WHERE target_id IS NOT NULL ORDER BY id DESC LIMIT 1"
                )
                if any_scoped is not None:
                    return _as_namespace(any_scoped), int(any_scoped['target_id'])

                if include_global_fallback:
                    global_row = _fetchone(
                        "SELECT * FROM ups_opt_variable_config WHERE target_id IS NULL ORDER BY id DESC LIMIT 1"
                    )
                    if global_row is not None:
                        return _as_namespace(global_row), None
                return None, None

            scoped_row = _fetchone(
                "SELECT * FROM ups_opt_variable_config WHERE target_id = ? ORDER BY id DESC LIMIT 1",
                (int(resolved_target_id),),
            )
            if scoped_row is not None:
                return _as_namespace(scoped_row), int(resolved_target_id)

            if not include_global_fallback:
                return None, int(resolved_target_id)

            any_scoped = _fetchone(
                "SELECT * FROM ups_opt_variable_config WHERE target_id IS NOT NULL ORDER BY id DESC LIMIT 1"
            )
            if any_scoped is not None:
                return _as_namespace(any_scoped), int(any_scoped['target_id'])

            global_row = _fetchone(
                "SELECT * FROM ups_opt_variable_config WHERE target_id IS NULL ORDER BY id DESC LIMIT 1"
            )
            if global_row is not None:
                return _as_namespace(global_row), int(resolved_target_id)

    except Exception as fallback_error:
        logger.error(f"SQLite fallback failed while resolving variable config row: {fallback_error}")

    return None, resolved_target_id

def get_database_stats():
    """Get database statistics and information"""
    try:
        db_path = current_app.config.get('SQLALCHEMY_DATABASE_URI', '').replace('sqlite:///', '')
        if not db_path or not os.path.exists(db_path):
            logger.error(f"Database file not found at {db_path}")
            return None

        stats = {
            'size': os.path.getsize(db_path),
            'total_records': 0,
            'last_write': None,
            'tables': {}
        }

        # Get tables information using SQLAlchemy
        for table in db.metadata.tables.values():
            table_name = table.name
            try:
                # Get record count
                count = db.session.query(table).count()
                
                # Get last write time (only if timestamp_utc column exists)
                last_write = None
                if hasattr(table.c, 'timestamp_utc'):
                    result = db.session.query(func.max(table.c.timestamp_utc)).scalar()
                    if result:
                        last_write = result.isoformat() if isinstance(result, datetime) else str(result)

                stats['tables'][table_name] = {
                    'record_count': count,
                    'last_write': last_write
                }
                
                stats['total_records'] += count
                
                # Update global last write if newer
                if last_write and (not stats['last_write'] or 
                    (isinstance(last_write, str) and (not stats['last_write'] or last_write > stats['last_write']))):
                    stats['last_write'] = last_write
                    
            except Exception as e:
                logger.error(f"Error getting stats for table {table_name}: {str(e)}")
                continue
                
        return stats
        
    except Exception as e:
        logger.error(f"Error getting database stats: {str(e)}")
        return None

def backup_database():
    """Create and return a backup of the database"""
    try:
        db_path = current_app.config['SQLALCHEMY_DATABASE_URI'].replace('sqlite:///', '')
        backup_dir = os.path.join(os.path.dirname(db_path), 'backups')
        os.makedirs(backup_dir, exist_ok=True)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_path = os.path.join(backup_dir, f'nutify_backup_{timestamp}.db')
        
        # Close all connections
        db.session.remove()
        db.engine.dispose()
        
        # Copy database file
        shutil.copy2(db_path, backup_path)
        
        return backup_path
        
    except Exception as e:
        logger.error(f"Error creating database backup: {str(e)}")
        return None

def optimize_database():
    """Optimize database tables"""
    try:
        db_path = current_app.config['SQLALCHEMY_DATABASE_URI'].replace('sqlite:///', '')
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("ANALYZE")
            cursor.execute("REINDEX")
        return True
    except Exception as e:
        logger.error(f"Error optimizing database: {str(e)}")
        return False

def vacuum_database():
    """Vacuum database to reclaim space"""
    try:
        db_path = current_app.config['SQLALCHEMY_DATABASE_URI'].replace('sqlite:///', '')
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("VACUUM")
        return True
    except Exception as e:
        logger.error(f"Error vacuuming database: {str(e)}")
        return False

def get_log_files(log_type='all', log_level='all', date_range='all') -> List[Dict]:
    """Get filtered log files"""
    try:
        # Get log directory from settings; if LOG_FILE is just a name without directory, use a fallback directory
        if LOG_FILE and os.path.dirname(LOG_FILE) != "":
            log_dir = os.path.dirname(LOG_FILE)
        else:
            log_dir = os.path.join(current_app.instance_path, 'logs')
        
        # Create logs directory if it doesn't exist
        os.makedirs(log_dir, exist_ok=True)
        
        if not os.path.exists(log_dir):
            return []
        
        # Create default log file if no logs exist
        if not os.listdir(log_dir):
            default_log = os.path.join(log_dir, 'system.log')
            with open(default_log, 'w') as f:
                f.write(f"Log file created on {datetime.now().isoformat()}\n")
        
        log_files = []
        
        # Define log file patterns
        patterns = {
            'all': r'.*\.log$',
            'system': r'system.*\.log$',
            'database': r'database.*\.log$',
            'ups': r'ups.*\.log$',
            'energy': r'energy.*\.log$',
            'web': r'web.*\.log$',
            'mail': r'mail.*\.log$',
            'options': r'options.*\.log$',
            'battery': r'battery.*\.log$',
            'upsmon': r'upsmon.*\.log$',
            'socket': r'socket.*\.log$',
            'voltage': r'voltage.*\.log$',
            'power': r'power.*\.log$'
        }
        
        pattern = patterns.get(log_type, patterns['all'])
        
        # Get all matching log files
        for file in os.listdir(log_dir):
            if re.match(pattern, file):
                file_path = os.path.join(log_dir, file)
                try:
                    with open(file_path, 'r') as f:
                        content = f.read()
                        
                    # Filter by log level if specified
                    if log_level != 'all':
                        level_pattern = f"\\b{log_level.upper()}\\b"
                        if not re.search(level_pattern, content, re.I):
                            continue
                            
                    file_stat = os.stat(file_path)
                    file_date = datetime.fromtimestamp(file_stat.st_mtime)
                    
                    # Apply date filter
                    if date_range != 'all':
                        now = datetime.now()
                        if date_range == 'today' and file_date.date() != now.date():
                            continue
                        elif date_range == 'week' and (now - file_date).days > 7:
                            continue
                        elif date_range == 'month' and (now - file_date).days > 30:
                            continue
                    
                    log_files.append({
                        'name': file,
                        'path': file_path,
                        'size': file_stat.st_size,
                        'modified': file_date.isoformat(),
                        'content': content
                    })
                except Exception as e:
                    logger.error(f"Error reading log file {file_path}: {str(e)}")
                    continue
        
        return log_files
        
    except Exception as e:
        logger.error(f"Error getting log files: {str(e)}")
        return []

def get_log_content(file_path, log_level='all'):
    """Get filtered content of a log file"""
    try:
        level_patterns = {
            'debug': r'DEBUG',
            'info': r'INFO',
            'warning': r'WARNING',
            'error': r'ERROR'
        }
        
        pattern = level_patterns.get(log_level, r'.*')
        
        content = []
        with open(file_path, 'r') as f:
            for line in f:
                if log_level == 'all' or re.search(pattern, line, re.I):
                    content.append(line.strip())
        
        return content
        
    except Exception as e:
        logger.error(f"Error reading log file: {str(e)}")
        return []

def download_logs(log_type='all', log_level='all', date_range='all'):
    """Create and return a zip file of filtered logs"""
    try:
        # Get log file metadata (without content)
        log_data = get_filtered_logs(
            log_type=log_type, 
            log_level=log_level, 
            date_range=date_range,
            return_metadata_only=True
        )
        
        if not log_data or not log_data['files']:
            return None
            
        # Create temporary zip file
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        zip_path = f'/tmp/logs_{timestamp}.zip'
        
        with gzip.open(zip_path, 'wb') as zf:
            for log_file in log_data['files']:
                file_path = log_file['path']
                try:
                    # Read the file content and filter by level if necessary
                    with open(file_path, 'r') as f:
                        content = f.read()
                        
                    # Filter by log level if specified
                    if log_level != 'all':
                        filtered_lines = []
                        for line in content.splitlines():
                            if re.search(f"\\b{log_level.upper()}\\b", line, re.I):
                                filtered_lines.append(line)
                        content = '\n'.join(filtered_lines)
                    
                    zf.write(content.encode())
                except Exception as e:
                    logger.error(f"Error adding log file {file_path} to zip: {str(e)}")
                    continue
        
        return zip_path
        
    except Exception as e:
        logger.error(f"Error creating log archive: {str(e)}")
        return None

def get_system_info():
    """Get system and project information"""
    try:
        # Read version information from version.txt file
        version_info = {
            'version': '0.0.1',  # Default value
            'last_update': 'Unknown',
            'status': 'Unknown',
            'changelog': 'Unknown'
        }
        
        try:
            version_file_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'version.txt')
            if os.path.exists(version_file_path):
                with open(version_file_path, 'r') as f:
                    lines = f.readlines()
                    i = 0
                    while i < len(lines):
                        line = lines[i].strip()
                        if '=' in line:
                            key, value = line.split('=', 1)
                            key = key.strip().lower()
                            value = value.strip()
                            
                            if key == 'version':
                                version_info['version'] = value
                            elif key == 'last_update':
                                version_info['last_update'] = value
                            elif key == 'status':
                                version_info['status'] = value
                            elif key == 'changelog' and value.startswith('"""'):
                                changelog = []
                                i += 1  # Skip the opening quotes line
                                while i < len(lines):
                                    if lines[i].strip().endswith('"""'):
                                        # Remove the closing quotes
                                        changelog.append(lines[i].strip()[:-3])
                                        break
                                    changelog.append(lines[i].rstrip())
                                    i += 1
                                version_info['changelog'] = '\n'.join(changelog)
                        i += 1
        except Exception as e:
            logger.error(f"Error reading version file: {str(e)}")
        
        info = {
            'version': version_info['version'],
            'last_update': version_info['last_update'],
            'status': version_info['status'],
            'changelog': version_info['changelog'],
            'python_version': os.sys.version,
            'platform': os.sys.platform,
            'database_version': sqlite3.sqlite_version,
            'timezone': current_app.CACHE_TIMEZONE.zone
        }
        return info
    except Exception as e:
        logger.error(f"Error getting system info: {str(e)}")
        return None

def get_filtered_logs(log_type: str = 'all', log_level: str = 'all', date_range: str = 'all', 
                     page: int = 1, page_size: int = 1000, return_metadata_only: bool = False) -> Dict:
    """
    Get filtered logs based on type, level and date range with pagination
    
    Args:
        log_type: Type of log to filter (all, system, database, etc.)
        log_level: Level of log to filter (all, debug, info, warning, error)
        date_range: Date range to filter (all, today, week, month)
        page: Page number (1-based)
        page_size: Number of lines per page
        return_metadata_only: If True, only return metadata without content
        
    Returns:
        Dictionary with metadata and log content
    """
    try:
        # Define log_dir based on LOG_FILE from settings; if LOG_FILE does not provide a directory, use the instance_path logs folder.
        if LOG_FILE and os.path.dirname(LOG_FILE) != "":
            log_dir = os.path.dirname(LOG_FILE)
        else:
            log_dir = os.path.join(current_app.instance_path, 'logs')
        
        if not os.path.exists(log_dir):
            return {"files": [], "total_files": 0, "total_size": 0, "lines": []}
            
        # Date range validation for LOG_FILE
        try:
            file_stat = os.stat(LOG_FILE)
            file_date = datetime.fromtimestamp(file_stat.st_mtime)
            
            if date_range != 'all':
                now = datetime.now()
                if date_range == 'today' and file_date.date() != now.date():
                    return {"files": [], "total_files": 0, "total_size": 0, "lines": []}
                elif date_range == 'week' and (now - file_date).days > 7:
                    return {"files": [], "total_files": 0, "total_size": 0, "lines": []}
                elif date_range == 'month' and (now - file_date).days > 30:
                    return {"files": [], "total_files": 0, "total_size": 0, "lines": []}
        except Exception as e:
            logger.error(f"Error getting log file date: {str(e)}")
 
        # File pattern matching
        patterns = {
            'all': r'.*\.log$',
            'system': r'system.*\.log$',
            'database': r'database.*\.log$',
            'ups': r'ups.*\.log$',
            'energy': r'energy.*\.log$',
            'web': r'web.*\.log$',
            'mail': r'mail.*\.log$',
            'options': r'options.*\.log$',
            'battery': r'battery.*\.log$',
            'upsmon': r'upsmon.*\.log$',
            'socket': r'socket.*\.log$',
            'voltage': r'voltage.*\.log$',
            'power': r'power.*\.log$'
        }
        pattern = patterns.get(log_type, patterns['all'])
 
        # Get matching log files metadata
        log_files = []
        total_size = 0
        
        for file in os.listdir(log_dir):
            if re.match(pattern, file):
                file_path = os.path.join(log_dir, file)
                try:
                    file_stat = os.stat(file_path)
                    file_date = datetime.fromtimestamp(file_stat.st_mtime)
                    
                    # Apply date filter for each file individually
                    if date_range != 'all':
                        now = datetime.now()
                        if date_range == 'today' and file_date.date() != now.date():
                            continue
                        elif date_range == 'week' and (now - file_date).days > 7:
                            continue
                        elif date_range == 'month' and (now - file_date).days > 30:
                            continue
                    
                    # Check if file contains the specified log level
                    if log_level != 'all':
                        # Use grep-like approach to check if file contains the log level
                        # without reading the entire file
                        level_found = False
                        with open(file_path, 'r') as f:
                            for i, line in enumerate(f):
                                if i > 1000:  # Check only first 1000 lines for performance
                                    break
                                if re.search(f"\\b{log_level.upper()}\\b", line, re.I):
                                    level_found = True
                                    break
                        if not level_found:
                            continue
                    
                    file_info = {
                        'name': file,
                        'path': file_path,
                        'size': file_stat.st_size,
                        'modified': file_date.isoformat(),
                    }
                    
                    log_files.append(file_info)
                    total_size += file_stat.st_size
                    
                except Exception as e:
                    logger.error(f"Error processing log file {file_path}: {str(e)}")
                    continue
        
        # Sort files by modification date (newest first)
        log_files.sort(key=lambda x: x['modified'], reverse=True)
        
        # If only metadata is requested, return it without content
        if return_metadata_only:
            return {
                "files": log_files,
                "total_files": len(log_files),
                "total_size": total_size,
                "lines": []
            }
        
        # Read content with pagination
        all_lines = []
        lines_read = 0
        start_line = (page - 1) * page_size
        end_line = start_line + page_size
        
        for file_info in log_files:
            if lines_read >= end_line:
                break
                
            file_path = file_info['path']
            try:
                file_lines = []
                with open(file_path, 'r') as f:
                    for line in f:
                        # Apply log level filter if specified
                        if log_level != 'all' and not re.search(f"\\b{log_level.upper()}\\b", line, re.I):
                            continue
                            
                        # Skip lines before start_line
                        if lines_read < start_line:
                            lines_read += 1
                            continue
                            
                        # Add line with metadata
                        line_data = {
                            'content': line.strip(),
                            'file': file_info['name'],
                            'line_number': lines_read + 1
                        }
                        
                        # Extract log level if present
                        level_match = re.search(r'\[(DEBUG|INFO|WARNING|ERROR)\]', line)
                        if level_match:
                            line_data['level'] = level_match.group(1)
                        
                        all_lines.append(line_data)
                        lines_read += 1
                        
                        # Stop if we've reached the page limit
                        if lines_read >= end_line:
                            break
            except Exception as e:
                logger.error(f"Error reading log file {file_path}: {str(e)}")
                continue
        
        return {
            "files": log_files,
            "total_files": len(log_files),
            "total_size": total_size,
            "lines": all_lines,
            "page": page,
            "page_size": page_size,
            "has_more": lines_read >= end_line
        }
        
    except Exception as e:
        logger.error(f"Error getting filtered logs: {str(e)}")
        return {"files": [], "total_files": 0, "total_size": 0, "lines": []}

def clear_logs(log_type: str) -> tuple[bool, str]:
    """Clear logs of specified type"""
    try:
        log_dir = os.path.dirname(LOG_FILE)
        files_deleted = 0
        for file in os.listdir(log_dir):
            # Check if file is a log and if it matches the type (or all logs)
            if file.endswith('.log') and (log_type == 'all' or file.startswith(log_type)):
                try:
                    log_file = os.path.join(log_dir, file)
                    # Retrieve log enabled flag from configuration
                    log_enabled = current_app.config.get("LOG_FILE_ENABLED", "true").lower() == "true"
                    if log_enabled:
                        try:
                            with open(log_file, "w") as f:
                                f.truncate(0)
                            message = "Logs cleared. Log file is ready to receive new logs."
                        except Exception as e:
                            logger.error(f"Error truncating log file: {str(e)}")
                            return False, str(e)
                    else:
                        try:
                            os.remove(log_file)
                            message = "Logs removed."
                        except Exception as e:
                            logger.error(f"Error removing log file: {str(e)}")
                            return False, str(e)
                    files_deleted += 1
                except Exception as e:
                    logger.error(f"Error deleting log file {file}: {str(e)}")
        # Create new empty log file for specific type if needed
        if log_type != 'all':
            default_log = os.path.join(log_dir, f'{log_type}.log')
            with open(default_log, 'w') as f:
                f.write(f"Log file created on {datetime.now().isoformat()}\n")
        return True, f"Cleared {files_deleted} log files"
    except Exception as e:
        logger.error(f"Error clearing logs: {str(e)}")
        return False, str(e) 

def get_variable_config_row(target_id=None, include_global_fallback=True):
    """
    Return the VariableConfig ORM row for the current target scope.

    Returns:
        tuple(config_row|None, resolved_target_id|None)
    """
    resolved_target_id = resolve_settings_target_id(target_id)

    try:
        variable_model = _get_variable_config_model()
        if variable_model is None:
            logger.error("VariableConfig model is unavailable while resolving variable config row")
            return None, resolved_target_id

        query = variable_model.query
        if not hasattr(variable_model, 'target_id'):
            return query.order_by(variable_model.id.desc()).first(), resolved_target_id

        if resolved_target_id is None:
            primary_target_id = None
            try:
                primary_row = db.session.execute(
                    text(
                        """
                        SELECT id
                        FROM ups_monitor_targets
                        WHERE is_primary = 1
                        ORDER BY id ASC
                        LIMIT 1
                        """
                    )
                ).fetchone()
                if primary_row is not None:
                    primary_target_id = int(primary_row[0])
            except Exception as primary_error:
                logger.debug(f"Could not resolve primary target for variable config scope: {primary_error}")

            if primary_target_id is not None:
                primary_scoped_row = (
                    query.filter(variable_model.target_id == int(primary_target_id))
                    .order_by(variable_model.id.desc())
                    .first()
                )
                if primary_scoped_row is not None:
                    return primary_scoped_row, primary_target_id

            any_scoped_row = (
                query.filter(variable_model.target_id.isnot(None))
                .order_by(variable_model.id.desc())
                .first()
            )
            if any_scoped_row is not None:
                return any_scoped_row, getattr(any_scoped_row, 'target_id', None)

            if include_global_fallback:
                legacy_global_row = (
                    query.filter(variable_model.target_id.is_(None))
                    .order_by(variable_model.id.desc())
                    .first()
                )
                return legacy_global_row, None
            return None, None

        scoped_row = (
            query.filter(variable_model.target_id == int(resolved_target_id))
            .order_by(variable_model.id.desc())
            .first()
        )
        if scoped_row or not include_global_fallback:
            return scoped_row, resolved_target_id

        any_scoped_row = (
            query.filter(variable_model.target_id.isnot(None))
            .order_by(variable_model.id.desc())
            .first()
        )
        if any_scoped_row is not None:
            return any_scoped_row, getattr(any_scoped_row, 'target_id', resolved_target_id)

        global_row = (
            variable_model.query.filter(variable_model.target_id.is_(None))
            .order_by(variable_model.id.desc())
            .first()
        )
        return global_row, resolved_target_id
    except Exception as e:
        logger.error(f"Error resolving variable config row: {str(e)}")
        fallback_row, fallback_scope = _get_variable_config_row_sqlite_fallback(
            resolved_target_id=resolved_target_id,
            include_global_fallback=include_global_fallback,
        )
        if fallback_row is not None:
            logger.warning("Using sqlite fallback for VariableConfig resolution")
            return fallback_row, fallback_scope
        return None, resolved_target_id


def _default_timezone_value():
    """Return best-effort default timezone value for variable options."""
    try:
        return str(getattr(current_app.CACHE_TIMEZONE, 'zone', 'UTC') or 'UTC')
    except Exception:
        return 'UTC'


def _normalize_nominal_power(value):
    """Normalize optional nominal power value."""
    try:
        parsed = int(value)
        if parsed <= 0:
            return None
        return parsed
    except (TypeError, ValueError):
        return None


def get_variable_config(target_id=None, include_global_fallback=True):
    """Return variable config payload for the current target scope."""
    defaults = {
        'timezone': _default_timezone_value(),
        'ups_realpower_nominal': None,
        'currency': 'EUR',
        'price_per_kwh': 0.25,
        'co2_factor': 0.4,
        'polling_interval': 1,
    }

    try:
        config, _resolved_target_id = get_variable_config_row(
            target_id=target_id,
            include_global_fallback=include_global_fallback,
        )
        if not config:
            logger.warning("No variable config found in database, returning default values")
            return defaults

        return {
            'timezone': str(getattr(config, 'timezone', None) or defaults['timezone']),
            'ups_realpower_nominal': _normalize_nominal_power(
                getattr(config, 'ups_realpower_nominal', None)
            ),
            'currency': config.currency,
            'price_per_kwh': float(config.price_per_kwh),
            'co2_factor': float(config.co2_factor),
            'polling_interval': int(config.polling_interval),
        }
    except Exception as e:
        logger.error(f"Error getting variable config: {str(e)}")
        return defaults
