/**
 * Voltageinsightspanel.
 *
 * Frontend module used by Nutify React UI flows and state management.
 */

import { useMemo } from 'react'

import { LegacyApexChart } from '../../components/LegacyApexChart'
import type { Point } from './voltagePageSupport'

type VoltageInsightsPanelProps = {
  history: Record<string, Point[]>
  displayInputVoltage: number
  displayNominalVoltage: number
  displayTransferLow: number
  displayTransferHigh: number
  timezone: string
}

type ChartPoint = {
  x: number
  y: number
}

function formatVoltageTime(value: number | string, timezone: string): string {
  const parsed = typeof value === 'number' ? value : Number(value)
  if (!Number.isFinite(parsed)) {
    return String(value)
  }

  const date = new Date(parsed)
  if (Number.isNaN(date.getTime())) {
    return String(value)
  }

  try {
    return date.toLocaleTimeString(undefined, {
      timeZone: timezone,
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      hour12: false,
    })
  } catch {
    return date.toLocaleTimeString(undefined, {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      hour12: false,
    })
  }
}

function formatSignedVoltage(value: number): string {
  const rounded = Number(value.toFixed(1))
  if (!Number.isFinite(rounded)) {
    return '0.0 V'
  }
  if (rounded > 0) {
    return `+${rounded.toFixed(1)} V`
  }
  return `${rounded.toFixed(1)} V`
}

function parsePositiveSeries(points: Point[] | undefined): Point[] {
  if (!Array.isArray(points)) {
    return []
  }
  return points.filter((point) => Number.isFinite(point.value) && point.value > 0 && point.timestamp > 0)
}

function clamp(value: number, min: number, max: number): number {
  if (value < min) {
    return min
  }
  if (value > max) {
    return max
  }
  return value
}

