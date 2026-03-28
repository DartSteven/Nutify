/**
 * Powerpagesupport.
 *
 * Frontend module used by Nutify React UI flows and state management.
 */

export type MetricStats = {
  min: number
  max: number
  avg: number
  current: number
  available: boolean
}

export type Point = {
  timestamp: number
  value: number
}

export type ApexPoint = {
  x: number
  y: number
}

export function asNumber(value: unknown, fallback = 0) {
  const numeric = Number(value)
  if (!Number.isFinite(numeric)) {
    return fallback
  }
  return numeric
}

export function asNullableNumber(value: unknown) {
  const numeric = Number(value)
  if (!Number.isFinite(numeric)) {
    return null
  }
  return numeric
}

export function asRecord(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    return {}
  }
  return value as Record<string, unknown>
}

export function defaultStats(): MetricStats {
  return {
    min: 0,
    max: 0,
    avg: 0,
    current: 0,
    available: false,
  }
}

function parseStatsEntry(value: unknown): MetricStats {
  const row = asRecord(value)
  return {
    min: asNumber(row.min),
    max: asNumber(row.max),
    avg: asNumber(row.avg),
    current: asNumber(row.current),
    available: Boolean(row.available),
  }
}

export function parseStatsPayload(payload: unknown): Record<string, MetricStats> {
  const source = asRecord(asRecord(payload).data)
  const result: Record<string, MetricStats> = {}
  for (const [key, value] of Object.entries(source)) {
    result[key] = parseStatsEntry(value)
  }
  return result
}

export function parseMetricsPayload(payload: unknown): Record<string, unknown> {
  return asRecord(asRecord(payload).data)
}

function parseHistorySeries(value: unknown): Point[] {
  if (!Array.isArray(value)) {
    return []
  }
  return value
    .map((item) => {
      const row = asRecord(item)
      return {
        timestamp: asNumber(row.timestamp),
        value: asNumber(row.value),
      }
    })
    .filter((point) => point.timestamp > 0)
}

export function parseHistoryPayload(payload: unknown) {
  const source = asRecord(asRecord(payload).data)
  return {
    realPower: parseHistorySeries(source.ups_realpower),
    inputVoltage: parseHistorySeries(source.input_voltage),
  }
}

export function aggregateSeries(points: ApexPoint[], maxPoints = 1200): ApexPoint[] {
  if (points.length <= maxPoints) {
    return points
  }

  if (maxPoints <= 2) {
    return [points[0], points[points.length - 1]]
  }

  const interior = points.slice(1, -1)
  if (interior.length === 0) {
    return points.slice(0, maxPoints)
  }

  const bucketCount = Math.max(1, Math.floor((maxPoints - 2) / 2))
  const bucketSize = Math.max(1, Math.ceil(interior.length / bucketCount))
  const sampled: ApexPoint[] = [points[0]]

  for (let start = 0; start < interior.length; start += bucketSize) {
    const bucket = interior.slice(start, start + bucketSize)
    if (!bucket.length) {
      continue
    }
    const low = bucket.reduce((best, current) => (current.y < best.y ? current : best), bucket[0])
    const high = bucket.reduce((best, current) => (current.y > best.y ? current : best), bucket[0])
    if (low.x <= high.x) {
      sampled.push(low)
      if (high !== low) {
        sampled.push(high)
      }
    } else {
      sampled.push(high)
      if (low !== high) {
        sampled.push(low)
      }
    }
  }

  sampled.push(points[points.length - 1])
  const sorted = [...sampled].sort((a, b) => a.x - b.x)
  const deduped = new Map<number, ApexPoint>()
  for (const point of sorted) {
    deduped.set(point.x, point)
  }
  const compact = [...deduped.values()]
  if (compact.length <= maxPoints) {
    return compact
  }

  const middle = compact.slice(1, -1)
  const keepMiddle = maxPoints - 2
  const step = Math.max(1, Math.ceil(middle.length / keepMiddle))
  return [compact[0], ...middle.filter((_, index) => index % step === 0).slice(0, keepMiddle), compact[compact.length - 1]]
}

export function readCurrent(stats: Record<string, MetricStats>, metrics: Record<string, unknown>, key: string) {
  const stat = stats[key]
  if (stat && stat.available) {
    return stat.current
  }
  return asNumber(metrics[key])
}

export function buildStatsQuery(period: {
  mode: 'realtime' | 'today' | 'day' | 'range'
  selectedDate: string
  rangeFrom: string
  rangeTo: string
  fromTime: string
  toTime: string
}, realtimeWindow: { fromTime: string; toTime: string }) {
  const params = new URLSearchParams()

  if (period.mode === 'realtime') {
    params.set('period', 'realtime')
    params.set('from_time', realtimeWindow.fromTime)
    params.set('to_time', realtimeWindow.toTime)
    return params
  }

  if (period.mode === 'day') {
    params.set('period', 'day')
    params.set('selected_date', period.selectedDate)
    return params
  }

  if (period.mode === 'range') {
    params.set('period', 'range')
    params.set('from_time', period.rangeFrom)
    params.set('to_time', period.rangeTo)
    return params
  }

  params.set('period', 'today')
  return params
}

export function buildHistoryQuery(period: {
  mode: 'realtime' | 'today' | 'day' | 'range'
  selectedDate: string
  rangeFrom: string
  rangeTo: string
  fromTime: string
  toTime: string
}) {
  const params = new URLSearchParams()

  if (period.mode === 'realtime') {
    params.set('period', 'realtime')
    return params
  }

  if (period.mode === 'day') {
    params.set('period', 'day')
    params.set('selected_day', period.selectedDate)
    return params
  }

  if (period.mode === 'range') {
    params.set('period', 'range')
    params.set('from_time', period.rangeFrom)
    params.set('to_time', period.rangeTo)
    return params
  }

  params.set('period', 'today')
  return params
}

export function readRealtimePower(payload: Record<string, unknown>): number | null {
  const direct = asNullableNumber(payload.ups_realpower)
  if (direct !== null) {
    return Math.max(direct, 0)
  }
  const fallback = asNullableNumber(payload.ups_power)
  if (fallback !== null) {
    return Math.max(fallback, 0)
  }
  return null
}
