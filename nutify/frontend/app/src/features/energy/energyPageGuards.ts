/**
 * Energypageguards.
 *
 * Frontend module used by Nutify React UI flows and state management.
 */

export function parseHasHourData(payload: unknown): boolean {
  if (!payload || typeof payload !== 'object') {
    return false
  }

  const directValue = (payload as { has_data?: unknown }).has_data
  if (typeof directValue === 'boolean') {
    return directValue
  }

  const nestedValue = (payload as { data?: { has_data?: unknown } }).data?.has_data
  if (typeof nestedValue === 'boolean') {
    return nestedValue
  }

  return false
}

export function notifyRealtimeModeEnforced() {
  const notifyFn = (window as Window & { notify?: (text: string, level: string, timeout?: number) => void }).notify
  if (typeof notifyFn === 'function') {
    notifyFn(
      'Real Time mode enforced: waiting for 1 hour of data collection. You can switch to other modes from the time range menu.',
      'warning',
      5000,
    )
  }
}
