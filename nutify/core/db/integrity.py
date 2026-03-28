"""
Database integrity check module.
This module verifies database tables integrity using ORM models.
"""

import logging
import os
import time
import sqlite3
from sqlalchemy import inspect, MetaData, Table, text
from sqlalchemy.exc import SQLAlchemyError, OperationalError, ProgrammingError
import traceback

from core.logger import database_logger as logger


def _is_missing_column_error(exc):
    """Return True when SQLAlchemy/SQLite error indicates a missing column."""
    text_error = str(exc or '').lower()
    return 'no such column' in text_error

def check_encryption_integrity(db, table_name, model, instance=None):
    """
    Verifies encryption integrity for tables with encrypted fields.
    Checks if decryption with current SECRET_KEY is possible.
    
    Args:
        db: SQLAlchemy database instance
        table_name: Name of the table to check
        model: ORM model class
        instance: Optional specific instance to check
        
    Returns:
        tuple: (bool, str) - (is_encryption_valid, error_message)
    """
    # Check if table exists first
    inspector = inspect(db.engine)
    if table_name not in inspector.get_table_names():
        return True, None  # Table doesn't exist yet, so no encryption issues
    
    try:
        # Define fields to check for each model type
        encryption_checks = {
            'ups_opt_mail_config': lambda obj: obj.password,
            'ups_opt_ntfy': lambda obj: obj.topic or obj.username or obj.password,
            'ups_opt_telegram': lambda obj: obj.bot_token or obj.chat_id,
            'ups_opt_webhook': lambda obj: obj.url or obj.auth_token or obj.auth_username or obj.auth_password
        }
        
        # Skip if table isn't one we need to check
        if table_name not in encryption_checks:
            return True, None
        
        logger.info(f"🔐 Checking encryption integrity for {table_name}...")
        
        # Get an instance to test
        if instance is None:
            # Query the first record from the table
            instance = db.session.query(model).first()
        
        # If no records exist, encryption is valid (nothing to check)
        if instance is None:
            logger.info(f"ℹ️ No records in {table_name} to check encryption")
            return True, None
        
        # Attempt to decrypt a field
        check_func = encryption_checks[table_name]
        value = check_func(instance)
        
        # If value is None but not because of decryption failure, it's valid
        logger.debug(f"🔑 Encryption check for {table_name}: {'OK' if value is not None else 'NULL'}")
        
        # Check if any encrypted fields exist but could not be decrypted
        # This relies on the models properly handling decryption failures by returning None
        # and logging the appropriate error messages
        if value is None:
            # Check if there was actually encrypted data that failed to decrypt
            # We only consider it a failure if there was data to decrypt but it failed
            # Note: The model's decryption methods already log detailed error messages
            
            # Get the encrypted column names based on table
            encrypted_columns = {
                'ups_opt_mail_config': ['_password'],
                'ups_opt_ntfy': ['_topic', '_username', '_password'],
                'ups_opt_telegram': ['_bot_token', '_chat_id'],
                'ups_opt_webhook': ['_url', '_auth_username', '_auth_password', '_auth_token']
            }.get(table_name, [])
            
            # Check if any encrypted columns have data but decryption failed
            has_encrypted_data = False
            for column_name in encrypted_columns:
                if hasattr(instance, column_name) and getattr(instance, column_name) is not None:
                    has_encrypted_data = True
                    break
            
            if has_encrypted_data:
                error_msg = f"❌ Encryption integrity check failed for {table_name}. SECRET_KEY mismatch detected."
                logger.error(error_msg)
                return False, error_msg
        
        return True, None
    
    except (OperationalError, ProgrammingError) as e:
        # Schema drift (e.g. new ORM column not migrated yet) must not be treated as
        # encryption corruption, otherwise integrity flow can drop/recreate the table.
        if _is_missing_column_error(e):
            logger.warning(
                "⚠️ Skipping encryption check for %s because schema migration is pending: %s",
                table_name,
                str(e),
            )
            return True, None

        error_msg = f"❌ Error checking encryption for {table_name}: {str(e)}"
        logger.error(error_msg)
        logger.error(traceback.format_exc())
        return False, error_msg
    except Exception as e:
        error_msg = f"❌ Error checking encryption for {table_name}: {str(e)}"
        logger.error(error_msg)
        logger.error(traceback.format_exc())
        return False, error_msg

