/**
 * Mainpage.
 *
 * Frontend module used by Nutify React UI flows and state management.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useQuery } from '@tanstack/react-query'

import { getAllUpsData } from '../../lib/api/ups'
import { getVariableConfig } from '../../lib/api/settings'
import { useCacheWebSocketManager } from '../../lib/realtime/cacheWebSocketManager'
import { useAppStore } from '../../store/appStore'
import { PageHeader } from '../../components/PageHeader'
import { loadMainPanelData } from './mainPanelData'
import { MainRealtimeChart } from './MainRealtimeChart'
import {
  asRecord,
  convertUtcTimeToLocal,
  formatEventTime,
  formatEventType,
  formatMetricValue,
  formatScheduleDays,
  getAlertIcon,
  getAlertSeverity,
  getEventIcon,
} from './mainPageSupport'

export function MainPage() {
  const bootstrap = useAppStore((state) => state.bootstrap)
  const activeTargetId = useAppStore((state) => state.activeTargetId)
  const targets = useAppStore((state) => state.targets)
  const bootstrapTimezone = bootstrap?.timezone ?? 'UTC'
  const monitoringProfile = bootstrap?.monitoring.monitoring_profile ?? 'single'

  const { data: variableConfig } = useQuery({
    queryKey: ['main', 'variable-config', activeTargetId],
    queryFn: () => getVariableConfig(activeTargetId),
    staleTime: 10_000,
    refetchInterval: 30_000,
  })

  const timezone = useMemo(() => {
    const scopedTimezone = String(variableConfig?.timezone ?? '').trim()
    return scopedTimezone || bootstrapTimezone
  }, [bootstrapTimezone, variableConfig?.timezone])

  const dataPollingIntervalMs = useMemo(() => {
    const activeTarget = targets.find((target) => target.id === activeTargetId) ?? null
    const policyValue = (activeTarget as { policy?: { polling_interval?: unknown } } | null)?.policy?.polling_interval
    const intervalSeconds = Number(policyValue ?? variableConfig?.polling_interval)
    if (Number.isFinite(intervalSeconds) && intervalSeconds > 0) {
      return Math.max(1000, Math.round(intervalSeconds * 1000))
    }
    return 5000
  }, [activeTargetId, targets, variableConfig?.polling_interval])

  const [latestSnapshot, setLatestSnapshot] = useState<Record<string, unknown>>({})
  const latestRealtimeAtRef = useRef(0)
  const { data: snapshot } = useQuery({
    queryKey: ['main', 'snapshot', activeTargetId],
    queryFn: () => getAllUpsData(activeTargetId),
    refetchInterval: false,
  })

  const { data: panelData } = useQuery({
    queryKey: ['main', 'panel', activeTargetId],
    queryFn: () => loadMainPanelData(activeTargetId),
    refetchInterval: 30_000,
  })

  useEffect(() => {
    setLatestSnapshot({})
    latestRealtimeAtRef.current = 0
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
    monitoringProfile,
    activeTargetId,
  })

  const metrics = useMemo(() => {
    const source = asRecord(latestSnapshot)
    return {
      battery: formatMetricValue('battery', source.battery_charge),
      runtime: formatMetricValue('runtime', source.battery_runtime),
      power: formatMetricValue('power', source.ups_realpower),
      load: formatMetricValue('load', source.ups_load),
    }
  }, [latestSnapshot])

  const events = panelData?.events ?? []
  const alerts = panelData?.alerts ?? []
  const schedules = panelData?.schedules ?? []

  return (
    <section className="dashboard-section main_dashboard_page">
      <PageHeader
        kicker="Live operations"
        title="Power overview"
        subtitle="Realtime UPS health, electrical load, active alerts, and recent operating events."
        nextOnly
      />
      <div className="stats_grid">
        <article className="stat_card">
          <div className="stat-icon">
            <i className="fas fa-battery-three-quarters" aria-hidden="true" />
          </div>
          <div className="stat-content">
            <div className="stat-header">
              <span className="stat-label">Battery Charge</span>
              <span className="selected-period">Now</span>
            </div>
            <span className="stat-value" data-type="battery">{metrics.battery}</span>
          </div>
        </article>

        <article className="stat_card">
          <div className="stat-icon">
            <i className="fas fa-clock" aria-hidden="true" />
          </div>
          <div className="stat-content">
            <div className="stat-header">
              <span className="stat-label">Runtime Remaining</span>
              <span className="selected-period">Now</span>
            </div>
            <span className="stat-value" data-type="runtime">{metrics.runtime}</span>
          </div>
        </article>

        <article className="stat_card">
          <div className="stat-icon">
            <i className="fas fa-plug" aria-hidden="true" />
          </div>
          <div className="stat-content">
            <div className="stat-header">
              <span className="stat-label">Power Usage</span>
              <span className="selected-period">Now</span>
            </div>
            <span className="stat-value" data-type="power">{metrics.power}</span>
          </div>
        </article>

        <article className="stat_card">
          <div className="stat-icon">
            <i className="fas fa-tachometer-alt" aria-hidden="true" />
          </div>
          <div className="stat-content">
            <div className="stat-header">
              <span className="stat-label">System Load</span>
              <span className="selected-period">Now</span>
            </div>
            <span className="stat-value" data-type="load">{metrics.load}</span>
          </div>
        </article>
      </div>

      <div className="charts_grid">
        <article className="chart_card performance-chart-card">
          <div className="chart_header">
            <h2>System Performance</h2>
          </div>
          <div className="chart_container" id="performanceChart">
            <MainRealtimeChart
              key={String(activeTargetId ?? 'single')}
              latestData={asRecord(latestSnapshot)}
              pollingIntervalMs={dataPollingIntervalMs}
            />
          </div>
        </article>
      </div>

      <div className="bottom_grid">
        <article className="combined_card">
          <div className="combined_header">
            <h2><i className="fas fa-history" /> Recent Events</h2>
          </div>
          <div id="recentEvents" className="recent-events-panel">
            {!events.length ? (
              <div className="no-events">No recent events</div>
            ) : (
              <div className="events-matrix-wrapper">
                <table className="events-matrix-table">
                  <thead>
                    <tr>
                      <th>Event</th>
                      <th>Status</th>
                      <th>Time</th>
                    </tr>
                  </thead>
                  <tbody>
                    {events.map((event, index) => {
                      const severity = getAlertSeverity(event.event_type)
                      return (
                        <tr
                          key={`${event.event_type}-${event.timestamp_utc_begin ?? 'n/a'}-${index}`}
                          className={`events-matrix-row severity-${severity}`}
                        >
                          <td>
                            <div className="events-name-cell">
                              <i className={getEventIcon(event.event_type)} />
                              <span>{formatEventType(event.event_type)}</span>
                            </div>
                          </td>
                          <td>
                            <span className={event.acknowledged ? 'events-status-badge is-seen' : 'events-status-badge is-new'}>
                              {event.acknowledged ? 'Seen' : 'New'}
                            </span>
                          </td>
                          <td>
                            <span className="events-time-cell">{formatEventTime(event.timestamp_utc_begin, timezone)}</span>
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </article>

        <article className="combined_card">
          <div className="combined_header">
            <h2><i className="fas fa-bell" /> Active Alerts</h2>
          </div>
          <div id="activeAlerts" className="alerts-list">
            <div className="alerts-section">
              {!alerts.length ? (
                <div className="no-alerts">No active alerts</div>
              ) : (
                <div className="alerts-matrix-wrapper">
                  <table className="alerts-matrix-table">
                    <thead>
                      <tr>
                        <th>Alert</th>
                        <th>Mail</th>
                        <th>Ntfy</th>
                        <th>Telegram</th>
                        <th>Webhook</th>
                      </tr>
                    </thead>
                    <tbody>
                      {alerts.map((alert) => {
                        const severity = getAlertSeverity(alert.eventType)
                        const hasMail = alert.channels.includes('email')
                        const hasNtfy = alert.channels.includes('ntfy')
                        const hasTelegram = alert.channels.includes('telegram')
                        const hasWebhook = alert.channels.includes('webhook')
                        return (
                          <tr key={alert.eventType} className={`alerts-matrix-row severity-${severity}`}>
                            <td>
                              <div className="alert-name-cell">
                                <i className={getAlertIcon(severity)} />
                                <span>{formatEventType(alert.eventType)}</span>
                              </div>
                            </td>
                            <td>
                              <span className={`alerts-matrix-check ${hasMail ? 'is-enabled' : ''}`} aria-label={hasMail ? 'enabled' : 'disabled'}>
                                <i className={`fas ${hasMail ? 'fa-check' : 'fa-minus'}`} />
                              </span>
                            </td>
                            <td>
                              <span className={`alerts-matrix-check ${hasNtfy ? 'is-enabled' : ''}`} aria-label={hasNtfy ? 'enabled' : 'disabled'}>
                                <i className={`fas ${hasNtfy ? 'fa-check' : 'fa-minus'}`} />
                              </span>
                            </td>
                            <td>
                              <span className={`alerts-matrix-check ${hasTelegram ? 'is-enabled' : ''}`} aria-label={hasTelegram ? 'enabled' : 'disabled'}>
                                <i className={`fas ${hasTelegram ? 'fa-check' : 'fa-minus'}`} />
                              </span>
                            </td>
                            <td>
                              <span className={`alerts-matrix-check ${hasWebhook ? 'is-enabled' : ''}`} aria-label={hasWebhook ? 'enabled' : 'disabled'}>
                                <i className={`fas ${hasWebhook ? 'fa-check' : 'fa-minus'}`} />
                              </span>
                            </td>
                          </tr>
                        )
                      })}
                    </tbody>
                  </table>
                </div>
              )}
            </div>

            <div className="schedules-section">
              <div className="section-header"><i className="fas fa-calendar" /> Active Schedules</div>
              <div className="schedules-grid">
                {!schedules.length ? (
                  <div className="no-schedules">No active schedules</div>
                ) : (
                  schedules.map((schedule) => (
                    <div key={schedule.id} className="schedule-item">
                      <div className="schedule-icon"><i className="fas fa-clock" /></div>
                      <div className="schedule-content">
                        <div className="schedule-title">{convertUtcTimeToLocal(schedule.time, timezone)}</div>
                        <div className="schedule-days">{formatScheduleDays(schedule.days)}</div>
                        <div className="schedule-reports">{schedule.reports.join(', ')}</div>
                      </div>
                    </div>
                  ))
                )}
              </div>
            </div>
          </div>
        </article>
      </div>
    </section>
  )
}
