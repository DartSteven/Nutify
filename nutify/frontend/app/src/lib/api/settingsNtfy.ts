/**
 * Settings Ntfy API.
 *
 * API wrappers for ntfy provider configuration and notification routing.
 */

import { requestSettingsJson, type JsonRecord } from './settingsShared'

export async function getNtfyConfigs(_targetId: number | null) {
  return requestSettingsJson('/api/ntfy/configs')
}

export async function saveNtfyConfig(input: JsonRecord, _targetId: number | null) {
  return requestSettingsJson(
    '/api/ntfy/config',
    {
      method: 'POST',
      body: JSON.stringify(input),
    },
  )
}

export async function deleteNtfyConfig(configId: number, _targetId: number | null) {
  return requestSettingsJson(`/api/ntfy/config/${configId}`, { method: 'DELETE' })
}

export async function getNtfyConfig(configId: number, _targetId: number | null) {
  return requestSettingsJson(`/api/ntfy/config/${configId}`)
}

export async function testNtfyConfig(configId: number, _targetId: number | null) {
  return requestSettingsJson(`/api/ntfy/test/${configId}`, { method: 'POST' })
}

export async function testNtfyConfigEvent(configId: number, eventType: string, _targetId: number | null) {
  return requestSettingsJson(
    `/api/ntfy/test/${configId}?event_type=${encodeURIComponent(eventType)}`,
    { method: 'POST' },
  )
}

export async function setNtfyDefaultConfig(configId: number, _targetId: number | null) {
  return requestSettingsJson(`/api/ntfy/config/${configId}/default`, { method: 'POST' })
}

export async function testNtfyRawConfig(input: JsonRecord, _targetId: number | null) {
  return requestSettingsJson(
    '/api/ntfy/test',
    {
      method: 'POST',
      body: JSON.stringify(input),
    },
  )
}

export async function getNtfyNotificationSettings(targetId: number | null) {
  return requestSettingsJson('/api/ntfy/settings', {}, targetId)
}

export async function saveNtfyNotificationSetting(
  input: { event_type: string; enabled: boolean; config_id: number | null },
  targetId: number | null,
) {
  return requestSettingsJson(
    '/api/ntfy/setting',
    {
      method: 'POST',
      body: JSON.stringify(input),
    },
    targetId,
  )
}
