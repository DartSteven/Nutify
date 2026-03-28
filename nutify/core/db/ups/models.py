"""
UPS Models Module.
This module defines functions for creating dynamic UPS models.
"""

import logging
from datetime import datetime
from sqlalchemy import inspect, text
import pytz
from flask import current_app

from core.logger import database_logger as logger
from core.db.ups.utils import ups_config
# Importiamo get_available_variables solo quando necessario per evitare import circolari

# Global variables for model caching
_UPSStaticData = None
_UPSDynamicData = None

# Correct definition of static UPS fields (fields that don't change)
STATIC_FIELDS = {
    # Device info
    'device.model', 'device.mfr', 'device.serial', 'device.type', 'device.description',
    'device.contact', 'device.location', 'device.part', 'device.macaddr', 'device.usb_version',
    
    # UPS info
    'ups.model', 'ups.mfr', 'ups.mfr.date', 'ups.serial', 'ups.vendorid',
    'ups.productid', 'ups.firmware', 'ups.firmware.aux', 'ups.type', 'ups.id',
    'ups.display.language', 'ups.contacts',
    
    # Battery static info
    'battery.type', 'battery.date', 'battery.mfr.date', 'battery.packs',
    'battery.packs.external', 'battery.protection',
    
    # Driver info
    'driver.name', 'driver.version', 'driver.version.internal',
    'driver.version.data', 'driver.version.usb'
}

# Correct definition of dynamic UPS fields (fields that change)
DYNAMIC_FIELDS = {
    # Device dynamic info
    'device.uptime', 'device.count',

    # UPS dynamic info
    'ups.status', 'ups.alarm', 'ups.time', 'ups.date', 'ups.temperature',
    'ups.load', 'ups.load.high', 'ups.delay.start', 'ups.delay.reboot', 'ups.delay.shutdown',
    'ups.timer.start', 'ups.timer.reboot', 'ups.timer.shutdown', 'ups.test.interval',
    'ups.test.result', 'ups.test.date', 'ups.display.language', 'ups.efficiency',
    'ups.power', 'ups.power.nominal', 'ups.realpower', 'ups.realpower.nominal',
    'ups.beeper.status', 'ups.watchdog.status', 'ups.start.auto', 'ups.start.battery',
    'ups.start.reboot', 'ups.shutdown',

    # Input measurements
    'input.voltage', 'input.voltage.maximum', 'input.voltage.minimum', 'input.voltage.status',
    'input.voltage.nominal', 'input.voltage.extended', 'input.transfer.low', 'input.transfer.high',
    'input.sensitivity', 'input.frequency', 'input.frequency.nominal', 'input.current',
    'input.current.nominal', 'input.realpower', 'input.realpower.nominal',

    # Output measurements
    'output.voltage', 'output.voltage.nominal', 'output.frequency', 'output.frequency.nominal',
    'output.current', 'output.current.nominal',

    # Battery measurements
    'battery.charge', 'battery.charge.low', 'battery.charge.warning', 'battery.voltage',
    'battery.voltage.nominal', 'battery.current', 'battery.temperature', 'battery.runtime',
    'battery.runtime.low', 'battery.alarm.threshold',

    # Ambient measurements
    'ambient.temperature', 'ambient.humidity', 'ambient.temperature.high',
    'ambient.temperature.low', 'ambient.humidity.high', 'ambient.humidity.low'
}

def is_static_field(field_name):
    """
    Determine if a field is static
    
    Args:
        field_name: Name of the field to check
        
    Returns:
        bool: True if the field is static, False otherwise
    """
    # Convert from DB format to NUT format (device_model -> device.model)
    nut_name = field_name.replace('_', '.')
    return nut_name in STATIC_FIELDS

