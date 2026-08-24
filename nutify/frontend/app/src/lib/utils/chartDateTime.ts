function asDate(value: number | string): Date | null {
  const timestamp = typeof value === 'number' ? value : Number(value)
  if (!Number.isFinite(timestamp)) {
    return null
  }
  const date = new Date(timestamp)
  return Number.isNaN(date.getTime()) ? null : date
}

function format(
  value: number | string,
  timezone: string,
  includeDate: boolean,
  includeSeconds: boolean,
): string {
  const date = asDate(value)
  if (!date) {
    return String(value)
  }
  const options: Intl.DateTimeFormatOptions = {
    timeZone: timezone,
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  }
  if (includeSeconds) {
    options.second = '2-digit'
  }
  if (includeDate) {
    options.year = 'numeric'
    options.month = '2-digit'
    options.day = '2-digit'
  }
  try {
    return new Intl.DateTimeFormat(undefined, options).format(date)
  } catch {
    delete options.timeZone
    return new Intl.DateTimeFormat(undefined, options).format(date)
  }
}

function localDateKey(value: number, timezone: string): string {
  const date = new Date(value)
  try {
    return new Intl.DateTimeFormat('en-CA', {
      timeZone: timezone,
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
    }).format(date)
  } catch {
    return `${date.getFullYear()}-${date.getMonth()}-${date.getDate()}`
  }
}

export function spansMultipleLocalDates(timestamps: number[], timezone: string): boolean {
  const valid = timestamps.filter(Number.isFinite)
  if (valid.length < 2) {
    return false
  }
  const min = Math.min(...valid)
  const max = Math.max(...valid)
  return localDateKey(min, timezone) !== localDateKey(max, timezone)
}

export function formatChartAxisTimestamp(
  value: number | string,
  timezone: string,
  includeDate: boolean,
): string {
  return format(value, timezone, includeDate, !includeDate)
}

export function formatCsvTimestamp(value: number | string, timezone: string): string {
  return format(value, timezone, true, true)
}
