/**
 * Powerpage.
 *
 * Frontend module used by Nutify React UI flows and state management.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useQuery } from '@tanstack/react-query'

import {
  LegacyRealtimeStreamChart,
  type RealtimeAxisConfig,
  type RealtimeSeriesConfig,
} from '../../components/LegacyRealtimeStreamChart'
import { LegacyApexChart } from '../../components/LegacyApexChart'
import { MetricCard } from '../../components/MetricCard'
import { PageHeader } from '../../components/PageHeader'
import {
  PeriodCompactControl,
  createDefaultPeriodSelection,
  createRealtimeWindow,
  formatPeriodLabel,
  type PeriodSelection,
} from '../../components/PeriodToolbar'
import { fetchRawJson } from '../../lib/api/raw'
import { getVariableConfig } from '../../lib/api/settings'
import { getAllUpsData } from '../../lib/api/ups'
import { useCacheWebSocketManager } from '../../lib/realtime/cacheWebSocketManager'
import { useAppStore } from '../../store/appStore'
import {
  aggregateSeries,
  asNullableNumber,
  asRecord,
  buildHistoryQuery,
  buildStatsQuery,
  defaultStats,
  parseHistoryPayload,
  parseMetricsPayload,
  parseStatsPayload,
  readCurrent,
  readRealtimePower,
} from './powerPageSupport'

function parseHasHourData(payload: unknown): boolean {
  if (!payload || typeof payload !== 'object') {
    return false
  }

  const directValue = (payload as { has_data?: unknown }).has_data
  if (typeof directValue === 'boolean') {
    return directValue
  }

  const nestedValue = (payload as { data?: { has_data?: unknown } }).data?.has_data
  if (typeof nestedValue === 'boolean') {
    return nestedValue
  }

  return false
}

function notifyRealtimeModeEnforced() {
  const notifyFn = (window as Window & { notify?: (text: string, level: string, timeout?: number) => void }).notify
  if (typeof notifyFn === 'function') {
    notifyFn(
      'Real Time mode enforced: waiting for 1 hour of data collection. You can switch to other modes from the time range menu.',
      'warning',
      5000,
    )
  }
}

function formatChartTime(value: number | string, timezone: string): string {
  const parsed = typeof value === 'number' ? value : Number(value)
  if (!Number.isFinite(parsed)) {
    return String(value)
  }
  const date = new Date(parsed)
  if (Number.isNaN(date.getTime())) {
    return String(value)
  }
  try {
    return date.toLocaleTimeString([], {
      timeZone: timezone,
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      hour12: false,
    })
  } catch {
    return date.toLocaleTimeString([], {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      hour12: false,
    })
  }
}

export function PowerPage() {
  const bootstrap = useAppStore((state) => state.bootstrap)
  const activeTargetId = useAppStore((state) => state.activeTargetId)
  const targets = useAppStore((state) => state.targets)
  const monitoringProfile = bootstrap?.monitoring.monitoring_profile ?? 'single'
  const bootstrapTimezone = bootstrap?.timezone ?? 'UTC'

  const [draftPeriod, setDraftPeriod] = useState<PeriodSelection>(createDefaultPeriodSelection)
  const [period, setPeriod] = useState<PeriodSelection>(createDefaultPeriodSelection)
  const [latestSnapshot, setLatestSnapshot] = useState<Record<string, unknown>>({})
  const latestRealtimeAtRef = useRef(0)
  const initialModeCheckedRef = useRef('')

  const isRealtimeMode = period.mode === 'realtime'

  useEffect(() => {
    const targetKey = activeTargetId === null ? 'single' : String(activeTargetId)
    if (initialModeCheckedRef.current === targetKey) {
      return
    }
    if (period.mode !== 'today') {
      initialModeCheckedRef.current = targetKey
      return
    }

    let cancelled = false
    void (async () => {
      try {
        const payload = await fetchRawJson('/api/power/has_hour_data', activeTargetId)
        if (cancelled) {
          return
        }
        initialModeCheckedRef.current = targetKey
        if (parseHasHourData(payload)) {
          return
        }
        setPeriod((current) => (current.mode === 'today' ? { ...current, mode: 'realtime' } : current))
        setDraftPeriod((current) => (current.mode === 'today' ? { ...current, mode: 'realtime' } : current))
        notifyRealtimeModeEnforced()
      } catch {
        initialModeCheckedRef.current = targetKey
      }
    })()

    return () => {
      cancelled = true
    }
  }, [activeTargetId, period.mode])

  const { data: variableConfig } = useQuery({
    queryKey: ['power', 'variable-config', activeTargetId],
    queryFn: () => getVariableConfig(activeTargetId),
    staleTime: 10_000,
    refetchInterval: 30_000,
  })

  const timezone = useMemo(() => {
    const scopedTimezone = String(variableConfig?.timezone ?? '').trim()
    return scopedTimezone || bootstrapTimezone
  }, [bootstrapTimezone, variableConfig?.timezone])

  const { data: snapshot } = useQuery({
    queryKey: ['power', 'snapshot', activeTargetId],
    queryFn: () => getAllUpsData(activeTargetId),
    refetchInterval: false,
  })

  const { data: metricsPayload } = useQuery({
    queryKey: ['power', 'metrics', activeTargetId],
    queryFn: () => fetchRawJson('/api/power/metrics', activeTargetId),
    refetchInterval: isRealtimeMode ? 6_000 : 10_000,
  })

  const { data: statsPayload } = useQuery({
    queryKey: ['power', 'stats', activeTargetId, period],
    queryFn: () => {
      const realtimeWindow = createRealtimeWindow()
      const params = buildStatsQuery(period, realtimeWindow)
      return fetchRawJson(`/api/power/stats?${params.toString()}`, activeTargetId)
    },
    refetchInterval: isRealtimeMode ? 6_000 : 12_000,
  })

  const { data: historyPayload } = useQuery({
    queryKey: ['power', 'history', activeTargetId, period],
    queryFn: () => fetchRawJson(`/api/power/history?${buildHistoryQuery(period).toString()}`, activeTargetId),
    enabled: !isRealtimeMode,
    refetchInterval: 15_000,
  })

  useEffect(() => {
    setLatestSnapshot({})
    latestRealtimeAtRef.current = 0
    initialModeCheckedRef.current = ''
  }, [activeTargetId])

  useEffect(() => {
    if (!snapshot) {
      return
    }
    if (latestRealtimeAtRef.current > 0) {
      return
    }
    setLatestSnapshot(asRecord(snapshot))
  }, [snapshot])

  const onRealtimeSnapshot = useCallback((payload: Record<string, unknown>) => {
    latestRealtimeAtRef.current = Date.now()
    setLatestSnapshot(asRecord(payload))
  }, [])

  useCacheWebSocketManager({
    onUpdate: onRealtimeSnapshot,
    enabled: isRealtimeMode,
    monitoringProfile,
    activeTargetId,
  })

  const pollingIntervalMs = useMemo(() => {
    const activeTarget = targets.find((target) => target.id === activeTargetId) ?? null
    const policyValue = activeTarget?.policy?.polling_interval
    const intervalSeconds = Number(policyValue ?? variableConfig?.polling_interval)
    if (Number.isFinite(intervalSeconds) && intervalSeconds > 0) {
      return Math.max(1000, Math.round(intervalSeconds * 1000))
    }
    return 5000
  }, [activeTargetId, targets, variableConfig?.polling_interval])

  const metrics = useMemo(() => parseMetricsPayload(metricsPayload), [metricsPayload])
  const stats = useMemo(() => parseStatsPayload(statsPayload), [statsPayload])
  const history = useMemo(() => parseHistoryPayload(historyPayload), [historyPayload])

  const realtimeData = useMemo(() => asRecord(latestSnapshot), [latestSnapshot])
  const realtimePower = useMemo(() => readRealtimePower(realtimeData), [realtimeData])
  const realtimeInputVoltage = useMemo(() => asNullableNumber(realtimeData.input_voltage), [realtimeData])
  const realtimeLoad = useMemo(() => asNullableNumber(realtimeData.ups_load), [realtimeData])
  const realtimeNominalPower = useMemo(
    () => asNullableNumber(realtimeData.ups_realpower_nominal),
    [realtimeData],
  )

  const realPower = isRealtimeMode
    ? realtimePower ?? readCurrent(stats, metrics, 'ups_realpower')
    : readCurrent(stats, metrics, 'ups_realpower')
  const inputVoltage = isRealtimeMode
    ? realtimeInputVoltage ?? readCurrent(stats, metrics, 'input_voltage')
    : readCurrent(stats, metrics, 'input_voltage')
  const load = isRealtimeMode
    ? realtimeLoad ?? readCurrent(stats, metrics, 'ups_load')
    : readCurrent(stats, metrics, 'ups_load')
  const nominalPower = isRealtimeMode
    ? realtimeNominalPower ?? readCurrent(stats, metrics, 'ups_realpower_nominal')
    : readCurrent(stats, metrics, 'ups_realpower_nominal')

  const realPowerStats = stats.ups_realpower ?? defaultStats()
  const inputVoltageStats = stats.input_voltage ?? defaultStats()

  const statusValueRaw = isRealtimeMode ? realtimeData.ups_status : metrics.ups_status
  const powerStatusRows = useMemo(() => {
    const statusValue =
      statusValueRaw === undefined || statusValueRaw === null || statusValueRaw === ''
        ? 'N/A'
        : String(statusValueRaw)
    const nominalValue = nominalPower > 0 ? `${nominalPower.toFixed(1)}W` : 'N/A'
    return [
      { label: 'Status:', value: statusValue },
      { label: 'Load:', value: `${load.toFixed(1)}%` },
      { label: 'Nominal Power:', value: nominalValue },
    ]
  }, [load, nominalPower, statusValueRaw])

  const chartSeries = useMemo(() => {
    const realPowerSeries = aggregateSeries(
      history.realPower.map((point) => ({ x: point.timestamp, y: point.value })),
    )
    const inputVoltageSeries = aggregateSeries(
      history.inputVoltage.map((point) => ({ x: point.timestamp, y: point.value })),
    )
    return [
      { name: 'Real Power', data: realPowerSeries },
      { name: 'Input Voltage', data: inputVoltageSeries },
    ]
  }, [history.inputVoltage, history.realPower])

  const chartRange = useMemo(() => {
    const allPoints = [...chartSeries[0].data, ...chartSeries[1].data]
    if (!allPoints.length) {
      return { min: undefined, max: undefined }
    }
    return {
      min: Math.min(...allPoints.map((point) => point.x)),
      max: Math.max(...allPoints.map((point) => point.x)),
    }
  }, [chartSeries])

  const hasPowerChartData = useMemo(
    () =>
      chartSeries.some((series) =>
        series.data.some((point) => Number.isFinite(point.y) && Number(point.y) > 0),
      ),
    [chartSeries],
  )

  const chartOptions = useMemo(() => {
    return {
      chart: {
        type: 'line',
        height: 450,
        animations: {
          enabled: true,
          easing: 'linear',
          dynamicAnimation: { speed: 1000 },
        },
        toolbar: { show: true },
      },
      stroke: {
        curve: 'smooth',
        width: [2, 2],
      },
      colors: ['#66DA26', '#FF9800'],
      legend: { horizontalAlign: 'center' },
      xaxis: {
        type: 'datetime',
        min: chartRange.min,
        max: chartRange.max,
        labels: {
          datetimeUTC: false,
          formatter: (value: string) => formatChartTime(value, timezone),
        },
      },
      tooltip: {
        x: {
          formatter: (value: number) => formatChartTime(value, timezone),
        },
        y: { formatter: (value: number) => Number(value).toFixed(1) },
      },
      yaxis: [
        {
          title: { text: 'Real Power (W)', style: { color: '#66DA26' } },
          labels: { formatter: (value: number) => String(Math.round(value)), style: { colors: '#66DA26' } },
        },
        {
          opposite: true,
          title: { text: 'Input Voltage (V)', style: { color: '#FF9800' } },
          labels: { formatter: (value: number) => String(Math.round(value)), style: { colors: '#FF9800' } },
        },
      ],
    }
  }, [chartRange.max, chartRange.min, timezone])

  const realtimeAxes = useMemo<RealtimeAxisConfig[]>(
    () => [
      {
        id: 'power-axis',
        position: 'left',
        title: 'Power (W)',
        color: '#66DA26',
        min: 0,
        formatter: (value) => `${Math.round(value)}`,
      },
      {
        id: 'voltage-axis',
        position: 'right',
        title: 'Voltage (V)',
        color: '#FF9800',
        min: 0,
        formatter: (value) => `${Math.round(value)}`,
      },
    ],
    [],
  )

  const realtimeSeries = useMemo<RealtimeSeriesConfig[]>(
    () => [
      {
        key: 'realtime-power',
        name: 'Real Power',
        color: '#66DA26',
        fillColor: 'rgba(102, 218, 38, 0.22)',
        yAxisId: 'power-axis',
        lineWidth: 2.4,
        precision: 1,
        unit: 'W',
        value: (payload) => readRealtimePower(asRecord(payload)),
      },
      {
        key: 'realtime-input-voltage',
        name: 'Input Voltage',
        color: '#FF9800',
        yAxisId: 'voltage-axis',
        lineWidth: 2,
        precision: 1,
        unit: 'V',
        value: (payload) => asNullableNumber(asRecord(payload).input_voltage),
      },
    ],
    [],
  )

  return (
    <section className="dashboard-section power_page">
      <PageHeader
        title="Power Management"
        subtitle="Real-time monitoring and analysis of UPS power output, efficiency, and load."
        actions={
          <PeriodCompactControl
            value={draftPeriod}
            displayValue={period}
            onChange={setDraftPeriod}
            onApply={setPeriod}
          />
        }
      />

      <div className="stats_grid">
        <MetricCard
          title="Real Power"
          value={`${realPower.toFixed(1)} W`}
          periodLabel={formatPeriodLabel(period)}
          detail={`Min ${realPowerStats.min.toFixed(1)}W | Max ${realPowerStats.max.toFixed(1)}W`}
          icon="fa-bolt"
        />
        <MetricCard
          title="Input Voltage"
          value={`${inputVoltage.toFixed(1)} V`}
          periodLabel={formatPeriodLabel(period)}
          detail={`Min ${inputVoltageStats.min.toFixed(1)}V | Max ${inputVoltageStats.max.toFixed(1)}V`}
          icon="fa-plug-circle-bolt"
        />
        <MetricCard
          title="UPS Status"
          value=""
          periodLabel={formatPeriodLabel(period)}
          rows={powerStatusRows}
          icon="fa-circle-info"
        />
      </div>

      {(isRealtimeMode || hasPowerChartData) ? (
        <article className="chart_card">
          <div className="chart_header">
            <h2>Power Analysis</h2>
            <p className="chart_subtitle">UPS Power, Real Power and Input Voltage</p>
          </div>
          <div className="chart_container chart_container--lg">
            {isRealtimeMode ? (
              <LegacyRealtimeStreamChart
                key={`power-realtime-${String(activeTargetId ?? 'single')}`}
                chartId="powerRealtimeChart"
                latestData={realtimeData}
                pollingIntervalMs={pollingIntervalMs}
                series={realtimeSeries}
                axes={realtimeAxes}
              />
            ) : (
              <LegacyApexChart options={chartOptions} series={chartSeries} style={{ height: '100%', width: '100%' }} />
            )}
          </div>
        </article>
      ) : null}
    </section>
  )
}
