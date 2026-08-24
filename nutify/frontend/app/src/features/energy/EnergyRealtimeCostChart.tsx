/**
 * Energyrealtimecostchart.
 *
 * Frontend module used by Nutify React UI flows and state management.
 */

import { useEffect, useRef } from 'react'

import { destroyChartSafely } from '../../lib/charts/safeChartDestroy'
import {
  REALTIME_FRAME_RATE,
  pauseRealtimeWhenHidden,
  resolveChartPixelRatio,
  resolveRealtimeDelayMs,
  resolveRealtimeRefreshMs,
} from '../../lib/charts/realtimePerformance'
import { applyChartJsTheme, resolveChartTheme, watchChartTheme } from '../../lib/charts/theme'

type ChartPoint = {
  x: number
  y: number
}

type ChartDataset = {
  data: ChartPoint[]
}

type ChartContext = {
  data: {
    datasets: ChartDataset[]
  }
}

type ChartConstructor = new (
  context: CanvasRenderingContext2D,
  config: Record<string, unknown>,
) => {
  destroy: () => void
}

declare global {
  interface Window {
    Chart?: ChartConstructor
  }
}

export type RealtimeStats = {
  powerWatts: number
  loadPercent: number
  costValue: number
}

type EnergyRealtimeCostChartProps = {
  latestData: Record<string, unknown>
  pricePerKwh: number
  currencySymbol: string
  pollingIntervalMs: number
  onRealtimeStats?: (stats: RealtimeStats) => void
}

const SCRIPT_BASE = `${import.meta.env.BASE_URL}vendor/chartjs/`
const SCRIPT_PATHS = [
  `${SCRIPT_BASE}luxon.min.js`,
  `${SCRIPT_BASE}chart.min.js`,
  `${SCRIPT_BASE}chartjs-adapter-luxon.min.js`,
  `${SCRIPT_BASE}chartjs-plugin-streaming.min.js`,
]

const DURATION_MS = 60_000
const MAX_POINTS = 220
const BUFFER_SIZE = 15
const DEFAULT_POWER = 1
const DEFAULT_LOAD = 0
let chartLoaderPromise: Promise<void> | null = null

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => {
    window.setTimeout(resolve, ms)
  })
}

function toNumber(value: unknown): number | null {
  const numeric = Number(value)
  if (!Number.isFinite(numeric)) {
    return null
  }
  return numeric
}

function clamp(value: number, min: number, max: number): number {
  return Math.max(min, Math.min(max, value))
}

function findExistingScript(source: string): HTMLScriptElement | null {
  const tagged = document.querySelector(`script[data-legacy-energy-chart-src="${source}"]`) as HTMLScriptElement | null
  if (tagged) {
    return tagged
  }

  const sourcePath = new URL(source, window.location.origin).pathname
  const scripts = Array.from(document.querySelectorAll('script[src]')) as HTMLScriptElement[]
  return (
    scripts.find((script) => {
      try {
        return new URL(script.src, window.location.origin).pathname === sourcePath
      } catch {
        return script.src.endsWith(source)
      }
    }) ?? null
  )
}

function loadScriptSequentially(source: string): Promise<void> {
  return new Promise<void>((resolve, reject) => {
    const existing = findExistingScript(source)
    if (existing) {
      const existingReadyState = (existing as HTMLScriptElement & { readyState?: string }).readyState
      if (existing.dataset.loaded === 'true' || existingReadyState === 'complete') {
        existing.dataset.loaded = 'true'
        resolve()
        return
      }
      existing.addEventListener('load', () => resolve(), { once: true })
      existing.addEventListener('error', () => reject(new Error(`Failed to load ${source}`)), { once: true })
      return
    }

    const script = document.createElement('script')
    script.src = source
    script.async = false
    script.dataset.legacyEnergyChartSrc = source
    script.onload = () => {
      script.dataset.loaded = 'true'
      resolve()
    }
    script.onerror = () => reject(new Error(`Failed to load ${source}`))
    document.head.appendChild(script)
  })
}

function hasStreamingPluginLoaded(): boolean {
  const chart = window.Chart as unknown as {
    defaults?: { plugins?: Record<string, unknown> }
    registry?: { getScale?: (name: string) => unknown }
  }

  if (!chart) {
    return false
  }

  if (chart.defaults?.plugins && 'streaming' in chart.defaults.plugins) {
    return true
  }

  try {
    return Boolean(chart.registry?.getScale?.('realtime'))
  } catch {
    return false
  }
}

function ensureChartJsLoaded(): Promise<void> {
  if (typeof window === 'undefined') {
    return Promise.resolve()
  }
  if (chartLoaderPromise) {
    return chartLoaderPromise
  }

  chartLoaderPromise = SCRIPT_PATHS.reduce(
    (promise, source) => promise.then(() => loadScriptSequentially(source)),
    Promise.resolve(),
  ).then(() => {
    if (!window.Chart || !hasStreamingPluginLoaded()) {
      throw new Error('Chart.js streaming plugin is not ready')
    }
  })

  return chartLoaderPromise
}

