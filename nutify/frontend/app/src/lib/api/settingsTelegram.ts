/**
 * Settings Telegram API.
 *
 * API wrappers for Telegram provider configuration and notification routing.
 */

import { requestSettingsJson, type JsonRecord } from './settingsShared'

export async function getTelegramConfigs(_targetId: number | null) {
  void _targetId
  return requestSettingsJson('/api/telegram/configs')
}

export async function saveTelegramConfig(input: JsonRecord, _targetId: number | null) {
  void _targetId
  return requestSettingsJson(
    '/api/telegram/config',
    {
      method: 'POST',
      body: JSON.stringify(input),
    },
  )
}

export async function deleteTelegramConfig(configId: number, _targetId: number | null) {
  void _targetId
  return requestSettingsJson(`/api/telegram/config/${configId}`, { method: 'DELETE' })
}

export async function getTelegramConfig(configId: number, _targetId: number | null) {
  void _targetId
  return requestSettingsJson(`/api/telegram/config/${configId}`)
}

export async function testTelegramConfig(configId: number, targetId: number | null) {
  return requestSettingsJson(`/api/telegram/test/${configId}`, { method: 'POST' }, targetId)
}

export async function testTelegramConfigEvent(configId: number, eventType: string, targetId: number | null) {
  return requestSettingsJson(
    `/api/telegram/test/${configId}?event_type=${encodeURIComponent(eventType)}`,
    { method: 'POST' },
    targetId,
  )
}

export async function setTelegramDefaultConfig(configId: number, _targetId: number | null) {
  void _targetId
  return requestSettingsJson(`/api/telegram/config/${configId}/default`, { method: 'POST' })
}

export async function testTelegramRawConfig(input: JsonRecord, targetId: number | null) {
  return requestSettingsJson(
    '/api/telegram/test',
    {
      method: 'POST',
      body: JSON.stringify(input),
    },
    targetId,
  )
}

export async function getTelegramNotificationSettings(targetId: number | null) {
  return requestSettingsJson('/api/telegram/settings', {}, targetId)
}

export async function saveTelegramNotificationSetting(
  input: { event_type: string; enabled: boolean; config_id: number | null },
  targetId: number | null,
) {
  return requestSettingsJson(
    '/api/telegram/setting',
    {
      method: 'POST',
      body: JSON.stringify(input),
    },
    targetId,
  )
}