def get_available_ups_variables():
    """
    Get all available variables from the UPS.
    
    Returns:
        dict: Dictionary of variable names and their values
    """
    # Dictionary to store variables
    variables = {}
    
    try:
        # Import required modules inside the function to prevent circular imports
        from core.db.ups.data import get_available_variables
        from core.db.ups.utils import _ups_command, _ups_name, _ups_host
        
        # Check if UPS configuration is initialized
        if not all([_ups_command, _ups_name, _ups_host]):
            logger.warning("UPS configuration not initialized in get_available_ups_variables. Using default values.")
            # Create default variables dictionary with empty values
            for field in list(STATIC_FIELDS) + list(DYNAMIC_FIELDS):
                if 'voltage' in field or 'current' in field or 'charge' in field:
                    variables[field] = "0.0"
                elif 'count' in field or 'packs' in field:
                    variables[field] = "0"
                else:
                    variables[field] = ""
            return variables
        
        # Try to get actual UPS variables
        try:
            # Normal case - UPS configuration is available
            all_variables = get_available_variables()
            logger.debug(f"📖 Found {len(all_variables)} UPS variables")
            return all_variables
        except ValueError as ve:
            # Specific handling for UPS configuration not initialized
            if "UPS configuration not initialized" in str(ve):
                logger.warning(f"UPS configuration not initialized in get_available_variables")
                # Fall through to use default values
            else:
                raise
        except Exception as e:
            logger.warning(f"Cannot communicate with UPS: {str(e)}")
            # Fall through to use default values
            
    except Exception as e:
        logger.warning(f"Error in get_available_ups_variables: {str(e)}")
        logger.warning("Using default model structure.")
    
    # If we reach here, it means we need to use default values
    # Create default variables dictionary with empty values
    for field in list(STATIC_FIELDS) + list(DYNAMIC_FIELDS):
        if 'voltage' in field or 'current' in field or 'charge' in field:
            variables[field] = "0.0"
        elif 'count' in field or 'packs' in field:
            variables[field] = "0"
        else:
            variables[field] = ""
    
    return variables

def get_ups_model(db=None):
    """
    Get the ORM model for the UPS dynamic data.
    Always returns the dynamically created model based on UPS data.
    
    Args:
        db: SQLAlchemy database instance (optional)
    
    Returns:
        Type: SQLAlchemy model class for dynamic UPS data
    """
    global _UPSDynamicData
    
    # If the model is already created, return it
    if _UPSDynamicData is not None:
        return _UPSDynamicData
    
    # If no db provided, try to import from the global db
    if db is None:
        try:
            from core.db.ups import db as global_db
            db = global_db
        except ImportError:
            logger.error("No database instance provided and cannot import global db")
            raise ValueError("Database instance is required to create model")
            
    # Create the model using the provided or global db
    _UPSDynamicData = create_dynamic_model(db)
    return _UPSDynamicData

def get_static_model(db=None):
    """
    Get the ORM model for the UPS static data.
    Always returns the dynamically created model based on UPS data.
    
    Args:
        db: SQLAlchemy database instance (optional)
    
    Returns:
        Type: SQLAlchemy model class for static UPS data
    """
    global _UPSStaticData
    
    # If the model is already created, return it
    if _UPSStaticData is not None:
        return _UPSStaticData
    
    # If no db provided, try to import from the global db
    if db is None:
        try:
            from core.db.ups import db as global_db
            db = global_db
        except ImportError:
            logger.error("No database instance provided and cannot import global db")
            raise ValueError("Database instance is required to create model")
            
    # Create the model using the provided or global db
    _UPSStaticData = create_static_model(db)
    return _UPSStaticData

