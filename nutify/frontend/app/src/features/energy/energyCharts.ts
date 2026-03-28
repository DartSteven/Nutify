/**
 * Energycharts.
 *
 * Frontend module used by Nutify React UI flows and state management.
 */

import { asNumber, parseChartPoint, type EnergyBucketLevel, type EnergySeriesPoint } from './energyPageSupport'

type TrendChartOptionsInput = {
  mode: 'today' | 'day' | 'range'
  bucketLevel: EnergyBucketLevel
  timezone: string
  currencySymbol: string
  pricePerKwh: number
  trendSeries: EnergySeriesPoint[]
  onBarSelect: (point: EnergySeriesPoint) => void
}

type DistributionChartOptionsInput = {
  currencySymbol: string
}

type DetailChartOptionsInput = {
  level: EnergyBucketLevel
  timezone: string
  currencySymbol: string
  pricePerKwh: number
  onBarSelect?: (point: EnergySeriesPoint) => void
}

type ApexSelectionPayload = {
  dataPointIndex?: number
  w?: {
    config?: {
      series?: Array<{ data?: unknown[] }>
    }
  }
}

function formatTime(value: number, timezone: string, options: Intl.DateTimeFormatOptions): string {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) {
    return String(value)
  }

  try {
    return date.toLocaleTimeString(undefined, { ...options, timeZone: timezone })
  } catch {
    return date.toLocaleTimeString(undefined, options)
  }
}

function formatDate(value: number, timezone: string, options: Intl.DateTimeFormatOptions): string {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) {
    return String(value)
  }

  try {
    return date.toLocaleDateString(undefined, { ...options, timeZone: timezone })
  } catch {
    return date.toLocaleDateString(undefined, options)
  }
}

function formatBucketLabel(value: number, timezone: string, bucketLevel: EnergyBucketLevel): string {
  if (bucketLevel === 'month') {
    return formatDate(value, timezone, { month: 'short' })
  }
  if (bucketLevel === 'day') {
    return formatDate(value, timezone, { day: '2-digit', month: 'short' })
  }
  if (bucketLevel === 'hour') {
    return formatTime(value, timezone, { hour: '2-digit', hour12: false }).split(':')[0]
  }
  return formatTime(value, timezone, {
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  })
}

function formatBucketTooltip(value: number, timezone: string, bucketLevel: EnergyBucketLevel): string {
  if (bucketLevel === 'month') {
    return formatDate(value, timezone, { month: 'long', year: 'numeric' })
  }
  if (bucketLevel === 'day') {
    return formatDate(value, timezone, { day: '2-digit', month: 'short', year: 'numeric' })
  }
  if (bucketLevel === 'hour') {
    return formatTime(value, timezone, {
      hour: '2-digit',
      minute: '2-digit',
      hour12: false,
    })
  }
  return formatTime(value, timezone, {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  })
}

function resolveColorScale(mode: 'today' | 'day' | 'range', trendSeries: EnergySeriesPoint[]) {
  if (mode !== 'range' || trendSeries.length === 0) {
    return null
  }

  const values = trendSeries.map((point) => point.y)
  const max = Math.max(...values)
  return trendSeries.map((point) => {
    if (point.y > max * 0.8) return '#006400'
    if (point.y > max * 0.6) return '#00A000'
    if (point.y > max * 0.4) return '#40C040'
    if (point.y > max * 0.2) return '#60D060'
    return '#80E080'
  })
}

export function buildTrendChartOptions({
  mode,
  bucketLevel,
  timezone,
  currencySymbol,
  pricePerKwh,
  trendSeries,
  onBarSelect,
}: TrendChartOptionsInput): Record<string, unknown> {
  const colorScale = resolveColorScale(mode, trendSeries)

  const options: Record<string, unknown> = {
    chart: {
      type: 'bar',
      height: 350,
      animations: {
        enabled: true,
        easing: 'linear',
        dynamicAnimation: {
          speed: 1000,
        },
      },
      events: {
        dataPointSelection: (_event: unknown, _chartContext: unknown, rawConfig: unknown) => {
          const config = rawConfig as ApexSelectionPayload
          const dataPointIndex = Number(config.dataPointIndex ?? -1)
          if (!Number.isInteger(dataPointIndex) || dataPointIndex < 0) {
            return
          }

          const rawSeries = config.w?.config?.series?.[0]?.data
          if (!Array.isArray(rawSeries)) {
            return
          }
          const point = parseChartPoint(rawSeries[dataPointIndex])
          if (!point) {
            return
          }
          onBarSelect(point)
        },
      },
    },
    plotOptions: {
      bar: {
        horizontal: false,
        columnWidth: '60%',
        borderRadius: 4,
        distributed: Array.isArray(colorScale) && colorScale.length > 0,
      },
    },
    dataLabels: {
      enabled: false,
    },
    colors: colorScale ?? ['#00A0FF'],
    xaxis: {
      type: 'datetime',
      labels: {
        datetimeUTC: false,
        formatter: (value: string) => {
          const timestamp = Number(value)
          if (!Number.isFinite(timestamp)) {
            return value
          }
          return formatBucketLabel(timestamp, timezone, bucketLevel)
        },
      },
      axisBorder: {
        show: true,
        color: '#78909C',
      },
      axisTicks: {
        show: true,
      },
    },
    yaxis: {
      title: {
        text: 'Energy Cost',
      },
      min: 0,
      forceNiceScale: true,
    },
    tooltip: {
      x: {
        formatter: (value: number) => formatBucketTooltip(value, timezone, bucketLevel),
      },
      y: {
        formatter: (value: number) => {
          const numeric = Number(value)
          const energyKwh = pricePerKwh > 0 ? numeric / pricePerKwh : 0
          return `${currencySymbol}${numeric.toFixed(4)} ( ${energyKwh.toFixed(4)} kWh )`
        },
      },
    },
    legend: {
      show: false,
    },
    grid: {
      show: false,
    },
  }

  return options
}

