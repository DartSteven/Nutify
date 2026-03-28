"""
Database initialization module.
This module provides functions to initialize the database properly
using SQLAlchemy ORM.
"""

import logging
import os
from sqlalchemy import text, inspect
import time
from flask import current_app
import pytz

from .integrity import check_database_integrity
from .db_patch import ensure_provider_render_mode_schema
from core.logger import system_logger as logger
from core.db.model_classes import init_model_classes, register_models_for_global_access

def get_app_timezone():
    """
    Returns the application's CACHE_TIMEZONE.
    This is used for database models that need timezone information.
    Database always uses UTC, while display uses CACHE_TIMEZONE.
    
    Returns:
        timezone: The timezone object from current_app.CACHE_TIMEZONE
    """
    # For database operations, always use UTC
    import pytz
    return lambda: pytz.UTC


def _normalize_monitoring_profile(value):
    normalized = str(value or '').strip().lower()
    if normalized in {'single', 'multi'}:
        return normalized
    return 'single'


def _normalize_timezone(value, fallback='UTC'):
    candidate = str(value or '').strip()
    if not candidate:
        return fallback
    try:
        pytz.timezone(candidate)
        return candidate
    except Exception:
        return fallback


def _normalize_currency(value, fallback='EUR'):
    candidate = str(value or '').strip().upper()
    if len(candidate) == 3 and candidate.isalpha():
        return candidate
    return fallback


def _coerce_positive_int(value):
    try:
        parsed = int(value)
        if parsed > 0:
            return parsed
    except (TypeError, ValueError):
        pass
    return None


def _coerce_positive_float(value, fallback):
    try:
        parsed = float(value)
        if parsed >= 0:
            return parsed
    except (TypeError, ValueError):
        pass
    return float(fallback)


def _coerce_polling_interval(value, fallback=1):
    try:
        parsed = int(value)
        if parsed >= 1:
            return parsed
    except (TypeError, ValueError):
        pass
    return int(fallback)


def _infer_monitoring_profile(target_model):
    if target_model is None:
        return 'single'
    try:
        enabled = target_model.query.filter_by(enabled=True).count()
        if int(enabled or 0) > 1:
            return 'multi'
    except Exception:
        pass
    return 'single'


def _get_latest_row(model, *order_columns):
    if model is None:
        return None
    query = model.query
    if order_columns:
        query = query.order_by(*order_columns)
    return query.first()


def _notification_event_types():
    """Return canonical notification event names."""
    try:
        from core.mail.mail import EmailNotifier

        events = [str(item).strip().upper() for item in EmailNotifier.EVENT_TYPES if str(item).strip()]
        if events:
            return sorted(set(events))
    except Exception as exc:
        logger.debug(f"Could not load notification event map from mail module: {exc}")

    return [
        'ONLINE',
        'ONBATT',
        'LOWBATT',
        'COMMOK',
        'COMMBAD',
        'SHUTDOWN',
        'REPLBATT',
        'NOCOMM',
        'NOPARENT',
    ]