function calculateSmoothedValue(dataBuffer: ChartPoint[]): number {
  if (dataBuffer.length === 0) {
    return 0
  }

  const weights: number[] = []
  for (let index = 0; index < dataBuffer.length; index += 1) {
    weights.push(Math.pow(1.2, index))
  }

  const weightSum = weights.reduce((acc, value) => acc + value, 0)
  let smoothedValue = 0

  for (let index = 0; index < dataBuffer.length; index += 1) {
    smoothedValue += dataBuffer[index].y * weights[index]
  }

  return smoothedValue / weightSum
}

function generateSyntheticSeries(now: number, baseCost: number): ChartPoint[] {
  const points: ChartPoint[] = []
  const stepMs = 1_000
  const totalPoints = Math.floor(DURATION_MS / stepMs)
  const safeBase = Math.max(0.000001, baseCost)

  for (let index = totalPoints; index > 0; index -= 1) {
    const timestamp = now - index * stepMs
    const wave = Math.sin(index / 8) * (safeBase * 0.04)
    const drift = Math.cos(index / 5) * (safeBase * 0.03)
    const value = Math.max(0, safeBase + wave + drift)
    points.push({ x: timestamp, y: value })
  }

  return points
}

function extractPowerAndLoad(payload: Record<string, unknown>): { power: number; load: number } {
  const directPower =
    toNumber(payload.ups_realpower) ??
    toNumber(payload.ups_power) ??
    toNumber(payload.power) ??
    DEFAULT_POWER
  const directLoad = toNumber(payload.ups_load) ?? DEFAULT_LOAD

  return {
    power: Math.max(DEFAULT_POWER, directPower),
    load: clamp(directLoad, 0, 100),
  }
}