def check_database_integrity(db):
    """
    Verifies database integrity using SQLAlchemy ORM.
    Compares actual database tables schema with ORM models.
    If schema mismatch is detected, drops and recreates the table.
    Also checks encryption integrity for tables with encrypted fields.
    
    Args:
        db: SQLAlchemy database instance
        
    Returns:
        dict: Dictionary with tables checked and their status
    """
    # Protected tables that should never be verified or modified
    # These tables are managed directly by core/db_module.py
    PROTECTED_TABLES = ['ups_static_data', 'ups_dynamic_data']
    
    logger.info("🔍 Starting database integrity check...")
    results = {}
    
    try:
        # Get all existing tables in the database
        inspector = inspect(db.engine)
        existing_tables = set(inspector.get_table_names())
        logger.info(f"📊 Found {len(existing_tables)} existing tables in database")
        
        # Using ORM-based table creation
        logger.info("ℹ️ Using ORM for table integrity")
        
        # Log the start of integrity check
        logger.info("==================================================")
        logger.info("📊 Integrity check using ORM-based approach")
        logger.info("==================================================")
        
        # Get all SQLAlchemy models from the ModelClasses object
        if hasattr(db, 'ModelClasses'):
            models = {}
            for attr_name in dir(db.ModelClasses):
                attr = getattr(db.ModelClasses, attr_name)
                if hasattr(attr, '__tablename__') and not attr_name.startswith('_'):
                    models[attr.__tablename__] = attr
            
            logger.info(f"Found {len(models)} models to check")
            
            # Check each table against its model
            for table_name, model in models.items():
                # Skip protected tables
                if table_name in PROTECTED_TABLES:
                    results[table_name] = "PROTECTED"
                    logger.info(f"🛡️ Table {table_name} is protected, skipping")
                    continue
                
                try:
                    # Check if table exists in database
                    if table_name in existing_tables:
                        # First check encryption integrity for tables with encrypted fields
                        encryption_valid, error_msg = check_encryption_integrity(db, table_name, model)
                        
                        if not encryption_valid:
                            logger.warning(f"⚠️ Encryption integrity failure detected for table {table_name}")
                            logger.warning(f"🔄 Dropping and recreating table {table_name}")
                            
                            # Force close all SQLAlchemy sessions and connections
                            try:
                                db.session.remove()
                            except:
                                pass
                            
                            # If the mail config table has encryption issues, we also need to 
                            # drop and recreate related tables due to dependency (ups_report_schedules and ups_opt_notification)
                            related_tables_to_reset = []
                            if table_name == 'ups_opt_mail_config':
                                logger.warning(f"⚠️ Mail config encryption issues detected. Will also drop related tables for data consistency")
                                related_tables_to_reset = ['ups_report_schedules', 'ups_opt_notification']
                                
                                # Drop related tables first
                                for related_table in related_tables_to_reset:
                                    if related_table in existing_tables and related_table in models:
                                        logger.warning(f"🔄 Dropping related table {related_table} due to mail config encryption issues")
                                        if force_drop_table(db, related_table):
                                            # Wait a moment
                                            time.sleep(0.5)
                                            try:
                                                # Recreate table
                                                related_model = models[related_table]
                                                related_model.__table__.create(db.engine)
                                                results[related_table] = "RECREATED_DEPENDENCY"
                                                logger.info(f"✅ Related table {related_table} recreated successfully")
                                            except Exception as e:
                                                error_msg = f"❌ Error recreating related table {related_table}: {str(e)}"
                                                logger.error(error_msg)
                                                results[related_table] = "ERROR: " + error_msg
                                        else:
                                            error_msg = f"❌ Failed to drop related table {related_table}"
                                            logger.error(error_msg)
                                            results[related_table] = "ERROR: " + error_msg
                            
                            # Force drop the table using direct SQLite connection
                            if force_drop_table(db, table_name):
                                # Wait a moment to ensure the database releases locks
                                time.sleep(0.5)
                                
                                try:
                                    # Now recreate the table using the model definition
                                    model.__table__.create(db.engine)
                                    results[table_name] = "RECREATED_ENCRYPTION"
                                    logger.info(f"✅ Table {table_name} recreated successfully due to encryption issues")
                                except OperationalError as oe:
                                    error_msg = f"❌ SQLAlchemy operational error recreating table {table_name}: {str(oe)}"
                                    logger.error(error_msg)
                                    results[table_name] = "ERROR: " + error_msg
                                except Exception as e:
                                    error_msg = f"❌ Error recreating table {table_name}: {str(e)}"
                                    logger.error(error_msg)
                                    logger.error(traceback.format_exc())
                                    results[table_name] = "ERROR: " + error_msg
                            else:
                                error_msg = f"❌ Failed to drop table {table_name}"
                                logger.error(error_msg)
                                results[table_name] = "ERROR: " + error_msg
                                
                            # Skip further checks for this table since we've already recreated it
                            continue
                        
                        # Get database columns
                        db_columns = {c['name']: c for c in inspector.get_columns(table_name)}
                        
                        # Get model columns
                        model_columns = {c.name: c for c in model.__table__.columns}
                        
                        logger.debug(f"Checking table {table_name}: DB has {len(db_columns)} columns, Model has {len(model_columns)} columns")
                        
                        # Check for schema mismatches
                        mismatch = False
                        
                        # 1. Check for missing columns
                        missing_columns = set(model_columns.keys()) - set(db_columns.keys())
                        if missing_columns:
                            logger.warning(f"❌ Table {table_name} is missing columns: {missing_columns}")
                            mismatch = True
                        
                        # 2. Check for column type mismatches
                        # This is more complex as SQLAlchemy types may not match DB types exactly
                        # We'll do a basic string comparison of the type names
                        for col_name, model_col in model_columns.items():
                            # Skip columns that don't exist in DB
                            if col_name in db_columns:
                                db_col = db_columns[col_name]
                                
                                # Get type name from model
                                model_type = str(model_col.type)
                                
                                # Get type name from database
                                db_type = db_col['type']
                                
                                # Compare type definitions (basic comparison)
                                # Note: This is not perfect as SQLAlchemy types might be represented
                                # differently in different databases, but should catch major differences
                                if not model_type.lower().startswith(str(db_type).lower()):
                                    logger.warning(f"❌ Column {table_name}.{col_name} type mismatch: DB={db_type}, Model={model_type}")
                                    mismatch = True
                        
                        if mismatch:
                            logger.warning(f"⚠️ Schema mismatch detected for table {table_name}")
                            logger.warning(f"🔄 Dropping and recreating table {table_name}")
                            
                            # Force close all SQLAlchemy sessions and connections
                            try:
                                db.session.remove()
                            except:
                                pass
                            
                            # Force drop the table using direct SQLite connection
                            if force_drop_table(db, table_name):
                                # Wait a moment to ensure the database releases locks
                                time.sleep(0.5)
                                
                                try:
                                    # Now recreate the table using the model definition
                                    model.__table__.create(db.engine)
                                    results[table_name] = "RECREATED"
                                    logger.info(f"✅ Table {table_name} recreated successfully")
                                except OperationalError as oe:
                                    error_msg = f"❌ SQLAlchemy operational error recreating table {table_name}: {str(oe)}"
                                    logger.error(error_msg)
                                    results[table_name] = "ERROR: " + error_msg
                                except ProgrammingError as pe:
                                    error_msg = f"❌ SQLAlchemy programming error creating table {table_name}: {str(pe)}"
                                    logger.error(error_msg)
                                    results[table_name] = "ERROR: " + error_msg
                                except Exception as e:
                                    error_msg = f"❌ Error recreating table {table_name}: {str(e)}"
                                    logger.error(error_msg)
                                    logger.error(traceback.format_exc())
                                    results[table_name] = "ERROR: " + error_msg
                            else:
                                error_msg = f"❌ Failed to drop table {table_name}"
                                logger.error(error_msg)
                                results[table_name] = "ERROR: " + error_msg
                        else:
                            results[table_name] = "OK"
                            logger.info(f"✅ Table {table_name} schema matches ORM model")
                    else:
                        # Table doesn't exist, create it
                        try:
                            logger.info(f"🆕 Creating table {table_name} which doesn't exist")
                            model.__table__.create(db.engine)
                            results[table_name] = "CREATED"
                            logger.info(f"✅ Table {table_name} created")
                        except OperationalError as oe:
                            error_msg = f"❌ SQLAlchemy operational error creating table {table_name}: {str(oe)}"
                            logger.error(error_msg)
                            results[table_name] = "ERROR: " + error_msg
                        except ProgrammingError as pe:
                            error_msg = f"❌ SQLAlchemy programming error creating table {table_name}: {str(pe)}"
                            logger.error(error_msg)
                            results[table_name] = "ERROR: " + error_msg
                        except Exception as e:
                            error_msg = f"❌ Error creating table {table_name}: {str(e)}"
                            logger.error(error_msg)
                            logger.error(traceback.format_exc())
                            results[table_name] = "ERROR: " + error_msg
                except Exception as e:
                    error_msg = f"❌ Error checking table {table_name}: {str(e)}"
                    logger.error(error_msg)
                    logger.error(traceback.format_exc())
                    results[table_name] = "ERROR: " + error_msg
        else:
            logger.warning("⚠️ db.ModelClasses not available, skipping schema verification")
            
            # Mark tables as ORM managed except protected ones (original behavior)
            for table in existing_tables:
                if table not in PROTECTED_TABLES:
                    results[table] = "ORM_MANAGED"
        
        logger.info("==================================================")
        logger.info("📊 Integrity check complete")
        logger.info("==================================================")
        
    except Exception as e:
        error_msg = f"❌ Error during integrity check: {str(e)}"
        logger.error(error_msg)
        logger.error(traceback.format_exc())
        
    return results

