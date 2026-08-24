/**
 * Mainpaneldata.
 *
 * Frontend module used by Nutify React UI flows and state management.
 */

import { fetchRawJson } from '../../lib/api/raw'
import { asRecord, type ActiveSchedule, type MainPanelData, type NotificationRow } from './mainPageSupport'

function parseMainPanelData(payload: {
  eventsPayload: unknown
  emailPayload: unknown
  ntfyPayload: unknown
  telegramPayload: unknown
  webhookPayload: unknown
  schedulePayload: unknown
}): MainPanelData {
  const eventsBody = asRecord(payload.eventsPayload)
  const eventRows = Array.isArray(eventsBody.rows) ? eventsBody.rows : []
  const events = eventRows.slice(0, 5).map((row) => {
    const value = asRecord(row)
    return {
      event_type: String(value.event_type ?? 'UNKNOWN'),
      timestamp_utc_begin: value.timestamp_utc_begin ? String(value.timestamp_utc_begin) : null,
      acknowledged: Boolean(value.acknowledged),
    }
  })

  const notifications: NotificationRow[] = []

  const emailBody = asRecord(payload.emailPayload)
  const emailRows = Array.isArray(emailBody.data) ? emailBody.data : []
  for (const row of emailRows) {
    const value = asRecord(row)
    notifications.push({
      event_type: String(value.event_type ?? ''),
      enabled: Boolean(value.enabled),
      channel: 'email',
    })
  }

  const ntfyBody = asRecord(payload.ntfyPayload)
  const ntfySettings = asRecord(ntfyBody.settings)
  for (const [eventType, settingValue] of Object.entries(ntfySettings)) {
    const setting = asRecord(settingValue)
    if (setting.enabled) {
      notifications.push({
        event_type: eventType,
        enabled: true,
        channel: 'ntfy',
      })
    }
  }

  const webhookBody = asRecord(payload.webhookPayload)
  const webhookSettings = asRecord(webhookBody.settings)
  for (const [eventType, settingValue] of Object.entries(webhookSettings)) {
    const setting = asRecord(settingValue)
    if (setting.enabled) {
      notifications.push({
        event_type: eventType,
        enabled: true,
        channel: 'webhook',
      })
    }
  }

  const telegramBody = asRecord(payload.telegramPayload)
  const telegramSettings = asRecord(telegramBody.settings)
  for (const [eventType, settingValue] of Object.entries(telegramSettings)) {
    const setting = asRecord(settingValue)
    if (setting.enabled) {
      notifications.push({
        event_type: eventType,
        enabled: true,
        channel: 'telegram',
      })
    }
  }

  const grouped = new Map<string, Set<'email' | 'ntfy' | 'telegram' | 'webhook'>>()
  for (const notification of notifications) {
    if (!notification.enabled || !notification.event_type) {
      continue
    }
    const existing = grouped.get(notification.event_type) ?? new Set<'email' | 'ntfy' | 'telegram' | 'webhook'>()
    existing.add(notification.channel)
    grouped.set(notification.event_type, existing)
  }

  const alerts = Array.from(grouped.entries()).map(([eventType, channels]) => ({
    eventType,
    channels: Array.from(channels),
  }))

  const scheduleBody = asRecord(payload.schedulePayload)
  const scheduleRows = Array.isArray(scheduleBody.data) ? scheduleBody.data : []
  const schedules: ActiveSchedule[] = scheduleRows
    .map((row) => {
      const value = asRecord(row)
      const reports = Array.isArray(value.reports)
        ? value.reports.map((report) => String(report))
        : typeof value.reports === 'string'
          ? value.reports.split(',').map((report) => report.trim()).filter((report) => report.length > 0)
          : []

      const days = Array.isArray(value.days) ? value.days.map((day) => Number(day)).filter(Number.isFinite) : []

      return {
        id: Number(value.id ?? 0),
        time: String(value.time ?? ''),
        days,
        reports,
        enabled: Boolean(value.enabled),
      }
    })
    .filter((schedule) => schedule.enabled)

  return { events, alerts, schedules }
}

export async function loadMainPanelData(targetId: number | null): Promise<MainPanelData> {
  const [eventsPayload, emailPayload, ntfyPayload, telegramPayload, webhookPayload, schedulePayload] = await Promise.all([
    fetchRawJson('/api/table/events?rows=5', targetId),
    fetchRawJson('/api/settings/nutify', targetId),
    fetchRawJson('/api/ntfy/settings', targetId).catch(() => ({ success: true, settings: {} })),
    fetchRawJson('/api/telegram/settings', targetId).catch(() => ({ success: true, settings: {} })),
    fetchRawJson('/api/webhook/settings', targetId).catch(() => ({ success: true, settings: {} })),
    fetchRawJson('/api/settings/report/schedules', targetId),
  ])

  return parseMainPanelData({
    eventsPayload,
    emailPayload,
    ntfyPayload,
    telegramPayload,
    webhookPayload,
    schedulePayload,
  })
}