def create_static_model(db=None):
    """
    Create the ORM model for the static UPS data dynamically.
    Always creates the model dynamically based on UPS data.
    
    Args:
        db: SQLAlchemy database instance (optional)
        
    Returns:
        Type: SQLAlchemy model class for static UPS data
    """
    global _UPSStaticData
    
    # If the model is already created, return it
    if (_UPSStaticData is not None):
        return _UPSStaticData
    
    # If no db provided, try to import from the global db
    if db is None:
        try:
            from core.db.ups import db as global_db
            db = global_db
        except ImportError:
            logger.error("No database instance provided and cannot import global db")
            raise ValueError("Database instance is required to create model")

    logger.info("🔄 Creating dynamic UPSStaticData model based on UPS variables")
    
    # Dictionary to store variables
    variables = {}
    
    try:
        # Get the available variables from the UPS
        try:
            from core.db.ups.data import get_available_variables
            all_variables = get_available_variables()
            # Filter only static fields
            for k, v in all_variables.items():
                if k in STATIC_FIELDS:
                    variables[k] = v
        except ValueError as ve:
            # Specific handling for UPS configuration not initialized
            if "UPS configuration not initialized" in str(ve):
                logger.warning(f"UPS configuration not initialized when creating static model")
                # Fall through to use default values
            else:
                raise
        except Exception as e:
            logger.warning(f"Cannot get UPS variables: {str(e)}")
            # Fall through to use default values
            
        # If no variables were obtained (empty dict), use default values
        if not variables:
            logger.warning("Using default model structure for UPS static data.")
            # Create default variables dictionary with empty values
            for field in STATIC_FIELDS:
                if 'voltage' in field or 'current' in field or 'charge' in field:
                    variables[field] = "0.0"
                elif 'count' in field or 'packs' in field:
                    variables[field] = "0"
                else:
                    variables[field] = ""
    except Exception as e:
        logger.warning(f"Error preparing variables for static model: {str(e)}")
        logger.warning("Using default model structure for UPS static data.")
        # Create default variables dictionary with empty values
        for field in STATIC_FIELDS:
            if 'voltage' in field or 'current' in field or 'charge' in field:
                variables[field] = "0.0"
            elif 'count' in field or 'packs' in field:
                variables[field] = "0"
            else:
                variables[field] = ""
                
    # Now create the model with the variables we have
    class UPSStaticData(db.Model):
        __tablename__ = 'ups_static_data'
        __table_args__ = {'extend_existing': True}
        
        # Base fields always present
        id = db.Column(db.Integer, primary_key=True)
        # Database timestamps are stored in UTC (database always uses UTC while display uses CACHE_TIMEZONE)
        timestamp_utc = db.Column(db.DateTime(timezone=True), nullable=False, 
                            default=lambda: datetime.now(pytz.UTC))
        
        # Add dynamically columns based on UPS data
        for key, value in variables.items():
            # Convert the key format from NUT to DB
            db_key = key.replace('.', '_')
            
            # Determine the column type based on the value
            try:
                float(value)
                vars()[db_key] = db.Column(db.Float)
            except ValueError:
                try:
                    int(value)
                    vars()[db_key] = db.Column(db.Integer)
                except ValueError:
                    # For string values we use String(255)
                    vars()[db_key] = db.Column(db.String(255))
        
        def __repr__(self):
            return f"<UPSStaticData {self.id} - {self.timestamp_utc}>"
            
    logger.debug(f"📚 Dynamically created UPSStaticData model with {len(variables)} columns")
    _UPSStaticData = UPSStaticData
    
    # Register the static model to ModelClasses if available
    if hasattr(db, 'ModelClasses'):
        try:
            from core.db.model_classes import register_dynamic_models
            register_dynamic_models(db.ModelClasses, UPSStaticData, None)
        except Exception as e:
            logger.warning(f"Could not register static model: {str(e)}")
    
    return _UPSStaticData