export function VoltageInsightsPanel({
  history,
  displayInputVoltage,
  displayNominalVoltage,
  displayTransferLow,
  displayTransferHigh,
  timezone,
}: VoltageInsightsPanelProps) {
  const inputSeries = useMemo(() => parsePositiveSeries(history.input_voltage), [history.input_voltage])
  const outputSeries = useMemo(() => parsePositiveSeries(history.output_voltage), [history.output_voltage])
  const nominalSeries = useMemo(
    () => parsePositiveSeries(history.input_voltage_nominal),
    [history.input_voltage_nominal],
  )

  const deviationSeries = useMemo(() => {
    const points: ChartPoint[] = []
    inputSeries.forEach((point, index) => {
      const nominalValue = nominalSeries[index]?.value
      const reference = nominalValue && nominalValue > 0 ? nominalValue : displayNominalVoltage
      if (reference <= 0) {
        return
      }
      points.push({
        x: point.timestamp,
        y: Number((point.value - reference).toFixed(3)),
      })
    })
    return points
  }, [displayNominalVoltage, inputSeries, nominalSeries])

  const inputOutputDeltaSeries = useMemo(() => {
    const maxLength = Math.min(inputSeries.length, outputSeries.length)
    const points: ChartPoint[] = []

    for (let index = 0; index < maxLength; index += 1) {
      const inputValue = inputSeries[index]?.value
      const outputValue = outputSeries[index]?.value
      if (!Number.isFinite(inputValue) || !Number.isFinite(outputValue)) {
        continue
      }
      points.push({
        x: inputSeries[index].timestamp,
        y: Number((outputValue - inputValue).toFixed(3)),
      })
    }

    return points
  }, [inputSeries, outputSeries])

  const occupancy = useMemo(() => {
    const counts = {
      below: 0,
      within: 0,
      above: 0,
    }

    if (displayTransferHigh <= displayTransferLow) {
      return counts
    }

    inputSeries.forEach((point) => {
      if (point.value < displayTransferLow) {
        counts.below += 1
      } else if (point.value > displayTransferHigh) {
        counts.above += 1
      } else {
        counts.within += 1
      }
    })

    return counts
  }, [displayTransferHigh, displayTransferLow, inputSeries])

  const hasRangeWidget = displayInputVoltage > 0 && displayTransferLow > 0 && displayTransferHigh > displayTransferLow
  const hasDeviationWidget = deviationSeries.length > 1
  const hasDeltaWidget = inputOutputDeltaSeries.length > 1
  const hasOccupancyWidget = occupancy.below + occupancy.within + occupancy.above > 0

  if (!hasRangeWidget && !hasDeviationWidget && !hasDeltaWidget && !hasOccupancyWidget) {
    return null
  }

  const rangeSpan = Math.max(displayTransferHigh - displayTransferLow, 1)
  const rangeProgress = clamp(((displayInputVoltage - displayTransferLow) / rangeSpan) * 100, 0, 100)
  const rangeZone =
    displayInputVoltage < displayTransferLow
      ? 'Below Range'
      : displayInputVoltage > displayTransferHigh
        ? 'Above Range'
        : 'Within Range'

  const rangeGaugeOptions = {
    chart: {
      type: 'radialBar',
      height: 220,
      sparkline: { enabled: true },
    },
    labels: ['Range Use'],
    plotOptions: {
      radialBar: {
        startAngle: -130,
        endAngle: 130,
        hollow: {
          size: '64%',
        },
        track: {
          background: 'rgba(120, 140, 170, 0.24)',
        },
        dataLabels: {
          name: {
            fontSize: '12px',
            offsetY: -10,
          },
          value: {
            fontSize: '22px',
            formatter: (value: number) => `${Math.round(value)}%`,
          },
        },
      },
    },
    fill: {
      type: 'gradient',
      gradient: {
        shade: 'dark',
        shadeIntensity: 0.3,
        gradientToColors: ['#66DA26'],
        stops: [0, 100],
      },
    },
    stroke: {
      lineCap: 'round',
    },
  }

  const deviationOptions = {
    chart: {
      type: 'area',
      height: 230,
      animations: { enabled: true },
      toolbar: { show: false },
    },
    dataLabels: {
      enabled: false,
    },
    colors: ['#38bdf8'],
    stroke: {
      curve: 'smooth',
      width: 2,
    },
    fill: {
      type: 'gradient',
      gradient: {
        shadeIntensity: 0.4,
        opacityFrom: 0.35,
        opacityTo: 0.03,
        stops: [0, 90, 100],
      },
    },
    xaxis: {
      type: 'datetime',
      labels: {
        datetimeUTC: false,
        formatter: (value: string) => formatVoltageTime(value, timezone),
      },
    },
    yaxis: {
      labels: {
        formatter: (value: number) => formatSignedVoltage(value),
      },
    },
    tooltip: {
      x: {
        formatter: (value: number) => formatVoltageTime(value, timezone),
      },
      y: {
        formatter: (value: number) => formatSignedVoltage(value),
      },
    },
  }

  const deltaOptions = {
    chart: {
      type: 'line',
      height: 230,
      animations: { enabled: true },
      toolbar: { show: false },
    },
    dataLabels: {
      enabled: false,
    },
    colors: ['#a78bfa'],
    stroke: {
      curve: 'smooth',
      width: 2,
    },
    xaxis: {
      type: 'datetime',
      labels: {
        datetimeUTC: false,
        formatter: (value: string) => formatVoltageTime(value, timezone),
      },
    },
    yaxis: {
      labels: {
        formatter: (value: number) => formatSignedVoltage(value),
      },
    },
    tooltip: {
      x: {
        formatter: (value: number) => formatVoltageTime(value, timezone),
      },
      y: {
        formatter: (value: number) => formatSignedVoltage(value),
      },
    },
  }

  const occupancyOptions = {
    chart: {
      type: 'donut',
      height: 220,
      toolbar: { show: false },
    },
    labels: ['Below', 'Within', 'Above'],
    colors: ['#f59e0b', '#22c55e', '#ef4444'],
    legend: {
      position: 'bottom',
    },
    plotOptions: {
      pie: {
        donut: {
          size: '68%',
        },
      },
    },
    tooltip: {
      y: {
        formatter: (value: number) => `${Math.round(value)} samples`,
      },
    },
  }

  const currentDeviation = displayInputVoltage > 0 && displayNominalVoltage > 0
    ? displayInputVoltage - displayNominalVoltage
    : deviationSeries[deviationSeries.length - 1]?.y ?? 0

  const latestDelta = inputOutputDeltaSeries[inputOutputDeltaSeries.length - 1]?.y ?? 0

  return (
    <div className="voltage_insights_grid">
      {hasRangeWidget ? (
        <article className="chart_card chart_card--compact voltage_insight_card">
          <div className="chart_header">
            <h2>Operating Voltage Range</h2>
            <p className="chart_subtitle">Current position inside transfer low/high boundaries</p>
          </div>
          <div className="chart_container chart_container--sm">
            <LegacyApexChart options={rangeGaugeOptions} series={[rangeProgress]} style={{ height: '100%', width: '100%' }} />
          </div>
          <div className="insight_meta">
            <div className="insight_meta_row">
              <span>Current</span>
              <strong>{displayInputVoltage.toFixed(1)} V</strong>
            </div>
            <div className="insight_meta_row">
              <span>Range</span>
              <strong>
                {displayTransferLow.toFixed(1)}V - {displayTransferHigh.toFixed(1)}V
              </strong>
            </div>
            <div className="insight_meta_row">
              <span>Status</span>
              <strong>{rangeZone}</strong>
            </div>
          </div>
        </article>
      ) : null}

      {hasDeviationWidget ? (
        <article className="chart_card chart_card--compact voltage_insight_card">
          <div className="chart_header">
            <h2>Voltage Deviation</h2>
            <p className="chart_subtitle">Input voltage delta compared to nominal reference</p>
          </div>
          <div className="chart_container chart_container--sm">
            <LegacyApexChart
              options={deviationOptions}
              series={[{ name: 'Deviation', data: deviationSeries }]}
              style={{ height: '100%', width: '100%' }}
            />
          </div>
          <div className="insight_badge">Current delta: {formatSignedVoltage(currentDeviation)}</div>
        </article>
      ) : null}

      {hasDeltaWidget ? (
        <article className="chart_card chart_card--compact voltage_insight_card">
          <div className="chart_header">
            <h2>Input vs Output Delta</h2>
            <p className="chart_subtitle">Difference between output and input voltage over time</p>
          </div>
          <div className="chart_container chart_container--sm">
            <LegacyApexChart
              options={deltaOptions}
              series={[{ name: 'Output - Input', data: inputOutputDeltaSeries }]}
              style={{ height: '100%', width: '100%' }}
            />
          </div>
          <div className="insight_badge">Latest delta: {formatSignedVoltage(latestDelta)}</div>
        </article>
      ) : null}

      {hasOccupancyWidget ? (
        <article className="chart_card chart_card--compact voltage_insight_card">
          <div className="chart_header">
            <h2>Band Occupancy</h2>
            <p className="chart_subtitle">Time distribution across voltage operating bands</p>
          </div>
          <div className="chart_container chart_container--sm">
            <LegacyApexChart
              options={occupancyOptions}
              series={[occupancy.below, occupancy.within, occupancy.above]}
              style={{ height: '100%', width: '100%' }}
            />
          </div>
        </article>
      ) : null}
    </div>
  )
}
