/**
 * Energypagesupport.
 *
 * Frontend module used by Nutify React UI flows and state management.
 */

import type { PeriodMode, PeriodSelection } from '../../components/PeriodToolbar'

export type CostDistribution = {
  morning: number
  afternoon: number
  evening: number
  night: number
}

export type EnergySummary = {
  totalEnergyWh: number
  totalCost: number
  averageLoad: number
  co2Kg: number
  currencyCode: string
  currencySymbol: string
  distribution: CostDistribution
}

export type RealtimeEnergyMetrics = {
  powerWatts: number
  loadPercent: number
  totalCost: number
  co2Kg: number
}

export type EnergyBucketLevel = 'month' | 'day' | 'hour' | 'minute'

export type EnergySeriesPoint = {
  x: number
  y: number
  level?: EnergyBucketLevel
  nextLevel?: EnergyBucketLevel | null
  fromIso?: string
  toIso?: string
  title?: string
}

export type EnergyDetailWindow = {
  fromIso: string
  toIso: string
  level: EnergyBucketLevel
  title: string
}

const DEFAULT_DISTRIBUTION: CostDistribution = {
  morning: 0,
  afternoon: 0,
  evening: 0,
  night: 0,
}

const CURRENCY_SYMBOLS: Record<string, string> = {
  EUR: '€',
  USD: '$',
  GBP: '£',
  JPY: '¥',
  AUD: 'A$',
  CAD: 'C$',
  CHF: 'Fr',
  CNY: '¥',
  INR: '₹',
  NZD: 'NZ$',
  BRL: 'R$',
  RUB: '₽',
  KRW: '₩',
  PLN: 'PLN',
}

const CURRENCY_ICONS: Record<string, string> = {
  EUR: 'fa-euro-sign',
  USD: 'fa-dollar-sign',
  GBP: 'fa-pound-sign',
  JPY: 'fa-yen-sign',
  CNY: 'fa-yen-sign',
  CHF: 'fa-franc-sign',
  INR: 'fa-rupee-sign',
  RUB: 'fa-ruble-sign',
  KRW: 'fa-won-sign',
}

export function asNumber(value: unknown, fallback = 0): number {
  const numeric = Number(value)
  if (!Number.isFinite(numeric)) {
    return fallback
  }
  return numeric
}

function normalizeTimestampMs(value: unknown): number {
  if (typeof value === 'string') {
    const trimmed = value.trim()
    if (!trimmed) {
      return -1
    }

    const numeric = Number(trimmed)
    if (Number.isFinite(numeric) && numeric > 0) {
      const normalized = numeric < 1_000_000_000_000 ? numeric * 1000 : numeric
      return Math.round(normalized)
    }

    const parsedDate = Date.parse(trimmed)
    if (Number.isFinite(parsedDate) && parsedDate > 0) {
      return Math.round(parsedDate)
    }

    return -1
  }

  const numeric = asNumber(value, -1)
  if (!Number.isFinite(numeric) || numeric <= 0) {
    return -1
  }

  const normalized = numeric < 1_000_000_000_000 ? numeric * 1000 : numeric
  return Math.round(normalized)
}

function normalizeBucketLevel(value: unknown): EnergyBucketLevel | undefined {
  const normalized = String(value ?? '').trim().toLowerCase()
  if (normalized === 'month' || normalized === 'day' || normalized === 'hour' || normalized === 'minute') {
    return normalized
  }
  return undefined
}

function nextBucketLevel(level: EnergyBucketLevel): EnergyBucketLevel | null {
  if (level === 'month') {
    return 'day'
  }
  if (level === 'day') {
    return 'hour'
  }
  if (level === 'hour') {
    return 'minute'
  }
  return null
}

function pad2(value: number): string {
  return String(value).padStart(2, '0')
}

export function asRecord(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    return {}
  }
  return value as Record<string, unknown>
}