export function buildDistributionChartOptions({
  currencySymbol,
}: DistributionChartOptionsInput): Record<string, unknown> {
  const readableTextColor = 'var(--text-primary, #e6edf7)'

  return {
    chart: {
      type: 'donut',
      height: 350,
      foreColor: readableTextColor,
    },
    labels: ['Morning (6-12)', 'Afternoon (12-18)', 'Evening (18-23)', 'Night (23-6)'],
    colors: ['#ffd700', '#ff8c00', '#4b0082', '#191970'],
    plotOptions: {
      pie: {
        donut: {
          size: '70%',
          labels: {
            show: true,
            name: {
              show: true,
              fontSize: '14px',
              fontFamily: 'Helvetica, Arial, sans-serif',
              color: readableTextColor,
            },
            value: {
              show: true,
              fontSize: '16px',
              fontFamily: 'Helvetica, Arial, sans-serif',
              color: readableTextColor,
              formatter: (value: number) => `${currencySymbol}${Number(value ?? 0).toFixed(2)}`,
            },
            total: {
              show: true,
              label: 'Total',
              color: readableTextColor,
              formatter: (chartContext: { globals?: { seriesTotals?: number[] } }) => {
                const total = chartContext.globals?.seriesTotals?.reduce((acc, item) => acc + item, 0) ?? 0
                return `${currencySymbol}${total.toFixed(2)}`
              },
            },
          },
        },
      },
    },
    legend: {
      position: 'bottom',
      labels: {
        colors: [readableTextColor],
      },
      formatter: (label: string, options: { w?: { globals?: { series?: number[] } }; seriesIndex: number }) => {
        const value = options.w?.globals?.series?.[options.seriesIndex] ?? 0
        return `${label}: ${currencySymbol}${Number(value).toFixed(2)}`
      },
    },
    tooltip: {
      y: {
        formatter: (value: number) => `${currencySymbol}${Number(value ?? 0).toFixed(2)}`,
      },
    },
  }
}

export function buildDetailChartOptions({
  level,
  timezone,
  currencySymbol,
  pricePerKwh,
  onBarSelect,
}: DetailChartOptionsInput): Record<string, unknown> {
  const callbacks = onBarSelect
    ? {
        dataPointSelection: (_event: unknown, _chartContext: unknown, rawConfig: unknown) => {
          const config = rawConfig as ApexSelectionPayload
          const dataPointIndex = Number(config.dataPointIndex ?? -1)
          if (!Number.isInteger(dataPointIndex) || dataPointIndex < 0) {
            return
          }
          const rawSeries = config.w?.config?.series?.[0]?.data
          if (!Array.isArray(rawSeries)) {
            return
          }
          const point = parseChartPoint(rawSeries[dataPointIndex])
          if (!point) {
            return
          }
          onBarSelect(point)
        },
      }
    : undefined

  return {
    chart: {
      type: 'bar',
      height: 420,
      animations: {
        enabled: true,
        easing: 'linear',
        dynamicAnimation: {
          speed: 1000,
        },
      },
      events: callbacks ?? {},
    },
    plotOptions: {
      bar: {
        horizontal: false,
        columnWidth: '50%',
        borderRadius: 4,
      },
    },
    dataLabels: {
      enabled: false,
    },
    xaxis: {
      type: 'datetime',
      labels: {
        show: true,
        datetimeUTC: false,
        formatter: (value: string) => {
          const timestamp = asNumber(value)
          return formatBucketLabel(timestamp, timezone, level)
        },
      },
      axisBorder: {
        show: true,
        color: '#64748B',
      },
      axisTicks: {
        show: true,
      },
    },
    yaxis: {
      min: 0,
      forceNiceScale: true,
      title: {
        text: 'Detailed Energy Cost',
      },
    },
    grid: {
      show: false,
    },
    tooltip: {
      x: {
        formatter: (value: number) => formatBucketTooltip(value, timezone, level),
      },
      y: {
        formatter: (value: number) => {
          const numeric = Number(value)
          const watt = pricePerKwh > 0 ? (numeric * 1000) / pricePerKwh : 0
          return `${currencySymbol}${numeric.toFixed(4)} ( ${watt.toFixed(1)} W )`
        },
      },
    },
  }
}
