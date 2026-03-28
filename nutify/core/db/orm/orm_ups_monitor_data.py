"""
UPS monitor data ORM model.

This model stores per-target snapshots collected by the Multi-NUT polling loop
using canonical variable names.
"""

from datetime import datetime

import pytz
from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, Text


logger = None


class UPSMonitorData:
    """Model for Multi-NUT time-series data."""

    __tablename__ = 'ups_monitor_data'

    id = Column(Integer, primary_key=True)
    target_id = Column(
        Integer,
        ForeignKey('ups_monitor_targets.id', ondelete='CASCADE'),
        nullable=False,
        index=True,
    )
    timestamp_utc = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(pytz.UTC),
        index=True,
    )
    shard_key = Column(String(20), nullable=True, index=True)

    # Canonical metrics frequently used by dashboards and APIs.
    ups_status = Column(String(255), nullable=True)
    ups_load = Column(Float, nullable=True)
    ups_power = Column(Float, nullable=True)
    ups_power_nominal = Column(Float, nullable=True)
    ups_realpower = Column(Float, nullable=True)
    ups_realpower_nominal = Column(Float, nullable=True)

    battery_charge = Column(Float, nullable=True)
    battery_charge_low = Column(Float, nullable=True)
    battery_charge_warning = Column(Float, nullable=True)
    battery_runtime = Column(Float, nullable=True)
    battery_runtime_low = Column(Float, nullable=True)
    battery_voltage = Column(Float, nullable=True)
    battery_voltage_nominal = Column(Float, nullable=True)
    battery_current = Column(Float, nullable=True)
    battery_temperature = Column(Float, nullable=True)
    battery_alarm_threshold = Column(Float, nullable=True)

    input_voltage = Column(Float, nullable=True)
    input_voltage_nominal = Column(Float, nullable=True)
    input_transfer_low = Column(Float, nullable=True)
    input_transfer_high = Column(Float, nullable=True)
    input_sensitivity = Column(String(255), nullable=True)
    input_current = Column(Float, nullable=True)
    input_frequency = Column(Float, nullable=True)
    input_frequency_nominal = Column(Float, nullable=True)

    output_voltage = Column(Float, nullable=True)
    output_voltage_nominal = Column(Float, nullable=True)
    output_current = Column(Float, nullable=True)
    output_frequency = Column(Float, nullable=True)
    output_frequency_nominal = Column(Float, nullable=True)

    device_model = Column(String(255), nullable=True)
    device_serial = Column(String(255), nullable=True)
    device_mfr = Column(String(255), nullable=True)
    battery_type = Column(String(255), nullable=True)
    battery_date = Column(String(255), nullable=True)
    battery_mfr_date = Column(String(255), nullable=True)

    # Full payload maps.
    data_json = Column(Text, nullable=True)  # Canonical payload
    raw_json = Column(Text, nullable=True)   # Original upsc payload

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(pytz.UTC))

    def to_dict(self):
        """Convert model to API-friendly dictionary."""
        return {
            'id': self.id,
            'target_id': self.target_id,
            'timestamp_utc': self.timestamp_utc.isoformat() if self.timestamp_utc else None,
            'shard_key': self.shard_key,
            'ups_status': self.ups_status,
            'ups_load': self.ups_load,
            'ups_power': self.ups_power,
            'ups_power_nominal': self.ups_power_nominal,
            'ups_realpower': self.ups_realpower,
            'ups_realpower_nominal': self.ups_realpower_nominal,
            'battery_charge': self.battery_charge,
            'battery_charge_low': self.battery_charge_low,
            'battery_charge_warning': self.battery_charge_warning,
            'battery_runtime': self.battery_runtime,
            'battery_runtime_low': self.battery_runtime_low,
            'battery_voltage': self.battery_voltage,
            'battery_voltage_nominal': self.battery_voltage_nominal,
            'battery_current': self.battery_current,
            'battery_temperature': self.battery_temperature,
            'battery_alarm_threshold': self.battery_alarm_threshold,
            'input_voltage': self.input_voltage,
            'input_voltage_nominal': self.input_voltage_nominal,
            'input_transfer_low': self.input_transfer_low,
            'input_transfer_high': self.input_transfer_high,
            'input_sensitivity': self.input_sensitivity,
            'input_current': self.input_current,
            'input_frequency': self.input_frequency,
            'input_frequency_nominal': self.input_frequency_nominal,
            'output_voltage': self.output_voltage,
            'output_voltage_nominal': self.output_voltage_nominal,
            'output_current': self.output_current,
            'output_frequency': self.output_frequency,
            'output_frequency_nominal': self.output_frequency_nominal,
            'device_model': self.device_model,
            'device_serial': self.device_serial,
            'device_mfr': self.device_mfr,
            'battery_type': self.battery_type,
            'battery_date': self.battery_date,
            'battery_mfr_date': self.battery_mfr_date,
            'data_json': self.data_json,
            'raw_json': self.raw_json,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


def init_model(model_base, db_logger=None):
    """Initialize model with SQLAlchemy base."""
    global logger

    if db_logger:
        logger = db_logger

    class UPSMonitorDataModel(model_base, UPSMonitorData):
        __table_args__ = {'extend_existing': True}

    return UPSMonitorDataModel