export function normalizeCurrencyCode(value: unknown, fallback = 'EUR'): string {
  const raw = String(value ?? '').trim().toUpperCase()
  if (!raw) {
    return fallback
  }
  if (raw === '€') return 'EUR'
  if (raw === '$') return 'USD'
  if (raw === '£') return 'GBP'
  if (raw === '¥') return 'JPY'
  if (raw === '₽') return 'RUB'
  if (raw === '₩') return 'KRW'
  if (raw === '₹') return 'INR'
  if (raw === 'FR') return 'CHF'
  return raw
}

export function getCurrencySymbol(currencyCode: string): string {
  return CURRENCY_SYMBOLS[currencyCode] ?? currencyCode
}

export function getCurrencyIcon(currencyCode: string): string {
  const normalized = normalizeCurrencyCode(currencyCode)
  return CURRENCY_ICONS[normalized] ?? 'fa-dollar-sign'
}

export function parseSummary(payload: unknown, fallbackCurrencyCode = 'EUR'): EnergySummary {
  const body = asRecord(payload)
  const source = body.data && typeof body.data === 'object' ? asRecord(body.data) : body
  const distributionSource = asRecord(source.cost_distribution)
  const currencyCode = normalizeCurrencyCode(source.currency, fallbackCurrencyCode)
  const symbolCandidate = String(source.currency_symbol ?? '').trim()
  const currencySymbol = symbolCandidate || getCurrencySymbol(currencyCode)

  return {
    totalEnergyWh: asNumber(source.totalEnergy ?? source.total_energy),
    totalCost: asNumber(source.totalCost ?? source.total_cost),
    averageLoad: asNumber(source.avgLoad ?? source.avg_load),
    co2Kg: asNumber(source.co2),
    currencyCode,
    currencySymbol,
    distribution: {
      morning: asNumber(distributionSource.morning),
      afternoon: asNumber(distributionSource.afternoon),
      evening: asNumber(distributionSource.evening),
      night: asNumber(distributionSource.night),
    },
  }
}

function parseSeriesPoint(value: unknown): EnergySeriesPoint | null {
  if (Array.isArray(value)) {
    if (value.length < 2) {
      return null
    }
    const x = normalizeTimestampMs(value[0])
    const y = asNumber(value[1])
    if (x <= 0) {
      return null
    }
    return { x, y }
  }

  const row = asRecord(value)
  const x = normalizeTimestampMs(row.x ?? row.timestamp ?? row.time ?? row.ts)
  const y = asNumber(row.y ?? row.value ?? row.cost ?? row.energy_cost)
  if (x <= 0) {
    return null
  }

  const level = normalizeBucketLevel(row.level)
  const nextLevel = normalizeBucketLevel(row.next_level ?? row.nextLevel)
  const fromIso = String(row.from_iso ?? row.fromIso ?? '').trim() || undefined
  const toIso = String(row.to_iso ?? row.toIso ?? '').trim() || undefined
  const title = String(row.title ?? '').trim() || undefined

  return {
    x,
    y,
    level,
    nextLevel: nextLevel ?? null,
    fromIso,
    toIso,
    title,
  }
}

export function parseSeries(payload: unknown): EnergySeriesPoint[] {
  const body = asRecord(payload)
  const nestedData = asRecord(body.data)
  const nestedSeries = nestedData.series
  const rawSeries = Array.isArray(body.series)
    ? body.series
    : Array.isArray(nestedSeries)
      ? nestedSeries
      : Array.isArray(body.data)
        ? body.data
        : nestedSeries && typeof nestedSeries === 'object'
          ? Object.values(nestedSeries as Record<string, unknown>)
          : []

  return rawSeries
    .map((item) => parseSeriesPoint(item))
    .filter((point): point is EnergySeriesPoint => Boolean(point))
}

export function parseChartPoint(value: unknown): EnergySeriesPoint | null {
  return parseSeriesPoint(value)
}

