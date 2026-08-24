/**
 * Legacyrealtimestreamchart.
 *
 * Frontend module used by Nutify React UI flows and state management.
 */

import { useEffect, useMemo, useRef } from 'react'

import { destroyChartSafely } from '../lib/charts/safeChartDestroy'
import {
  REALTIME_FRAME_RATE,
  pauseRealtimeWhenHidden,
  resolveChartPixelRatio,
  resolveRealtimeDelayMs,
  resolveRealtimeRefreshMs,
} from '../lib/charts/realtimePerformance'
import { applyChartJsTheme, resolveChartTheme, watchChartTheme } from '../lib/charts/theme'

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

type AxisPosition = 'left' | 'right'

export type RealtimeAxisConfig = {
  id: string
  position: AxisPosition
  title: string
  color?: string
  min?: number
  max?: number
  formatter?: (value: number) => string
}

export type RealtimeSeriesConfig = {
  key: string
  name: string
  color: string
  fillColor?: string
  yAxisId: string
  lineWidth?: number
  tension?: number
  precision?: number
  unit?: string
  value: (payload: Record<string, unknown>) => number | null
}

type LegacyRealtimeStreamChartProps = {
  chartId: string
  latestData: Record<string, unknown>
  pollingIntervalMs: number
  series: RealtimeSeriesConfig[]
  axes: RealtimeAxisConfig[]
  durationMs?: number
  maxPoints?: number
}

const SCRIPT_BASE = `${import.meta.env.BASE_URL}vendor/chartjs/`
const SCRIPT_PATHS = [
  `${SCRIPT_BASE}luxon.min.js`,
  `${SCRIPT_BASE}chart.min.js`,
  `${SCRIPT_BASE}chartjs-adapter-luxon.min.js`,
  `${SCRIPT_BASE}chartjs-plugin-streaming.min.js`,
]

let chartLoaderPromise: Promise<void> | null = null

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => {
    window.setTimeout(resolve, ms)
  })
}

