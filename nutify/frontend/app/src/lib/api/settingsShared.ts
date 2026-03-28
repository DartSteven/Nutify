/**
 * Settings Shared API Helpers.
 *
 * Shared request helpers and common types for settings API modules.
 */

import { withTarget } from './client'

export type JsonRecord = Record<string, unknown>

export async function requestSettingsJson(
  url: string,
  options: RequestInit = {},
  targetId: number | null = null,
): Promise<JsonRecord> {
  const response = await fetch(withTarget(url, targetId), {
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
      `HTTP ${response.status}`
    throw new Error(message)
  }
  return payload
}
