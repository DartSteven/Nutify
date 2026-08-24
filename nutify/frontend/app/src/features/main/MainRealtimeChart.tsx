/**
 * Mainrealtimechart.
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
import {
  BUFFER_SIZE,
  FALLBACK_LOAD,
  MAX_POINTS,
  calculateSmoothedValue,
  clamp,
  generateSyntheticSeries,
  getLastKnownPowerValue,
  toNumber,
} from './mainPageSupport'

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
  const tagged = document.querySelector(`script[data-legacy-chartjs-src="${source}"]`) as HTMLScriptElement | null
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
    script.dataset.legacyChartjsSrc = source
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

type MainRealtimeChartProps = {
  latestData: Record<string, unknown>
  pollingIntervalMs: number
}

function getBaseValues(latestData: Record<string, unknown>): { power: number; load: number } {
  const latestPower = toNumber(latestData.ups_realpower)
  const latestLoad = toNumber(latestData.ups_load)

  const power = latestPower !== null ? Math.max(latestPower, 1) : getLastKnownPowerValue()
  const load = clamp(latestLoad !== null ? latestLoad : FALLBACK_LOAD, 0, 100)

  return { power, load }
}

export function MainRealtimeChart({ latestData, pollingIntervalMs }: MainRealtimeChartProps) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null)
  const chartRef = useRef<{ destroy: () => void } | null>(null)
  const latestDataRef = useRef<Record<string, unknown>>(latestData)
  const smoothingBufferRef = useRef<ChartPoint[]>([])
  const fallbackPowerRef = useRef<number>(getLastKnownPowerValue())
  const fallbackLoadRef = useRef<number>(FALLBACK_LOAD)

  useEffect(() => {
    latestDataRef.current = latestData
  }, [latestData])

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

      if (!loaded) {
        return
      }
      if (disposed || !canvasRef.current || !window.Chart) {
        return
      }

      const context = canvasRef.current.getContext('2d')
      if (!context) {
        return
      }

      const now = Date.now()
      const refreshMs = resolveRealtimeRefreshMs(pollingIntervalMs)
      const baseValues = getBaseValues(latestDataRef.current)
      const synthetic = generateSyntheticSeries(now, baseValues.power, baseValues.load)
      const syntheticPowerData = synthetic.realPower.map((point) => ({ x: point.timestamp, y: point.value }))
      const syntheticLoadData = synthetic.systemLoad.map((point) => ({ x: point.timestamp, y: point.value }))

      smoothingBufferRef.current = syntheticPowerData.slice(-BUFFER_SIZE)
      fallbackPowerRef.current = baseValues.power
      fallbackLoadRef.current = baseValues.load

      const powerGradient = context.createLinearGradient(0, 0, 0, 300)
      powerGradient.addColorStop(0, 'rgba(0, 200, 83, 0.3)')
      powerGradient.addColorStop(1, 'rgba(0, 200, 83, 0.0)')
      const theme = resolveChartTheme()

      const onRefresh = (chart: ChartContext) => {
        if (!chart?.data?.datasets) {
          return
        }

        const timestamp = Date.now()
        const payload = latestDataRef.current
        const powerValueRaw = toNumber(payload.ups_realpower)
        const loadValueRaw = toNumber(payload.ups_load)

        const pollingSeconds = Number.isFinite(Number(pollingIntervalMs))
          ? Math.max(1, Number(pollingIntervalMs) / 1000)
          : 1
        const fallbackPowerNoise = Math.min(6, Math.max(1.5, pollingSeconds))
        const fallbackLoadNoise = Math.min(4, Math.max(1, pollingSeconds / 2))

        const powerValue =
          powerValueRaw !== null
            ? Math.max(powerValueRaw, 1)
            : Math.max(fallbackPowerRef.current + (Math.random() * (fallbackPowerNoise * 2) - fallbackPowerNoise), 1)
        fallbackPowerRef.current = powerValue

        if (powerValue > 0) {
          const clampedPower = powerValue
          smoothingBufferRef.current.push({ x: timestamp, y: clampedPower })
          if (smoothingBufferRef.current.length > BUFFER_SIZE) {
            smoothingBufferRef.current = smoothingBufferRef.current.slice(
              smoothingBufferRef.current.length - BUFFER_SIZE,
            )
          }

          const smoothedPower = calculateSmoothedValue(
            smoothingBufferRef.current.map((point) => ({
              timestamp: point.x,
              value: point.y,
            })),
          )
          window.localStorage.setItem('lastPowerValue', String(clampedPower))
          chart.data.datasets[0].data.push({ x: timestamp, y: smoothedPower })
        }

        const loadValue =
          loadValueRaw !== null
            ? clamp(loadValueRaw, 0, 100)
            : clamp(fallbackLoadRef.current + (Math.random() * (fallbackLoadNoise * 2) - fallbackLoadNoise), 0, 100)
        fallbackLoadRef.current = loadValue
        chart.data.datasets[1].data.push({ x: timestamp, y: loadValue })

        chart.data.datasets.forEach((dataset) => {
          if (dataset.data.length > MAX_POINTS) {
            dataset.data.shift()
          }
        })

      }

      const chart = new window.Chart(context, {
        type: 'line',
        data: {
          datasets: [
            {
              label: 'Real Power',
              backgroundColor: powerGradient,
              borderColor: '#00c853',
              borderWidth: 2.5,
              data: syntheticPowerData,
              pointRadius: 0,
              tension: 0.4,
              fill: true,
              cubicInterpolationMode: 'monotone',
            },
            {
              label: 'System Load',
              backgroundColor: 'rgba(255, 105, 180, 0.2)',
              borderColor: '#FF69B4',
              borderWidth: 2,
              data: syntheticLoadData,
              pointRadius: 0,
              tension: 0.4,
              fill: false,
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
                label: (tooltipItem: { dataset: { label?: string }; parsed: { y: number } }) => {
                  const label = tooltipItem.dataset.label ?? ''
                  if (label === 'Real Power') {
                    return `${label}: ${tooltipItem.parsed.y.toFixed(1)} W`
                  }
                  if (label === 'System Load') {
                    return `${label}: ${tooltipItem.parsed.y.toFixed(1)} %`
                  }
                  return `${label}: ${tooltipItem.parsed.y.toFixed(1)}`
                },
              },
            },
          },
          scales: {
            x: {
              type: 'realtime',
              realtime: {
                duration: 60_000,
                refresh: refreshMs,
                delay: resolveRealtimeDelayMs(refreshMs),
                frameRate: REALTIME_FRAME_RATE,
                pause: pauseRealtimeWhenHidden,
                ttl: 60_000,
                onRefresh,
              },
              time: {
                unit: 'second',
                displayFormats: {
                  second: 'HH:mm:ss',
                  minute: 'HH:mm:ss',
                  hour: 'HH:mm:ss',
                },
                tooltipFormat: 'HH:mm:ss',
              },
              grid: { display: false, color: theme.gridColor },
              ticks: { maxRotation: 0, autoSkip: true, autoSkipPadding: 20, color: theme.mutedTextColor },
            },
            y: {
              min: 0,
              max: (ctx: { chart: { data: { datasets: Array<{ data: ChartPoint[] }> } } }) => {
                const data = ctx.chart.data.datasets[0]?.data ?? []
                if (data.length === 0) {
                  return 100
                }
                const max = Math.max(...data.map((point) => point.y))
                return Math.max(100, Math.ceil(max * 1.2))
              },
              grid: { display: false, color: theme.gridColor },
              ticks: {
                stepSize: 20,
                color: '#00c853',
              },
              title: {
                display: true,
                text: 'Power (W)',
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
      destroyChartSafely(chart, 'MainRealtimeChart')
      smoothingBufferRef.current = []
    }
  }, [pollingIntervalMs])

  return <canvas ref={canvasRef} />
}
