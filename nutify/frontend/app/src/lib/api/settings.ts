/**
 * Settings.
 *
 * Frontend module used by Nutify React UI flows and state management.
 */

import { requestSettingsJson, type JsonRecord } from './settingsShared'

export type VariableConfig = {
  timezone?: string
  ups_realpower_nominal?: number | null
  currency: string
  price_per_kwh: number
  co2_factor: number
  polling_interval?: number
  target_id: number | null
  scope_target_id: number | null
}

export type OperationSettings = {
  measured_power_metric_key: string
  load_metric_key: string
  nominal_power_metric_key: string
  realpower_formula: string
  power_calibration_factor: number
  energy_formula: string
  cost_formula: string
  co2_formula: string
  target_id: number | null
  scope_target_id: number | null
}

function parseNullableNumber(value: unknown): number | null {
  if (value === null || value === undefined || value === '') {
    return null
  }
  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed : null
}

export async function getVariableConfig(targetId: number | null): Promise<VariableConfig> {
  const payload = await requestSettingsJson('/api/settings/variables', {}, targetId)
  const data = (payload.data ?? {}) as JsonRecord
  return {
    timezone: typeof data.timezone === 'string' ? data.timezone : undefined,
    ups_realpower_nominal: parseNullableNumber(data.ups_realpower_nominal),
    currency: String(data.currency ?? 'EUR'),
    price_per_kwh: Number(data.price_per_kwh ?? 0),
    co2_factor: Number(data.co2_factor ?? 0),
    polling_interval: Number.isFinite(Number(data.polling_interval)) ? Number(data.polling_interval) : undefined,
    target_id: parseNullableNumber(data.target_id),
    scope_target_id: parseNullableNumber(data.scope_target_id),
  }
}

export async function saveVariableConfig(
  input: {
    currency: string
    price_per_kwh: number
    co2_factor: number
    timezone?: string
    ups_realpower_nominal?: number | null
  },
  targetId: number | null,
) {
  return requestSettingsJson(
    '/api/settings/variables',
    {
      method: 'POST',
      body: JSON.stringify(input),
    },
    targetId,
  )
}

export async function getOperationSettings(targetId: number | null): Promise<OperationSettings> {
  const payload = await requestSettingsJson('/api/settings/operations', {}, targetId)
  const data = (payload.data ?? {}) as JsonRecord
  return {
    measured_power_metric_key: String(data.measured_power_metric_key ?? 'ups_realpower'),
    load_metric_key: String(data.load_metric_key ?? 'ups_load'),
    nominal_power_metric_key: String(data.nominal_power_metric_key ?? 'ups_realpower_nominal'),
    realpower_formula: String(data.realpower_formula ?? '(load_percent / 100.0) * nominal_power_w'),
    power_calibration_factor: Number(data.power_calibration_factor ?? 1.0),
    energy_formula: String(data.energy_formula ?? 'power_w * delta_hours'),
    cost_formula: String(data.cost_formula ?? '(energy_wh / 1000.0) * price_per_kwh'),
    co2_formula: String(data.co2_formula ?? '(energy_wh / 1000.0) * co2_factor'),
    target_id: parseNullableNumber(data.target_id),
    scope_target_id: parseNullableNumber(data.scope_target_id),
  }
}

export async function saveOperationSettings(input: Partial<OperationSettings>, targetId: number | null) {
  return requestSettingsJson(
    '/api/settings/operations',
    {
      method: 'POST',
      body: JSON.stringify(input),
    },
    targetId,
  )
}

export async function updatePollingInterval(pollingInterval: number) {
  return requestSettingsJson('/api/settings/polling-interval', {
    method: 'POST',
    body: JSON.stringify({ polling_interval: pollingInterval }),
  })
}

export async function getInitialSetupOptions() {
  return requestSettingsJson('/api/options/options-from-initial-setup')
}

export async function saveInitialSetupOptions(input: {
  server_name: string
  timezone: string
  monitoring_profile?: 'single' | 'multi'
  ups_realpower_nominal?: number | null
}) {
  return requestSettingsJson('/api/options/options-from-initial-setup', {
    method: 'POST',
    body: JSON.stringify(input),
  })
}

export async function getDatabaseStats() {
  return requestSettingsJson('/api/database/stats')
}

export async function optimizeDatabase() {
  return requestSettingsJson('/api/database/optimize', { method: 'POST' })
}

export async function vacuumDatabase() {
  return requestSettingsJson('/api/database/vacuum', { method: 'POST' })
}

export function getDatabaseBackupDownloadUrl() {
  return '/api/database/backup'
}

