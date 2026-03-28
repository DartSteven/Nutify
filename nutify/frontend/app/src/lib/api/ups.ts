/**
 * Ups.
 *
 * Frontend module used by Nutify React UI flows and state management.
 */

import { z } from 'zod'

import { requestJson, withTarget } from './client'

const columnEnvelope = z.object({
  success: z.boolean(),
  data: z.record(z.string(), z.union([z.string(), z.number(), z.null()])),
})

const allDataSchema = z.object({
  success: z.boolean(),
  data: z.record(z.string(), z.unknown()),
})

const tableDynamicSchema = z.object({
  success: z.boolean(),
  rows: z.array(z.record(z.string(), z.unknown())).optional(),
})

export type TimeseriesPoint = {
  timestamp: number
  value: number
}

export type MainHistory = {
  realPower: TimeseriesPoint[]
  systemLoad: TimeseriesPoint[]
}

function toTimestamp(value: unknown): number {
  if (typeof value === 'number') {
    return Number.isFinite(value) ? value : Date.now()
  }

  if (typeof value === 'string') {
    const parsed = Date.parse(value)
    if (Number.isFinite(parsed)) {
      return parsed
    }
  }

  return Date.now()
}

function toNumeric(value: unknown): number | null {
  const numeric = Number(value)
  if (!Number.isFinite(numeric)) {
    return null
  }
  return numeric
}

export async function getColumnValue(column: string, targetId: number | null): Promise<string | number | null> {
  const url = withTarget(`/api/data/${column}`, targetId)
  const payload = await requestJson(url, columnEnvelope)
  return payload.data[column] ?? null
}

export async function getAllUpsData(targetId: number | null): Promise<Record<string, unknown>> {
  const url = withTarget('/api/data/all', targetId)
  const payload = await requestJson(url, allDataSchema)
  return payload.data
}

export async function getMainHistory(targetId: number | null, rows = 240): Promise<MainHistory> {
  const url = withTarget(`/api/table/dynamic?rows=${rows}`, targetId)
  const payload = await requestJson(url, tableDynamicSchema)
  const sourceRows = Array.isArray(payload.rows) ? payload.rows : []

  const realPower: TimeseriesPoint[] = []
  const systemLoad: TimeseriesPoint[] = []

  for (const row of sourceRows) {
    const timestamp = toTimestamp(row.timestamp_utc ?? row.timestamp)

    const power = toNumeric(row.ups_realpower ?? row.ups_power)
    if (power !== null) {
      realPower.push({ timestamp, value: power })
    }

    const load = toNumeric(row.ups_load)
    if (load !== null) {
      systemLoad.push({ timestamp, value: load })
    }
  }

  realPower.sort((a, b) => a.timestamp - b.timestamp)
  systemLoad.sort((a, b) => a.timestamp - b.timestamp)

  return { realPower, systemLoad }
}
