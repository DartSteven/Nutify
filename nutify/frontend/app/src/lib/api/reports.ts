/**
 * Reports.
 *
 * Frontend module used by Nutify React UI flows and state management.
 */

import { withTarget } from './client'

type JsonRecord = Record<string, unknown>

async function requestReportsJson(url: string, options: RequestInit = {}): Promise<JsonRecord> {
  const response = await fetch(url, {
    credentials: 'same-origin',
    headers: {
      'Content-Type': 'application/json',
      ...(options.headers ?? {}),
    },
    ...options,
  })

  const payload = (await response.json().catch(() => ({}))) as JsonRecord
  if (!response.ok) {
    const message =
      (typeof payload.error === 'string' && payload.error) ||
      (typeof payload.message === 'string' && payload.message) ||
      (typeof payload.status === 'string' && payload.status === 'error' && typeof payload.message === 'string'
        ? payload.message
        : '') ||
      `HTTP ${response.status}`
    throw new Error(message)
  }
  return payload
}

export async function generateReport(input: {
  from_date: string
  to_date: string
  report_type: string
}, targetId: number | null = null) {
  return requestReportsJson(withTarget('/api/report/generate', targetId), {
    method: 'POST',
    body: JSON.stringify(input),
  })
}

export async function sendReport(input: {
  from_date: string
  to_date: string
  report_type: string
  recipients: string[]
}, targetId: number | null = null) {
  return requestReportsJson(withTarget('/api/report/send', targetId), {
    method: 'POST',
    body: JSON.stringify(input),
  })
}

export async function listReportSchedules(targetId: number | null = null) {
  return requestReportsJson(withTarget('/api/settings/report/schedules', targetId))
}

export async function getReportSchedule(scheduleId: number, targetId: number | null = null) {
  return requestReportsJson(withTarget(`/api/settings/report/schedules/${scheduleId}`, targetId))
}

export type SaveScheduleInput = {
  reports: string[]
  period_type: string
  days?: number[]
  time?: string
  email?: string | null
  mail_config_id: number
  enabled?: boolean
  from_date?: string
  to_date?: string
}

export async function createReportSchedule(input: SaveScheduleInput, targetId: number | null = null) {
  return requestReportsJson(withTarget('/api/settings/report/schedules', targetId), {
    method: 'POST',
    body: JSON.stringify(input),
  })
}

export async function updateReportSchedule(
  scheduleId: number,
  input: Partial<SaveScheduleInput>,
  targetId: number | null = null,
) {
  return requestReportsJson(withTarget(`/api/settings/report/schedules/${scheduleId}`, targetId), {
    method: 'PUT',
    body: JSON.stringify(input),
  })
}

export async function deleteReportSchedule(scheduleId: number, targetId: number | null = null) {
  return requestReportsJson(withTarget(`/api/settings/report/schedules/${scheduleId}`, targetId), {
    method: 'DELETE',
  })
}

export async function testReportSchedule(input: SaveScheduleInput, targetId: number | null = null) {
  return requestReportsJson(withTarget('/api/settings/report/schedules/test', targetId), {
    method: 'POST',
    body: JSON.stringify(input),
  })
}
