/**
 * Batterypagesupport.
 *
 * Frontend module used by Nutify React UI flows and state management.
 */

import type { BatteryHistoryPayload, BatteryPoint } from './batteryCharts'

export type MetricStats = {
  min: number
  max: number
  avg: number
  current: number
  available: boolean
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

function parseHistorySeries(value: unknown): BatteryPoint[] {
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

export function parseHistoryPayload(payload: unknown): BatteryHistoryPayload {
  const source = asRecord(asRecord(payload).data)
  return {
    charge: parseHistorySeries(source.battery_charge),
    runtime: parseHistorySeries(source.battery_runtime),
    voltage: parseHistorySeries(source.battery_voltage),
    temperature: parseHistorySeries(source.battery_temperature),
  }
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
