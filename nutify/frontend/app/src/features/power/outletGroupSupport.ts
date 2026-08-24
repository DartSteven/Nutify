import { aggregateSeries, asNullableNumber, asNumber, asRecord, type ApexPoint, type MetricStats } from './powerPageSupport'

export type OutletGroup = {
  key: string
  label: string
  current: number
  available: boolean
  stats: MetricStats
  series: ApexPoint[]
}

export type OutletGroupsPayload = {
  groups: OutletGroup[]
  hasData: boolean
}

const OUTLET_REALPOWER_RE = /^outlet(?:[._][a-z0-9-]+)*[._]realpower$/i

function defaultStats(): MetricStats {
  return {
    min: 0,
    max: 0,
    avg: 0,
    current: 0,
    available: false,
  }
}

function canonicalOutletKey(key: string): string {
  return key.trim().toLowerCase().replace(/\./g, '_').replace(/_+/g, '_').replace(/^_|_$/g, '')
}

function outletLabel(key: string): string {
  const parts = canonicalOutletKey(key).split('_').slice(1, -1)
  return parts.length ? `Outlet ${parts.join(' ')}` : 'Outlet Total'
}

function parseStats(value: unknown): MetricStats {
  const row = asRecord(value)
  return {
    min: asNumber(row.min),
    max: asNumber(row.max),
    avg: asNumber(row.avg),
    current: asNumber(row.current),
    available: Boolean(row.available),
  }
}

function parseSeries(value: unknown): ApexPoint[] {
  if (!Array.isArray(value)) {
    return []
  }
  return value
    .map((item) => {
      const row = asRecord(item)
      return { x: asNumber(row.timestamp), y: asNumber(row.value) }
    })
    .filter((point) => point.x > 0)
}

export function parseOutletGroupsPayload(payload: unknown): OutletGroupsPayload {
  const data = asRecord(asRecord(payload).data)
  const groupsRaw = Array.isArray(data.groups) ? data.groups : []
  const groups = groupsRaw
    .map((item) => {
      const row = asRecord(item)
      const key = canonicalOutletKey(String(row.key ?? ''))
      if (!OUTLET_REALPOWER_RE.test(key)) {
        return null
      }
      const stats = parseStats(row.stats)
      return {
        key,
        label: String(row.label ?? outletLabel(key)),
        current: asNumber(row.current),
        available: Boolean(row.available),
        stats,
        series: parseSeries(row.series),
      }
    })
    .filter((item): item is OutletGroup => item !== null)

  return {
    groups,
    hasData: Boolean(data.has_data) || groups.some((group) => group.available || group.series.length > 0),
  }
}

export function extractRealtimeOutletGroups(payload: Record<string, unknown>): OutletGroup[] {
  return Object.entries(payload)
    .map((entry): OutletGroup | null => {
      const [rawKey, value] = entry
      const key = canonicalOutletKey(rawKey)
      const current = asNullableNumber(value)
      if (!OUTLET_REALPOWER_RE.test(key) || current === null) {
        return null
      }
      return {
        key,
        label: outletLabel(key),
        current,
        available: true,
        stats: defaultStats(),
        series: [],
      }
    })
    .filter((item): item is OutletGroup => item !== null)
}

export function mergeOutletGroups(serverGroups: OutletGroup[], realtimeGroups: OutletGroup[]): OutletGroup[] {
  const merged = new Map<string, OutletGroup>()
  for (const group of serverGroups) {
    merged.set(group.key, group)
  }
  for (const group of realtimeGroups) {
    const existing = merged.get(group.key)
    merged.set(group.key, existing ? { ...existing, current: group.current, available: true } : group)
  }
  return [...merged.values()]
}

export function outletChartSeries(groups: OutletGroup[]) {
  return groups
    .filter((group) => group.series.length > 0)
    .map((group) => ({
      name: group.label,
      data: aggregateSeries(group.series),
    }))
}
