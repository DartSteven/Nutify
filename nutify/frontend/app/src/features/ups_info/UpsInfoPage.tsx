/**
 * Upsinfopage.
 *
 * Frontend module used by Nutify React UI flows and state management.
 */

import { useEffect, useMemo, useState } from 'react'

import { fetchRawJson } from '../../lib/api/raw'
import { useCacheWebSocketManager } from '../../lib/realtime/cacheWebSocketManager'
import { useAppStore } from '../../store/appStore'
import { FIELD_ICONS, SECTIONS } from './catalog'

function asRecord(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    return {}
  }
  return value as Record<string, unknown>
}

function parseApiData(payload: unknown): Record<string, unknown> {
  const body = asRecord(payload)
  const data = asRecord(body.data)
  return data
}

function hasMeaningfulValue(value: unknown): boolean {
  return value !== undefined && value !== null && value !== 'N/A'
}

function asNumber(value: unknown): number | null {
  if (typeof value === 'number' && Number.isFinite(value)) {
    return value
  }
  if (typeof value === 'string') {
    const parsed = Number(value)
    if (Number.isFinite(parsed)) {
      return parsed
    }
  }
  return null
}

function formatUpsStatus(status: string): string {
  const states: Record<string, string> = {
    OL: 'Online',
    OB: 'On Battery',
    LB: 'Low Battery',
    HB: 'High Battery',
    RB: 'Replace Battery',
    CHRG: 'Charging',
    DISCHRG: 'Discharging',
    BYPASS: 'Bypass Mode',
    CAL: 'Calibration',
    OFF: 'Offline',
    OVER: 'Overloaded',
    TRIM: 'Trimming Voltage',
    BOOST: 'Boosting Voltage',
  }

  return status
    .split(' ')
    .map((item) => states[item] ?? item)
    .join(' + ')
}

function formatBatteryType(type: string): string {
  const batteryTypes: Record<string, string> = {
    PbAc: 'Lead Acid',
    Li: 'Lithium Ion',
    LiP: 'Lithium Polymer',
    NiCd: 'Nickel Cadmium',
    NiMH: 'Nickel Metal Hydride',
    SLA: 'Sealed Lead Acid',
    VRLA: 'Valve Regulated Lead Acid',
    AGM: 'Absorbed Glass Mat',
    Gel: 'Gel Cell',
    Flooded: 'Flooded Lead Acid',
  }
  return batteryTypes[type] ?? type
}

function formatRuntime(secondsValue: unknown): string {
  const seconds = asNumber(secondsValue)
  if (seconds === null || seconds <= 0) {
    return 'Unknown'
  }

  const fullSeconds = Math.floor(seconds)
  const hours = Math.floor(fullSeconds / 3600)
  const minutes = Math.floor((fullSeconds % 3600) / 60)

  if (hours > 0) {
    return `${hours} h ${minutes} min`
  }
  return `${minutes} min`
}

function formatNumericField(key: string, numericValue: number): string {
  if (key.includes('voltage')) {
    return `${numericValue.toLocaleString('en-US', { minimumFractionDigits: 0, maximumFractionDigits: 2 })}V`
  }
  if (key.includes('current')) {
    return `${numericValue.toLocaleString('en-US', { minimumFractionDigits: 0, maximumFractionDigits: 2 })}A`
  }
  if (key.includes('power')) {
    return `${numericValue.toLocaleString('en-US', { minimumFractionDigits: 0, maximumFractionDigits: 2 })}W`
  }
  if (key.includes('temperature')) {
    return `${numericValue.toLocaleString('en-US', { minimumFractionDigits: 0, maximumFractionDigits: 1 })}°C`
  }
  if (key.includes('charge') || key.includes('load') || key.includes('efficiency')) {
    return `${numericValue.toLocaleString('en-US', { minimumFractionDigits: 0, maximumFractionDigits: 1 })}%`
  }
  return numericValue.toLocaleString('en-US', { minimumFractionDigits: 0, maximumFractionDigits: 2 })
}

