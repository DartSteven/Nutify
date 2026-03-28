/**
 * Energypage.
 *
 * Frontend module used by Nutify React UI flows and state management.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useQuery } from '@tanstack/react-query'

import { LegacyApexChart } from '../../components/LegacyApexChart'
import { MetricCard } from '../../components/MetricCard'
import { PageHeader } from '../../components/PageHeader'
import {
  PeriodCompactControl,
  createDefaultPeriodSelection,
  formatPeriodLabel,
  type PeriodSelection,
} from '../../components/PeriodToolbar'
import { fetchRawJson } from '../../lib/api/raw'
import { getVariableConfig } from '../../lib/api/settings'
import { getAllUpsData } from '../../lib/api/ups'
import { useCacheWebSocketManager } from '../../lib/realtime/cacheWebSocketManager'
import { useAppStore } from '../../store/appStore'
import { EnergyDetailModal } from './EnergyDetailModal'
import { EnergyRealtimeCostChart, type RealtimeStats } from './EnergyRealtimeCostChart'
import {
  buildDetailChartOptions,
  buildDistributionChartOptions,
  buildTrendChartOptions,
} from './energyCharts'
import {
  asRecord,
  buildDataQuery,
  buildInitialDetailWindow,
  buildNextDetailWindow,
  buildTrendQuery,
  createEmptySummary,
  formatEnergyMetric,
  getCurrencyIcon,
  getCurrencySymbol,
  normalizeCurrencyCode,
  parseSeries,
  parseSummary,
  resolveRealtimeMetrics,
  type EnergyBucketLevel,
  type EnergyDetailWindow,
  type EnergySeriesPoint,
  type RealtimeEnergyMetrics,
} from './energyPageSupport'
import { notifyRealtimeModeEnforced, parseHasHourData } from './energyPageGuards'

type DetailState = {
  open: boolean
  title: string
  level: EnergyBucketLevel
  series: EnergySeriesPoint[]
  loading: boolean
}

function createDefaultDetailState(): DetailState {
  return {
    open: false,
    title: '',
    level: 'hour',
    series: [],
    loading: false,
  }
}

export function EnergyPage() {
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
  const [realtimeChartStats, setRealtimeChartStats] = useState<RealtimeEnergyMetrics | null>(null)
  const [detailState, setDetailState] = useState<DetailState>(createDefaultDetailState)

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
        const payload = await fetchRawJson('/api/energy/has_hour_data', activeTargetId)
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
    queryKey: ['energy', 'variable-config', activeTargetId],
    queryFn: () => getVariableConfig(activeTargetId),
    staleTime: 10_000,
    refetchInterval: 30_000,
  })

  const timezone = useMemo(() => {
    const scopedTimezone = String(variableConfig?.timezone ?? '').trim()
    return scopedTimezone || bootstrapTimezone
  }, [bootstrapTimezone, variableConfig?.timezone])

  const { data: snapshot } = useQuery({
    queryKey: ['energy', 'snapshot', activeTargetId],
    queryFn: () => getAllUpsData(activeTargetId),
    refetchInterval: false,
  })

  const { data: summaryPayload } = useQuery({
    queryKey: ['energy', 'summary', activeTargetId, period],
    queryFn: () => fetchRawJson(`/api/energy/data?${buildDataQuery(period).toString()}`, activeTargetId),
    enabled: !isRealtimeMode,
    refetchInterval: 12_000,
  })

  const { data: trendPayload } = useQuery({
    queryKey: ['energy', 'trend', activeTargetId, period],
    queryFn: () => fetchRawJson(`/api/energy/cost-trend?${buildTrendQuery(period).toString()}`, activeTargetId),
    enabled: !isRealtimeMode,
    refetchInterval: 15_000,
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

  useEffect(() => {
    setLatestSnapshot({})
    latestRealtimeAtRef.current = 0
    initialModeCheckedRef.current = ''
    setRealtimeChartStats(null)
    setDetailState(createDefaultDetailState())
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

  const variableCurrencyCode = normalizeCurrencyCode(variableConfig?.currency ?? 'EUR')
  const variableCurrencySymbol = getCurrencySymbol(variableCurrencyCode)
  const pricePerKwh = Number.isFinite(variableConfig?.price_per_kwh) ? Math.max(0, variableConfig?.price_per_kwh ?? 0) : 0
  const co2Factor = Number.isFinite(variableConfig?.co2_factor) ? Math.max(0, variableConfig?.co2_factor ?? 0) : 0

  const apiSummary = useMemo(() => parseSummary(summaryPayload, variableCurrencyCode), [summaryPayload, variableCurrencyCode])
  const trendSeries = useMemo(() => parseSeries(trendPayload), [trendPayload])

  const currencyCode = useMemo(
    () => (isRealtimeMode ? variableCurrencyCode : normalizeCurrencyCode(apiSummary.currencyCode || variableCurrencyCode)),
    [apiSummary.currencyCode, isRealtimeMode, variableCurrencyCode],
  )
  const currencySymbol = useMemo(
    () =>
      isRealtimeMode
        ? variableCurrencySymbol
        : String(apiSummary.currencySymbol || '').trim() || getCurrencySymbol(currencyCode),
    [apiSummary.currencySymbol, currencyCode, isRealtimeMode, variableCurrencySymbol],
  )

  const realtimeMetrics = useMemo(
    () => resolveRealtimeMetrics(latestSnapshot, realtimeChartStats, pricePerKwh, co2Factor),
    [co2Factor, latestSnapshot, pricePerKwh, realtimeChartStats],
  )

  const summary = useMemo(() => {
    if (isRealtimeMode) {
      const realtimeSummary = createEmptySummary(currencyCode)
      realtimeSummary.totalEnergyWh = realtimeMetrics.powerWatts
      realtimeSummary.totalCost = realtimeMetrics.totalCost
      realtimeSummary.averageLoad = realtimeMetrics.loadPercent
      realtimeSummary.co2Kg = realtimeMetrics.co2Kg
      return realtimeSummary
    }

    return {
      ...apiSummary,
      currencyCode,
      currencySymbol,
    }
  }, [apiSummary, currencyCode, currencySymbol, isRealtimeMode, realtimeMetrics])
  const totalCostCurrencySymbol = summary.currencySymbol || currencySymbol

  const currentRate = useMemo(() => {
    if (!variableConfig) {
      return '--'
    }
    return `${pricePerKwh.toFixed(4)}${summary.currencySymbol || currencySymbol}/kWh`
  }, [currencySymbol, pricePerKwh, summary.currencySymbol, variableConfig])

  const loadDetailSeries = useCallback(
    async (windowData: EnergyDetailWindow): Promise<EnergySeriesPoint[]> => {
      const params = new URLSearchParams()
      params.set('from_time', windowData.fromIso)
      params.set('to_time', windowData.toIso)
      params.set('detail_type', windowData.level)
      const payload = await fetchRawJson(`/api/energy/detailed?${params.toString()}`, activeTargetId)
      return parseSeries(payload)
    },
    [activeTargetId],
  )

  const openDetailModal = useCallback(
    async (windowData: EnergyDetailWindow) => {
      setDetailState({
        open: true,
        title: windowData.title,
        level: windowData.level,
        series: [],
        loading: true,
      })

      try {
        const series = await loadDetailSeries(windowData)
        setDetailState({
          open: true,
          title: windowData.title,
          level: windowData.level,
          series,
          loading: false,
        })
      } catch (error) {
        console.error('Error loading detailed energy data', error)
        setDetailState({
          open: true,
          title: windowData.title,
          level: windowData.level,
          series: [],
          loading: false,
        })
      }
    },
    [loadDetailSeries],
  )

  const handleTrendBarSelect = useCallback(
    (point: EnergySeriesPoint) => {
      const windowData = buildInitialDetailWindow(point, period.mode)
      void openDetailModal(windowData)
    },
    [openDetailModal, period.mode],
  )

  const handleDetailBarSelect = useCallback(
    (point: EnergySeriesPoint) => {
      const windowData = buildNextDetailWindow(point, detailState.level)
      if (!windowData) {
        return
      }
      void openDetailModal(windowData)
    },
    [detailState.level, openDetailModal],
  )

  const trendChartSeries = useMemo(
    () => [
      {
        name: 'Energy Cost',
        data: trendSeries,
      },
    ],
    [trendSeries],
  )
  const hasTrendChartData = useMemo(
    () => trendSeries.some((point) => Number.isFinite(point.y) && Number(point.y) > 0),
    [trendSeries],
  )

  const trendModeForOptions = period.mode === 'range' ? 'range' : period.mode === 'day' ? 'day' : 'today'
  const trendBucketLevel = useMemo<EnergyBucketLevel>(() => {
    const firstPoint = trendSeries[0]
    if (firstPoint?.level) {
      return firstPoint.level
    }
    if (trendModeForOptions === 'range') {
      return 'day'
    }
    return 'hour'
  }, [trendModeForOptions, trendSeries])
  const trendChartOptions = useMemo(
    () =>
      buildTrendChartOptions({
        mode: trendModeForOptions,
        bucketLevel: trendBucketLevel,
        timezone,
        currencySymbol,
        pricePerKwh,
        trendSeries,
        onBarSelect: handleTrendBarSelect,
      }),
    [currencySymbol, handleTrendBarSelect, pricePerKwh, timezone, trendModeForOptions, trendSeries, trendBucketLevel],
  )

  const distributionSeries = useMemo(
    () => [
      summary.distribution.morning,
      summary.distribution.afternoon,
      summary.distribution.evening,
      summary.distribution.night,
    ],
    [summary.distribution],
  )
  const hasDistributionChartData = useMemo(
    () => distributionSeries.some((value) => Number.isFinite(Number(value)) && Number(value) > 0),
    [distributionSeries],
  )

  const distributionChartOptions = useMemo(
    () =>
      buildDistributionChartOptions({
        currencySymbol,
      }),
    [currencySymbol],
  )

  const detailChartOptions = useMemo(
    () =>
      buildDetailChartOptions({
        level: detailState.level,
        timezone,
        currencySymbol,
        pricePerKwh,
        onBarSelect: detailState.level !== 'minute' ? handleDetailBarSelect : undefined,
      }),
    [currencySymbol, detailState.level, handleDetailBarSelect, pricePerKwh, timezone],
  )

  const onRealtimeChartStats = useCallback(
    (stats: RealtimeStats) => {
      setRealtimeChartStats({
        powerWatts: stats.powerWatts,
        loadPercent: stats.loadPercent,
        totalCost: stats.costValue,
        co2Kg: (stats.powerWatts / 1000) * co2Factor,
      })
    },
    [co2Factor],
  )

  return (
    <section className="dashboard-section energy_page">
      <PageHeader
        title="Energy Management"
        subtitle="Comprehensive analysis of your UPS energy consumption and costs"
        actions={
          <>
            <div className="rate_display">
              <span className="rate_label">Current Rate:</span>
              <span className="rate_value">{currentRate}</span>
              <a className="rate_edit" href="/settings?view=target&tab=powerflow" title="Edit in Settings">
                <i className="fas fa-edit" aria-hidden="true" />
                <span className="sr-only">Edit rate in settings</span>
              </a>
            </div>
            <PeriodCompactControl
              value={draftPeriod}
              displayValue={period}
              onChange={setDraftPeriod}
              onApply={setPeriod}
            />
          </>
        }
      />

      <div className="stats_grid">
        <MetricCard
          title="Total Energy Used"
          value={formatEnergyMetric(summary.totalEnergyWh, period.mode)}
          periodLabel={formatPeriodLabel(period)}
          icon="fa-bolt"
        />
        <MetricCard
          title="Total Cost"
          value={`${totalCostCurrencySymbol}${summary.totalCost.toFixed(isRealtimeMode ? 4 : 2)}`}
          periodLabel={formatPeriodLabel(period)}
          icon={getCurrencyIcon(summary.currencyCode)}
        />
        <MetricCard
          title="Average Load"
          value={`${summary.averageLoad.toFixed(1)}%`}
          periodLabel={formatPeriodLabel(period)}
          icon="fa-plug-circle-bolt"
        />
        <MetricCard
          title="CO₂ Emissions"
          value={`${summary.co2Kg.toFixed(2)} kg`}
          periodLabel={formatPeriodLabel(period)}
          icon="fa-leaf"
        />
      </div>

      <div className={isRealtimeMode ? 'charts_grid' : 'charts_grid charts_grid--two'} id="chartsContainer">
        {(isRealtimeMode || hasTrendChartData) ? (
          <article className="chart_card" id="costTrendCard">
            <div className="chart_header">
              <h2>Energy Cost Trend</h2>
            </div>
            <div id="costTrendChart" className="chart_container" style={{ height: '350px' }}>
              {isRealtimeMode ? (
                <EnergyRealtimeCostChart
                  key={String(activeTargetId ?? 'single')}
                  latestData={latestSnapshot}
                  pricePerKwh={pricePerKwh}
                  currencySymbol={currencySymbol}
                  pollingIntervalMs={pollingIntervalMs}
                  onRealtimeStats={onRealtimeChartStats}
                />
              ) : (
                <LegacyApexChart options={trendChartOptions} series={trendChartSeries} style={{ height: '100%', width: '100%' }} />
              )}
            </div>
          </article>
        ) : null}

        {!isRealtimeMode && hasDistributionChartData ? (
          <article className="chart_card" id="dailyDistributionCard">
            <div className="chart_header">
              <h2>Daily Cost Distribution</h2>
            </div>
            <div id="usagePatternChart" className="chart_container" style={{ height: '350px' }}>
              <LegacyApexChart
                options={distributionChartOptions}
                series={distributionSeries}
                style={{ height: '100%', width: '100%' }}
              />
            </div>
          </article>
        ) : null}
      </div>

      <EnergyDetailModal
        open={detailState.open && !isRealtimeMode}
        title={detailState.title}
        loading={detailState.loading}
        options={detailChartOptions}
        series={detailState.series}
        onClose={() => setDetailState(createDefaultDetailState())}
      />
    </section>
  )
}
