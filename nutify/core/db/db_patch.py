"""Database schema patch helpers used during startup."""

import logging
from sqlalchemy import inspect, text
from flask import current_app
from sqlalchemy.exc import SQLAlchemyError
import pytz
from datetime import datetime

from core.logger import database_logger as logger

def get_application_timezone(db):
    """Return the application timezone from Flask runtime, with UTC fallback."""
    try:
        if current_app and hasattr(current_app, 'CACHE_TIMEZONE'):
            logger.info(f"🕒 Using application timezone from app.CACHE_TIMEZONE: {current_app.CACHE_TIMEZONE.zone}")
            return current_app.CACHE_TIMEZONE
        else:
            logger.error("❌ CACHE_TIMEZONE not available from Flask app! This should never happen.")
            return pytz.UTC
    except Exception as e:
        logger.error(f"❌ Error getting application timezone: {str(e)}")
        logger.warning("⚠️ Falling back to UTC timezone for conversion")
        return pytz.UTC

def check_timestamp_columns(db, app):
    """Ensure legacy timestamp_tz columns are converted to timestamp_utc."""
    logger.info("🔍 Checking timestamp columns in database tables...")
    
    app_timezone = get_application_timezone(db)
    
    tables_to_check = {
        'ups_dynamic_data': {'id_column': 'id', 'old_column': 'timestamp_tz', 'new_column': 'timestamp_utc'},
        'ups_static_data': {'id_column': 'id', 'old_column': 'timestamp_tz', 'new_column': 'timestamp_utc'},
        'ups_events': {'id_column': 'id', 'old_column': 'timestamp_tz', 'new_column': 'timestamp_utc'}
    }
    
    inspector = inspect(db.engine)
    existing_tables = inspector.get_table_names()
    all_correct = True
    
    for table_name, columns in tables_to_check.items():
        if table_name not in existing_tables:
            logger.info(f"Table {table_name} doesn't exist yet, skipping")
            continue
        
        table_columns = [c['name'] for c in inspector.get_columns(table_name)]
        
        old_column = columns['old_column']
        new_column = columns['new_column']
        
        if old_column in table_columns and new_column not in table_columns:
            logger.warning(f"⚠️ Table {table_name} has old column '{old_column}' instead of '{new_column}'")
            all_correct = False
            with app.app_context():
                convert_timestamp_column(db, table_name, old_column, new_column, columns['id_column'], app_timezone)
                
        elif old_column not in table_columns and new_column in table_columns:
            logger.info(f"✅ Table {table_name} has correct column '{new_column}'")
            
        elif old_column in table_columns and new_column in table_columns:
            logger.warning(f"⚠️ Table {table_name} has both '{old_column}' and '{new_column}' columns")
            all_correct = False
            with app.app_context():
                transfer_and_drop_column(db, table_name, old_column, new_column, columns['id_column'], app_timezone)
                
        elif old_column not in table_columns and new_column not in table_columns:
            logger.warning(f"⚠️ Table {table_name} doesn't have either '{old_column}' or '{new_column}'")
            all_correct = False
    
    return all_correct

def convert_timestamp_column(db, table_name, old_column, new_column, id_column, app_timezone):
    """Convert one timestamp column in place and rename it in SQLite."""
    logger.info(f"🔄 Converting column '{old_column}' to '{new_column}' in table '{table_name}'")
    
    try:
        with db.engine.connect() as conn:
            # Check if table is empty
            result = conn.execute(text(f"SELECT COUNT({id_column}) FROM {table_name}")).fetchone()
            total_rows = result[0] if result else 0
            
            if total_rows == 0:
                logger.info(f"📊 Table {table_name} is empty, performing simple column rename")
                conn.execute(text(f"ALTER TABLE {table_name} RENAME COLUMN {old_column} TO {new_column}"))
                conn.commit()
                logger.info(f"✅ Successfully renamed column in empty table {table_name}")
                return
            
            logger.info(f"📊 Processing {table_name} with {total_rows} rows")
            
            # Fetch all rows with non-NULL timestamps
            rows = conn.execute(text(f"SELECT {id_column}, {old_column} FROM {table_name} WHERE {old_column} IS NOT NULL")).fetchall()
            
            # Convert timestamps to UTC
            for row in rows:
                row_id, timestamp_str = row
                try:
                    # Parse the timestamp (assuming ISO 8601 format)
                    if timestamp_str:
                        # Handle possible formats
                        try:
                            # Try parsing with timezone info
                            dt = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                        except ValueError:
                            # Fallback to naive datetime in app timezone
                            dt = datetime.fromisoformat(timestamp_str)
                            dt = app_timezone.localize(dt)
                        
                        # Convert to UTC
                        dt_utc = dt.astimezone(pytz.UTC)
                        # Format as ISO 8601 without timezone (since SQLite doesn't store it)
                        utc_timestamp = dt_utc.strftime('%Y-%m-%d %H:%M:%S')
                        
                        # Update the row
                        conn.execute(
                            text(f"UPDATE {table_name} SET {old_column} = :utc_timestamp WHERE {id_column} = :row_id"),
                            {"utc_timestamp": utc_timestamp, "row_id": row_id}
                        )
                except ValueError as e:
                    logger.warning(f"⚠️ Invalid timestamp format in {table_name} (ID {row_id}): {timestamp_str}, skipping")
                    continue
            
            conn.commit()
            
            # Rename the column to timestamp_utc
            conn.execute(text(f"ALTER TABLE {table_name} RENAME COLUMN {old_column} TO {new_column}"))
            conn.commit()
            
        logger.info(f"✅ Successfully converted and renamed column in table {table_name}")
        
    except SQLAlchemyError as e:
        logger.error(f"❌ Error converting column in table {table_name}: {str(e)}")
        db.session.rollback()
        raise