function formatFieldValue(key: string, value: unknown, data: Record<string, unknown>): string {
  if (key === 'UPS_REALPOWER_NOMINAL') {
    const realNominal = asNumber(data.ups_realpower_nominal)
    const powerNominal = asNumber(data.ups_power_nominal)
    const manualNominal = asNumber(data.UPS_REALPOWER_NOMINAL)
    const selected = realNominal && realNominal > 0 ? realNominal : powerNominal && powerNominal > 0 ? powerNominal : manualNominal
    if (selected !== null) {
      return `${selected.toLocaleString('en-US', { minimumFractionDigits: 0, maximumFractionDigits: 2 })}W`
    }
  }

  if (key === 'ups_status') {
    return formatUpsStatus(String(value))
  }

  if (key === 'battery_type') {
    return formatBatteryType(String(value))
  }

  if (key === 'battery_runtime' || key === 'battery_runtime_low') {
    return formatRuntime(value)
  }

  const numeric = asNumber(value)
  if (numeric !== null) {
    return formatNumericField(key, numeric)
  }

  return String(value)
}

function fieldIcon(key: string): string {
  const lowered = key.toLowerCase()
  for (const [token, icon] of Object.entries(FIELD_ICONS)) {
    if (lowered.includes(token)) {
      return icon
    }
  }
  return 'fa-circle'
}

export function UpsInfoPage() {
  const activeTargetId = useAppStore((state) => state.activeTargetId)
  const monitoringProfile = useAppStore((state) => state.bootstrap?.monitoring.monitoring_profile ?? 'single')
  const [data, setData] = useState<Record<string, unknown>>({})
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => {
    let mounted = true

    async function loadInitialData() {
      try {
        const payload = await fetchRawJson('/api/data/all', activeTargetId)
        if (!mounted) {
          return
        }
        setData((previous) => ({ ...previous, ...parseApiData(payload) }))
      } catch {
        if (!mounted) {
          return
        }
      } finally {
        if (mounted) {
          setIsLoading(false)
        }
      }
    }

    void loadInitialData()
    return () => {
      mounted = false
    }
  }, [activeTargetId])

  useCacheWebSocketManager({
    onUpdate: (payload) => {
      setData((previous) => ({ ...previous, ...payload }))
      setIsLoading(false)
    },
    monitoringProfile,
    activeTargetId,
  })

  const cards = useMemo(() => {
    return SECTIONS.map((section) => {
      const rows = section.fields
        .map(([label, key]) => {
          let resolvedLabel = label
          if (section.title === 'UPS Power' && key === 'UPS_REALPOWER_NOMINAL') {
            const realNominal = asNumber(data.ups_realpower_nominal)
            const powerNominal = asNumber(data.ups_power_nominal)
            resolvedLabel = realNominal && realNominal > 0 || powerNominal && powerNominal > 0 ? 'Nominal Power' : 'Manual Nominal Power'
          }
          return [resolvedLabel, key, data[key]] as const
        })
        .filter(([, , value]) => hasMeaningfulValue(value))

      if (rows.length === 0) {
        return null
      }

      return (
        <div key={section.title} className="stat_card ups_info_card">
          <div className="ups_info_card_header">
            <div className="ups_info_card_icon">
              <i className={`fas ${section.icon}`} />
            </div>
            <h3 className="ups_info_card_title">{section.title}</h3>
          </div>
          <ul className="ups_info_rows">
            {rows.map(([label, key, value]) => (
              <li key={`${section.title}-${key}`} className="ups_info_row">
                <span className="ups_info_row_icon" aria-hidden="true">
                  <i className={`fas ${fieldIcon(key)} fa-fw`} />
                </span>
                <span className="ups_info_row_label" title={label}>
                  {label}
                </span>
                <span className="ups_info_row_value" title={formatFieldValue(key, value, data)}>
                  {formatFieldValue(key, value, data)}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )
    }).filter(Boolean)
  }, [data])

  return (
    <div className="page ups_info_page">
      <div className="page_header">
        <div className="page_title">
          <h1>UPS Information</h1>
        </div>
      </div>

      <div className="stats_grid ups_info_grid">
        {cards}
        {cards.length === 0 && isLoading ? (
          <div className="stat_card ups_info_card">
            <div className="stat-content">
              <div className="stat-header">
                <span className="stat-label">Loading UPS data...</span>
              </div>
            </div>
          </div>
        ) : null}
      </div>
    </div>
  )
}