def create_dynamic_model(db=None):
    """
    Create the ORM model for the dynamic UPS data dynamically.
    Always creates the model dynamically based on UPS data.
    
    Args:
        db: SQLAlchemy database instance (optional)
        
    Returns:
        Type: SQLAlchemy model class for dynamic UPS data
    """
    global _UPSDynamicData
    
    # If the model is already created, return it
    if (_UPSDynamicData is not None):
        return _UPSDynamicData
    
    # If no db provided, try to import from the global db
    if db is None:
        try:
            from core.db.ups import db as global_db
            db = global_db
        except ImportError:
            logger.error("No database instance provided and cannot import global db")
            raise ValueError("Database instance is required to create model")

    logger.info("🔄 Creating dynamic UPSDynamicData model based on UPS variables")

    # Dictionary to store variables
    variables = {}
    
    try:
        # Get the available variables from the UPS
        try:
            from core.db.ups.data import get_available_variables
            all_variables = get_available_variables()
            # Filter only dynamic fields
            for k, v in all_variables.items():
                if k in DYNAMIC_FIELDS:
                    variables[k] = v
        except ValueError as ve:
            # Specific handling for UPS configuration not initialized
            if "UPS configuration not initialized" in str(ve):
                logger.warning(f"UPS configuration not initialized when creating dynamic model")
                # Fall through to use default values
            else:
                raise
        except Exception as e:
            logger.warning(f"Cannot get UPS variables: {str(e)}")
            # Fall through to use default values
            
        # If no variables were obtained (empty dict), use default values
        if not variables:
            logger.warning("Using default model structure for UPS dynamic data.")
            # Create default variables dictionary with empty values
            for field in DYNAMIC_FIELDS:
                if 'voltage' in field or 'current' in field or 'charge' in field:
                    variables[field] = "0.0"
                elif 'count' in field or 'packs' in field:
                    variables[field] = "0"
                else:
                    variables[field] = ""
    except Exception as e:
        logger.warning(f"Error preparing variables for dynamic model: {str(e)}")
        logger.warning("Using default model structure for UPS dynamic data.")
        # Create default variables dictionary with empty values
        for field in DYNAMIC_FIELDS:
            if 'voltage' in field or 'current' in field or 'charge' in field:
                variables[field] = "0.0"
            elif 'count' in field or 'packs' in field:
                variables[field] = "0"
            else:
                variables[field] = ""
                
    class UPSDynamicData(db.Model):
        __tablename__ = 'ups_dynamic_data'
        __table_args__ = {'extend_existing': True}
        
        # Base fields always present
        id = db.Column(db.Integer, primary_key=True)
        # Database timestamps are stored in UTC (database always uses UTC while display uses CACHE_TIMEZONE)
        timestamp_utc = db.Column(db.DateTime(timezone=True), nullable=False, 
                            default=lambda: datetime.now(pytz.UTC))
        
        # Ensure ups_realpower and ups_realpower_hrs are always present
        ups_realpower = db.Column(db.Float)
        ups_realpower_hrs = db.Column(db.Float)  # Added field for hourly average
        ups_realpower_days = db.Column(db.Float)  # Field for daily average
        
        # Ensure ups_status is always present
        ups_status = db.Column(db.String(255))
        
        # Add dynamically columns based on UPS data
        for key, value in variables.items():
            # Convert the key format from NUT to DB
            db_key = key.replace('.', '_')
            
            # Skip fields we already explicitly defined
            if db_key not in ['ups_realpower', 'ups_realpower_hrs', 'ups_realpower_days', 'ups_status']:
                # Determine the column type based on the value
                try:
                    float(value)
                    vars()[db_key] = db.Column(db.Float)
                except ValueError:
                    try:
                        int(value)
                        vars()[db_key] = db.Column(db.Integer)
                    except ValueError:
                        # For string values we use String(255)
                        vars()[db_key] = db.Column(db.String(255))
        
        @property
        def daily_power(self):
            return self.ups_realpower_days
        
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
        
        def __repr__(self):
            return f"<UPSDynamicData {self.id} - {self.timestamp_utc}>"
    
    logger.debug(f"📚 Dynamically created UPSDynamicData model with {len(variables)} columns")
    _UPSDynamicData = UPSDynamicData
    
    # Register the dynamic model to ModelClasses if available
    if hasattr(db, 'ModelClasses'):
        try:
            from core.db.model_classes import register_dynamic_models
            if hasattr(db.ModelClasses, 'UPSStaticData'):
                register_dynamic_models(db.ModelClasses, db.ModelClasses.UPSStaticData, UPSDynamicData)
            else:
                register_dynamic_models(db.ModelClasses, None, UPSDynamicData)
        except Exception as e:
            logger.warning(f"Could not register dynamic model: {str(e)}")
    
    return _UPSDynamicData