def transfer_and_drop_column(db, table_name, old_column, new_column, id_column, app_timezone):
    """Move legacy timestamp data into the UTC column and remove old column."""
    logger.info(f"🔄 Transferring data from '{old_column}' to '{new_column}' in table '{table_name}'")
    
    try:
        with db.engine.connect() as conn:
            # Check if table is empty
            result = conn.execute(text(f"SELECT COUNT({id_column}) FROM {table_name}")).fetchone()
            total_rows = result[0] if result else 0
            
            if total_rows == 0:
                logger.info(f"📊 Table {table_name} is empty, dropping old column")
                conn.execute(text(f"ALTER TABLE {table_name} DROP COLUMN {old_column}"))
                conn.commit()
                logger.info(f"✅ Successfully dropped old column in empty table {table_name}")
                return
            
            logger.info(f"📊 Processing {table_name} with {total_rows} rows")
            
            # Fetch rows where old_column is not NULL and new_column needs updating
            rows = conn.execute(
                text(f"SELECT {id_column}, {old_column} FROM {table_name} WHERE {old_column} IS NOT NULL")
            ).fetchall()
            
            # Convert timestamps to UTC and update new_column
            for row in rows:
                row_id, timestamp_str = row
                try:
                    if timestamp_str:
                        # Parse the timestamp
                        try:
                            dt = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                        except ValueError:
                            dt = datetime.fromisoformat(timestamp_str)
                            dt = app_timezone.localize(dt)
                        
                        # Convert to UTC
                        dt_utc = dt.astimezone(pytz.UTC)
                        utc_timestamp = dt_utc.strftime('%Y-%m-%d %H:%M:%S')
                        
                        # Update new_column
                        conn.execute(
                            text(f"UPDATE {table_name} SET {new_column} = :utc_timestamp WHERE {id_column} = :row_id"),
                            {"utc_timestamp": utc_timestamp, "row_id": row_id}
                        )
                except ValueError as e:
                    logger.warning(f"⚠️ Invalid timestamp format in {table_name} (ID {row_id}): {timestamp_str}, skipping")
                    continue
            
            conn.commit()
            
            # Drop the old column
            # Note: SQLite doesn't support DROP COLUMN directly, so we need to recreate the table
            inspector = inspect(db.engine)
            columns = inspector.get_columns(table_name)
            new_columns = [c for c in columns if c['name'] != old_column]
            
            # Create a new table with all columns except old_column
            temp_table_name = f"{table_name}_temp"
            column_defs = []
            for col in new_columns:
                col_name = col['name']
                col_type = 'TEXT' if col_name in [new_column, old_column] else str(col['type']).upper()
                col_def = f"{col_name} {col_type}"
                if col_name == id_column:
                    col_def += " PRIMARY KEY"
                if not col.get('nullable', True):
                    col_def += " NOT NULL"
                column_defs.append(col_def)
            
            create_stmt = f"CREATE TABLE {temp_table_name} ({', '.join(column_defs)})"
            conn.execute(text(create_stmt))
            
            # Copy data to new table
            column_names = [c['name'] for c in new_columns]
            columns_sql = ', '.join(column_names)
            conn.execute(text(f"INSERT INTO {temp_table_name} ({columns_sql}) SELECT {columns_sql} FROM {table_name}"))
            
            # Drop original table and rename new table
            conn.execute(text(f"DROP TABLE {table_name}"))
            conn.execute(text(f"ALTER TABLE {temp_table_name} RENAME TO {table_name}"))
            
            conn.commit()
            
        logger.info(f"✅ Successfully transferred data and dropped old column in table {table_name}")
        
    except SQLAlchemyError as e:
        logger.error(f"❌ Error transferring data in table {table_name}: {str(e)}")
        db.session.rollback()
        # Clean up temp table if it exists
        try:
            with db.engine.connect() as conn:
                inspector = inspect(db.engine)
                if temp_table_name in inspector.get_table_names():
                    conn.execute(text(f"DROP TABLE {temp_table_name}"))
                    conn.commit()
        except:
            pass
        raise