def force_drop_table(db, table_name):
    """
    Force drop a table using direct SQLite connection to bypass any SQLAlchemy transaction issues.
    
    Args:
        db: SQLAlchemy database instance
        table_name: Name of the table to drop
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Safety check for protected tables
        PROTECTED_TABLES = ['ups_dynamic_data']
        if table_name in PROTECTED_TABLES:
            logger.warning(f"🔒 Cannot drop protected table {table_name}")
            return False
        
        # Get database path from SQLAlchemy engine
        db_path = db.engine.url.database
        
        if db_path:
            logger.info(f"🗑️ Force dropping table {table_name} using direct SQLite connection")
            
            # Close any existing SQLAlchemy connections
            db.engine.dispose()
            
            # Use direct SQLite connection
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            # Drop table and commit immediately
            cursor.execute(f"DROP TABLE IF EXISTS {table_name}")
            conn.commit()
            
            # Close connection
            cursor.close()
            conn.close()
            
            logger.info(f"🗑️ Table {table_name} dropped successfully via direct SQLite connection")
            return True
        else:
            # If using in-memory DB or can't get path, fall back to SQLAlchemy
            logger.warning(f"⚠️ Cannot determine SQLite DB path, using SQLAlchemy fallback for {table_name}")
            with db.engine.connect() as conn:
                conn.execute(text(f"DROP TABLE IF EXISTS {table_name}"))
                conn.commit()
            logger.info(f"🗑️ Table {table_name} dropped via SQLAlchemy")
            return True
            
    except Exception as e:
        logger.error(f"❌ Error force dropping table {table_name}: {str(e)}")
        logger.error(traceback.format_exc())
        return False 
