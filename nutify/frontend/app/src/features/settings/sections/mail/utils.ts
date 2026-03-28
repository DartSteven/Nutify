/**
 * Utils.
 *
 * Frontend module used by Nutify React UI flows and state management.
 */

import type {
  MailConfigRow,
  NotificationSelection,
  NotificationSelections,
  ProviderMap,
  ReportScheduleRow,
  ReportSettingsState,
  ScheduleFormState,
} from './types'
import { LEGACY_NOTIFICATION_EVENTS } from '../shared/notificationEvents'

type JsonRecord = Record<string, unknown>

export function notifyUser(message: string, tone: 'success' | 'error' | 'info'): void {
  const unsafeWindow = window as unknown as {
    notify?: (text: string, level: string, timeout?: number) => void
  }
  if (typeof unsafeWindow.notify === 'function') {
    unsafeWindow.notify(message, tone, 5000)
  }
}

export function normalizeMailConfigs(payload: unknown): MailConfigRow[] {
  if (!payload || typeof payload !== 'object') {
    return []
  }
  const rows = (payload as { data?: unknown }).data
  if (!Array.isArray(rows)) {
    return []
  }
  return rows
    .map((row) => {
      if (!row || typeof row !== 'object') {
        return null
      }
      const entry = row as JsonRecord
      const id = Number(entry.id)
      if (!Number.isFinite(id)) {
        return null
      }
      return {
        id,
        smtp_server: String(entry.smtp_server ?? ''),
        smtp_port: String(entry.smtp_port ?? ''),
        username: String(entry.username ?? ''),
        enabled: Boolean(entry.enabled),
        provider: String(entry.provider ?? ''),
        render_mode: String(entry.render_mode ?? 'graphic'),
        tls: Boolean(entry.tls),
        tls_starttls: Boolean(entry.tls_starttls),
        to_email: String(entry.to_email ?? ''),
      } satisfies MailConfigRow
    })
    .filter((row): row is MailConfigRow => row !== null)
}

export function normalizeProviderMap(payload: unknown): ProviderMap {
  if (!payload || typeof payload !== 'object') {
    return {}
  }
  const map = (payload as { providers?: unknown }).providers
  if (!map || typeof map !== 'object') {
    return {}
  }
  return map as ProviderMap
}

export function normalizeNotificationSelections(payload: unknown): NotificationSelections {
  const initial: NotificationSelections = {}
  LEGACY_NOTIFICATION_EVENTS.forEach((eventMeta) => {
    initial[eventMeta.eventType] = { enabled: false, configId: '' }
  })
  if (!payload || typeof payload !== 'object') {
    return initial
  }
  const rows = (payload as { data?: unknown }).data
  if (!Array.isArray(rows)) {
    return initial
  }
  rows.forEach((row) => {
    if (!row || typeof row !== 'object') {
      return
    }
    const entry = row as JsonRecord
    const eventType = String(entry.event_type ?? '').toUpperCase()
    if (!eventType) {
      return
    }
    initial[eventType] = {
      enabled: Boolean(entry.enabled),
      configId: Number.isFinite(Number(entry.id_email)) ? String(entry.id_email) : '',
    } satisfies NotificationSelection
  })
  return initial
}

export function normalizeSchedules(payload: unknown): ReportScheduleRow[] {
  if (!payload || typeof payload !== 'object') {
    return []
  }
  const rows = (payload as { data?: unknown }).data
  if (!Array.isArray(rows)) {
    return []
  }
  return rows
    .map((row) => {
      if (!row || typeof row !== 'object') {
        return null
      }
      const entry = row as JsonRecord
      const id = Number(entry.id)
      if (!Number.isFinite(id)) {
        return null
      }
      const daysRaw = Array.isArray(entry.days) ? entry.days : []
      const reportsRaw = Array.isArray(entry.reports) ? entry.reports : []
      return {
        id,
        time: String(entry.time ?? ''),
        days: daysRaw.map((day) => Number(day)).filter((day) => Number.isFinite(day)),
        reports: reportsRaw.map((report) => String(report)).filter(Boolean),
        email: entry.email ? String(entry.email) : null,
        mail_config_id: Number.isFinite(Number(entry.mail_config_id)) ? Number(entry.mail_config_id) : null,
        period_type: String(entry.period_type ?? 'yesterday'),
        from_date: entry.from_date ? String(entry.from_date) : null,
        to_date: entry.to_date ? String(entry.to_date) : null,
        enabled: Boolean(entry.enabled),
      } satisfies ReportScheduleRow
    })
    .filter((row): row is ReportScheduleRow => row !== null)
}

