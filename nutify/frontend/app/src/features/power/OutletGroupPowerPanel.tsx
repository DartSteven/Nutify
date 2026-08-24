import { useMemo } from 'react'

import {
  LegacyRealtimeStreamChart,
  type RealtimeAxisConfig,
  type RealtimeSeriesConfig,
} from '../../components/LegacyRealtimeStreamChart'
import { LegacyApexChart } from '../../components/LegacyApexChart'
import { MetricCard } from '../../components/MetricCard'
import { asNullableNumber, asRecord } from './powerPageSupport'
import { outletChartSeries, type OutletGroup } from './outletGroupSupport'
import {
  formatChartAxisTimestamp,
  formatCsvTimestamp,
  spansMultipleLocalDates,
} from '../../lib/utils/chartDateTime'

const OUTLET_COLORS = ['#06B6D4', '#F97316', '#84CC16', '#EC4899', '#A855F7', '#14B8A6', '#F59E0B', '#64748B']

function colorForIndex(index: number): string {
  return OUTLET_COLORS[index % OUTLET_COLORS.length]
}

function readOutletValue(payload: Record<string, unknown>, key: string): number | null {
  const direct = asNullableNumber(payload[key])
  if (direct !== null) {
    return direct
  }
  return asNullableNumber(payload[key.replace(/_/g, '.')])
}

type OutletGroupPowerPanelProps = {
  groups: OutletGroup[]
  isRealtimeMode: boolean
  latestData: Record<string, unknown>
  pollingIntervalMs: number
  timezone: string
  activeTargetKey: string
}

export function OutletGroupPowerPanel({
  groups,
  isRealtimeMode,
  latestData,
  pollingIntervalMs,
  timezone,
  activeTargetKey,
}: OutletGroupPowerPanelProps) {
  const visibleGroups = useMemo(() => groups.filter((group) => group.available || group.series.length > 0), [groups])

  const apexSeries = useMemo(() => outletChartSeries(visibleGroups), [visibleGroups])
  const hasChartData = isRealtimeMode || apexSeries.some((series) => series.data.length > 0)

  const chartRange = useMemo(() => {
    const points = apexSeries.flatMap((series) => series.data)
    if (!points.length) {
      return { min: undefined, max: undefined }
    }
    return {
      min: Math.min(...points.map((point) => point.x)),
      max: Math.max(...points.map((point) => point.x)),
    }
  }, [apexSeries])

  const chartSpansMultipleDates = useMemo(
    () => spansMultipleLocalDates(
      apexSeries.flatMap((series) => series.data.map((point) => point.x)),
      timezone,
    ),
    [apexSeries, timezone],
  )

  const chartOptions = useMemo(() => ({
    chart: {
      type: 'line',
      height: 420,
      toolbar: {
        show: true,
        export: { csv: { categoryFormatter: (value: number) => formatCsvTimestamp(value, timezone) } },
      },
    },
    stroke: { curve: 'smooth', width: 2.4 },
    colors: visibleGroups.map((_, index) => colorForIndex(index)),
    legend: { horizontalAlign: 'center' },
    xaxis: {
      type: 'datetime',
      min: chartRange.min,
      max: chartRange.max,
      labels: {
        datetimeUTC: false,
        formatter: (value: string) => formatChartAxisTimestamp(value, timezone, chartSpansMultipleDates),
      },
    },
    tooltip: {
      x: { formatter: (value: number) => formatCsvTimestamp(value, timezone) },
      y: { formatter: (value: number) => `${Number(value).toFixed(1)} W` },
    },
    yaxis: {
      title: { text: 'Outlet Real Power (W)' },
      labels: { formatter: (value: number) => String(Math.round(value)) },
    },
  }), [chartRange.max, chartRange.min, chartSpansMultipleDates, timezone, visibleGroups])

  const realtimeAxes = useMemo<RealtimeAxisConfig[]>(
    () => [{
      id: 'outlet-power-axis',
      position: 'left',
      title: 'Outlet Power (W)',
      color: '#06B6D4',
      min: 0,
      formatter: (value) => `${Math.round(value)}`,
    }],
    [],
  )

  const realtimeSeries = useMemo<RealtimeSeriesConfig[]>(
    () => visibleGroups.map((group, index) => ({
      key: `outlet-${group.key}`,
      name: group.label,
      color: colorForIndex(index),
      yAxisId: 'outlet-power-axis',
      lineWidth: 2.2,
      precision: 1,
      unit: 'W',
      value: (payload) => readOutletValue(asRecord(payload), group.key),
    })),
    [visibleGroups],
  )

  if (!visibleGroups.length) {
    return null
  }

  return (
    <>
      <div className="stats_grid">
        {visibleGroups.map((group) => (
          <MetricCard
            key={group.key}
            title={group.label}
            value={`${group.current.toFixed(1)} W`}
            periodLabel="Outlet group"
            detail={`Min ${group.stats.min.toFixed(1)}W | Max ${group.stats.max.toFixed(1)}W`}
            icon="fa-plug"
          />
        ))}
      </div>

      {hasChartData ? (
        <article className="chart_card">
          <div className="chart_header">
            <h2>Outlet Group Power Split</h2>
            <p className="chart_subtitle">Real power reported by NUT outlet-group metrics</p>
          </div>
          <div className="chart_container chart_container--lg">
            {isRealtimeMode ? (
              <LegacyRealtimeStreamChart
                key={`outlet-groups-${activeTargetKey}`}
                chartId="outletGroupPowerChart"
                latestData={latestData}
                pollingIntervalMs={pollingIntervalMs}
                series={realtimeSeries}
                axes={realtimeAxes}
              />
            ) : (
              <LegacyApexChart options={chartOptions} series={apexSeries} style={{ height: '100%', width: '100%' }} />
            )}
          </div>
        </article>
      ) : null}
    </>
  )
}