def synchronize_master_control_and_variable_scopes(db):
    """
    Normalize instance metadata and variable rows:
    - nutify_master_control becomes canonical instance metadata storage
    - ups_opt_variable_config keeps one row per target_id (no global NULL scope rows)
    """
    if not hasattr(db, 'ModelClasses'):
        return

    model_space = db.ModelClasses
    MasterControl = getattr(model_space, 'MasterControl', None)
    VariableConfig = getattr(model_space, 'VariableConfig', None)
    NotificationSettings = getattr(model_space, 'NotificationSettings', None)
    UPSMonitorTarget = getattr(model_space, 'UPSMonitorTarget', None)
    if MasterControl is None or VariableConfig is None or UPSMonitorTarget is None:
        logger.warning("⚠️ Skipping master-control synchronization (required models not available)")
        return

    session = db.session

    legacy_row = None
    try:
        inspector = inspect(db.engine)
        if 'ups_initial_setup' in set(inspector.get_table_names()):
            with db.engine.connect() as conn:
                raw_row = conn.execute(
                    text(
                        "SELECT server_name, timezone, is_configured, monitoring_profile, ups_realpower_nominal "
                        "FROM ups_initial_setup ORDER BY id DESC LIMIT 1"
                    )
                ).fetchone()
                if raw_row:
                    legacy_row = dict(raw_row._mapping)
    except Exception as legacy_error:
        logger.debug(f"Legacy initial-setup row unavailable during sync: {legacy_error}")

    master_row = _get_latest_row(MasterControl, MasterControl.updated_at.desc(), MasterControl.id.desc())
    if master_row is None:
        master_row = MasterControl()
        session.add(master_row)

    targets = UPSMonitorTarget.query.order_by(UPSMonitorTarget.is_primary.desc(), UPSMonitorTarget.id.asc()).all()
    target_ids = [int(target.id) for target in targets if getattr(target, 'id', None) is not None]

    inferred_profile = _infer_monitoring_profile(UPSMonitorTarget)
    master_profile = _normalize_monitoring_profile(
        getattr(master_row, 'monitoring_profile', None)
        or (legacy_row.get('monitoring_profile') if legacy_row else None)
        or inferred_profile
    )
    server_name = str(
        getattr(master_row, 'server_name', None)
        or (legacy_row.get('server_name') if legacy_row else None)
        or 'Nutify'
    ).strip() or 'Nutify'
    is_configured = bool(
        getattr(master_row, 'is_configured', False)
        or (legacy_row.get('is_configured', False) if legacy_row else False)
        or bool(target_ids)
    )

    master_row.server_name = server_name
    master_row.monitoring_profile = master_profile
    master_row.is_configured = is_configured

    global_row = None
    if hasattr(VariableConfig, 'target_id'):
        global_row = (
            VariableConfig.query
            .filter(VariableConfig.target_id.is_(None))
            .order_by(VariableConfig.id.desc())
            .first()
        )

    default_timezone = _normalize_timezone(
        getattr(global_row, 'timezone', None)
        or (legacy_row.get('timezone') if legacy_row else None)
        or 'UTC',
        fallback='UTC',
    )
    default_currency = _normalize_currency(
        getattr(global_row, 'currency', None) or 'EUR',
        fallback='EUR',
    )
    default_nominal = _coerce_positive_int(
        getattr(global_row, 'ups_realpower_nominal', None)
        or (legacy_row.get('ups_realpower_nominal') if legacy_row else None)
    )
    default_price = _coerce_positive_float(getattr(global_row, 'price_per_kwh', None), 0.25)
    default_co2 = _coerce_positive_float(getattr(global_row, 'co2_factor', None), 0.4)
    default_polling = _coerce_polling_interval(getattr(global_row, 'polling_interval', None), 1)

    for target in targets:
        target_id = int(target.id)
        scoped_rows = (
            VariableConfig.query
            .filter(VariableConfig.target_id == target_id)
            .order_by(VariableConfig.updated_at.desc(), VariableConfig.id.desc())
            .all()
        )
        scoped_row = scoped_rows[0] if scoped_rows else None
        duplicates = scoped_rows[1:] if len(scoped_rows) > 1 else []

        if scoped_row is None:
            scoped_row = VariableConfig()
            scoped_row.target_id = target_id
            session.add(scoped_row)

        scoped_row.timezone = _normalize_timezone(getattr(scoped_row, 'timezone', None), fallback=default_timezone)
        scoped_row.currency = _normalize_currency(getattr(scoped_row, 'currency', None), fallback=default_currency)
        scoped_row.price_per_kwh = _coerce_positive_float(getattr(scoped_row, 'price_per_kwh', None), default_price)
        scoped_row.co2_factor = _coerce_positive_float(getattr(scoped_row, 'co2_factor', None), default_co2)
        scoped_row.polling_interval = _coerce_polling_interval(getattr(scoped_row, 'polling_interval', None), default_polling)
        if _coerce_positive_int(getattr(scoped_row, 'ups_realpower_nominal', None)) is None:
            scoped_row.ups_realpower_nominal = default_nominal

        for duplicate in duplicates:
            session.delete(duplicate)

    if hasattr(VariableConfig, 'target_id'):
        orphan_rows = VariableConfig.query.filter(VariableConfig.target_id.isnot(None)).all()
        valid_target_ids = set(target_ids)
        for row in orphan_rows:
            if int(row.target_id) not in valid_target_ids:
                session.delete(row)

        global_rows = VariableConfig.query.filter(VariableConfig.target_id.is_(None)).all()
        for row in global_rows:
            session.delete(row)

    # Normalize notification rows:
    # - multi profile: strictly target-scoped rows, no NULL scope records
    # - single profile: keep NULL scope records as canonical
    if NotificationSettings is not None and hasattr(NotificationSettings, 'target_id'):
        notification_events = _notification_event_types()
        valid_target_ids = set(target_ids)

        def _collect_rows_for_scope(scope_target_id):
            query = NotificationSettings.query
            if scope_target_id is None:
                query = query.filter(NotificationSettings.target_id.is_(None))
            else:
                query = query.filter(NotificationSettings.target_id == int(scope_target_id))
            return query.order_by(NotificationSettings.updated_at.desc(), NotificationSettings.id.desc()).all()

        if master_profile == 'multi':
            for target_id in target_ids:
                rows = _collect_rows_for_scope(target_id)
                by_event = {}
                duplicates = []
                for row in rows:
                    event_type = str(getattr(row, 'event_type', '') or '').strip().upper()
                    if not event_type:
                        duplicates.append(row)
                        continue
                    if event_type in by_event:
                        duplicates.append(row)
                        continue
                    by_event[event_type] = row

                for event_type in notification_events:
                    if event_type in by_event:
                        continue
                    session.add(
                        NotificationSettings(
                            target_id=int(target_id),
                            event_type=event_type,
                            enabled=False,
                        )
                    )

                for duplicate in duplicates:
                    session.delete(duplicate)

            orphan_rows = NotificationSettings.query.filter(NotificationSettings.target_id.isnot(None)).all()
            for row in orphan_rows:
                if int(row.target_id) not in valid_target_ids:
                    session.delete(row)

            global_rows = NotificationSettings.query.filter(NotificationSettings.target_id.is_(None)).all()
            for row in global_rows:
                session.delete(row)
        else:
            rows = _collect_rows_for_scope(None)
            by_event = {}
            duplicates = []
            for row in rows:
                event_type = str(getattr(row, 'event_type', '') or '').strip().upper()
                if not event_type:
                    duplicates.append(row)
                    continue
                if event_type in by_event:
                    duplicates.append(row)
                    continue
                by_event[event_type] = row

            for event_type in notification_events:
                if event_type in by_event:
                    continue
                session.add(
                    NotificationSettings(
                        target_id=None,
                        event_type=event_type,
                        enabled=False,
                    )
                )

            for duplicate in duplicates:
                session.delete(duplicate)

    session.commit()
    logger.info(
        "✅ Master-control sync complete: server_name=%s profile=%s targets=%s",
        server_name,
        master_profile,
        len(target_ids),
    )

