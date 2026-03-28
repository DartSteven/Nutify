/** Utility types and format helpers for Multi-UPS monitoring views. */

export type OverviewRow = {
  target: Record<string, unknown>
  summary: Record<string, unknown>
  latestMetrics: Record<string, unknown>
  latest: Record<string, unknown>
  channels: Record<string, unknown>
}

export type MapHealthState = 'online' | 'on_battery' | 'warning' | 'critical' | 'offline'

export type RuntimeRow = OverviewRow & {
  targetId: number
  status: {
    isOnline: boolean
    label: string
    rawStatus: string
  }
  healthState: MapHealthState
  locationCountry: string
  locationCity: string
  locationLabel: string
  locationLatitude: number | null
  locationLongitude: number | null
  batteryValue: number | null
  runtimeValue: number | null
  powerValue: number | null
  loadValue: number | null
}

export const ALL_LOCATIONS = 'ALL'

export function asNumber(value: unknown): number | null {
  const numeric = Number(value)
  if (!Number.isFinite(numeric)) {
    return null
  }
  return numeric
}

export function asText(value: unknown): string {
  if (value === null || value === undefined) {
    return '-'
  }
  return String(value)
}

export function asRecord(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    return {}
  }
  return value as Record<string, unknown>
}

export function parseJsonRecord(value: unknown): Record<string, unknown> {
  if (typeof value !== 'string' || !value.trim()) {
    return {}
  }
  try {
    const parsed = JSON.parse(value) as unknown
    return asRecord(parsed)
  } catch {
    return {}
  }
}

export function lookupMetric(sources: Record<string, unknown>[], metric: string): unknown {
  const dottedMetric = metric.replaceAll('_', '.')
  for (const source of sources) {
    if (source[metric] !== undefined && source[metric] !== null) {
      return source[metric]
    }
    if (source[dottedMetric] !== undefined && source[dottedMetric] !== null) {
      return source[dottedMetric]
    }
  }
  return null
}

export function formatRuntimeSeconds(value: unknown): string {
  const numeric = Number(value)
  if (!Number.isFinite(numeric)) {
    return '--'
  }
  const totalSeconds = Math.max(0, Math.floor(numeric))
  const totalMinutes = Math.floor(totalSeconds / 60)
  const seconds = totalSeconds % 60
  if (totalMinutes >= 60) {
    const hours = Math.floor(totalMinutes / 60)
    const minutes = totalMinutes % 60
    return `${hours}h ${minutes}m`
  }
  return `${totalMinutes}m ${seconds}s`
}

export function formatPercent(value: unknown): string {
  const numeric = Number(value)
  if (!Number.isFinite(numeric)) {
    return '--'
  }
  return `${numeric.toFixed(1)}%`
}

export function formatWatts(value: unknown): string {
  const numeric = Number(value)
  if (!Number.isFinite(numeric)) {
    return '--'
  }
  return `${numeric.toFixed(1)}W`
}

export function statusState(rawValue: unknown): { isOnline: boolean; label: string; rawStatus: string } {
  const rawStatus = String(rawValue ?? 'UNKNOWN').trim() || 'UNKNOWN'
  const normalized = rawStatus.toUpperCase()
  const offlineMarkers = ['ERROR', 'NOCOMM', 'TIMEOUT', 'COMMBAD', 'UNREACHABLE', 'OFFLINE', 'UNKNOWN']
  const isOffline = offlineMarkers.some((marker) => normalized.includes(marker))
  return {
    isOnline: !isOffline,
    label: isOffline ? 'Offline' : 'Online',
    rawStatus,
  }
}

export function resolveMapHealthState(rawStatus: string, isOnline: boolean, batteryValue: number | null): MapHealthState {
  if (!isOnline) {
    return 'offline'
  }

  const normalized = String(rawStatus || '').toUpperCase()
  const markers = new Set(normalized.split(/[\s,;|]+/).filter(Boolean))
  if (markers.has('LB') || markers.has('FSD') || markers.has('RB') || (batteryValue !== null && batteryValue <= 15)) {
    return 'critical'
  }
  if (markers.has('OB')) {
    return 'on_battery'
  }

  const warningMarkers = ['OVER', 'OVERLOAD', 'BYPASS', 'TRIM', 'BOOST', 'CAL', 'REPLACEBATT', 'CHRG']
  if (warningMarkers.some((marker) => normalized.includes(marker)) || (batteryValue !== null && batteryValue <= 30)) {
    return 'warning'
  }

  return 'online'
}

export function formatCost(summary: Record<string, unknown>): string {
  const cost = Number(summary.cost)
  if (!Number.isFinite(cost)) {
    return '--'
  }
  const currency = String(summary.currency ?? 'EUR')
  return `${cost.toFixed(4)} ${currency}`
}

export function channelBadge(label: string, enabled: boolean) {
  const style = enabled
    ? { background: 'rgba(46, 204, 113, 0.16)', color: '#2ecc71' }
    : { background: 'rgba(231, 76, 60, 0.16)', color: '#e74c3c' }
  return (
    <span className="multi_channel_badge" style={style}>
      <i className={`fas ${enabled ? 'fa-check-circle' : 'fa-times-circle'}`} aria-hidden="true" /> {label}
    </span>
  )
}

export function normalizeLocationValue(value: unknown): string {
  return String(value ?? '').trim()
}

export function normalizeCoordinate(value: unknown, minimum: number, maximum: number): number | null {
  const numeric = Number(value)
  if (!Number.isFinite(numeric)) {
    return null
  }
  if (numeric < minimum || numeric > maximum) {
    return null
  }
  return numeric
}
