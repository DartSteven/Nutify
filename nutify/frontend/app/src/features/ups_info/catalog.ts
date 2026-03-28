/**
 * Catalog.
 *
 * Frontend module used by Nutify React UI flows and state management.
 */

export type SectionField = [label: string, key: string]
export type SectionDefinition = {
  title: string
  icon: string
  fields: SectionField[]
}

export const FIELD_ICONS: Record<string, string> = {
  model: 'fa-microchip',
  serial: 'fa-barcode',
  type: 'fa-info-circle',
  manufacturer: 'fa-industry',
  firmware: 'fa-code',
  version: 'fa-code-branch',
  date: 'fa-calendar-alt',
  location: 'fa-map-marker-alt',
  contact: 'fa-address-card',
  language: 'fa-language',
  protection: 'fa-shield-alt',
  packs: 'fa-battery-full',
  name: 'fa-tag',
  description: 'fa-file-alt',
  macaddr: 'fa-network-wired',
  usb: 'fa-usb',
  vendorid: 'fa-fingerprint',
  productid: 'fa-box',
  voltage: 'fa-bolt',
  current: 'fa-tachometer-alt',
  power: 'fa-plug',
  load: 'fa-weight',
  efficiency: 'fa-chart-line',
  temperature: 'fa-thermometer-half',
  humidity: 'fa-tint',
  status: 'fa-info-circle',
  alarm: 'fa-exclamation-triangle',
  runtime: 'fa-clock',
  charge: 'fa-battery-three-quarters',
  sensitivity: 'fa-sliders-h',
  frequency: 'fa-wave-square',
  beeper: 'fa-volume-up',
  watchdog: 'fa-dog',
  id: 'fa-hashtag',
}

