/**
 * Mainpagesupport.
 *
 * Frontend module used by Nutify React UI flows and state management.
 */

import type { TimeseriesPoint } from '../../lib/api/ups'

export type MainSeries = {
  realPower: TimeseriesPoint[]
  systemLoad: TimeseriesPoint[]
}

export type MainEvent = {
  event_type: string
  timestamp_utc_begin: string | null
  acknowledged: boolean
}

export type AlertGroup = {
  eventType: string
  channels: Array<'email' | 'ntfy' | 'telegram' | 'webhook'>
}

export type ActiveSchedule = {
  id: number
  time: string
  days: number[]
  reports: string[]
  enabled: boolean
}

export type MainPanelData = {
  events: MainEvent[]
  alerts: AlertGroup[]
  schedules: ActiveSchedule[]
}

export type NotificationRow = {
  event_type: string
  enabled: boolean
  channel: 'email' | 'ntfy' | 'telegram' | 'webhook'
}

export const BUFFER_SIZE = 15
export const MAX_POINTS = 100
export const CHART_WINDOW_MS = 60_000
export const FALLBACK_LOAD = 25
export const SYNTHETIC_POINT_COUNT = 60

const EVENT_LABELS: Record<string, string> = {
  ONBATT: 'On Battery',
  ONLINE: 'Online',
  LOWBATT: 'Low Battery',
  COMMOK: 'Communication OK',
  COMMBAD: 'Communication Lost',
  SHUTDOWN: 'Shutdown',
  REPLBATT: 'Replace Battery',
  NOCOMM: 'No Communication',
  NOPARENT: 'No Parent',
}

const EVENT_ICONS: Record<string, string> = {
  ONBATT: 'fas fa-battery-quarter',
  ONLINE: 'fas fa-plug',
  LOWBATT: 'fas fa-battery-empty',
  COMMOK: 'fas fa-check-circle',
  COMMBAD: 'fas fa-times-circle',
  NOCOMM: 'fas fa-wifi-slash',
  SHUTDOWN: 'fas fa-power-off',
  REPLBATT: 'fas fa-exclamation-triangle',
}

const ALERT_SEVERITY: Record<string, string> = {
  LOWBATT: 'critical',
  ONBATT: 'warning',
  COMMBAD: 'critical',
  NOCOMM: 'critical',
  SHUTDOWN: 'critical',
  REPLBATT: 'warning',
  NOPARENT: 'warning',
}

export function asRecord(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    return {}
  }
  return value as Record<string, unknown>
}

export function toNumber(value: unknown): number | null {
  const numeric = Number(value)
  return Number.isFinite(numeric) ? numeric : null
}

export function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value))
}

export function appendPoint(points: TimeseriesPoint[], point: TimeseriesPoint): TimeseriesPoint[] {
  const next = [...points, point].sort((a, b) => a.timestamp - b.timestamp)
  if (next.length <= MAX_POINTS) {
    return next
  }
  return next.slice(next.length - MAX_POINTS)
}

export function getLastKnownPowerValue(): number {
  const cached = window.localStorage.getItem('lastPowerValue')
  const parsed = toNumber(cached)
  return parsed !== null ? parsed : 100
}

export function generateSyntheticSeries(now: number, basePower: number, baseLoad: number): MainSeries {
  const realPower: TimeseriesPoint[] = []
  const systemLoad: TimeseriesPoint[] = []
  const points = SYNTHETIC_POINT_COUNT
  const stepMs = Math.floor(CHART_WINDOW_MS / Math.max(points, 1))
  const safePowerBase = Math.max(basePower, 1)
  const safeLoadBase = clamp(baseLoad, 0, 100)

  for (let index = points; index > 0; index -= 1) {
    const timestamp = now - index * stepMs
    const powerWave = Math.sin(index / 8) * (safePowerBase * 0.04)
    const powerDrift = Math.cos(index / 5) * (safePowerBase * 0.03)
    const loadWave = Math.sin(index / 9) * 1.5
    const loadDrift = Math.cos(index / 7) * 1.2

    const powerValue = Math.max(1, safePowerBase + powerWave + powerDrift)
    const loadValue = clamp(safeLoadBase + loadWave + loadDrift, 0, 100)

    realPower.push({ timestamp, value: Number(powerValue.toFixed(4)) })
    systemLoad.push({ timestamp, value: Number(loadValue.toFixed(4)) })
  }

  return { realPower, systemLoad }
}

export function calculateSmoothedValue(buffer: TimeseriesPoint[]): number {
  if (!buffer.length) {
    return 0
  }

  const weights = buffer.map((_, index) => Math.pow(1.2, index))
  const weightSum = weights.reduce((sum, current) => sum + current, 0)
  const weightedTotal = buffer.reduce((sum, point, index) => sum + point.value * weights[index], 0)
  return weightedTotal / weightSum
}

export function formatMetricValue(type: 'battery' | 'runtime' | 'power' | 'load', value: unknown): string {
  const numeric = toNumber(value)
  if (numeric === null) {
    return '--'
  }

  if (type === 'battery' || type === 'load') {
    return `${numeric.toFixed(1)} %`
  }

  if (type === 'runtime') {
    return `${Math.round(numeric / 60)} min`
  }

  if (numeric >= 1000) {
    return `${(numeric / 1000).toFixed(2)} kW`
  }

  return `${numeric.toFixed(1)} W`
}

export function formatEventType(eventType: string): string {
  if (!eventType) {
    return 'Unknown'
  }
  return EVENT_LABELS[eventType] ?? eventType
}

export function getEventIcon(eventType: string): string {
  return EVENT_ICONS[eventType] ?? 'fas fa-info-circle'
}

export function getAlertSeverity(eventType: string): string {
  return ALERT_SEVERITY[eventType] ?? 'info'
}

export function getAlertIcon(severity: string): string {
  if (severity === 'critical') {
    return 'fas fa-exclamation-circle'
  }
  if (severity === 'warning') {
    return 'fas fa-exclamation-triangle'
  }
  return 'fas fa-info-circle'
}

export function getChannelIcon(channel: 'email' | 'ntfy' | 'telegram' | 'webhook'): string {
  if (channel === 'email') {
    return 'fas fa-paper-plane'
  }
  if (channel === 'ntfy') {
    return 'fas fa-bell'
  }
  if (channel === 'telegram') {
    return 'fab fa-telegram-plane'
  }
  return 'fas fa-code'
}

export function formatScheduleDays(days: number[]): string {
  const dayNames = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']
  return days.map((day) => dayNames[day] ?? '?').join(', ')
}

export function formatEventTime(value: string | null, timezone: string): string {
  if (!value) {
    return 'N/A'
  }

  let normalized = value
  if (!normalized.endsWith('Z') && !normalized.match(/[+-]\d{2}:\d{2}$/)) {
    normalized = `${normalized}Z`
  }

  const parsed = new Date(normalized)
  if (Number.isNaN(parsed.getTime())) {
    return 'Invalid Date'
  }

  return parsed.toLocaleString(undefined, { timeZone: timezone })
}

export function convertUtcTimeToLocal(utcTime: string, timezone: string): string {
  const [hourRaw, minuteRaw] = utcTime.split(':')
  const hour = Number(hourRaw)
  const minute = Number(minuteRaw)
  if (!Number.isFinite(hour) || !Number.isFinite(minute)) {
    return utcTime
  }

  const now = new Date()
  const utcDate = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate(), hour, minute, 0))

  return new Intl.DateTimeFormat(undefined, {
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
    timeZone: timezone,
  }).format(utcDate)
}
