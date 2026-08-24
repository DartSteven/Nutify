export type RollingPeriodPreset = 'last_week' | 'last_month' | 'last_year'

export const ROLLING_PERIOD_OPTIONS: Array<{ value: RollingPeriodPreset; label: string }> = [
  { value: 'last_week', label: 'Last 7 Days' },
  { value: 'last_month', label: 'Last 30 Days' },
  { value: 'last_year', label: 'Last 12 Months' },
]

export function toLocalIsoDate(date: Date): string {
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

function startOfRollingYear(today: Date): Date {
  const anniversary = new Date(today)
  anniversary.setFullYear(today.getFullYear() - 1)

  // setFullYear maps Feb 29 to March in non-leap years. Clamp to Feb 28 first.
  if (anniversary.getMonth() !== today.getMonth()) {
    anniversary.setDate(0)
  }
  anniversary.setDate(anniversary.getDate() + 1)
  return anniversary
}

export function resolveRollingPeriod(
  preset: RollingPeriodPreset,
  referenceDate = new Date(),
): { from: string; to: string } {
  const today = new Date(
    referenceDate.getFullYear(),
    referenceDate.getMonth(),
    referenceDate.getDate(),
  )
  const start = new Date(today)

  if (preset === 'last_week') {
    start.setDate(today.getDate() - 6)
  } else if (preset === 'last_month') {
    start.setDate(today.getDate() - 29)
  } else {
    return { from: toLocalIsoDate(startOfRollingYear(today)), to: toLocalIsoDate(today) }
  }

  return { from: toLocalIsoDate(start), to: toLocalIsoDate(today) }
}
