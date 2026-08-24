/**
 * Legacyapexchart.
 *
 * Frontend module used by Nutify React UI flows and state management.
 */

import { useEffect, useRef, type CSSProperties } from 'react'

import { mergeApexThemeOptions, watchChartTheme } from '../lib/charts/theme'

type ApexSeries = unknown[]

type ApexChartProps = {
  options: Record<string, unknown>
  series: ApexSeries
  className?: string
  style?: CSSProperties
}

type ApexChartInstance = {
  render: () => Promise<void> | void
  updateOptions: (
    options: Record<string, unknown>,
    redrawPaths?: boolean,
    animate?: boolean,
    updateSyncedCharts?: boolean,
  ) => Promise<void> | void
  updateSeries: (series: ApexSeries, animate?: boolean) => Promise<void> | void
  destroy: () => void
}

type ApexChartConstructor = new (element: Element, options: Record<string, unknown>) => ApexChartInstance

declare global {
  interface Window {
    ApexCharts?: ApexChartConstructor
  }
}

const APEX_SCRIPT_SRC = `${import.meta.env.BASE_URL}vendor/apexcharts/apexcharts.min.js`
let apexLoaderPromise: Promise<void> | null = null

function loadApexScript(): Promise<void> {
  if (typeof window === 'undefined') {
    return Promise.resolve()
  }

  if (window.ApexCharts) {
    return Promise.resolve()
  }

  if (apexLoaderPromise) {
    return apexLoaderPromise
  }

  apexLoaderPromise = new Promise<void>((resolve, reject) => {
    const existingScript = document.querySelector(`script[data-legacy-apex="true"]`) as HTMLScriptElement | null
    if (existingScript) {
      existingScript.addEventListener('load', () => resolve(), { once: true })
      existingScript.addEventListener('error', () => reject(new Error('Failed to load legacy ApexCharts script')), {
        once: true,
      })
      return
    }

    const script = document.createElement('script')
    script.src = APEX_SCRIPT_SRC
    script.async = true
    script.dataset.legacyApex = 'true'
    script.onload = () => resolve()
    script.onerror = () => reject(new Error('Failed to load legacy ApexCharts script'))
    document.head.appendChild(script)
  })

  return apexLoaderPromise
}

function mergeChartOptions(options: Record<string, unknown>, series: ApexSeries): Record<string, unknown> {
  const chartConfig =
    options.chart && typeof options.chart === 'object' && !Array.isArray(options.chart)
      ? (options.chart as Record<string, unknown>)
      : {}
  const chartType = String(chartConfig.type ?? '').toLowerCase()
  const hasExplicitGrid = Object.prototype.hasOwnProperty.call(options, 'grid')
  const shouldDisableGrid = !hasExplicitGrid && (chartType === 'line' || chartType === 'area')

  return {
    ...mergeApexThemeOptions(options),
    ...(shouldDisableGrid ? { grid: { show: false } } : {}),
    series,
  }
}

function isDetachedApexError(error: unknown): boolean {
  const message = error instanceof Error ? error.message : String(error ?? '')
  return (
    message.includes('this.w.globals.dom.Paper') ||
    message.includes("can't access property \"node\"") ||
    message.includes("Cannot read properties of undefined (reading 'node')")
  )
}

export function LegacyApexChart({ options, series, className, style }: ApexChartProps) {
  const elementRef = useRef<HTMLDivElement | null>(null)
  const chartRef = useRef<ApexChartInstance | null>(null)
  const optionsRef = useRef(options)
  const seriesRef = useRef(series)
  const destroyedRef = useRef(false)
  const readyRef = useRef(false)

  useEffect(() => {
    optionsRef.current = options
    seriesRef.current = series
  }, [options, series])

  useEffect(() => {
    let disposed = false
    destroyedRef.current = false
    readyRef.current = false

    const mountChart = async () => {
      try {
        await loadApexScript()
      } catch (error) {
        console.error('Failed to load ApexCharts script', error)
        return
      }

      if (disposed || destroyedRef.current || !elementRef.current || !window.ApexCharts) {
        return
      }

      try {
        const chart = new window.ApexCharts(
          elementRef.current,
          mergeChartOptions(optionsRef.current, seriesRef.current),
        )
        await chart.render()
        if (disposed || destroyedRef.current) {
          try {
            chart.destroy()
          } catch (error) {
            if (!isDetachedApexError(error)) {
              console.error('Failed to destroy ApexCharts instance during unmount race', error)
            }
          }
          return
        }
        chartRef.current = chart
        readyRef.current = true
      } catch (error) {
        if (!isDetachedApexError(error)) {
          console.error('Failed to mount ApexCharts instance', error)
        }
      }
    }

    void mountChart()

    return () => {
      disposed = true
      destroyedRef.current = true
      readyRef.current = false
      if (chartRef.current) {
        try {
          chartRef.current.destroy()
        } catch (error) {
          if (!isDetachedApexError(error)) {
            console.error('Failed to destroy ApexCharts instance', error)
          }
        } finally {
          chartRef.current = null
        }
      }
    }
  }, [])

  useEffect(() => {
    const chart = chartRef.current
    if (!chart || destroyedRef.current || !readyRef.current) {
      return
    }

    try {
      void chart.updateOptions(mergeChartOptions(options, series), false, false, false)
    } catch (error) {
      if (!isDetachedApexError(error)) {
        console.error('Failed to update ApexCharts instance', error)
      }
    }
  }, [options, series])

  useEffect(() => {
    return watchChartTheme(() => {
      const chart = chartRef.current
      if (!chart || destroyedRef.current || !readyRef.current) {
        return
      }
      try {
        void chart.updateOptions(mergeChartOptions(options, series), false, false, false)
      } catch (error) {
        if (!isDetachedApexError(error)) {
          console.error('Failed to update ApexCharts theme', error)
        }
      }
    })
  }, [options, series])

  return <div ref={elementRef} className={className} style={style} />
}