def initialize_static_data(db):
    """
    Initialize the UPS static data in the database
    - Get the current UPS data
    - Create a new record in the static table
    - Save the data in the database
    
    Args:
        db: SQLAlchemy database instance
        
    Raises:
        Exception: If an error occurs during initialization
    """
    try:
        UPSStaticData = create_static_model(db)
        
        # Get the current UPS data
        try:
            from core.db.ups.data import get_available_variables
            variables = get_available_variables()
            logger.info("Got current UPS variables for static data initialization")
        except Exception as e:
            logger.warning(f"Cannot get UPS variables for initialization: {str(e)}")
            logger.warning("Using default values for static data initialization")
            
            # Create default variables with empty values
            variables = {}
            for field in STATIC_FIELDS:
                if 'voltage' in field or 'current' in field or 'charge' in field:
                    variables[field] = "0.0"
                elif 'count' in field or 'packs' in field:
                    variables[field] = "0"
                else:
                    variables[field] = ""
        
        # Create a new record with ID=1
        static_data = UPSStaticData(id=1)
        
        # Map the fields from NUT format to database format
        static_fields = [c.name for c in UPSStaticData.__table__.columns 
                        if c.name not in ('id', 'timestamp_utc')]
        
        for field in static_fields:
            ups_key = field.replace('_', '.')  # Convert the format (es: device_model -> device.model)
            if ups_key in variables:
                setattr(static_data, field, variables[ups_key])
                logger.debug(f"Set static field {field}={variables[ups_key]}")
        
        # Save the data in the database - check if a transaction is active before starting a new one
        try:
            # Try to execute without explicit transaction first
            db.session.add(static_data)
            db.session.commit()
            logger.info("Static UPS data saved successfully")
        except Exception as e:
            if "A transaction is already begun on this Session" in str(e):
                # If transaction already exists, just add without committing
                db.session.add(static_data)
                logger.info("Static UPS data added to existing transaction")
            else:
                raise
            
    except Exception as e:
        logger.error(f"Error initializing static data: {str(e)}")
        try:
            db.session.rollback()
        except:
            # Ignore rollback errors
            pass
        raise