export type LogsQuery = {
  type?: string
  level?: string
  range?: string
  page?: number
  page_size?: number
}

function buildLogQuery(params: LogsQuery): string {
  const query = new URLSearchParams()
  if (params.type) query.set('type', params.type)
  if (params.level) query.set('level', params.level)
  if (params.range) query.set('range', params.range)
  if (typeof params.page === 'number') query.set('page', String(params.page))
  if (typeof params.page_size === 'number') query.set('page_size', String(params.page_size))
  return query.toString()
}

export async function getLogs(params: LogsQuery = {}) {
  const query = buildLogQuery(params)
  const url = query ? `/api/logs?${query}` : '/api/logs'
  return requestSettingsJson(url)
}

export async function clearLogs(type = 'all') {
  return requestSettingsJson(`/api/logs/clear?type=${encodeURIComponent(type)}`, { method: 'POST' })
}

export function getLogsDownloadUrl(params: LogsQuery = {}) {
  const query = buildLogQuery(params)
  return query ? `/api/logs/download?${query}` : '/api/logs/download'
}

export async function getSystemInfo() {
  return requestSettingsJson('/api/system/info')
}

export type ScriptActionConfig = {
  id: number
  target_id?: number | null
  name: string
  enabled: boolean
  trigger_event: 'ONBATT' | 'LOWBATT'
  battery_threshold: number
  cooldown_seconds: number
  script_body: string
  last_executed_at?: string | null
  last_exit_code?: number | null
  last_output?: string | null
  condition_active?: boolean
}

export async function getScriptActions(targetId: number | null) {
  return requestSettingsJson('/api/options/script-actions', {}, targetId)
}

export async function createScriptAction(input: Partial<ScriptActionConfig>, targetId: number | null) {
  return requestSettingsJson('/api/options/script-actions', {
    method: 'POST',
    body: JSON.stringify(input),
  }, targetId)
}

export async function updateScriptAction(actionId: number, input: Partial<ScriptActionConfig>, targetId: number | null) {
  return requestSettingsJson(`/api/options/script-actions/${actionId}`, {
    method: 'PUT',
    body: JSON.stringify(input),
  }, targetId)
}

export async function deleteScriptAction(actionId: number, targetId: number | null) {
  return requestSettingsJson(`/api/options/script-actions/${actionId}`, {
    method: 'DELETE',
  }, targetId)
}

export async function testScriptAction(actionId: number, targetId: number | null) {
  return requestSettingsJson(`/api/options/script-actions/${actionId}/test`, {
    method: 'POST',
  }, targetId)
}

export async function getAboutImage() {
  return requestSettingsJson('/api/about/image')
}

export async function getLogSettings() {
  return requestSettingsJson('/api/settings/log')
}

export async function saveLogSettings(input: { log: boolean; level: string; werkzeug: boolean }) {
  return requestSettingsJson('/api/settings/log', {
    method: 'POST',
    body: JSON.stringify(input),
  })
}

export async function getAdvancedNutFiles() {
  return requestSettingsJson('/api/advanced/nut/files')
}

export async function getAdvancedNutConfig(filename: string) {
  return requestSettingsJson(`/api/advanced/nut/config/${encodeURIComponent(filename)}`)
}

export async function saveAdvancedNutConfig(filename: string, content: string) {
  return requestSettingsJson(`/api/advanced/nut/config/${encodeURIComponent(filename)}`, {
    method: 'POST',
    body: JSON.stringify({ content }),
  })
}

export async function restartAdvancedNutServices() {
  return requestSettingsJson('/api/advanced/nut/restart', { method: 'POST' })
}

export async function getAdvancedNutDocs(filename: string) {
  return requestSettingsJson(`/api/advanced/nut/docs/${encodeURIComponent(filename)}`)
}

export async function getMailConfigs(_targetId: number | null) {
  return requestSettingsJson('/api/settings/mail/all')
}

export async function getMailConfig(_targetId: number | null) {
  return requestSettingsJson('/api/settings/mail')
}

export async function getMailConfigById(configId: number, _targetId: number | null) {
  return requestSettingsJson(`/api/settings/mail/${configId}`)
}

export async function getMailProviders(_targetId: number | null) {
  return requestSettingsJson('/api/settings/mail/providers')
}

export async function getMailProviderConfig(provider: string, _targetId: number | null) {
  return requestSettingsJson(`/api/settings/mail/providers/${encodeURIComponent(provider)}`)
}