def _get_index_definitions(conn, table_name):
    """Return index definitions for a SQLite table."""
    indexes = []
    try:
        index_rows = conn.execute(text(f"PRAGMA index_list('{table_name}')")).fetchall()
    except Exception:
        return indexes

    for row in index_rows:
        # SQLite tuple shape: (seq, name, unique, origin, partial)
        name = row[1]
        unique = bool(row[2])
        try:
            cols_rows = conn.execute(text(f"PRAGMA index_info('{name}')")).fetchall()
            columns = [col_row[2] for col_row in cols_rows]
        except Exception:
            columns = []
        indexes.append({
            'name': name,
            'unique': unique,
            'columns': columns,
        })
    return indexes


def _rebuild_notification_table_with_target_scope(conn):
    """
    Rebuild ups_opt_notification to replace legacy unique(event_type)
    with unique(target_id, event_type) in SQLite-safe way.
    """
    pragma_rows = conn.execute(text("PRAGMA table_info(ups_opt_notification)")).fetchall()
    existing_columns = {row[1] for row in pragma_rows}
    has_target_id = 'target_id' in existing_columns
    has_ntfy_enabled = 'ntfy_enabled' in existing_columns
    has_id_ntfy = 'id_ntfy' in existing_columns
    has_telegram_enabled = 'telegram_enabled' in existing_columns
    has_id_telegram = 'id_telegram' in existing_columns
    has_webhook_enabled = 'webhook_enabled' in existing_columns
    has_id_webhook = 'id_webhook' in existing_columns

    conn.execute(text("DROP TABLE IF EXISTS ups_opt_notification__migrating"))
    conn.execute(
        text(
            """
            CREATE TABLE ups_opt_notification__migrating (
                id INTEGER PRIMARY KEY,
                event_type VARCHAR(50) NOT NULL,
                enabled BOOLEAN,
                id_email INTEGER,
                ntfy_enabled BOOLEAN,
                id_ntfy INTEGER,
                telegram_enabled BOOLEAN,
                id_telegram INTEGER,
                webhook_enabled BOOLEAN,
                id_webhook INTEGER,
                created_at DATETIME,
                updated_at DATETIME,
                target_id INTEGER
            )
            """
        )
    )

    target_id_expr = "target_id" if has_target_id else "NULL"
    ntfy_enabled_expr = "ntfy_enabled" if has_ntfy_enabled else "0"
    id_ntfy_expr = "id_ntfy" if has_id_ntfy else "NULL"
    telegram_enabled_expr = "telegram_enabled" if has_telegram_enabled else "0"
    id_telegram_expr = "id_telegram" if has_id_telegram else "NULL"
    webhook_enabled_expr = "webhook_enabled" if has_webhook_enabled else "0"
    id_webhook_expr = "id_webhook" if has_id_webhook else "NULL"
    conn.execute(
        text(
            f"""
            INSERT INTO ups_opt_notification__migrating (
                id,
                event_type,
                enabled,
                id_email,
                ntfy_enabled,
                id_ntfy,
                telegram_enabled,
                id_telegram,
                webhook_enabled,
                id_webhook,
                created_at,
                updated_at,
                target_id
            )
            SELECT
                id,
                event_type,
                enabled,
                id_email,
                {ntfy_enabled_expr},
                {id_ntfy_expr},
                {telegram_enabled_expr},
                {id_telegram_expr},
                {webhook_enabled_expr},
                {id_webhook_expr},
                created_at,
                updated_at,
                {target_id_expr}
            FROM ups_opt_notification
            """
        )
    )

    conn.execute(text("DROP TABLE ups_opt_notification"))
    conn.execute(text("ALTER TABLE ups_opt_notification__migrating RENAME TO ups_opt_notification"))
    conn.execute(
        text(
            "CREATE INDEX IF NOT EXISTS idx_ups_opt_notification_target_id "
            "ON ups_opt_notification(target_id)"
        )
    )
    conn.execute(
        text(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_notification_target_event "
            "ON ups_opt_notification(target_id, event_type)"
        )
    )