def initialize_static_data_if_needed(db):
    """
    Initialize static UPS data if needed.
    - Checks if the ups_static_data table exists
    - If it exists, verifies its schema matches the expected model
    - If schema mismatch is detected, drops and recreates the table
    - Checks if the table has data
    - If empty, initializes it with current UPS data
    
    Args:
        db: SQLAlchemy database instance
        
    Returns:
        bool: True if successful, False on error
    """
    try:
        # Get the inspector to check if table exists
        inspector = inspect(db.engine)
        table_exists = 'ups_static_data' in inspector.get_table_names()
        
        # Step 1: Create the table if it doesn't exist
        if not table_exists:
            logger.info("🏗️ Static data table does not exist - creating table...")
            # Make sure the model is created
            UPSStaticData = create_static_model(db)
            # Create the table
            UPSStaticData.__table__.create(db.engine)
            logger.info("✅ Created ups_static_data table")
            # Now we need to initialize the data
            logger.info("🔄 Initializing static data after table creation...")
            try:
                initialize_static_data(db)
                logger.info("✅ Static data initialization complete")
            except Exception as e:
                logger.error(f"❌ Error initializing static data after table creation: {str(e)}")
                # Continue even if initialization fails - app will use default values
            return True
        
        # Step 1.5: SCHEMA VERIFICATION - Check if table schema matches expected
        logger.info("🔍 Verifying ups_static_data table schema...")
        try:
            # Get the current model with expected schema
            UPSStaticData = create_static_model(db)
            
            # Get current columns from database
            db_columns = {c['name']: c for c in inspector.get_columns('ups_static_data')}
            
            # Get model columns (expected schema)
            model_columns = {c.name: c for c in UPSStaticData.__table__.columns}
            
            # Check for schema mismatches
            schema_mismatch = False
            missing_columns = set(model_columns.keys()) - set(db_columns.keys())
            extra_columns = set(db_columns.keys()) - set(model_columns.keys())
            
            # Report missing columns
            if missing_columns:
                logger.warning(f"❌ ups_static_data table is missing columns: {missing_columns}")
                schema_mismatch = True
                
            # Report extra columns
            if extra_columns:
                logger.warning(f"❌ ups_static_data table has extra columns: {extra_columns}")
                schema_mismatch = True
                
            # Check for column type mismatches on common columns
            for col_name in set(model_columns.keys()) & set(db_columns.keys()):
                model_col = model_columns[col_name]
                db_col = db_columns[col_name]
                
                # Get type name from model and db
                model_type = str(model_col.type)
                db_type = db_col['type']
                
                # Basic type comparison - this could be improved for more precise type checking
                if not model_type.lower().startswith(str(db_type).lower()):
                    logger.warning(f"❌ Column ups_static_data.{col_name} type mismatch: DB={db_type}, Model={model_type}")
                    schema_mismatch = True
            
            # If schema mismatch detected, drop and recreate table
            if schema_mismatch:
                logger.warning("⚠️ Schema mismatch detected for ups_static_data table")
                logger.warning("🔄 Dropping and recreating ups_static_data table")
                
                try:
                    # First, commit any pending transactions to avoid conflicts
                    try:
                        db.session.commit()
                    except:
                        db.session.rollback()
                    
                    # Drop the table
                    with db.engine.connect() as conn:
                        # Use ORM instead of raw SQL to drop the table
                        UPSStaticData.__table__.drop(db.engine, checkfirst=True)
                        conn.commit()
                    logger.info("🗑️ ups_static_data table dropped")
                    
                    # Recreate the table
                    UPSStaticData.__table__.create(db.engine)
                    logger.info("✅ ups_static_data table recreated")
                    
                    # Initialize with data
                    logger.info("🔄 Initializing static data after table recreation...")
                    initialize_static_data(db)
                    logger.info("✅ Static data initialization complete after schema update")
                    return True
                except Exception as e:
                    logger.error(f"❌ Error recreating ups_static_data table: {str(e)}")
                    # Continue to allow application to start
            else:
                logger.info("✅ ups_static_data table schema matches expected model")
        except Exception as e:
            logger.error(f"❌ Error verifying ups_static_data schema: {str(e)}")
            # Continue to allow application to start
        
        # Step 2: Check if there is data in the table
        try:
            # Use SQLAlchemy ORM query to count records
            result = db.session.query(db.func.count()).select_from(get_static_model(db)).scalar()
            
            if result == 0:
                # If no static data exists, initialize it
                logger.info("🔄 Table exists but no static data found - initializing static data...")
                try:
                    initialize_static_data(db)
                    logger.info("✅ Static data initialization complete")
                except Exception as e:
                    logger.error(f"❌ Error initializing static data: {str(e)}")
                    # Continue even if initialization fails - app will use default values
            else:
                logger.info(f"✓ Found {result} static data entries - using existing data")
                
            return True
            
        except Exception as e:
            logger.error(f"❌ Error checking static data: {str(e)}")
            # Continue anyway to allow the application to start
            return True
        
    except Exception as e:
        logger.error(f"❌ Error in initialize_static_data_if_needed: {str(e)}")
        # Continue anyway to allow the application to start
        return True