export async function saveMailConfig(input: JsonRecord, _targetId: number | null) {
  return requestSettingsJson(
    '/api/settings/mail',
    {
      method: 'POST',
      body: JSON.stringify(input),
    },
  )
}

export async function updateMailConfigEnabled(configId: number, enabled: boolean, _targetId: number | null) {
  return requestSettingsJson(
    '/api/settings/mail',
    {
      method: 'POST',
      body: JSON.stringify({
        id: configId,
        enabled,
        update_enabled_only: true,
      }),
    },
  )
}

export async function updateMailConfig(configId: number, input: JsonRecord, _targetId: number | null) {
  return requestSettingsJson(
    `/api/settings/mail/${configId}`,
    {
      method: 'PUT',
      body: JSON.stringify(input),
    },
  )
}

export async function deleteMailConfig(configId: number, _targetId: number | null) {
  return requestSettingsJson(`/api/settings/mail/${configId}`, { method: 'DELETE' })
}

export async function testMailConfig(configId: number, toEmail: string, _targetId: number | null) {
  return requestSettingsJson(
    `/api/settings/mail/${configId}/test`,
    {
      method: 'POST',
      body: JSON.stringify({ to_email: toEmail, is_test: true }),
    },
  )
}

export async function testMailRawConfig(input: JsonRecord, _targetId: number | null) {
  return requestSettingsJson(
    '/api/settings/mail/test',
    {
      method: 'POST',
      body: JSON.stringify(input),
    },
  )
}

export async function getNotificationSettings(targetId: number | null) {
  return requestSettingsJson('/api/settings/nutify', {}, targetId)
}

export async function getNotificationSettingsByEmail(emailId: number, targetId: number | null) {
  return requestSettingsJson(`/api/settings/nutify/by-email/${emailId}`, {}, targetId)
}

export async function updateNotificationSetting(
  eventType: string,
  enabled: boolean,
  idEmail: number | null,
  targetId: number | null,
) {
  return requestSettingsJson(
    '/api/settings/nutify/single',
    {
      method: 'POST',
      body: JSON.stringify({
        event_type: eventType,
        enabled,
        id_email: idEmail,
      }),
    },
    targetId,
  )
}

export async function updateNotificationSettingsBatch(
  input: Array<{ event_type: string; enabled: boolean; id_email: number | null }>,
  targetId: number | null,
) {
  return requestSettingsJson(
    '/api/settings/nutify',
    {
      method: 'POST',
      body: JSON.stringify(input),
    },
    targetId,
  )
}

export async function testEmailNotification(eventType: string, idEmail: number, targetId: number | null) {
  return requestSettingsJson(
    `/api/settings/test-notification?event_type=${encodeURIComponent(eventType)}&id_email=${encodeURIComponent(String(idEmail))}`,
    {
      method: 'POST',
    },
    targetId,
  )
}

export type ReportSchedulePayload = {
  id?: number
  time: string
  days: number[]
  reports: string[]
  email?: string
  mail_config_id: number
  period_type: string
  from_date?: string | null
  to_date?: string | null
  enabled?: boolean
}

export async function getReportSchedules(targetId: number | null) {
  return requestSettingsJson('/api/settings/report/schedules', {}, targetId)
}

export async function getReportSchedule(scheduleId: number, targetId: number | null) {
  return requestSettingsJson(`/api/settings/report/schedules/${scheduleId}`, {}, targetId)
}

export async function createReportSchedule(payload: ReportSchedulePayload, targetId: number | null) {
  return requestSettingsJson(
    '/api/settings/report/schedules',
    {
      method: 'POST',
      body: JSON.stringify(payload),
    },
    targetId,
  )
}

export async function updateReportSchedule(
  scheduleId: number,
  payload: Partial<ReportSchedulePayload>,
  targetId: number | null,
) {
  return requestSettingsJson(
    `/api/settings/report/schedules/${scheduleId}`,
    {
      method: 'PUT',
      body: JSON.stringify(payload),
    },
    targetId,
  )
}

export async function deleteReportSchedule(scheduleId: number, targetId: number | null) {
  return requestSettingsJson(
    `/api/settings/report/schedules/${scheduleId}`,
    {
      method: 'DELETE',
    },
    targetId,
  )
}

export async function testReportSchedule(
  payload: Omit<ReportSchedulePayload, 'time' | 'days'>,
  targetId: number | null,
) {
  return requestSettingsJson(
    '/api/settings/report/schedules/test',
    {
      method: 'POST',
      body: JSON.stringify(payload),
    },
    targetId,
  )
}

export * from './settingsNtfy'
export * from './settingsTelegram'
export * from './settingsWebhook'
