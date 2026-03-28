"""
Variable Configuration ORM model.
"""

from datetime import datetime

import pytz
from flask import current_app, has_app_context
from sqlalchemy import Column, DateTime, Float, Integer, String, inspect, text

from core.db.ups import db as app_db

# Set during model initialization.
db = None


def _resolve_engine(model_base):
    """Resolve SQLAlchemy engine from model base/app context."""
    metadata = getattr(model_base, 'metadata', None)
    engine = getattr(metadata, 'bind', None) if metadata else None
    if engine is not None:
        return engine

    if not has_app_context():
        return None

    try:
        extension = current_app.extensions.get('sqlalchemy')
        if extension is None:
            return None
        extension_engine = getattr(extension, 'engine', None)
        if extension_engine is not None:
            return extension_engine

        db_handle = getattr(extension, 'db', None)
        if db_handle is not None:
            return db_handle.engine
    except Exception:
        return None
    return None


def ensure_variable_config_columns(model_base):
    """Ensure runtime option columns exist on ups_opt_variable_config."""
    engine = _resolve_engine(model_base)
    if engine is None:
        return

    required_columns = {
        'timezone': "VARCHAR(64)",
        'ups_realpower_nominal': "INTEGER",
        'measured_power_metric_key': "VARCHAR(120) DEFAULT 'ups_realpower'",
        'load_metric_key': "VARCHAR(120) DEFAULT 'ups_load'",
        'nominal_power_metric_key': "VARCHAR(120) DEFAULT 'ups_realpower_nominal'",
        'realpower_formula': "VARCHAR(260) DEFAULT '(load_percent / 100.0) * nominal_power_w'",
        'power_calibration_factor': "FLOAT DEFAULT 1.0",
        'energy_formula': "VARCHAR(260) DEFAULT 'power_w * delta_hours'",
        'cost_formula': "VARCHAR(260) DEFAULT '(energy_wh / 1000.0) * price_per_kwh'",
        'co2_formula': "VARCHAR(260) DEFAULT '(energy_wh / 1000.0) * co2_factor'",
    }

    try:
        inspector = inspect(engine)
        table_names = inspector.get_table_names()
        if 'ups_opt_variable_config' not in table_names:
            return

        existing_columns = {column['name'] for column in inspector.get_columns('ups_opt_variable_config')}
        with engine.begin() as connection:
            for column_name, ddl in required_columns.items():
                if column_name in existing_columns:
                    continue
                connection.execute(
                    text(
                        f"ALTER TABLE ups_opt_variable_config "
                        f"ADD COLUMN {column_name} {ddl}"
                    )
                )
    except Exception:
        # Keep startup resilient: database patching is best-effort.
        pass


class VariableConfig:
    """Model for PowerFlow and polling configuration."""

    __tablename__ = "ups_opt_variable_config"

    id = Column(Integer, primary_key=True)
    target_id = Column(Integer, nullable=True, index=True)
    timezone = Column(String(64), nullable=True, default='UTC')
    ups_realpower_nominal = Column(Integer, nullable=True)
    currency = Column(String(3), nullable=False, default="EUR")
    price_per_kwh = Column(Float, nullable=False, default=0.25)
    co2_factor = Column(Float, nullable=False, default=0.4)
    polling_interval = Column(Integer, nullable=False, default=1)
    measured_power_metric_key = Column(String(120), nullable=False, default='ups_realpower')
    load_metric_key = Column(String(120), nullable=False, default='ups_load')
    nominal_power_metric_key = Column(String(120), nullable=False, default='ups_realpower_nominal')
    realpower_formula = Column(String(260), nullable=False, default='(load_percent / 100.0) * nominal_power_w')
    power_calibration_factor = Column(Float, nullable=False, default=1.0)
    energy_formula = Column(String(260), nullable=False, default='power_w * delta_hours')
    cost_formula = Column(String(260), nullable=False, default='(energy_wh / 1000.0) * price_per_kwh')
    co2_formula = Column(String(260), nullable=False, default='(energy_wh / 1000.0) * co2_factor')
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(pytz.UTC))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(pytz.UTC),
        onupdate=lambda: datetime.now(pytz.UTC),
    )

    @classmethod
    def _scoped_query(cls, target_id=None):
        query = app_db.session.query(cls)
        if not hasattr(cls, "target_id"):
            return query
        if target_id is None:
            return query.filter(cls.target_id.is_(None))
        return query.filter(cls.target_id == int(target_id))

    @classmethod
    def init_default_config(cls):
        """Create a global default row when none exists."""
        try:
            from core.logger import database_logger as logger

            logger.info("Starting VariableConfig initialization")

            existing_config = cls._scoped_query(target_id=None).order_by(cls.id.asc()).first()
            if existing_config:
                logger.info(f"Default config already exists: {existing_config.id}")
                return False

            logger.info("No default config found, creating one")
            default_config = cls(
                timezone="UTC",
                currency="EUR",
                price_per_kwh=0.25,
                co2_factor=0.4,
                polling_interval=1,
            )
            if hasattr(cls, "target_id"):
                default_config.target_id = None

            app_db.session.add(default_config)

            try:
                app_db.session.commit()
                logger.info("Default variable configuration created and committed")
                return True
            except Exception as exc:
                if "transaction is already begun" in str(exc):
                    app_db.session.flush()
                    logger.info("Default variable configuration flushed to session")
                    return True
                app_db.session.rollback()
                logger.error(f"Error during commit: {str(exc)}")
                raise
        except Exception as exc:
            try:
                app_db.session.rollback()
            except Exception:
                pass
            from core.logger import database_logger as logger

            logger.error(f"Error initializing default variable config: {str(exc)}")
            return False

    @classmethod
    def utc_to_local(cls, utc_dt):
        """Convert UTC datetime to configured local timezone."""
        from core.db.ups.utils import utc_to_local as utils_utc_to_local

        return utils_utc_to_local(utc_dt)

    @classmethod
    def local_to_utc(cls, local_dt):
        """Convert local timezone datetime to UTC."""
        from core.db.ups.utils import local_to_utc as utils_local_to_utc

        return utils_local_to_utc(local_dt)


def init_model(model_base):
    """
    Initialize the VariableConfig model with the SQLAlchemy base.
    """
    global db
    db = model_base
    ensure_variable_config_columns(model_base)

    class VariableConfigModel(model_base, VariableConfig):
        """ORM model for variable configuration."""

        __table_args__ = {"extend_existing": True}

    return VariableConfigModel
