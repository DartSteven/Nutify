/**
 * Timepreferences.
 *
 * Frontend module used by Nutify React UI flows and state management.
 */

export type ClockFormatPreference = 'ampm' | '24h'

export const CLOCK_FORMAT_STORAGE_KEY = 'nutify.clock.format'
export const CLOCK_FORMAT_EVENT = 'nutify:clock-format-changed'

function normalizeClockFormat(value: unknown): ClockFormatPreference {
  const normalized = String(value ?? '').trim().toLowerCase()
  if (normalized === 'ampm' || normalized === '12h') {
    return 'ampm'
  }
  return '24h'
}

export function getClockFormatPreference(): ClockFormatPreference {
  if (typeof window === 'undefined') {
    return '24h'
  }
  return normalizeClockFormat(window.localStorage.getItem(CLOCK_FORMAT_STORAGE_KEY))
}

export function setClockFormatPreference(value: ClockFormatPreference): ClockFormatPreference {
  const normalized = normalizeClockFormat(value)
  if (typeof window === 'undefined') {
    return normalized
  }
  window.localStorage.setItem(CLOCK_FORMAT_STORAGE_KEY, normalized)
  window.dispatchEvent(
    new CustomEvent(CLOCK_FORMAT_EVENT, {
      detail: { format: normalized },
    }),
  )
  return normalized
}
