/**
 * Batteryinsightspanel.
 *
 * Frontend module used by Nutify React UI flows and state management.
 */

import { useMemo } from 'react'

import { LegacyApexChart } from '../../components/LegacyApexChart'
import { BATTERY_HEALTH_OPTIONS, type BatteryHistoryPayload } from './batteryCharts'

type BatteryHealthView = {
  score: number
  level: string
  summary: string
  recommendations: string[]
}

type BatteryInsightsPanelProps = {
  history: BatteryHistoryPayload
  timezone: string
  charge: number
  runtimeSeconds: number
  voltage: number
  temperature: number | null
  health: BatteryHealthView
  batteryType: string
  batteryDate: string
  manufacturerDate: string
}

type ChartPoint = {
  x: number
  y: number
}

function formatBatteryTime(value: number | string, timezone: string): string {
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

function parsePositiveSeries(points: Array<{ timestamp: number; value: number }>): ChartPoint[] {
  return points
    .filter((point) => Number.isFinite(point.timestamp) && point.timestamp > 0)
    .filter((point) => Number.isFinite(point.value) && point.value > 0)
    .map((point) => ({ x: point.timestamp, y: point.value }))
}

function average(values: number[]): number {
  if (!values.length) {
    return 0
  }
  return values.reduce((sum, value) => sum + value, 0) / values.length
}

function standardDeviation(values: number[]): number {
  if (values.length < 2) {
    return 0
  }

  const mean = average(values)
  const variance = values.reduce((sum, value) => sum + (value - mean) ** 2, 0) / values.length
  return Math.sqrt(variance)
}

function classifyStability(coefficient: number): string {
  if (coefficient <= 6) {
    return 'Stable'
  }
  if (coefficient <= 12) {
    return 'Moderate'
  }
  return 'Volatile'
}

function buildTrendOptions(
  timezone: string,
  unit: string,
  color: string,
  decimals: number,
) {
  return {
    chart: {
      type: 'line',
      height: 220,
      toolbar: { show: false },
      animations: { enabled: true },
    },
    stroke: {
      curve: 'smooth',
      width: 2,
    },
    colors: [color],
    xaxis: {
      type: 'datetime',
      labels: {
        datetimeUTC: false,
        formatter: (value: string) => formatBatteryTime(value, timezone),
      },
    },
    yaxis: {
      labels: {
        formatter: (value: number) => `${value.toFixed(decimals)}${unit}`,
      },
    },
    tooltip: {
      x: {
        formatter: (value: number) => formatBatteryTime(value, timezone),
      },
      y: {
        formatter: (value: number) => `${value.toFixed(decimals)}${unit}`,
      },
    },
  }
}

export function BatteryInsightsPanel({
  history,
  timezone,
  charge,
  runtimeSeconds,
  voltage,
  temperature,
  health,
  batteryType,
  batteryDate,
  manufacturerDate,
}: BatteryInsightsPanelProps) {
  const gaugeValue = Number(health.score.toFixed(2))

  const runtimeSeries = useMemo(
    () => parsePositiveSeries(history.runtime).map((point) => ({ x: point.x, y: point.y / 60 })),
    [history.runtime],
  )
  const voltageSeries = useMemo(() => parsePositiveSeries(history.voltage), [history.voltage])
  const temperatureSeries = useMemo(() => parsePositiveSeries(history.temperature), [history.temperature])
  const chargeSeries = useMemo(() => parsePositiveSeries(history.charge), [history.charge])

  const runtimeValues = runtimeSeries.map((point) => point.y)
  const voltageValues = voltageSeries.map((point) => point.y)
  const temperatureValues = temperatureSeries.map((point) => point.y)

  const runtimeAvg = average(runtimeValues)
  const runtimeStdDev = standardDeviation(runtimeValues)
  const runtimeCv = runtimeAvg > 0 ? (runtimeStdDev / runtimeAvg) * 100 : 0

  const voltageAvg = average(voltageValues)
  const voltageStdDev = standardDeviation(voltageValues)
  const voltageCv = voltageAvg > 0 ? (voltageStdDev / voltageAvg) * 100 : 0

  const temperatureAvg = average(temperatureValues)
  const temperatureStdDev = standardDeviation(temperatureValues)

  const runtimeTrendOptions = useMemo(
    () => buildTrendOptions(timezone, ' min', '#22c55e', 1),
    [timezone],
  )
  const voltageTrendOptions = useMemo(
    () => buildTrendOptions(timezone, ' V', '#38bdf8', 1),
    [timezone],
  )
  const temperatureTrendOptions = useMemo(
    () => buildTrendOptions(timezone, ' °C', '#f59e0b', 1),
    [timezone],
  )

  const chargeRetention = useMemo(() => {
    if (chargeSeries.length === 0) {
      return 0
    }
    const fullChargeSamples = chargeSeries.filter((point) => point.y >= 95).length
    return Number(((fullChargeSamples / chargeSeries.length) * 100).toFixed(1))
  }, [chargeSeries])

  const chargeRetentionOptions = {
    chart: {
      type: 'radialBar',
      height: 220,
      sparkline: { enabled: true },
    },
    labels: ['Retention'],
    plotOptions: {
      radialBar: {
        startAngle: -130,
        endAngle: 130,
        hollow: {
          size: '62%',
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
        gradientToColors: ['#22c55e'],
        stops: [0, 100],
      },
    },
    stroke: {
      lineCap: 'round',
    },
  }

  const hasHealthData = charge > 0 || runtimeSeconds > 0 || voltage > 0 || (temperature ?? 0) > 0
  const hasRuntimeTrend = runtimeSeries.length > 1 || runtimeSeconds > 0
  const hasVoltageTrend = voltageSeries.length > 1 || voltage > 0
  const hasTemperatureTrend = temperatureSeries.length > 1 || (temperature ?? 0) > 0
  const hasChargeRetention = chargeSeries.length > 1

  const lifecycleRows = [
    batteryType.trim() ? { label: 'Type', value: batteryType.trim() } : null,
    batteryDate.trim() ? { label: 'Battery Date', value: batteryDate.trim() } : null,
    manufacturerDate.trim() ? { label: 'Mfr Date', value: manufacturerDate.trim() } : null,
  ].filter(Boolean) as Array<{ label: string; value: string }>

  if (
    !hasHealthData &&
    !hasRuntimeTrend &&
    !hasVoltageTrend &&
    !hasTemperatureTrend &&
    !hasChargeRetention &&
    lifecycleRows.length === 0
  ) {
    return null
  }

  return (
    <div className="battery_insights_grid">
      {hasHealthData ? (
        <article className="chart_card chart_card--compact battery_insight_card">
          <div className="chart_header">
            <h2>Battery Health</h2>
            <p className="chart_subtitle">Quality score derived from charge, runtime, voltage and temperature.</p>
          </div>
          <div className="battery_health_layout">
            <div className="battery_health_gauge">
              <LegacyApexChart options={BATTERY_HEALTH_OPTIONS} series={[gaugeValue]} style={{ height: '100%', width: '100%' }} />
            </div>
            <div className="battery_health_summary">
              <div className="battery_health_level">
                <span className="battery_health_level_label">Health Level</span>
                <span className="battery_health_level_value">
                  {health.level} ({health.score}%)
                </span>
              </div>
              <div className="card_subtitle" style={{ marginBottom: '8px' }}>
                {health.summary}
              </div>
              <div className="battery_health_inputs">
                <span>Charge {charge.toFixed(1)}%</span>
                <span>Runtime {(runtimeSeconds / 60).toFixed(1)} min</span>
                <span>Voltage {voltage.toFixed(1)} V</span>
                <span>Temperature {temperature !== null ? `${temperature.toFixed(1)} °C` : 'N/A'}</span>
              </div>
              {health.recommendations[0] ? (
                <ul className="battery_health_recommendations">
                  <li className="card_subtitle">{health.recommendations[0]}</li>
                </ul>
              ) : null}
            </div>
          </div>
        </article>
      ) : null}

      {hasRuntimeTrend ? (
        <article className="chart_card chart_card--compact battery_insight_card">
          <div className="chart_header">
            <h2>Runtime Stability</h2>
            <p className="chart_subtitle">Runtime consistency over selected period</p>
          </div>
          <div className="chart_container chart_container--sm">
            <LegacyApexChart
              options={runtimeTrendOptions}
              series={[{ name: 'Runtime', data: runtimeSeries }]}
              style={{ height: '100%', width: '100%' }}
            />
          </div>
          <div className="insight_meta">
            <div className="insight_meta_row">
              <span>Average</span>
              <strong>{runtimeAvg.toFixed(1)} min</strong>
            </div>
            <div className="insight_meta_row">
              <span>Std Dev</span>
              <strong>{runtimeStdDev.toFixed(2)} min</strong>
            </div>
            <div className="insight_meta_row">
              <span>Stability</span>
              <strong>{classifyStability(runtimeCv)}</strong>
            </div>
          </div>
        </article>
      ) : null}

      {hasVoltageTrend ? (
        <article className="chart_card chart_card--compact battery_insight_card">
          <div className="chart_header">
            <h2>Voltage Stability</h2>
            <p className="chart_subtitle">Battery voltage trend and variability</p>
          </div>
          <div className="chart_container chart_container--sm">
            <LegacyApexChart
              options={voltageTrendOptions}
              series={[{ name: 'Voltage', data: voltageSeries }]}
              style={{ height: '100%', width: '100%' }}
            />
          </div>
          <div className="insight_meta">
            <div className="insight_meta_row">
              <span>Average</span>
              <strong>{voltageAvg.toFixed(2)} V</strong>
            </div>
            <div className="insight_meta_row">
              <span>Std Dev</span>
              <strong>{voltageStdDev.toFixed(3)} V</strong>
            </div>
            <div className="insight_meta_row">
              <span>Stability</span>
              <strong>{classifyStability(voltageCv)}</strong>
            </div>
          </div>
        </article>
      ) : null}

      {hasTemperatureTrend ? (
        <article className="chart_card chart_card--compact battery_insight_card">
          <div className="chart_header">
            <h2>Temperature Stability</h2>
            <p className="chart_subtitle">Battery temperature behavior over the selected period</p>
          </div>
          <div className="chart_container chart_container--sm">
            <LegacyApexChart
              options={temperatureTrendOptions}
              series={[{ name: 'Temperature', data: temperatureSeries }]}
              style={{ height: '100%', width: '100%' }}
            />
          </div>
          <div className="insight_meta">
            <div className="insight_meta_row">
              <span>Average</span>
              <strong>{temperatureAvg.toFixed(2)} °C</strong>
            </div>
            <div className="insight_meta_row">
              <span>Std Dev</span>
              <strong>{temperatureStdDev.toFixed(3)} °C</strong>
            </div>
          </div>
        </article>
      ) : null}

      {hasChargeRetention ? (
        <article className="chart_card chart_card--compact battery_insight_card">
          <div className="chart_header">
            <h2>Charge Retention</h2>
            <p className="chart_subtitle">Percentage of samples with battery charge at or above 95%</p>
          </div>
          <div className="chart_container chart_container--sm">
            <LegacyApexChart
              options={chargeRetentionOptions}
              series={[chargeRetention]}
              style={{ height: '100%', width: '100%' }}
            />
          </div>
          <div className="insight_badge">Retention score: {chargeRetention.toFixed(1)}%</div>
        </article>
      ) : null}

      {lifecycleRows.length > 0 ? (
        <article className="chart_card chart_card--compact battery_insight_card">
          <div className="chart_header">
            <h2>Battery Lifecycle</h2>
            <p className="chart_subtitle">Lifecycle metadata and replacement context</p>
          </div>
          <div className="insight_meta">
            {lifecycleRows.map((row) => (
              <div className="insight_meta_row" key={`${row.label}:${row.value}`}>
                <span>{row.label}</span>
                <strong>{row.value}</strong>
              </div>
            ))}
          </div>
        </article>
      ) : null}
    </div>
  )
}