function findExistingScript(source: string): HTMLScriptElement | null {
  const tagged = document.querySelector(`script[data-legacy-stream-src="${source}"]`) as HTMLScriptElement | null
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
    script.dataset.legacyStreamSrc = source
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

function buildInitialSeriesData(
  now: number,
  durationMs: number,
  stepMs: number,
  latestData: Record<string, unknown>,
  series: RealtimeSeriesConfig[],
): ChartPoint[][] {
  const totalPoints = Math.max(1, Math.floor(durationMs / stepMs))
  return series.map((config) => {
    const initialValue = config.value(latestData)
    if (initialValue === null) {
      return []
    }
    const safeBase = Number(initialValue)
    const waveAmplitude = Math.max(Math.abs(safeBase) * 0.04, 0.5)
    const driftAmplitude = Math.max(Math.abs(safeBase) * 0.03, 0.3)
    const rows: ChartPoint[] = []
    for (let index = totalPoints; index > 0; index -= 1) {
      const wave = Math.sin(index / 8) * waveAmplitude
      const drift = Math.cos(index / 5) * driftAmplitude
      const syntheticValue = safeBase + wave + drift
      rows.push({
        x: now - index * stepMs,
        y: safeBase >= 0 ? Math.max(0, syntheticValue) : syntheticValue,
      })
    }
    return rows
  })
}

function calculateSmoothedValue(points: ChartPoint[]): number {
  if (points.length === 0) {
    return 0
  }
  const weights = points.map((_, index) => Math.pow(1.2, index))
  const weightSum = weights.reduce((sum, value) => sum + value, 0)
  const weightedTotal = points.reduce((sum, point, index) => sum + point.y * weights[index], 0)
  return weightedTotal / weightSum
}

function axisLabelFormatter(
  axis: RealtimeAxisConfig,
): (value: number | string) => string {
  return (value: number | string) => {
    const numeric = Number(value)
    if (!Number.isFinite(numeric)) {
      return String(value)
    }
    if (axis.formatter) {
      return axis.formatter(numeric)
    }
    return numeric.toFixed(0)
  }
}

function tooltipFormatter(unit: string | undefined, precision: number | undefined): (value: number) => string {
  return (value: number) => {
    const digits = Number.isFinite(Number(precision)) ? Math.max(0, Number(precision)) : 1
    const suffix = unit ? ` ${unit}` : ''
    return `${Number(value).toFixed(digits)}${suffix}`
  }
}

export function LegacyRealtimeStreamChart({
  chartId,
  latestData,
  pollingIntervalMs,
  series,
  axes,
  durationMs = 60_000,
  maxPoints = 260,
}: LegacyRealtimeStreamChartProps) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null)
  const chartRef = useRef<{ destroy: () => void } | null>(null)
  const latestDataRef = useRef<Record<string, unknown>>(latestData)
  const seriesRef = useRef<RealtimeSeriesConfig[]>(series)
  const lastValuesRef = useRef<Record<string, number | null>>({})
  const seriesBuffersRef = useRef<Record<string, ChartPoint[]>>({})

  useEffect(() => {
    latestDataRef.current = latestData
  }, [latestData])

  useEffect(() => {
    seriesRef.current = series
  }, [series])

  const refreshMs = useMemo(() => {
    return resolveRealtimeRefreshMs(pollingIntervalMs)
  }, [pollingIntervalMs])

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

      const now = Date.now()
      const stepMs = Math.max(200, refreshMs)
      const initialSeriesData = buildInitialSeriesData(
        now,
        durationMs,
        stepMs,
        latestDataRef.current,
        seriesRef.current,
      )

      seriesRef.current.forEach((config, index) => {
        const initialPoint = initialSeriesData[index].at(-1)
        lastValuesRef.current[config.key] = initialPoint ? initialPoint.y : null
        seriesBuffersRef.current[config.key] = initialSeriesData[index].slice(-15)
      })

      const datasets = seriesRef.current.map((config, index) => ({
        label: config.name,
        data: initialSeriesData[index],
        borderColor: config.color,
        backgroundColor: config.fillColor ?? `${config.color}22`,
        borderWidth: config.lineWidth ?? 2,
        pointRadius: 0,
        tension: config.tension ?? 0.35,
        cubicInterpolationMode: 'monotone',
        yAxisID: config.yAxisId,
        fill: Boolean(config.fillColor),
      }))

      const theme = resolveChartTheme()
      const scales = Object.fromEntries(
        axes.map((axis) => [
          axis.id,
          {
            type: 'linear',
            position: axis.position,
            min: axis.min,
            max: axis.max,
            title: {
              display: true,
              text: axis.title,
              color: axis.color ?? theme.textColor,
            },
            grid: {
              drawOnChartArea: axis.position === 'left',
              color: theme.gridColor,
            },
            ticks: {
              color: axis.color ?? theme.mutedTextColor,
              callback: axisLabelFormatter(axis),
            },
          },
        ]),
      )

      const onRefresh = (chart: ChartContext) => {
        const payload = latestDataRef.current
        const timestamp = Date.now()

        seriesRef.current.forEach((config, index) => {
          const dataset = chart.data.datasets[index]
          if (!dataset) {
            return
          }

          const nextValue = config.value(payload)
          const fallback = lastValuesRef.current[config.key]
          const value = nextValue !== null ? nextValue : fallback
          if (value === null || !Number.isFinite(value)) {
            return
          }

          lastValuesRef.current[config.key] = value
          const buffer = seriesBuffersRef.current[config.key] ?? []
          buffer.push({
            x: timestamp,
            y: value,
          })
          if (buffer.length > 15) {
            buffer.splice(0, buffer.length - 15)
          }
          seriesBuffersRef.current[config.key] = buffer
          const smoothedValue = calculateSmoothedValue(buffer)
          dataset.data.push({
            x: timestamp,
            y: smoothedValue,
          })

          while (dataset.data.length > maxPoints) {
            dataset.data.shift()
          }
        })

      }

      const chart = new window.Chart(context, {
        type: 'line',
        data: {
          datasets,
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          devicePixelRatio: resolveChartPixelRatio(),
          normalized: true,
          animation: false,
          plugins: {
            legend: {
              display: true,
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
                label: (tooltipItem: { dataset: { label?: string }; datasetIndex: number; parsed: { y: number } }) => {
                  const config = seriesRef.current[tooltipItem.datasetIndex]
                  const formatter = tooltipFormatter(config?.unit, config?.precision)
                  const label = tooltipItem.dataset.label || 'Value'
                  return `${label}: ${formatter(tooltipItem.parsed.y)}`
                },
              },
            },
          },
          scales: {
            x: {
              type: 'realtime',
              realtime: {
                duration: durationMs,
                refresh: refreshMs,
                delay: resolveRealtimeDelayMs(refreshMs),
                frameRate: REALTIME_FRAME_RATE,
                pause: pauseRealtimeWhenHidden,
                ttl: durationMs,
                onRefresh,
              },
              ticks: {
                color: theme.mutedTextColor,
                autoSkip: true,
                maxRotation: 0,
              },
              grid: {
                color: theme.gridColor,
              },
            },
            ...scales,
          },
        },
      })

      chartRef.current = chart
      const colorLockedAxes = axes.filter((axis) => axis.color).map((axis) => axis.id)
      applyChartJsTheme(chart, {
        preserveTickColors: colorLockedAxes,
        preserveTitleColors: colorLockedAxes,
      })
      unwatchTheme = watchChartTheme(() =>
        applyChartJsTheme(chart, {
          preserveTickColors: colorLockedAxes,
          preserveTitleColors: colorLockedAxes,
        }),
      )
    }

    void mountChart()

    return () => {
      disposed = true
      unwatchTheme()
      const chart = chartRef.current
      chartRef.current = null
      destroyChartSafely(chart, 'LegacyRealtimeStreamChart')
      lastValuesRef.current = {}
      seriesBuffersRef.current = {}
    }
  }, [axes, durationMs, maxPoints, refreshMs, series])

  return <canvas ref={canvasRef} id={chartId} />
}
