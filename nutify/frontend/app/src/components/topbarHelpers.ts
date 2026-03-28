/**
 * Topbar Helpers.
 *
 * Shared formatting and status helpers for topbar state derivation.
 */

export type HeaderMetrics = {
  batteryCharge: string
  load: string
  power: string
  status: string
  serial: string
}

export type SystemStats = {
  cpu: string
  ram: string
}

export const INITIAL_METRICS: HeaderMetrics = {
  batteryCharge: '-',
  load: '-',
  power: '-',
  status: 'Unknown',
  serial: 'S/N: Unknown',
}

export const INITIAL_SYSTEM_STATS: SystemStats = {
  cpu: '--',
  ram: '--',
}

export function pickFirstMetricValue(
  payload: Record<string, unknown>,
  keys: string[],
): string | number | null {
  for (const key of keys) {
    const value = payload[key]
    if (value === undefined || value === null) {
      continue
    }
    if (typeof value === 'string' && value.trim().length === 0) {
      continue
    }
    if (typeof value === 'number' && !Number.isFinite(value)) {
      continue
    }
    return value as string | number
  }
  return null
}

export function formatUpsStatus(status: string | null): string {
  if (!status) {
    return 'Unknown'
  }

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
    OVER: 'Overload',
    TRIM: 'Trim',
    BOOST: 'Boost',
  }

  return status
    .split(' ')
    .filter((token) => token.trim().length > 0)
    .map((token) => states[token] ?? token)
    .join(' ')
}

export function isOfflineStatus(status: string | null | undefined): boolean {
  const normalized = String(status ?? '').trim().toUpperCase()
  if (!normalized) {
    return false
  }

  const offlineMarkers = ['ERROR', 'NOCOMM', 'TIMEOUT', 'UNREACHABLE', 'OFFLINE']
  return offlineMarkers.some((marker) => normalized.includes(marker))
}

export function isAttentionStatus(status: string | null | undefined): boolean {
  const normalized = String(status ?? '').trim().toUpperCase()
  if (!normalized || isOfflineStatus(normalized)) {
    return false
  }

  const warningMarkers = [
    'OB',
    'ONBATT',
    'LB',
    'LOWBATT',
    'RB',
    'REPLBATT',
    'COMMBAD',
    'NOPARENT',
    'COMMLOST',
    'OVERLOAD',
    'OVERHEAT',
    'ALARM',
    'FSD',
    'SHUTDOWN',
    'BYPASS',
    'OVER',
  ]
  return warningMarkers.some((marker) => normalized.includes(marker))
}

export function asRecord(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    return {}
  }
  return value as Record<string, unknown>
}