export function providerDisplayName(providerKey: string, providers: ProviderMap): string {
  if (!providerKey) {
    return 'Custom'
  }
  const provider = providers[providerKey]
  if (provider?.displayName) {
    return provider.displayName
  }
  return providerKey
}

export function emailOptionLabel(config: MailConfigRow, providers: ProviderMap): string {
  const provider = providerDisplayName(config.provider, providers)
  const recipient = config.to_email || 'No recipient'
  return `${config.id} - ${provider} - ${recipient}`
}

export function parseScheduleTimeToLocal(utcTime: string): string {
  if (!utcTime || !utcTime.includes(':')) {
    return utcTime
  }
  const [hoursRaw, minutesRaw] = utcTime.split(':')
  const hours = Number(hoursRaw)
  const minutes = Number(minutesRaw)
  if (!Number.isFinite(hours) || !Number.isFinite(minutes)) {
    return utcTime
  }
  const now = new Date()
  const utcDate = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate(), hours, minutes, 0))
  const localHours = String(utcDate.getHours()).padStart(2, '0')
  const localMinutes = String(utcDate.getMinutes()).padStart(2, '0')
  return `${localHours}:${localMinutes}`
}

export function formatScheduleDays(days: number[]): string {
  const shortDays = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']
  const sorted = [...days].sort((a, b) => a - b)
  if (sorted.length === 0) {
    return 'No days selected'
  }
  if (sorted.length === 7) {
    return 'Every day'
  }
  if (sorted.length === 5 && !sorted.includes(0) && !sorted.includes(6)) {
    return 'Weekdays'
  }
  if (sorted.length === 2 && sorted.includes(0) && sorted.includes(6)) {
    return 'Weekends'
  }
  return sorted.map((day) => shortDays[day] ?? '').filter(Boolean).join(', ')
}

export function formatSchedulePeriod(schedule: ReportScheduleRow): string {
  const periodType = schedule.period_type || 'daily'
  if (periodType === 'daily') {
    return 'Daily'
  }
  if (periodType === 'range') {
    const from = schedule.from_date ? new Date(schedule.from_date).toLocaleDateString() : 'N/A'
    const to = schedule.to_date ? new Date(schedule.to_date).toLocaleDateString() : 'N/A'
    return `Range: ${from} to ${to}`
  }
  return periodType.charAt(0).toUpperCase() + periodType.slice(1)
}

export function createDefaultReportSettings(): ReportSettingsState {
  const today = new Date()
  const yesterday = new Date(today)
  yesterday.setDate(today.getDate() - 1)
  return {
    selectedReports: [],
    fromDate: yesterday.toISOString().split('T')[0],
    toDate: today.toISOString().split('T')[0],
    mailConfigId: '',
  }
}

export function fillScheduleForm(schedule: ReportScheduleRow): ScheduleFormState {
  return {
    editId: schedule.id,
    selectedDays: Array.isArray(schedule.days) ? [...schedule.days] : [],
    time: parseScheduleTimeToLocal(schedule.time || ''),
    reports: Array.isArray(schedule.reports) ? [...schedule.reports] : [],
    periodType:
      schedule.period_type === 'range' ||
      schedule.period_type === 'yesterday' ||
      schedule.period_type === 'last_week' ||
      schedule.period_type === 'last_month'
        ? schedule.period_type
        : 'yesterday',
    rangeFromDate: schedule.from_date ? schedule.from_date.split('T')[0] : '',
    rangeToDate: schedule.to_date ? schedule.to_date.split('T')[0] : '',
    mailConfigId: schedule.mail_config_id ? String(schedule.mail_config_id) : '',
  }
}

export function toggleListNumber(values: number[], value: number): number[] {
  if (values.includes(value)) {
    return values.filter((item) => item !== value)
  }
  return [...values, value]
}

export function toggleListString(values: string[], value: string): string[] {
  if (values.includes(value)) {
    return values.filter((item) => item !== value)
  }
  return [...values, value]
}