export const SECTIONS: SectionDefinition[] = [
  {
    title: 'Device Info',
    icon: 'fa-microchip',
    fields: [
      ['Model', 'device_model'],
      ['Manufacturer', 'device_mfr'],
      ['Type', 'device_type'],
      ['Serial', 'device_serial'],
      ['Description', 'device_description'],
      ['Part', 'device_part'],
    ],
  },
  {
    title: 'Device Network',
    icon: 'fa-network-wired',
    fields: [
      ['Location', 'device_location'],
      ['Contact', 'device_contact'],
      ['MAC Address', 'device_macaddr'],
      ['USB Version', 'device_usb_version'],
    ],
  },
  {
    title: 'UPS Model',
    icon: 'fa-server',
    fields: [
      ['Model', 'ups_model'],
      ['Manufacturer', 'ups_mfr'],
      ['Manufacturing Date', 'ups_mfr_date'],
      ['Serial', 'ups_serial'],
      ['Type', 'ups_type'],
      ['ID', 'ups_id'],
    ],
  },
  {
    title: 'UPS Technical',
    icon: 'fa-cogs',
    fields: [
      ['Vendor ID', 'ups_vendorid'],
      ['Product ID', 'ups_productid'],
      ['Firmware', 'ups_firmware'],
      ['Auxiliary Firmware', 'ups_firmware_aux'],
      ['Display Language', 'ups_display_language'],
      ['Contacts', 'ups_contacts'],
    ],
  },
  {
    title: 'Driver Information',
    icon: 'fa-code',
    fields: [
      ['Name', 'driver_name'],
      ['Version', 'driver_version'],
      ['Internal Version', 'driver_version_internal'],
      ['Data Version', 'driver_version_data'],
      ['USB Version', 'driver_version_usb'],
    ],
  },
  {
    title: 'Battery Status',
    icon: 'fa-battery-three-quarters',
    fields: [
      ['Charge', 'battery_charge'],
      ['Charge Low', 'battery_charge_low'],
      ['Charge Warning', 'battery_charge_warning'],
      ['Runtime', 'battery_runtime'],
      ['Runtime Low', 'battery_runtime_low'],
      ['Alarm Threshold', 'battery_alarm_threshold'],
    ],
  },
  {
    title: 'Battery Details',
    icon: 'fa-car-battery',
    fields: [
      ['Type', 'battery_type'],
      ['Date', 'battery_date'],
      ['Manufacturing Date', 'battery_mfr_date'],
      ['Packs', 'battery_packs'],
      ['External Packs', 'battery_packs_external'],
      ['Protection', 'battery_protection'],
    ],
  },
  {
    title: 'Battery Technical',
    icon: 'fa-bolt',
    fields: [
      ['Voltage', 'battery_voltage'],
      ['Voltage Nominal', 'battery_voltage_nominal'],
      ['Current', 'battery_current'],
      ['Temperature', 'battery_temperature'],
    ],
  },
  {
    title: 'Input Power',
    icon: 'fa-plug',
    fields: [
      ['Voltage', 'input_voltage'],
      ['Voltage Maximum', 'input_voltage_maximum'],
      ['Voltage Minimum', 'input_voltage_minimum'],
      ['Voltage Status', 'input_voltage_status'],
      ['Voltage Nominal', 'input_voltage_nominal'],
      ['Voltage Extended', 'input_voltage_extended'],
    ],
  },
  {
    title: 'Input Settings',
    icon: 'fa-sliders-h',
    fields: [
      ['Transfer Low', 'input_transfer_low'],
      ['Transfer High', 'input_transfer_high'],
      ['Sensitivity', 'input_sensitivity'],
    ],
  },
  {
    title: 'Input Technical',
    icon: 'fa-tachometer-alt',
    fields: [
      ['Frequency', 'input_frequency'],
      ['Frequency Nominal', 'input_frequency_nominal'],
      ['Current', 'input_current'],
      ['Current Nominal', 'input_current_nominal'],
      ['Real Power', 'input_realpower'],
      ['Real Power Nominal', 'input_realpower_nominal'],
    ],
  },
  {
    title: 'Output Power',
    icon: 'fa-bolt',
    fields: [
      ['Voltage', 'output_voltage'],
      ['Voltage Nominal', 'output_voltage_nominal'],
      ['Frequency', 'output_frequency'],
      ['Frequency Nominal', 'output_frequency_nominal'],
    ],
  },
  {
    title: 'Output Technical',
    icon: 'fa-tachometer-alt',
    fields: [
      ['Current', 'output_current'],
      ['Current Nominal', 'output_current_nominal'],
    ],
  },
  {
    title: 'UPS Status',
    icon: 'fa-info-circle',
    fields: [
      ['Status', 'ups_status'],
      ['Alarm', 'ups_alarm'],
      ['Time', 'ups_time'],
      ['Date', 'ups_date'],
      ['Temperature', 'ups_temperature'],
    ],
  },
  {
    title: 'UPS Load',
    icon: 'fa-weight',
    fields: [
      ['Load', 'ups_load'],
      ['Load High', 'ups_load_high'],
      ['Efficiency', 'ups_efficiency'],
    ],
  },
  {
    title: 'UPS Power',
    icon: 'fa-bolt',
    fields: [
      ['Power', 'ups_power'],
      ['Power Nominal', 'ups_power_nominal'],
      ['Real Power', 'ups_realpower'],
      ['Real Power Nominal', 'ups_realpower_nominal'],
      ['Nominal Power', 'UPS_REALPOWER_NOMINAL'],
      ['Real Power Hours', 'ups_realpower_hrs'],
      ['Real Power Days', 'ups_realpower_days'],
    ],
  },
  {
    title: 'UPS Control',
    icon: 'fa-toggle-on',
    fields: [
      ['Beeper Status', 'ups_beeper_status'],
      ['Watchdog Status', 'ups_watchdog_status'],
    ],
  },
  {
    title: 'Environment',
    icon: 'fa-thermometer-half',
    fields: [
      ['Temperature', 'ambient_temperature'],
      ['Temperature High', 'ambient_temperature_high'],
      ['Temperature Low', 'ambient_temperature_low'],
      ['Humidity', 'ambient_humidity'],
      ['Humidity High', 'ambient_humidity_high'],
      ['Humidity Low', 'ambient_humidity_low'],
    ],
  },
]
