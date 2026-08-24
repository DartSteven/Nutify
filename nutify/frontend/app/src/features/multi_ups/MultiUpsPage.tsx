/**
 * Multiupspage.
 *
 * Frontend module used by Nutify React UI flows and state management.
 */

import { useCallback, useEffect, useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link, useNavigate } from 'react-router-dom'

import { getOverview, getTargets, setActiveTarget } from '../../lib/api/multiNut'
import { useCacheWebSocketManager } from '../../lib/realtime/cacheWebSocketManager'
import { useAppStore } from '../../store/appStore'
import { MultiUpsLocationNetworkChart } from './MultiUpsLocationNetworkChart'
import {
  ALL_LOCATIONS,
  asNumber,
  asRecord,
  asText,
  channelBadge,
  formatCost,
  formatPercent,
  formatRuntimeSeconds,
  formatWatts,
  lookupMetric,
  normalizeCoordinate,
  normalizeLocationValue,
  parseJsonRecord,
  resolveMapHealthState,
  statusState,
  type OverviewRow,
  type RuntimeRow,
} from './multiUpsSupport'

export function MultiUpsPage() {
  const navigate = useNavigate()
  const monitoringProfile = useAppStore((state) => state.bootstrap?.monitoring.monitoring_profile ?? 'single')
  const [switchingTargetId, setSwitchingTargetId] = useState<number | null>(null)
  const [selectedCountry, setSelectedCountry] = useState(ALL_LOCATIONS)
  const [selectedCity, setSelectedCity] = useState(ALL_LOCATIONS)
  const [showLocationChart, setShowLocationChart] = useState(false)
  const [realtimeByTarget, setRealtimeByTarget] = useState<Record<number, Record<string, unknown>>>({})

  const {
    data: targets = [],
    refetch: refetchTargets,
  } = useQuery({
    queryKey: ['multi-ups', 'targets'],
    queryFn: () => getTargets(),
    refetchInterval: 15_000,
  })

  const {
    data: overviewRows = [],
    refetch: refetchOverview,
  } = useQuery({
    queryKey: ['multi-ups', 'overview'],
    queryFn: () => getOverview(24),
    refetchInterval: 10_000,
  })

  const onFleetRealtimeUpdate = useCallback((payload: Record<string, unknown>) => {
    const targetId = Number(payload.target_id ?? payload.targetId)
    if (!Number.isFinite(targetId) || targetId <= 0) {
      return
    }
    setRealtimeByTarget((previous) => ({
      ...previous,
      [targetId]: payload,
    }))
  }, [])

  useCacheWebSocketManager({
    onUpdate: onFleetRealtimeUpdate,
    monitoringProfile,
    activeTargetId: null,
    enabled: monitoringProfile === 'multi',
    acceptTargetedUpdates: true,
  })

  const rows = useMemo<OverviewRow[]>(() => {
    const byId = new Map<number, Record<string, unknown>>()
    for (const item of overviewRows) {
      const row = asRecord(item)
      const target = asRecord(row.target)
      const targetId = Number(target.id)
      if (!Number.isFinite(targetId)) {
        continue
      }
      byId.set(targetId, row)
    }

    return targets.map((target) => {
      const overview = byId.get(target.id) ?? {}
      const targetInfo = asRecord(overview.target)
      const summary = asRecord(overview.summary)
      const latestMetrics = asRecord(overview.latest_metrics)
      const latest = asRecord(overview.latest)
      const channels = asRecord(overview.channels)

      return {
        target: Object.keys(targetInfo).length > 0 ? targetInfo : (target as unknown as Record<string, unknown>),
        summary,
        latestMetrics,
        latest,
        channels,
      }
    })
  }, [overviewRows, targets])

  useEffect(() => {
    const validTargetIds = new Set(targets.map((target) => target.id))
    setRealtimeByTarget((previous) => {
      const next: Record<number, Record<string, unknown>> = {}
      let changed = false
      for (const [targetIdString, payload] of Object.entries(previous)) {
        const targetId = Number(targetIdString)
        if (!Number.isFinite(targetId) || !validTargetIds.has(targetId)) {
          changed = true
          continue
        }
        next[targetId] = payload
      }
      return changed ? next : previous
    })
  }, [targets])

  const runtimeRows = useMemo<RuntimeRow[]>(() => {
    return rows.map((row) => {
      const target = row.target
      const summary = row.summary
      const latestMetrics = row.latestMetrics
      const latest = row.latest
      const realtimePayload = asRecord(realtimeByTarget[Number(target.id)])
      const latestDataJson = parseJsonRecord(latest.data_json)
      const latestRawJson = parseJsonRecord(latest.raw_json)
      const metricSources = [realtimePayload, latestMetrics, latestDataJson, latestRawJson, latest]
      const status = statusState(lookupMetric(metricSources, 'ups_status') ?? summary.latest_status)
      const locationCountry = normalizeLocationValue(target.location_country)
      const locationCity = normalizeLocationValue(target.location_city)
      const locationLabel = normalizeLocationValue(target.location)
      const locationLatitude = normalizeCoordinate(target.location_latitude, -90, 90)
      const locationLongitude = normalizeCoordinate(target.location_longitude, -180, 180)
      const batteryValue = status.isOnline ? asNumber(lookupMetric(metricSources, 'battery_charge')) : null
      const runtimeValue = status.isOnline ? asNumber(lookupMetric(metricSources, 'battery_runtime')) : null
      const powerValue = status.isOnline ? asNumber(lookupMetric(metricSources, 'ups_realpower')) : null
      const loadValue = status.isOnline ? asNumber(lookupMetric(metricSources, 'ups_load')) : null
      const healthState = resolveMapHealthState(status.rawStatus, status.isOnline, batteryValue)

      return {
        ...row,
        targetId: Number(target.id),
        status,
        healthState,
        locationCountry,
        locationCity,
        locationLabel,
        locationLatitude,
        locationLongitude,
        batteryValue,
        runtimeValue,
        powerValue,
        loadValue,
      }
    })
  }, [realtimeByTarget, rows])

  const countryOptions = useMemo(() => {
    const values = new Set<string>()
    for (const row of runtimeRows) {
      if (Boolean(row.target.location_enabled) && row.locationCountry) {
        values.add(row.locationCountry)
      }
    }
    return Array.from(values).sort((left, right) => left.localeCompare(right))
  }, [runtimeRows])

  const cityOptions = useMemo(() => {
    const values = new Set<string>()
    for (const row of runtimeRows) {
      if (!row.target.location_enabled || !row.locationCity) {
        continue
      }
      if (selectedCountry !== ALL_LOCATIONS && row.locationCountry !== selectedCountry) {
        continue
      }
      values.add(row.locationCity)
    }
    return Array.from(values).sort((left, right) => left.localeCompare(right))
  }, [runtimeRows, selectedCountry])

  useEffect(() => {
    if (selectedCity === ALL_LOCATIONS) {
      return
    }
    if (!cityOptions.includes(selectedCity)) {
      setSelectedCity(ALL_LOCATIONS)
    }
  }, [cityOptions, selectedCity])

  const filteredRows = useMemo(() => {
    return runtimeRows.filter((row) => {
      if (selectedCountry !== ALL_LOCATIONS) {
        if (!row.target.location_enabled || row.locationCountry !== selectedCountry) {
          return false
        }
      }
      if (selectedCity !== ALL_LOCATIONS) {
        if (!row.target.location_enabled || row.locationCity !== selectedCity) {
          return false
        }
      }
      return true
    })
  }, [runtimeRows, selectedCity, selectedCountry])

  const mapPoints = useMemo(() => {
    return filteredRows
      .filter(
        (row) =>
          Boolean(row.target.location_enabled)
          && (row.locationLabel || row.locationCity || row.locationCountry),
      )
      .map((row) => ({
        id: row.targetId,
        name: asText(row.target.name),
        location: row.locationLabel,
        city: row.locationCity,
        country: row.locationCountry,
        latitude: row.locationLatitude,
        longitude: row.locationLongitude,
        isPrimary: Boolean(row.target.is_primary),
        isOnline: row.status.isOnline,
        health: row.healthState,
      }))
  }, [filteredRows])

  const hasLocationConfigured = useMemo(
    () => runtimeRows.some((row) => Boolean(row.target.location_enabled)),
    [runtimeRows],
  )

  async function handleMonitorTarget(targetId: number) {
    if (!Number.isFinite(targetId) || targetId <= 0) {
      return
    }
    try {
      setSwitchingTargetId(targetId)
      await setActiveTarget(targetId)
      navigate('/')
      window.location.href = '/'
    } finally {
      setSwitchingTargetId(null)
    }
  }

  function downloadReport() {
    const params = new URLSearchParams({
      scope: 'all',
      hours: '24',
      download: 'true',
    })
    window.location.href = `/api/multi-nut/report?${params.toString()}`
  }

  return (
    <section className="page multi_ups_page">
      <div className="page_header">
        <div className="page_title">
          <h1>Multi-UPS Monitoring</h1>
          <p className="page_subtitle">One row per UPS with realtime battery, runtime, power, load, cost, average load, and channels.</p>
        </div>
        <div className="page_actions" style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', flexWrap: 'wrap' }}>
          <button className="options_btn options_btn_primary" type="button" onClick={() => void Promise.all([refetchTargets(), refetchOverview()])}>
            <i className="fas fa-sync" aria-hidden="true" /> Refresh
          </button>
          <button className="options_btn options_btn_secondary" type="button" onClick={downloadReport}>
            <i className="fas fa-file-download" aria-hidden="true" /> Export Report
          </button>
          <Link className="options_btn options_btn_secondary" to="/settings?view=system">
            <i className="fas fa-sliders-h" aria-hidden="true" /> Manage Targets
          </Link>
        </div>
      </div>

      <div className="options_card" style={{ marginBottom: '1rem' }}>
        <div className="card_header">
          <h2>Location Filters</h2>
          <p className="card_subtitle">Filter fleet rows by country and city from the location data configured in the setup wizard.</p>
        </div>
        <div className="options_mail_form_grid">
          <div className="options_mail_form_group">
            <label htmlFor="multi_filter_country">
              <i className="fas fa-globe-europe" /> Country
            </label>
            <select
              id="multi_filter_country"
              className="options_input form-select dropdown-below"
              value={selectedCountry}
              onChange={(event) => setSelectedCountry(event.target.value)}
            >
              <option value={ALL_LOCATIONS}>All Countries</option>
              {countryOptions.map((country) => (
                <option key={country} value={country}>
                  {country}
                </option>
              ))}
            </select>
          </div>
          <div className="options_mail_form_group">
            <label htmlFor="multi_filter_city">
              <i className="fas fa-city" /> City
            </label>
            <select
              id="multi_filter_city"
              className="options_input form-select dropdown-below"
              value={selectedCity}
              onChange={(event) => setSelectedCity(event.target.value)}
            >
              <option value={ALL_LOCATIONS}>All Cities</option>
              {cityOptions.map((city) => (
                <option key={city} value={city}>
                  {city}
                </option>
              ))}
            </select>
          </div>
        </div>
      </div>

      {hasLocationConfigured ? (
        <div className="options_card" style={{ marginBottom: '1rem' }}>
          <div className="card_header" style={{ display: 'flex', justifyContent: 'space-between', gap: '1rem', alignItems: 'center' }}>
            <div>
              <h2>Global UPS Network Flow</h2>
              <p className="card_subtitle">Collapse panel with a live location network built from wizard location data.</p>
            </div>
            <button
              type="button"
              className="options_btn options_btn_secondary"
              onClick={() => setShowLocationChart((previous) => !previous)}
            >
              <i className={`fas ${showLocationChart ? 'fa-chevron-up' : 'fa-chevron-down'}`} aria-hidden="true" />
              {showLocationChart ? 'Hide Graph' : 'Show Graph'}
            </button>
          </div>
          {showLocationChart ? <MultiUpsLocationNetworkChart points={mapPoints} /> : null}
        </div>
      ) : null}

      <div className="options_card">
        <div className="card_header">
          <h2>Configured UPS Fleet</h2>
          <p className="card_subtitle">One row per UPS with realtime battery, runtime, power, load, cost, average load, and active notification channels.</p>
        </div>

        {filteredRows.length === 0 ? (
          <p className="card_subtitle">No target data available for the selected location filters.</p>
        ) : (
          <div className="multi_fleet_table_wrapper">
            <table className="multi_fleet_table">
              <thead>
                <tr>
                  <th>UPS</th>
                  <th>Status</th>
                  <th>Battery</th>
                  <th>Runtime Remaining</th>
                  <th>Power Usage</th>
                  <th>System Load</th>
                  <th>Total Cost (24h)</th>
                  <th>Average Load</th>
                  <th>Channels</th>
                  <th>Action</th>
                </tr>
              </thead>
              <tbody>
                {filteredRows.map((row) => {
                  const target = row.target
                  const summary = row.summary
                  const channels = row.channels
                  const targetId = row.targetId
                  const endpoint = `${asText(target.ups_name)}@${asText(target.host)}${
                    Number(target.port ?? 3493) === 3493 ? '' : `:${target.port}`
                  }`

                  return (
                    <tr key={`${targetId}-${endpoint}`} className={row.status.isOnline ? '' : 'is-offline'}>
                      <td>
                        <div className="multi_target_info">
                          <strong>{asText(target.name)}</strong>
                          <span className="card_subtitle">{endpoint}</span>
                          <span
                            className="multi_role_badge"
                            style={
                              target.is_primary
                                ? { background: 'rgba(80,148,255,0.18)', color: '#5094ff' }
                                : { background: 'rgba(180,180,180,0.18)', color: '#b4b4b4' }
                            }
                          >
                            {target.is_primary ? 'Primary' : 'Secondary'}
                          </span>
                          {row.locationLabel ? <span className="card_subtitle">{row.locationLabel}</span> : null}
                        </div>
                      </td>
                      <td>
                        <div className="multi_status_wrap">
                          <span
                            className="multi_status_badge"
                            style={
                              row.status.isOnline
                                ? { background: 'rgba(46, 204, 113, 0.18)', color: '#2ecc71' }
                                : { background: 'rgba(231, 76, 60, 0.18)', color: '#e74c3c' }
                            }
                          >
                            <i className={`fas ${row.status.isOnline ? 'fa-circle-check' : 'fa-circle-xmark'}`} aria-hidden="true" />
                            {row.status.label}
                          </span>
                          <span className="card_subtitle">{row.status.rawStatus}</span>
                        </div>
                      </td>
                      <td>{formatPercent(row.batteryValue)}</td>
                      <td>{formatRuntimeSeconds(row.runtimeValue)}</td>
                      <td>{formatWatts(row.powerValue)}</td>
                      <td>{formatPercent(row.loadValue)}</td>
                      <td>{formatCost(summary)}</td>
                      <td>{formatPercent(asNumber(summary.avg_load))}</td>
                      <td>
                        <div className="multi_channels_wrap">
                          {channelBadge('Mail', Boolean(channels.mail))}
                          {channelBadge('Ntfy', Boolean(channels.ntfy))}
                          {channelBadge('Telegram', Boolean(channels.telegram))}
                          {channelBadge('Webhook', Boolean(channels.webhook))}
                        </div>
                      </td>
                      <td>
                        <button
                          className="options_btn options_btn_secondary"
                          type="button"
                          disabled={switchingTargetId === targetId}
                          onClick={() => void handleMonitorTarget(targetId)}
                        >
                          <i className="fas fa-location-arrow" aria-hidden="true" /> {switchingTargetId === targetId ? 'Switching...' : 'Monitor'}
                        </button>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </section>
  )
}
