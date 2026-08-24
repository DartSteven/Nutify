/**
 * Batterypage.
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
  buildBatteryCombinedSeries,
  buildBatteryCombinedOptions,
} from './batteryCharts'
import { buildBatteryHealthAssessment } from './batteryHealthAssessment'
import { BatteryInsightsPanel } from './BatteryInsightsPanel'
import {
  asNullableNumber,
  asRecord,
  buildHistoryQuery,
  buildStatsQuery,
  parseHistoryPayload,
  parseMetricsPayload,
  parseStatsPayload,
  readCurrent,
} from './batteryPageSupport'

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

export function BatteryPage() {
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
        const payload = await fetchRawJson('/api/battery/has_hour_data', activeTargetId)
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
    queryKey: ['battery', 'variable-config', activeTargetId],
    queryFn: () => getVariableConfig(activeTargetId),
    staleTime: 10_000,
    refetchInterval: 30_000,
  })

  const timezone = useMemo(() => {
    const scopedTimezone = String(variableConfig?.timezone ?? '').trim()
    return scopedTimezone || bootstrapTimezone
  }, [bootstrapTimezone, variableConfig?.timezone])

  const { data: snapshot } = useQuery({
    queryKey: ['battery', 'snapshot', activeTargetId],
    queryFn: () => getAllUpsData(activeTargetId),
    refetchInterval: false,
  })

  const { data: metricsPayload } = useQuery({
    queryKey: ['battery', 'metrics', activeTargetId],
    queryFn: () => fetchRawJson('/api/battery/metrics', activeTargetId),
    refetchInterval: isRealtimeMode ? 6_000 : 10_000,
  })

  const { data: statsPayload } = useQuery({
    queryKey: ['battery', 'stats', activeTargetId, period],
    queryFn: () => {
      const realtimeWindow = createRealtimeWindow()
      const params = buildStatsQuery(period, realtimeWindow)
      return fetchRawJson(`/api/battery/stats?${params.toString()}`, activeTargetId)
    },
    refetchInterval: isRealtimeMode ? 6_000 : 12_000,
  })

  const { data: historyPayload } = useQuery({
    queryKey: ['battery', 'history', activeTargetId, period],
    queryFn: () => fetchRawJson(`/api/battery/history?${buildHistoryQuery(period).toString()}`, activeTargetId),
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

  const realtimeCharge = useMemo(() => asNullableNumber(realtimeData.battery_charge), [realtimeData])
  const realtimeRuntimeSeconds = useMemo(() => asNullableNumber(realtimeData.battery_runtime), [realtimeData])
  const realtimeVoltage = useMemo(() => asNullableNumber(realtimeData.battery_voltage), [realtimeData])
  const realtimeTemperature = useMemo(() => asNullableNumber(realtimeData.battery_temperature), [realtimeData])

  const charge = isRealtimeMode
    ? realtimeCharge ?? readCurrent(stats, metrics, 'battery_charge')
    : readCurrent(stats, metrics, 'battery_charge')
  const runtimeSeconds = isRealtimeMode
    ? realtimeRuntimeSeconds ?? readCurrent(stats, metrics, 'battery_runtime')
    : readCurrent(stats, metrics, 'battery_runtime')
  const voltage = isRealtimeMode
    ? realtimeVoltage ?? readCurrent(stats, metrics, 'battery_voltage')
    : readCurrent(stats, metrics, 'battery_voltage')
  const temperature = isRealtimeMode
    ? realtimeTemperature ?? readCurrent(stats, metrics, 'battery_temperature')
    : readCurrent(stats, metrics, 'battery_temperature')

  const chargeStats = stats.battery_charge
  const runtimeStats = stats.battery_runtime
  const voltageStats = stats.battery_voltage
  const combinedSeries = useMemo(() => buildBatteryCombinedSeries(history), [history])
  const combinedChartOptions = useMemo(
    () => buildBatteryCombinedOptions(
      timezone,
      combinedSeries.flatMap((series) => series.data.map((point) => point.x)),
      period.mode === 'range' && period.rangeFrom !== period.rangeTo,
    ),
    [combinedSeries, period.mode, period.rangeFrom, period.rangeTo, timezone],
  )

  const batteryType = String((isRealtimeMode ? realtimeData.battery_type : metrics.battery_type) ?? 'Unknown')
  const batteryDateValue = String((isRealtimeMode ? realtimeData.battery_date : metrics.battery_date) ?? '').trim()
  const manufacturerDateValue = String((isRealtimeMode ? realtimeData.battery_mfr_date : metrics.battery_mfr_date) ?? '').trim()
  const batteryStatusRows = useMemo(() => {
    const statusValue = String((isRealtimeMode ? realtimeData.ups_status : metrics.ups_status) ?? 'N/A')
    const healthValue = charge > 0 ? `${charge.toFixed(1)}%` : 'N/A'
    const rows = [
      { label: 'Status:', value: statusValue },
      { label: 'Type:', value: batteryType },
      { label: 'Health:', value: healthValue },
    ]
    if (batteryDateValue) {
      rows.push({ label: 'Battery Date:', value: batteryDateValue })
    }
    if (manufacturerDateValue) {
      rows.push({ label: 'Mfr Date:', value: manufacturerDateValue })
    }
    return rows
  }, [
    batteryDateValue,
    batteryType,
    charge,
    manufacturerDateValue,
    metrics.ups_status,
    isRealtimeMode,
    realtimeData.ups_status,
  ])

  const combinedRealtimeAxes = useMemo<RealtimeAxisConfig[]>(
    () => [
      { id: 'battery-charge-axis', position: 'left', title: 'Charge (%)', color: '#2E93fA', min: 0, max: 100, formatter: (value) => `${Math.round(value)}` },
      { id: 'battery-runtime-axis', position: 'right', title: 'Runtime (min)', color: '#66DA26', min: 0, formatter: (value) => `${Math.round(value)}` },
      { id: 'battery-voltage-axis', position: 'right', title: 'Voltage (V)', color: '#FF9800', min: 0, formatter: (value) => `${Math.round(value)}` },
    ],
    [],
  )

  const combinedRealtimeSeries = useMemo<RealtimeSeriesConfig[]>(
    () => [
      {
        key: 'battery-charge',
        name: 'Battery Charge',
        color: '#2E93fA',
        yAxisId: 'battery-charge-axis',
        precision: 1,
        unit: '%',
        value: (payload) => asNullableNumber(asRecord(payload).battery_charge),
      },
      {
        key: 'battery-runtime',
        name: 'Runtime',
        color: '#66DA26',
        yAxisId: 'battery-runtime-axis',
        precision: 1,
        unit: 'min',
        value: (payload) => {
          const value = asNullableNumber(asRecord(payload).battery_runtime)
          return value === null ? null : value / 60
        },
      },
      {
        key: 'battery-voltage',
        name: 'Voltage',
        color: '#FF9800',
        yAxisId: 'battery-voltage-axis',
        precision: 1,
        unit: 'V',
        value: (payload) => asNullableNumber(asRecord(payload).battery_voltage),
      },
    ],
    [],
  )

  const healthAssessment = useMemo(
    () => buildBatteryHealthAssessment(charge, runtimeSeconds / 60, voltage, temperature),
    [charge, runtimeSeconds, temperature, voltage],
  )
  const hasCombinedChartData = useMemo(
    () =>
      !isRealtimeMode || combinedSeries.some((series) =>
        series.data.some((point) => Number.isFinite(point.x) && Number.isFinite(point.y)),
      ),
    [combinedSeries, isRealtimeMode],
  )

  return (
    <section className="dashboard-section battery_page">
      <PageHeader
        title="Battery Management"
        subtitle="Comprehensive analysis of your UPS battery status and health"
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
        <MetricCard title="Battery Charge" value={`${charge.toFixed(1)}%`} periodLabel={formatPeriodLabel(period)} detail={`Min ${(chargeStats?.min ?? 0).toFixed(1)}% | Max ${(chargeStats?.max ?? 0).toFixed(1)}%`} icon="fa-battery-full" />
        <MetricCard title="Runtime Remaining" value={`${(runtimeSeconds / 60).toFixed(1)} min`} periodLabel={formatPeriodLabel(period)} detail={`Min ${((runtimeStats?.min ?? 0) / 60).toFixed(1)}min | Max ${((runtimeStats?.max ?? 0) / 60).toFixed(1)}min`} icon="fa-clock" />
        <MetricCard title="Battery Voltage" value={`${voltage.toFixed(1)} V`} periodLabel={formatPeriodLabel(period)} detail={`Min ${(voltageStats?.min ?? 0).toFixed(1)}V | Max ${(voltageStats?.max ?? 0).toFixed(1)}V`} icon="fa-bolt" />
        <MetricCard title="Battery Status" value="" periodLabel={formatPeriodLabel(period)} rows={batteryStatusRows} icon="fa-circle-info" />
      </div>

      {(isRealtimeMode || hasCombinedChartData) ? (
        <article className="chart_card">
          <div className="chart_header">
            <h2>Battery Analysis</h2>
            <p className="chart_subtitle">Level, Runtime and Voltage</p>
          </div>
          <div className="chart_container chart_container--lg">
            {isRealtimeMode ? (
              <LegacyRealtimeStreamChart
                key={`battery-realtime-${String(activeTargetId ?? 'single')}`}
                chartId="batteryRealtimeChart"
                latestData={realtimeData}
                pollingIntervalMs={pollingIntervalMs}
                series={combinedRealtimeSeries}
                axes={combinedRealtimeAxes}
              />
            ) : (
              <LegacyApexChart options={combinedChartOptions} series={combinedSeries} style={{ height: '100%', width: '100%' }} />
            )}
          </div>
        </article>
      ) : null}

      <BatteryInsightsPanel
        history={history}
        timezone={timezone}
        charge={charge}
        runtimeSeconds={runtimeSeconds}
        voltage={voltage}
        temperature={temperature}
        health={healthAssessment}
        batteryType={batteryType}
        batteryDate={batteryDateValue}
        manufacturerDate={manufacturerDateValue}
      />
    </section>
  )
}