def insert_initial_dynamic_data(db):
    """
    Initialize UPS dynamic data if needed.
    - Checks if the ups_dynamic_data table exists
    - If it doesn't exist, creates it
    - Checks if the table has data
    - If empty, initializes it with current UPS data
    
    Args:
        db: SQLAlchemy database instance
        
    Returns:
        bool: True if successful, False on error
    """
    try:
        # Get the inspector to check if table exists
        inspector = inspect(db.engine)
        table_exists = 'ups_dynamic_data' in inspector.get_table_names()
        
        # Step 1: Create the table if it doesn't exist
        if not table_exists:
            logger.info("🏗️ Dynamic data table does not exist - creating table...")
            # Make sure the model is created
            UPSDynamicData = create_dynamic_model(db)
            # Create the table
            UPSDynamicData.__table__.create(db.engine)
            logger.info("✅ Created ups_dynamic_data table")
        
        # Step 2: Get the model for dynamic data
        UPSDynamicData = get_ups_model(db)
        
        # Step 3: Check if the dynamic table is empty
        has_records = False
        try:
            # Use SQLAlchemy ORM query to count records
            result = db.session.query(db.func.count()).select_from(UPSDynamicData).scalar()
            has_records = result > 0
            
            if has_records:
                logger.info(f"✓ Found {result} dynamic data records - using existing data")
                return True
                
        except Exception as e:
            logger.error(f"❌ Error checking for existing dynamic data: {str(e)}")
            # Continue anyway to allow the application to start
            return True
            
        # Step 4: If no records exist, insert initial data
        if not has_records:
            logger.info("🔄 No dynamic data found - inserting initial UPS data...")
            try:
                # Get UPS data
                try:
                    from core.db.ups.data import get_ups_data
                    data = get_ups_data()
                    # Convert from DotDict to standard dict
                    data_dict = vars(data)
                except Exception as e:
                    logger.warning(f"Cannot get UPS data for initialization: {str(e)}")
                    logger.warning("Using default values for dynamic data initialization")
                    
                    # Create default values for essential fields
                    data_dict = {
                        'ups_status': 'INITIALIZING',
                        'ups_model': 'Unknown',
                        'ups_load': 0,
                        'ups_realpower': 0,
                        'ups_realpower_hrs': 0,
                        'ups_realpower_days': 0,
                        'input_voltage': 0,
                        'output_voltage': 0,
                        'battery_charge': 0,
                        'battery_runtime': 0
                    }
                
                # Create a new record with the data
                new_entry = UPSDynamicData()
                
                # For each column in the table, set it if it's in data_dict
                for column in [c.name for c in UPSDynamicData.__table__.columns]:
                    if column in data_dict:
                        setattr(new_entry, column, data_dict[column])
                
                # Insert the record - check if a transaction is active before starting a new one
                try:
                    # Try to execute without explicit transaction first
                    db.session.add(new_entry)
                    db.session.commit()
                    logger.info("✅ Initial dynamic data inserted successfully")
                except Exception as e:
                    if "A transaction is already begun on this Session" in str(e):
                        # If transaction already exists, just add without committing
                        db.session.add(new_entry)
                        logger.info("✅ Initial dynamic data added to existing transaction")
                    else:
                        logger.error(f"❌ Error during commit: {str(e)}")
                
                return True
                
            except Exception as e:
                logger.error(f"❌ Error inserting initial dynamic data: {str(e)}")
                try:
                    db.session.rollback()
                except:
                    # Ignore rollback errors
                    pass
                # Continue anyway to allow the application to start
                return True
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Error in insert_initial_dynamic_data: {str(e)}")
        # Continue anyway to allow the application to start
        return True

def get_ups_data(field=None):
    """
    Get the current UPS data with the possibility to filter by field
    
    Args:
        field: specific field to retrieve (default: None, for all fields)
        
    Returns:
        UPSData: Object containing current UPS data
        
    Raises:
        UPSDataError: If retrieving UPS data fails
    """
    try:
        from core.db.ups.utils import ups_config

    except Exception as e:
        logger.error(f"❌ Error in get_ups_data: {str(e)}")
        raise