export function EnergyRealtimeCostChart({
  latestData,
  pricePerKwh,
  currencySymbol,
  pollingIntervalMs,
  onRealtimeStats,
}: EnergyRealtimeCostChartProps) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null)
  const chartRef = useRef<{ destroy: () => void } | null>(null)
  const latestDataRef = useRef<Record<string, unknown>>(latestData)
  const smoothingBufferRef = useRef<ChartPoint[]>([])
  const fallbackPowerRef = useRef<number>(DEFAULT_POWER)
  const fallbackLoadRef = useRef<number>(DEFAULT_LOAD)
  const priceRef = useRef<number>(pricePerKwh)
  const symbolRef = useRef<string>(currencySymbol)
  const onRealtimeStatsRef = useRef<typeof onRealtimeStats>(onRealtimeStats)

  useEffect(() => {
    latestDataRef.current = latestData
  }, [latestData])

  useEffect(() => {
    priceRef.current = Number.isFinite(pricePerKwh) ? Math.max(pricePerKwh, 0) : 0
  }, [pricePerKwh])

  useEffect(() => {
    symbolRef.current = currencySymbol || ''
  }, [currencySymbol])

  useEffect(() => {
    onRealtimeStatsRef.current = onRealtimeStats
  }, [onRealtimeStats])

  useEffect(() => {
    let disposed = false
    let unwatchTheme = () => {}

    const mountChart = async () => {
      let loaded = false
      for (let attempt = 0; attempt < 3; attempt += 1) {
        try {
          await ensureChartJsLoaded()
          loaded = true
          break
        } catch {
          chartLoaderPromise = null
          if (attempt < 2) {
            await sleep(120)
          }
        }
      }

      if (!loaded || disposed || !canvasRef.current || !window.Chart) {
        return
      }

      const context = canvasRef.current.getContext('2d')
      if (!context) {
        return
      }

      const base = extractPowerAndLoad(latestDataRef.current)
      const refreshMs = resolveRealtimeRefreshMs(pollingIntervalMs)
      fallbackPowerRef.current = base.power
      fallbackLoadRef.current = base.load

      const baseCost = (base.power / 1000) * Math.max(priceRef.current, 0)
      const initialData = generateSyntheticSeries(Date.now(), baseCost)
      smoothingBufferRef.current = initialData.slice(-BUFFER_SIZE)

      const costGradient = context.createLinearGradient(0, 0, 0, 400)
      costGradient.addColorStop(0, 'rgba(0, 200, 83, 0.30)')
      costGradient.addColorStop(1, 'rgba(0, 200, 83, 0.0)')
      const theme = resolveChartTheme()

      const onRefresh = (chart: ChartContext) => {
        const dataset = chart?.data?.datasets?.[0]
        if (!dataset) {
          return
        }

        const now = Date.now()
        const payload = latestDataRef.current
        const direct = extractPowerAndLoad(payload)

        const pollingSeconds = Number.isFinite(Number(pollingIntervalMs))
          ? Math.max(1, Number(pollingIntervalMs) / 1000)
          : 1
        const powerNoise = Math.min(8, Math.max(1.5, pollingSeconds))
        const loadNoise = Math.min(4, Math.max(1, pollingSeconds / 2))

        const hasRealtimePower =
          toNumber(payload.ups_realpower) !== null || toNumber(payload.ups_power) !== null || toNumber(payload.power) !== null
        const hasRealtimeLoad = toNumber(payload.ups_load) !== null

        const powerWatts = hasRealtimePower
          ? direct.power
          : Math.max(DEFAULT_POWER, fallbackPowerRef.current + (Math.random() * (powerNoise * 2) - powerNoise))
        const loadPercent = hasRealtimeLoad
          ? direct.load
          : clamp(fallbackLoadRef.current + (Math.random() * (loadNoise * 2) - loadNoise), 0, 100)

        fallbackPowerRef.current = powerWatts
        fallbackLoadRef.current = loadPercent

        const costValue = (powerWatts / 1000) * Math.max(priceRef.current, 0)

        smoothingBufferRef.current.push({ x: now, y: costValue })
        if (smoothingBufferRef.current.length > BUFFER_SIZE) {
          smoothingBufferRef.current = smoothingBufferRef.current.slice(
            smoothingBufferRef.current.length - BUFFER_SIZE,
          )
        }

        const smoothedCost = calculateSmoothedValue(smoothingBufferRef.current)
        dataset.data.push({ x: now, y: smoothedCost })

        if (dataset.data.length > MAX_POINTS) {
          dataset.data.shift()
        }

        onRealtimeStatsRef.current?.({
          powerWatts,
          loadPercent,
          costValue,
        })

      }

      const chart = new window.Chart(context, {
        type: 'line',
        data: {
          datasets: [
            {
              label: 'Energy Cost',
              backgroundColor: costGradient,
              borderColor: '#00c853',
              borderWidth: 2.5,
              data: initialData,
              pointRadius: 0,
              tension: 0.4,
              fill: true,
              cubicInterpolationMode: 'monotone',
            },
          ],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          devicePixelRatio: resolveChartPixelRatio(),
          normalized: true,
          animation: false,
          plugins: {
            legend: {
              position: 'top',
              labels: {
                color: theme.textColor,
                padding: 15,
              },
            },
            tooltip: {
              backgroundColor: theme.tooltipBackground,
              titleColor: theme.tooltipTextColor,
              bodyColor: theme.tooltipTextColor,
              callbacks: {
                label: (contextItem: { parsed: { y: number } }) => {
                  const currentPrice = Math.max(priceRef.current, 0)
                  const cost = contextItem.parsed.y
                  const watts = currentPrice > 0 ? (cost * 1000) / currentPrice : 0
                  return `${symbolRef.current}${cost.toFixed(5)} ( ${watts.toFixed(1)} W )`
                },
              },
            },
          },
          scales: {
            x: {
              type: 'realtime',
              realtime: {
                duration: DURATION_MS,
                refresh: refreshMs,
                delay: resolveRealtimeDelayMs(refreshMs),
                frameRate: REALTIME_FRAME_RATE,
                pause: pauseRealtimeWhenHidden,
                ttl: DURATION_MS,
                onRefresh,
              },
              time: {
                unit: 'second',
                displayFormats: {
                  second: 'HH:mm:ss',
                },
              },
              grid: {
                display: false,
                color: theme.gridColor,
              },
              ticks: {
                maxRotation: 0,
                autoSkip: true,
                autoSkipPadding: 20,
                color: theme.mutedTextColor,
              },
            },
            y: {
              min: 0,
              max: (ctx: { chart: { data: { datasets: Array<{ data: ChartPoint[] }> } } }) => {
                const values = ctx.chart.data.datasets[0]?.data ?? []
                if (values.length === 0) {
                  return 0.05
                }
                const maxValue = Math.max(...values.map((point) => point.y))
                return Math.max(0.05, Math.ceil(maxValue * 1.5 * 100) / 100)
              },
              grid: {
                display: false,
                color: theme.gridColor,
              },
              ticks: {
                color: '#00c853',
              },
              title: {
                display: true,
                text: `Cost (${symbolRef.current})`,
                color: theme.textColor,
              },
            },
          },
          interaction: {
            intersect: false,
            mode: 'nearest',
          },
        },
      })

      chartRef.current = chart
      applyChartJsTheme(chart, { preserveTickColors: ['y'] })
      unwatchTheme = watchChartTheme(() => applyChartJsTheme(chart, { preserveTickColors: ['y'] }))
    }

    void mountChart()

    return () => {
      disposed = true
      unwatchTheme()
      const chart = chartRef.current
      chartRef.current = null
      destroyChartSafely(chart, 'EnergyRealtimeCostChart')
      smoothingBufferRef.current = []
    }
  }, [pollingIntervalMs])

  return <canvas ref={canvasRef} id="realtimeEnergyChart" />
}
