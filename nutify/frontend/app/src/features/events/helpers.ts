/**
 * Helpers.
 *
 * Frontend module used by Nutify React UI flows and state management.
 */

export type EventsApiRow = {
  id: number
  event_type: string
  acknowledged: boolean
  timestamp_utc_begin: string | null
  timestamp_utc_end: string | null
}

export type StatsSnapshot = {
  totalEvents: number
  todayEvents: number
  batteryTimeLabel: string
  lastEventLabel: string
}

export type NotificationPermission = 'default' | 'denied' | 'granted'

const EVENT_TYPE_LABELS: Record<string, string> = {
  ONBATT: 'On Battery',
  ONLINE: 'Online',
  LOWBATT: 'Low Battery',
  COMMOK: 'Comm OK',
  COMMBAD: 'Comm Bad',
  SHUTDOWN: 'Shutdown',
  REPLBATT: 'Replace Battery',
  NOCOMM: 'No Communication',
  NOPARENT: 'No Parent',
}

function asRecord(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    return {}
  }
  return value as Record<string, unknown>
}

function asArray(value: unknown): unknown[] {
  return Array.isArray(value) ? value : []
}

export function normalizeRows(payload: unknown): EventsApiRow[] {
  const body = asRecord(payload)
  const rows = asArray(body.rows)

  return rows
    .map((item) => {
      const row = asRecord(item)
      const id = Number(row.id ?? 0)
      if (!Number.isFinite(id) || id <= 0) {
        return null
      }
      return {
        id,
        event_type: String(row.event_type ?? ''),
        acknowledged: Boolean(row.acknowledged),
        timestamp_utc_begin: row.timestamp_utc_begin ? String(row.timestamp_utc_begin) : null,
        timestamp_utc_end: row.timestamp_utc_end ? String(row.timestamp_utc_end) : null,
      }
    })
    .filter((item): item is EventsApiRow => item !== null)
}

export function parseDate(timestamp: string | null): Date | null {
  if (!timestamp) {
    return null
  }

  let value = timestamp
  if (typeof value === 'string' && !value.endsWith('Z') && !value.match(/[+-]\d{2}:\d{2}$/)) {
    value = `${value}Z`
  }

  const date = new Date(value)
  if (Number.isNaN(date.getTime())) {
    return null
  }
  return date
}

export function formatEventType(eventType: string): string {
  return EVENT_TYPE_LABELS[eventType] ?? eventType
}

export function formatDateTime(timestamp: string | null, timezone: string): string {
  const date = parseDate(timestamp)
  if (!date) {
    return 'N/A'
  }

  try {
    return date.toLocaleString([], {
      timeZone: timezone,
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      hour12: false,
    })
  } catch {
    return date.toLocaleString()
  }
}

export function getEventDurationLabel(row: EventsApiRow): string {
  if (row.event_type !== 'ONBATT') {
    return ''
  }

  const start = parseDate(row.timestamp_utc_begin)
  const end = parseDate(row.timestamp_utc_end)

  if (!start) {
    return ''
  }
  if (!end) {
    return 'In progress...'
  }

  const diffInSeconds = Math.floor((end.getTime() - start.getTime()) / 1000)
  if (diffInSeconds < 0) {
    return 'Invalid duration'
  }
  const minutes = Math.floor(diffInSeconds / 60)
  const seconds = diffInSeconds % 60
  return `${minutes}m ${seconds}s`
}

function calculateBatteryTimeSeconds(rows: EventsApiRow[]): number {
  return rows.reduce((total, row) => {
    if (row.event_type !== 'ONBATT' || !row.timestamp_utc_end) {
      return total
    }

    const start = parseDate(row.timestamp_utc_begin)
    const end = parseDate(row.timestamp_utc_end)
    if (!start || !end) {
      return total
    }

    const diff = Math.floor((end.getTime() - start.getTime()) / 1000)
    return diff > 0 ? total + diff : total
  }, 0)
}

function formatDuration(seconds: number): string {
  const minutes = Math.floor(seconds / 60)
  const remainder = Math.floor(seconds % 60)
  return `${minutes}m ${remainder}s`
}

function buildDayKey(date: Date, timezone: string): string {
  try {
    return new Intl.DateTimeFormat('en-CA', {
      timeZone: timezone,
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
    }).format(date)
  } catch {
    return new Intl.DateTimeFormat('en-CA', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
    }).format(date)
  }
}

export function buildStats(rows: EventsApiRow[], timezone: string): StatsSnapshot {
  const todayKey = buildDayKey(new Date(), timezone)
  const todayEvents = rows.filter((row) => {
    const start = parseDate(row.timestamp_utc_begin)
    if (!start) {
      return false
    }
    return buildDayKey(start, timezone) === todayKey
  }).length

  const batterySeconds = calculateBatteryTimeSeconds(rows)
  const lastEventLabel = rows.length > 0 ? formatEventType(rows[0].event_type) : '-'

  return {
    totalEvents: rows.length,
    todayEvents,
    batteryTimeLabel: formatDuration(batterySeconds),
    lastEventLabel,
  }
}
