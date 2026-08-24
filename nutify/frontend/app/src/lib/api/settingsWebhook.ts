/**
 * Settings Webhook API.
 *
 * API wrappers for webhook provider configuration and notification routing.
 */

import { requestSettingsJson, type JsonRecord } from './settingsShared'

export async function getWebhookConfigs(_targetId: number | null) {
  void _targetId
  return requestSettingsJson('/api/webhook/configs')
}

export async function saveWebhookConfig(input: JsonRecord, _targetId: number | null) {
  void _targetId
  return requestSettingsJson(
    '/api/webhook/config',
    {
      method: 'POST',
      body: JSON.stringify(input),
    },
  )
}

export async function updateWebhookConfig(configId: number, input: JsonRecord, _targetId: number | null) {
  void _targetId
  return requestSettingsJson(
    `/api/webhook/config/${configId}`,
    {
      method: 'POST',
      body: JSON.stringify(input),
    },
  )
}

export async function deleteWebhookConfig(configId: number, _targetId: number | null) {
  void _targetId
  return requestSettingsJson(`/api/webhook/config/${configId}`, { method: 'DELETE' })
}

export async function testWebhookConfig(configId: number, targetId: number | null) {
  return requestSettingsJson(`/api/webhook/test/${configId}`, { method: 'POST' }, targetId)
}

export async function getWebhookConfig(configId: number, _targetId: number | null) {
  void _targetId
  return requestSettingsJson(`/api/webhook/config/${configId}`)
}

export async function testWebhookConfigEvent(configId: number, eventType: string, targetId: number | null) {
  return requestSettingsJson(
    `/api/webhook/test/${configId}?event_type=${encodeURIComponent(eventType)}`,
    {
      method: 'POST',
    },
    targetId,
  )
}

export async function setWebhookDefaultConfig(configId: number, _targetId: number | null) {
  void _targetId
  return requestSettingsJson(`/api/webhook/config/${configId}/default`, { method: 'POST' })
}

export async function testWebhookRawConfig(input: JsonRecord, targetId: number | null) {
  return requestSettingsJson(
    '/api/webhook/test',
    {
      method: 'POST',
      body: JSON.stringify(input),
    },
    targetId,
  )
}

export async function getWebhookNotificationSettings(targetId: number | null) {
  return requestSettingsJson('/api/webhook/settings', {}, targetId)
}

export async function saveWebhookNotificationSetting(
  input: { event_type: string; enabled: boolean; config_id: number | null },
  targetId: number | null,
) {
  return requestSettingsJson(
    '/api/webhook/setting',
    {
      method: 'POST',
      body: JSON.stringify(input),
    },
    targetId,
  )
}