function buildPeriodQuery(period: PeriodSelection): URLSearchParams {
  const params = new URLSearchParams()

  if (period.mode === 'realtime') {
    const window = createRealtimeWindow()
    params.set('type', 'realtime')
    params.set('from_time', window.fromTime)
    params.set('to_time', window.toTime)
    return params
  }

  if (period.mode === 'day') {
    params.set('type', 'day')
    params.set('selected_date', period.selectedDate)
    return params
  }

  if (period.mode === 'range') {
    params.set('type', 'range')
    params.set('from_time', period.rangeFrom)
    params.set('to_time', period.rangeTo)
    return params
  }

  params.set('type', 'today')
  return params
}

export function buildDataQuery(period: PeriodSelection): URLSearchParams {
  return buildPeriodQuery(period)
}

export function buildTrendQuery(period: PeriodSelection): URLSearchParams {
  return buildPeriodQuery(period)
}

export function createRealtimeWindow() {
  const now = new Date()
  const start = new Date(now.getTime() - 5 * 60 * 1000)
  const fromHours = String(start.getHours()).padStart(2, '0')
  const fromMinutes = String(start.getMinutes()).padStart(2, '0')
  const toHours = String(now.getHours()).padStart(2, '0')
  const toMinutes = String(now.getMinutes()).padStart(2, '0')
  return {
    fromTime: `${fromHours}:${fromMinutes}`,
    toTime: `${toHours}:${toMinutes}`,
  }
}

export function createEmptySummary(currencyCode = 'EUR'): EnergySummary {
  const normalizedCode = normalizeCurrencyCode(currencyCode)
  return {
    totalEnergyWh: 0,
    totalCost: 0,
    averageLoad: 0,
    co2Kg: 0,
    currencyCode: normalizedCode,
    currencySymbol: getCurrencySymbol(normalizedCode),
    distribution: { ...DEFAULT_DISTRIBUTION },
  }
}

export function resolveRealtimeMetrics(
  snapshot: Record<string, unknown>,
  fallback: RealtimeEnergyMetrics | null,
  pricePerKwh: number,
  co2Factor: number,
): RealtimeEnergyMetrics {
  const directPowerCandidates = [snapshot.ups_realpower, snapshot.ups_power, snapshot.power]
  let directPower = Number.NaN
  for (const candidate of directPowerCandidates) {
    const value = asNumber(candidate, Number.NaN)
    if (Number.isFinite(value)) {
      directPower = value
      break
    }
  }
  const directLoad = asNumber(snapshot.ups_load, NaN)

  const powerWatts = Number.isFinite(directPower)
    ? Math.max(0, directPower)
    : Math.max(0, fallback?.powerWatts ?? 0)
  const loadPercent = Number.isFinite(directLoad)
    ? Math.max(0, Math.min(100, directLoad))
    : Math.max(0, Math.min(100, fallback?.loadPercent ?? 0))

  const normalizedPrice = Number.isFinite(pricePerKwh) ? Math.max(0, pricePerKwh) : 0
  const normalizedCo2 = Number.isFinite(co2Factor) ? Math.max(0, co2Factor) : 0

  return {
    powerWatts,
    loadPercent,
    totalCost: (powerWatts / 1000) * normalizedPrice,
    co2Kg: (powerWatts / 1000) * normalizedCo2,
  }
}

export function formatEnergyMetric(totalEnergyWh: number, mode: PeriodMode): string {
  if (mode === 'realtime') {
    if (totalEnergyWh < 1000) {
      return `${totalEnergyWh.toFixed(1)} W`
    }
    return `${(totalEnergyWh / 1000).toFixed(2)} kW`
  }

  if (totalEnergyWh < 1000) {
    return `${totalEnergyWh.toFixed(1)} Wh`
  }
  return `${(totalEnergyWh / 1000).toFixed(2)} kWh`
}