def ensure_target_scope_schema(db):
    """Ensure target-scoped tables expose target_id and required indexes."""
    logger.info("🔍 Checking target scope schema (target_id columns/indexes)...")

    table_specs = {
        'ups_opt_notification': {
            'require_unique_target_event': True,
        },
        'ups_report_schedules': {},
        'ups_events': {},
        'ups_variables_upscmd': {},
        'ups_variables_upsrw': {},
    }

    try:
        inspector = inspect(db.engine)
        existing_tables = set(inspector.get_table_names())

        with db.engine.begin() as conn:
            for table_name, spec in table_specs.items():
                if table_name not in existing_tables:
                    logger.info(f"ℹ️ Skipping missing table: {table_name}")
                    continue

                table_columns = {column['name'] for column in inspector.get_columns(table_name)}
                if 'target_id' not in table_columns:
                    logger.warning(f"⚠️ Adding missing target_id column on {table_name}")
                    conn.execute(text(f"ALTER TABLE {table_name} ADD COLUMN target_id INTEGER"))

                conn.execute(
                    text(
                        f"CREATE INDEX IF NOT EXISTS idx_{table_name}_target_id "
                        f"ON {table_name}(target_id)"
                    )
                )

                if spec.get('require_unique_target_event'):
                    index_defs = _get_index_definitions(conn, table_name)
                    legacy_unique_indexes = [
                        index_def for index_def in index_defs
                        if index_def['unique'] and index_def['columns'] == ['event_type']
                    ]

                    if legacy_unique_indexes and any(
                        index_def['name'].startswith('sqlite_autoindex_')
                        for index_def in legacy_unique_indexes
                    ):
                        logger.warning(
                            "⚠️ Rebuilding ups_opt_notification to replace legacy unique(event_type) constraint"
                        )
                        _rebuild_notification_table_with_target_scope(conn)
                        continue

                    # Drop legacy unique(event_type) index if it exists.
                    for index_def in legacy_unique_indexes:
                        logger.warning(
                            f"⚠️ Dropping legacy unique index {index_def['name']} on {table_name}(event_type)"
                        )
                        conn.execute(text(f"DROP INDEX IF EXISTS {index_def['name']}"))

                    conn.execute(
                        text(
                            "CREATE UNIQUE INDEX IF NOT EXISTS uq_notification_target_event "
                            "ON ups_opt_notification(target_id, event_type)"
                        )
                    )

        logger.info("✅ Target scope schema check completed")
        return True
    except Exception as exc:
        logger.error(f"❌ Error while checking target scope schema: {exc}", exc_info=True)
        db.session.rollback()
        return False


def ensure_provider_render_mode_schema(db):
    """Ensure provider tables include a valid render_mode column."""
    logger.info("🔍 Checking provider render_mode schema...")
    provider_tables = (
        'ups_opt_mail_config',
        'ups_opt_ntfy',
        'ups_opt_telegram',
        'ups_opt_webhook',
    )

    try:
        inspector = inspect(db.engine)
        existing_tables = set(inspector.get_table_names())

        with db.engine.begin() as conn:
            for table_name in provider_tables:
                if table_name not in existing_tables:
                    logger.info(f"ℹ️ Skipping missing provider table: {table_name}")
                    continue

                table_info = conn.execute(text(f"PRAGMA table_info('{table_name}')")).fetchall()
                column_names = {row[1] for row in table_info}
                if 'render_mode' not in column_names:
                    logger.warning(f"⚠️ Adding missing render_mode column on {table_name}")
                    conn.execute(text(f"ALTER TABLE {table_name} ADD COLUMN render_mode VARCHAR(20)"))

                conn.execute(
                    text(
                        f"""
                        UPDATE {table_name}
                        SET render_mode = 'graphic'
                        WHERE render_mode IS NULL
                           OR TRIM(render_mode) = ''
                           OR LOWER(render_mode) NOT IN ('graphic', 'text')
                        """
                    )
                )

        logger.info("✅ Provider render_mode schema check completed")
        return True
    except Exception as exc:
        logger.error(f"❌ Error while checking provider render_mode schema: {exc}", exc_info=True)
        db.session.rollback()
        return False
