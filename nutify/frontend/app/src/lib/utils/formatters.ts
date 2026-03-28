/**
 * Formatters.
 *
 * Frontend module used by Nutify React UI flows and state management.
 */

export function formatNumber(value: unknown, digits = 1): string {
  const numeric = Number(value)
  if (!Number.isFinite(numeric)) {
    return '-'
  }
  return numeric.toFixed(digits)
}

export function formatPercent(value: unknown, digits = 1): string {
  const numeric = Number(value)
  if (!Number.isFinite(numeric)) {
    return '-'
  }
  return `${numeric.toFixed(digits)}%`
}

export function formatWatts(value: unknown, digits = 1): string {
  const numeric = Number(value)
  if (!Number.isFinite(numeric)) {
    return '-'
  }
  return `${numeric.toFixed(digits)}W`
}

export function formatMinutes(value: unknown): string {
  const numeric = Number(value)
  if (!Number.isFinite(numeric)) {
    return '-'
  }

  const rounded = Math.max(0, Math.round(numeric / 60))
  return `${rounded} min`
}

export function formatClock(
  timestamp: number,
  timezone = 'UTC',
  mode: '24h' | 'ampm' = '24h',
): string {
  const useAmPm = mode === 'ampm'
  return new Intl.DateTimeFormat(useAmPm ? 'en-US' : 'en-GB', {
    hour: useAmPm ? 'numeric' : '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: useAmPm,
    hourCycle: useAmPm ? 'h12' : 'h23',
    timeZone: timezone,
  }).format(new Date(timestamp))
}