def init_database(app, db):
    """
    Initialize the database with all tables using ORM.
    
    Args:
        app: Flask application instance
        db: SQLAlchemy database instance
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Initialize the models
        from .models import init_models
        
        # Clear separator for major initialization steps
        logger.info("=" * 50)
        logger.info("📚 DATABASE INITIALIZATION SEQUENCE START")
        logger.info("=" * 50)
        
        # Step 1: Initialize ORM models
        logger.info("📦 Step 1: Initializing ORM models...")
        models_dict = init_models(db, get_app_timezone())
        
        # Explicitly attach models to db.ModelClasses namespace for global access
        if not hasattr(db, 'ModelClasses'):
            # Use the ModelClasses module to create a proper ModelClasses instance
            model_classes = init_model_classes(db, get_app_timezone())
            db.ModelClasses = model_classes
            logger.info("✅ Models attached to db.ModelClasses namespace")
            
        logger.info("✅ ORM models initialized successfully")

        # Step 2: Create all ORM tables.
        logger.info("🏗️ Step 2: Creating ORM tables...")
        db.create_all()
        logger.info("✅ All tables created successfully")

        # Step 3: Drop legacy single-table artifacts if present.
        logger.info("🧹 Step 3: Removing legacy UPS single-monitor tables if present...")
        inspector = inspect(db.engine)
        existing_tables = set(inspector.get_table_names())
        with db.engine.begin() as conn:
            if 'ups_static_data' in existing_tables:
                conn.execute(text("DROP TABLE ups_static_data"))
                logger.info("✅ Dropped legacy table: ups_static_data")
            if 'ups_dynamic_data' in existing_tables:
                conn.execute(text("DROP TABLE ups_dynamic_data"))
                logger.info("✅ Dropped legacy table: ups_dynamic_data")

        # Step 4: Register models in UPS module to ensure they're available globally
        logger.info("🔗 Step 4: Registering models globally...")
        from core.db.ups import register_models_from_modelclasses
        register_models_from_modelclasses(db.ModelClasses)
        logger.info("✅ Models registered globally")

        # Step 4.5: Ensure provider render-mode schema is in place before integrity checks
        logger.info("🧩 Step 4.5: Ensuring provider render-mode schema...")
        try:
            ensure_provider_render_mode_schema(db)
            logger.info("✅ Provider render-mode schema ready")
        except Exception as provider_schema_error:
            logger.warning(
                f"⚠️ Provider render-mode schema pre-check failed: {provider_schema_error}"
            )

        # Step 5: Check database integrity
        logger.info("=" * 50)
        logger.info("🔍 Step 5: CHECKING DATABASE INTEGRITY")
        logger.info("=" * 50)
        
        integrity_results = check_database_integrity(db)
        logger.info("✅ Database integrity check completed")
        
        # Step 6: Initialize default configurations and settings
        logger.info("🔧 Step 6: Initializing default configurations...")
        
        # Initialize variable configuration
        try:
            # Ensure ModelClasses is attached to db
            if hasattr(db, 'ModelClasses'):
                # Initialize VariableConfig defaults if available
                if hasattr(db.ModelClasses, 'VariableConfig'):
                    try:
                        db.ModelClasses.VariableConfig.init_default_config()
                        logger.info("✅ Default variable configuration initialized")
                    except Exception as ve:
                        logger.warning(f"⚠️ Error initializing variable configuration: {str(ve)}")
                else:
                    logger.warning("⚠️ VariableConfig model not available, skipping default config initialization")
                
                # Initialize notification settings if available
                if hasattr(db.ModelClasses, 'NotificationSettings'):
                    try:
                        db.ModelClasses.NotificationSettings.init_notification_settings()
                        logger.info("✅ Default notification settings initialized")
                    except Exception as ne:
                        logger.warning(f"⚠️ Error initializing notification settings: {str(ne)}")
                else:
                    logger.warning("⚠️ NotificationSettings model not available, skipping notification settings initialization")
                
                # Update global settings from database
                try:
                    from core.settings import get_server_name
                    server_name = get_server_name()
                    logger.info(f"✅ Global server_name updated to: {server_name}")
                except Exception as se:
                    logger.warning(f"⚠️ Error updating global server_name: {str(se)}")
            else:
                logger.warning("⚠️ ModelClasses namespace not available on db, skipping default configuration initialization")
                
        except Exception as e:
            logger.warning(f"⚠️ Error initializing default configurations: {str(e)}")

        # Step 7: Ensure Multi-NUT primary target exists
        logger.info("🔧 Step 7: Initializing Multi-NUT target registry...")
        try:
            from core.multi_nut.storage import bootstrap_primary_target

            bootstrap_result = bootstrap_primary_target()
            if bootstrap_result.get('created'):
                logger.info("✅ Multi-NUT primary target created from current NUT configuration")
            else:
                logger.info("✅ Multi-NUT target registry already initialized")
        except Exception as e:
            logger.warning(f"⚠️ Error initializing Multi-NUT target registry: {str(e)}")

        # Step 8: Normalize master-control and target-scoped variable rows
        logger.info("🔧 Step 8: Synchronizing master-control and variable target scope...")
        try:
            synchronize_master_control_and_variable_scopes(db)
        except Exception as sync_error:
            logger.warning(f"⚠️ Error synchronizing master-control data: {sync_error}")
        
        # Final success message
        logger.info("=" * 50)
        logger.info("✅ DATABASE INITIALIZATION COMPLETE")
        logger.info("=" * 50)
        
        return True
    
    except Exception as e:
        logger.error(f"❌ Database initialization error: {str(e)}")
        return False 
