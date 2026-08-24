/**
 * Voltagepagesupport.
 *
 * Frontend module used by Nutify React UI flows and state management.
 */

import { formatChartAxisTimestamp } from '../../lib/utils/chartDateTime'

export type Point = {
  timestamp: number
  value: number
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

export function formatVoltageTime(
  value: number | string,
  timezone: string,
  includeDate = false,
): string {
  return formatChartAxisTimestamp(value, timezone, includeDate)
}

export function lastPositiveValue(points: Array<{ value: number }>): number | null {
  for (let index = points.length - 1; index >= 0; index -= 1) {
    const value = Number(points[index]?.value)
    if (Number.isFinite(value) && value > 0) {
      return value
    }
  }
  return null
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

export function parseMetricsPayload(payload: unknown): Record<string, unknown> {
  return asRecord(asRecord(payload).data)
}

export function parseHistoryPayload(payload: unknown): Record<string, Point[]> {
  const source = asRecord(asRecord(payload).data)
  return {
    input_voltage: parseHistorySeries(source.input_voltage),
    output_voltage: parseHistorySeries(source.output_voltage),
    input_voltage_nominal: parseHistorySeries(source.input_voltage_nominal),
    input_transfer_low: parseHistorySeries(source.input_transfer_low),
    input_transfer_high: parseHistorySeries(source.input_transfer_high),
  }
}

export function metricCurrent(metrics: Record<string, unknown>, history: Record<string, Point[]>, key: string) {
  const direct = Number(metrics[key])
  if (Number.isFinite(direct)) {
    return direct
  }

  const values = history[key]
  if (!Array.isArray(values) || values.length === 0) {
    return 0
  }
  return values[values.length - 1].value
}

export function buildHistoryQuery(period: {
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