function fallbackWindowFromTimestamp(timestampMs: number, level: EnergyBucketLevel): EnergyDetailWindow {
  const clickedDate = new Date(timestampMs)

  if (level === 'day') {
    const dayStart = new Date(clickedDate)
    dayStart.setHours(0, 0, 0, 0)

    const dayEnd = new Date(dayStart)
    dayEnd.setDate(dayEnd.getDate() + 1)

    return {
      fromIso: dayStart.toISOString(),
      toIso: dayEnd.toISOString(),
      level,
      title: `Hours detail for ${clickedDate.toLocaleDateString()}`,
    }
  }

  if (level === 'hour') {
    const hourStart = new Date(clickedDate)
    hourStart.setMinutes(0, 0, 0)

    const hourEnd = new Date(hourStart)
    hourEnd.setHours(hourEnd.getHours() + 1)

    return {
      fromIso: hourStart.toISOString(),
      toIso: hourEnd.toISOString(),
      level,
      title: `Minutes detail for ${pad2(clickedDate.getHours())}:00`,
    }
  }

  const minuteStart = new Date(clickedDate)
  minuteStart.setSeconds(0, 0)
  const minuteEnd = new Date(minuteStart)
  minuteEnd.setMinutes(minuteEnd.getMinutes() + 1)

  return {
    fromIso: minuteStart.toISOString(),
    toIso: minuteEnd.toISOString(),
    level,
    title: `Minute detail for ${pad2(clickedDate.getHours())}:${pad2(clickedDate.getMinutes())}`,
  }
}

export function buildInitialDetailWindow(point: EnergySeriesPoint, mode: PeriodMode): EnergyDetailWindow {
  if (point.nextLevel && point.fromIso && point.toIso) {
    return {
      fromIso: point.fromIso,
      toIso: point.toIso,
      level: point.nextLevel,
      title: point.title || 'Interval details',
    }
  }

  if (mode === 'range') {
    return fallbackWindowFromTimestamp(point.x, 'day')
  }
  return fallbackWindowFromTimestamp(point.x, 'minute')
}

export function buildNextDetailWindow(
  point: EnergySeriesPoint,
  currentLevel: EnergyBucketLevel,
): EnergyDetailWindow | null {
  if (point.nextLevel && point.fromIso && point.toIso) {
    return {
      fromIso: point.fromIso,
      toIso: point.toIso,
      level: point.nextLevel,
      title: point.title || 'Interval details',
    }
  }

  const fallbackLevel = nextBucketLevel(currentLevel)
  if (!fallbackLevel) {
    return null
  }

  return fallbackWindowFromTimestamp(point.x, fallbackLevel)
}

export function buildSyntheticDetailSeries(
  windowData: EnergyDetailWindow,
  snapshot: Record<string, unknown>,
  pricePerKwh: number,
): EnergySeriesPoint[] {
  const startMs = normalizeTimestampMs(windowData.fromIso)
  if (startMs <= 0 || windowData.level !== 'minute') {
    return []
  }

  const directPower = asNumber(snapshot.ups_realpower ?? snapshot.ups_power, NaN)
  const loadPercent = asNumber(snapshot.ups_load, NaN)
  const nominalPower = asNumber(snapshot.ups_realpower_nominal, NaN)

  let watts = directPower
  if (!Number.isFinite(watts) || watts <= 0) {
    if (Number.isFinite(loadPercent) && Number.isFinite(nominalPower) && nominalPower > 0) {
      watts = (nominalPower * loadPercent) / 100
    } else {
      watts = 0
    }
  }

  const normalizedRate = Number.isFinite(pricePerKwh) && pricePerKwh > 0 ? pricePerKwh : 0
  const minuteCost = ((Math.max(0, watts) / 1000) * normalizedRate) / 60

  return Array.from({ length: 60 }, (_, index) => ({
    x: startMs + index * 60_000,
    y: Number(minuteCost.toFixed(6)),
    level: 'minute',
    nextLevel: null,
  }))
}
