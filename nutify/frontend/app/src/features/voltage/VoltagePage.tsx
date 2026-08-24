/**
 * Voltagepage.
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
  type PeriodSelection,
} from '../../components/PeriodToolbar'
import { fetchRawJson } from '../../lib/api/raw'
import { getVariableConfig } from '../../lib/api/settings'
import { getAllUpsData } from '../../lib/api/ups'
import { useCacheWebSocketManager } from '../../lib/realtime/cacheWebSocketManager'
import { useAppStore } from '../../store/appStore'
import { formatCsvTimestamp, spansMultipleLocalDates } from '../../lib/utils/chartDateTime'
import { VoltageInsightsPanel } from './VoltageInsightsPanel'
import {
  asNullableNumber,
  asRecord,
  buildHistoryQuery,
  formatVoltageTime,
  lastPositiveValue,
  metricCurrent,
  notifyRealtimeModeEnforced,
  parseHistoryPayload,
  parseHasHourData,
  parseMetricsPayload,
} from './voltagePageSupport'

export function VoltagePage() {
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
        const payload = await fetchRawJson('/api/voltage/has_hour_data', activeTargetId)
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
    queryKey: ['voltage', 'variable-config', activeTargetId],
    queryFn: () => getVariableConfig(activeTargetId),
    staleTime: 10_000,
    refetchInterval: 30_000,
  })

  const timezone = useMemo(() => {
    const scopedTimezone = String(variableConfig?.timezone ?? '').trim()
    return scopedTimezone || bootstrapTimezone
  }, [bootstrapTimezone, variableConfig?.timezone])

  const { data: snapshot } = useQuery({
    queryKey: ['voltage', 'snapshot', activeTargetId],
    queryFn: () => getAllUpsData(activeTargetId),
    refetchInterval: false,
  })

  const { data: metricsPayload } = useQuery({
    queryKey: ['voltage', 'metrics', activeTargetId],
    queryFn: () => fetchRawJson('/api/voltage/metrics', activeTargetId),
    refetchInterval: isRealtimeMode ? 6_000 : 10_000,
  })

  const { data: historyPayload } = useQuery({
    queryKey: ['voltage', 'history', activeTargetId, period],
    queryFn: () => {
      const realtimeWindow = createRealtimeWindow()
      const params = buildHistoryQuery(period, realtimeWindow)
      return fetchRawJson(`/api/voltage/history?${params.toString()}`, activeTargetId)
    },
    enabled: !isRealtimeMode,
    refetchInterval: 12_000,
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
  const history = useMemo(() => parseHistoryPayload(historyPayload), [historyPayload])
  const realtimeData = useMemo(() => asRecord(latestSnapshot), [latestSnapshot])

  const inputVoltage = isRealtimeMode
    ? asNullableNumber(realtimeData.input_voltage) ?? metricCurrent(metrics, history, 'input_voltage')
    : metricCurrent(metrics, history, 'input_voltage')
  const nominalVoltage = isRealtimeMode
    ? asNullableNumber(realtimeData.input_voltage_nominal) ?? metricCurrent(metrics, history, 'input_voltage_nominal')
    : metricCurrent(metrics, history, 'input_voltage_nominal')
  const transferLow = isRealtimeMode
    ? asNullableNumber(realtimeData.input_transfer_low) ?? metricCurrent(metrics, history, 'input_transfer_low')
    : metricCurrent(metrics, history, 'input_transfer_low')
  const transferHigh = isRealtimeMode
    ? asNullableNumber(realtimeData.input_transfer_high) ?? metricCurrent(metrics, history, 'input_transfer_high')
    : metricCurrent(metrics, history, 'input_transfer_high')
  const sensitivityRaw = String((isRealtimeMode ? realtimeData.input_sensitivity : metrics.input_sensitivity) ?? '').trim()
  const sensitivity = sensitivityRaw || 'unknown'

  const hasSensitivityData = sensitivityRaw.length > 0 && !['unknown', 'unknow', 'n/a', 'na', '--', 'none'].includes(sensitivityRaw.toLowerCase())

  const historyInputVoltageValues = history.input_voltage.map((point) => point.value).filter((value) => value > 0)
  const inputVoltageMin = historyInputVoltageValues.length > 0 ? Math.min(...historyInputVoltageValues) : null
  const inputVoltageMax = historyInputVoltageValues.length > 0 ? Math.max(...historyInputVoltageValues) : null

  const fallbackInputVoltage = lastPositiveValue(history.input_voltage)
  const fallbackNominalVoltage = lastPositiveValue(history.input_voltage_nominal)
  const fallbackTransferLow = lastPositiveValue(history.input_transfer_low)
  const fallbackTransferHigh = lastPositiveValue(history.input_transfer_high)

  const displayInputVoltage = inputVoltage > 0 ? inputVoltage : fallbackInputVoltage ?? 0
  const displayNominalVoltage = nominalVoltage > 0 ? nominalVoltage : fallbackNominalVoltage ?? 0
  const displayTransferLow = transferLow > 0 ? transferLow : fallbackTransferLow ?? 0
  const displayTransferHigh = transferHigh > 0 ? transferHigh : fallbackTransferHigh ?? 0

  const hasInputVoltageData = displayInputVoltage > 0
  const hasNominalVoltageData = displayNominalVoltage > 0
  const hasTransferLowData = displayTransferLow > 0
  const hasTransferHighData = displayTransferHigh > 0

  const inputVoltageDetail =
    inputVoltageMin !== null && inputVoltageMax !== null
      ? `Min ${inputVoltageMin.toFixed(1)}V | Max ${inputVoltageMax.toFixed(1)}V`
      : undefined

  const voltageSeries = useMemo(() => {
    const series = [
      { name: 'INPUT VOLTAGE', data: history.input_voltage.map((point) => ({ x: point.timestamp, y: point.value })) },
    ]
    if (history.output_voltage.length > 0) {
      series.push({
        name: 'OUTPUT VOLTAGE',
        data: history.output_voltage.map((point) => ({ x: point.timestamp, y: point.value })),
      })
    }
    if (history.input_voltage_nominal.length > 0) {
      series.push({
        name: 'INPUT NOMINAL',
        data: history.input_voltage_nominal.map((point) => ({ x: point.timestamp, y: point.value })),
      })
    } else if (history.input_voltage.length > 0) {
      series.push({
        name: 'INPUT NOMINAL',
        data: history.input_voltage.map((point) => ({ x: point.timestamp, y: displayNominalVoltage })),
      })
    }
    return series
  }, [displayNominalVoltage, history.input_voltage, history.input_voltage_nominal, history.output_voltage])

  const voltageChartSpansMultipleDates = useMemo(
    () => (
      (period.mode === 'range' && period.rangeFrom !== period.rangeTo)
      || spansMultipleLocalDates(
        voltageSeries.flatMap((series) => series.data.map((point) => point.x)),
        timezone,
      )
    ),
    [period.mode, period.rangeFrom, period.rangeTo, timezone, voltageSeries],
  )

  const voltageOptions = useMemo(() => {
    const metricNames = voltageSeries.map((item) => item.name)
    const colors: string[] = []
    const strokeWidths: number[] = []
    const dashArrays: number[] = []
    metricNames.forEach((name) => {
      if (name === 'INPUT VOLTAGE') {
        colors.push('#2E93fA')
        strokeWidths.push(2)
        dashArrays.push(0)
        return
      }
      if (name === 'OUTPUT VOLTAGE') {
        colors.push('#66DA26')
        strokeWidths.push(2)
        dashArrays.push(0)
        return
      }
      colors.push('#546E7A')
      strokeWidths.push(1)
      dashArrays.push(5)
    })
    return {
      chart: {
        type: 'line',
        height: 350,
        animations: { enabled: true, easing: 'linear', dynamicAnimation: { speed: 1000 } },
        toolbar: {
          show: true,
          export: { csv: { categoryFormatter: (value: number) => formatCsvTimestamp(value, timezone) } },
        },
      },
      stroke: { curve: 'smooth', width: strokeWidths, dashArray: dashArrays },
      colors,
      legend: { show: true, position: 'top' },
      xaxis: {
        type: 'datetime',
        labels: {
          datetimeUTC: false,
          formatter: (value: string) => formatVoltageTime(value, timezone, voltageChartSpansMultipleDates),
        },
      },
      tooltip: {
        x: {
          formatter: (value: number) => formatCsvTimestamp(value, timezone),
        },
      },
      yaxis: { labels: { formatter: (value: number) => `${value.toFixed(1)}V` } },
    }
  }, [timezone, voltageChartSpansMultipleDates, voltageSeries])

  const transferSeries = useMemo(
    () => [
      { name: 'INPUT TRANSFER LOW', data: history.input_voltage.map((point) => ({ x: point.timestamp, y: displayTransferLow })) },
      { name: 'INPUT TRANSFER HIGH', data: history.input_voltage.map((point) => ({ x: point.timestamp, y: displayTransferHigh })) },
      { name: 'NOMINAL REFERENCE', data: history.input_voltage.map((point) => ({ x: point.timestamp, y: displayNominalVoltage })) },
    ],
    [displayNominalVoltage, displayTransferHigh, displayTransferLow, history.input_voltage],
  )

  const hasVoltageChartData = useMemo(
    () =>
      !isRealtimeMode || voltageSeries.some((series) =>
        series.data.some((point) => Number.isFinite(point.x) && Number.isFinite(point.y)),
      ),
    [isRealtimeMode, voltageSeries],
  )

  const hasTransferChartData = useMemo(
    () =>
      !isRealtimeMode || transferSeries.some((series) =>
        series.data.some((point) => Number.isFinite(point.x) && Number.isFinite(point.y)),
      ),
    [isRealtimeMode, transferSeries],
  )

  const hasVoltageMonitorCard = isRealtimeMode || hasVoltageChartData
  const hasTransferThresholdCard = isRealtimeMode || hasTransferChartData
  const useTwoColumnPrimaryCharts = hasVoltageMonitorCard && hasTransferThresholdCard

  const transferOptions = useMemo(
    () => ({
      chart: {
        type: 'line',
        height: 350,
        animations: { enabled: true, easing: 'linear', dynamicAnimation: { speed: 1000 } },
        toolbar: {
          show: true,
          export: { csv: { categoryFormatter: (value: number) => formatCsvTimestamp(value, timezone) } },
        },
      },
      stroke: { curve: 'smooth', width: [2, 2, 1], dashArray: [0, 0, 5] },
      colors: ['#FF4560', '#FF4560', '#546E7A'],
      legend: { show: true, position: 'top' },
      xaxis: {
        type: 'datetime',
        labels: {
          datetimeUTC: false,
          formatter: (value: string) => formatVoltageTime(value, timezone, voltageChartSpansMultipleDates),
        },
      },
      tooltip: {
        x: {
          formatter: (value: number) => formatCsvTimestamp(value, timezone),
        },
      },
      yaxis: { labels: { formatter: (value: number) => `${value.toFixed(1)}V` } },
    }),
    [timezone, voltageChartSpansMultipleDates],
  )

  const realtimeVoltageAxes = useMemo<RealtimeAxisConfig[]>(
    () => [{ id: 'voltage-axis', position: 'left', title: 'Voltage (V)', color: '#2E93fA', min: 0, formatter: (value) => `${value.toFixed(1)}` }],
    [],
  )

  const realtimeVoltageSeries = useMemo<RealtimeSeriesConfig[]>(
    () => [
      { key: 'input-voltage', name: 'INPUT VOLTAGE', color: '#2E93fA', fillColor: 'rgba(46, 147, 250, 0.16)', yAxisId: 'voltage-axis', precision: 1, unit: 'V', value: (payload) => asNullableNumber(asRecord(payload).input_voltage) },
      { key: 'output-voltage', name: 'OUTPUT VOLTAGE', color: '#66DA26', yAxisId: 'voltage-axis', precision: 1, unit: 'V', value: (payload) => asNullableNumber(asRecord(payload).output_voltage) },
      { key: 'nominal-voltage', name: 'INPUT NOMINAL', color: '#546E7A', yAxisId: 'voltage-axis', precision: 1, unit: 'V', value: (payload) => asNullableNumber(asRecord(payload).input_voltage_nominal) },
    ],
    [],
  )

  const realtimeThresholdAxes = useMemo<RealtimeAxisConfig[]>(
    () => [{ id: 'threshold-axis', position: 'left', title: 'Voltage (V)', color: '#B0BEC5', min: 0, formatter: (value) => `${value.toFixed(1)}` }],
    [],
  )

  const realtimeThresholdSeries = useMemo<RealtimeSeriesConfig[]>(
    () => [
      { key: 'transfer-low', name: 'INPUT TRANSFER LOW', color: '#FF4560', yAxisId: 'threshold-axis', precision: 1, unit: 'V', value: (payload) => asNullableNumber(asRecord(payload).input_transfer_low) },
      { key: 'transfer-high', name: 'INPUT TRANSFER HIGH', color: '#FF4560', yAxisId: 'threshold-axis', precision: 1, unit: 'V', value: (payload) => asNullableNumber(asRecord(payload).input_transfer_high) },
      { key: 'nominal-reference', name: 'NOMINAL REFERENCE', color: '#546E7A', yAxisId: 'threshold-axis', precision: 1, unit: 'V', value: (payload) => asNullableNumber(asRecord(payload).input_voltage_nominal) },
    ],
    [],
  )

  return (
    <section className="dashboard-section voltage_page">
      <PageHeader
        title="Voltage Management"
        subtitle="Real-time monitoring of voltage, current and power quality"
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
        {hasSensitivityData ? <MetricCard title="Input Sensitivity" value={sensitivity} periodLabel="Now" icon="fa-sliders-h" /> : null}
        {hasTransferHighData ? <MetricCard title="Transfer High" value={`${displayTransferHigh.toFixed(1)} V`} periodLabel="Now" icon="fa-right-left" /> : null}
        {hasTransferLowData ? <MetricCard title="Transfer Low" value={`${displayTransferLow.toFixed(1)} V`} periodLabel="Now" icon="fa-right-left" /> : null}
        {hasInputVoltageData ? (
          <MetricCard
            title="Input Voltage"
            value={`${displayInputVoltage.toFixed(1)} V`}
            periodLabel="Now"
            detail={inputVoltageDetail}
            icon="fa-bolt"
          />
        ) : null}
        {hasNominalVoltageData ? (
          <MetricCard title="Nominal Voltage" value={`${displayNominalVoltage.toFixed(1)} V`} periodLabel="Reference" icon="fa-circle-info" />
        ) : null}
      </div>

      <div className={`charts_grid ${useTwoColumnPrimaryCharts ? 'charts_grid--two' : ''}`.trim()}>
        {hasVoltageMonitorCard ? (
          <article className="chart_card">
            <div className="chart_header">
              <h2>Voltage Monitor</h2>
              <p className="chart_subtitle">Real-time voltage monitoring with nominal values</p>
            </div>
            <div className="chart_container chart_container--md">
              {isRealtimeMode ? (
                <LegacyRealtimeStreamChart
                  key={`voltage-realtime-${String(activeTargetId ?? 'single')}`}
                  chartId="voltageRealtimeChart"
                  latestData={realtimeData}
                  pollingIntervalMs={pollingIntervalMs}
                  series={realtimeVoltageSeries}
                  axes={realtimeVoltageAxes}
                />
              ) : (
                <LegacyApexChart options={voltageOptions} series={voltageSeries} style={{ height: '100%', width: '100%' }} />
              )}
            </div>
          </article>
        ) : null}

        {hasTransferThresholdCard ? (
          <article className="chart_card">
            <div className="chart_header">
              <h2>Transfer Thresholds</h2>
              <p className="chart_subtitle">Operating voltage boundaries</p>
            </div>
            <div className="chart_container chart_container--md">
              {isRealtimeMode ? (
                <LegacyRealtimeStreamChart
                  key={`voltage-thresholds-realtime-${String(activeTargetId ?? 'single')}`}
                  chartId="voltageThresholdsRealtimeChart"
                  latestData={realtimeData}
                  pollingIntervalMs={pollingIntervalMs}
                  series={realtimeThresholdSeries}
                  axes={realtimeThresholdAxes}
                />
              ) : (
                <LegacyApexChart options={transferOptions} series={transferSeries} style={{ height: '100%', width: '100%' }} />
              )}
            </div>
          </article>
        ) : null}
      </div>

      <VoltageInsightsPanel
        history={history}
        displayInputVoltage={displayInputVoltage}
        displayNominalVoltage={displayNominalVoltage}
        displayTransferLow={displayTransferLow}
        displayTransferHigh={displayTransferHigh}
        timezone={timezone}
      />
    </section>
  )
}
