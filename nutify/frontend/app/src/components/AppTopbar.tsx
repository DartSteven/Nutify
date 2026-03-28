/**
 * Apptopbar.
 *
 * Frontend module used by Nutify React UI flows and state management.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link, useLocation, useNavigate } from 'react-router-dom'

import { setActiveTarget } from '../lib/api/multiNut'
import { getVariableConfig } from '../lib/api/settings'
import { logout } from '../lib/api/auth'
import { useCacheWebSocketManager } from '../lib/realtime/cacheWebSocketManager'
import { useAppStore } from '../store/appStore'
import { formatClock, formatPercent, formatWatts } from '../lib/utils/formatters'
import {
  formatUpsStatus,
  INITIAL_METRICS,
  INITIAL_SYSTEM_STATS,
  isAttentionStatus,
  isOfflineStatus,
  pickFirstMetricValue,
  type HeaderMetrics,
  type SystemStats,
} from './topbarHelpers'
import { useTopbarTargetSync } from './topbarTargetSync'
import {
  CLOCK_FORMAT_EVENT,
  CLOCK_FORMAT_STORAGE_KEY,
  getClockFormatPreference,
  type ClockFormatPreference,
} from '../lib/utils/timePreferences'

export function AppTopbar() {
  const location = useLocation()
  const navigate = useNavigate()
  const bootstrap = useAppStore((state) => state.bootstrap)
  const targets = useAppStore((state) => state.targets)
  const setTargets = useAppStore((state) => state.setTargets)
  const activeTargetId = useAppStore((state) => state.activeTargetId)
  const setActiveTargetId = useAppStore((state) => state.setActiveTargetId)

  const [metrics, setMetrics] = useState<HeaderMetrics>(INITIAL_METRICS)
  const [systemStats, setSystemStats] = useState<SystemStats>(INITIAL_SYSTEM_STATS)
  const [currentTimestamp, setCurrentTimestamp] = useState(Date.now())
  const [clockFormat, setClockFormat] = useState<ClockFormatPreference>(() => getClockFormatPreference())
  const [isTargetMenuOpen, setIsTargetMenuOpen] = useState(false)
  const [fleetOfflineCount, setFleetOfflineCount] = useState(0)
  const [fleetAttentionCount, setFleetAttentionCount] = useState(0)
  const [fleetStatusByTarget, setFleetStatusByTarget] = useState<Record<number, string>>({})
  const targetMenuRef = useRef<HTMLDivElement | null>(null)
  const bootstrapTimezone = bootstrap?.timezone ?? 'UTC'

  const monitoringProfile = bootstrap?.monitoring.monitoring_profile ?? 'single'
  const { data: variableConfig } = useQuery({
    queryKey: ['topbar', 'variable-config', activeTargetId],
    queryFn: () => getVariableConfig(activeTargetId),
    staleTime: 10_000,
    refetchInterval: 30_000,
  })
  const clockTimezone = useMemo(() => {
    const scopedTimezone = String(variableConfig?.timezone ?? '').trim()
    return scopedTimezone || bootstrapTimezone
  }, [bootstrapTimezone, variableConfig?.timezone])

  const onRealtimeSnapshot = useCallback((payload: Record<string, unknown>) => {
    const status = pickFirstMetricValue(payload, ['ups_status', 'status'])
    const battery = pickFirstMetricValue(payload, ['battery_charge', 'charge'])
    const load = pickFirstMetricValue(payload, ['ups_load', 'load'])
    const power = pickFirstMetricValue(payload, ['ups_realpower', 'ups_power', 'power'])
    const serial = pickFirstMetricValue(payload, ['device_serial', 'ups_serial', 'serial'])
    const statusText = status !== null ? String(status) : null
    const targetOffline = isOfflineStatus(statusText)

    setMetrics((previous) => ({
      status: statusText !== null ? formatUpsStatus(statusText) : previous.status,
      batteryCharge: targetOffline ? '-' : battery !== null ? formatPercent(battery, 1) : '-',
      load: targetOffline ? '-' : load !== null ? formatPercent(load, 1) : '-',
      power: targetOffline ? '-' : power !== null ? formatWatts(power, 1) : '-',
      serial: serial !== null ? `S/N: ${String(serial)}` : previous.serial,
    }))
  }, [])

  useCacheWebSocketManager({
    onUpdate: onRealtimeSnapshot,
    monitoringProfile,
    activeTargetId,
  })

  const onFleetRealtimeSnapshot = useCallback((payload: Record<string, unknown>) => {
    const targetId = Number(payload.target_id ?? payload.targetId)
    if (!Number.isFinite(targetId) || targetId <= 0) {
      return
    }
    const statusValue = payload.ups_status ?? payload.status
    if (statusValue === undefined || statusValue === null) {
      return
    }
    const normalizedStatus = String(statusValue).trim() || 'UNKNOWN'
    setFleetStatusByTarget((previous) => {
      if (previous[targetId] === normalizedStatus) {
        return previous
      }
      return {
        ...previous,
        [targetId]: normalizedStatus,
      }
    })
  }, [])

  useCacheWebSocketManager({
    onUpdate: onFleetRealtimeSnapshot,
    monitoringProfile,
    activeTargetId: null,
    enabled: monitoringProfile === 'multi',
    acceptTargetedUpdates: true,
  })

  useEffect(() => {
    const timer = window.setInterval(() => setCurrentTimestamp(Date.now()), 1000)
    return () => window.clearInterval(timer)
  }, [])

  useEffect(() => {
    const syncClockFormat = () => setClockFormat(getClockFormatPreference())

    const handleStorage = (event: StorageEvent) => {
      if (!event.key || event.key === CLOCK_FORMAT_STORAGE_KEY) {
        syncClockFormat()
      }
    }

    window.addEventListener('storage', handleStorage)
    window.addEventListener(CLOCK_FORMAT_EVENT, syncClockFormat as EventListener)

    return () => {
      window.removeEventListener('storage', handleStorage)
      window.removeEventListener(CLOCK_FORMAT_EVENT, syncClockFormat as EventListener)
    }
  }, [])

  useEffect(() => {
    let mounted = true

    async function loadSystemStats() {
      try {
        const response = await fetch('/api/system_stats', { credentials: 'same-origin' })
        if (!response.ok) {
          return
        }
        const payload = (await response.json()) as { cpu?: number; ram_percent?: number }
        if (!mounted) {
          return
        }
        const cpu = Number(payload.cpu)
        const ram = Number(payload.ram_percent)
        setSystemStats({
          cpu: Number.isFinite(cpu) ? cpu.toFixed(1) : '--',
          ram: Number.isFinite(ram) ? ram.toFixed(1) : '--',
        })
      } catch {
        if (!mounted) {
          return
        }
        setSystemStats(INITIAL_SYSTEM_STATS)
      }
    }

    void loadSystemStats()
    const timer = window.setInterval(() => void loadSystemStats(), 3000)

    return () => {
      mounted = false
      window.clearInterval(timer)
    }
  }, [])

  useTopbarTargetSync({
    activeTargetId,
    monitoringProfile,
    setTargets,
    setActiveTargetId,
    setFleetStatusByTarget,
  })

  useEffect(() => {
    if (monitoringProfile !== 'multi') {
      setFleetOfflineCount(0)
      setFleetAttentionCount(0)
      setFleetStatusByTarget({})
      return
    }

    const enabledTargetIds = targets.map((target) => target.id)
    if (enabledTargetIds.length === 0) {
      setFleetOfflineCount(0)
      setFleetAttentionCount(0)
      return
    }

    let offlineCount = 0
    let attentionCount = 0
    for (const targetId of enabledTargetIds) {
      const status = fleetStatusByTarget[targetId]
      if (!status) {
        continue
      }
      if (isOfflineStatus(status)) {
        offlineCount += 1
        continue
      }
      if (isAttentionStatus(status)) {
        attentionCount += 1
      }
    }
    setFleetOfflineCount(offlineCount)
    setFleetAttentionCount(attentionCount)
  }, [fleetStatusByTarget, monitoringProfile, targets])

  const activeTarget = useMemo(
    () => targets.find((target) => target.id === activeTargetId) ?? null,
    [activeTargetId, targets],
  )

  const bootstrapTargetName = useMemo(() => {
    const active = bootstrap?.monitoring.active_target
    if (!active || typeof active !== 'object') {
      return null
    }
    const maybeName = active['name']
    return typeof maybeName === 'string' && maybeName.trim().length > 0 ? maybeName : null
  }, [bootstrap?.monitoring.active_target])

  const handleTargetSelect = useCallback(
    async (targetId: number) => {
      if (targetId === activeTargetId) {
        setIsTargetMenuOpen(false)
        return
      }

      setIsTargetMenuOpen(false)

      try {
        await setActiveTarget(targetId)
        setActiveTargetId(targetId)
        navigate({ pathname: window.location.pathname, search: '' }, { replace: true })
      } catch {
        // Keep previous selection when backend rejects active target change.
      }
    },
    [activeTargetId, navigate, setActiveTargetId],
  )

  const handleThemeToggle = useCallback(() => {
    const currentTheme = document.documentElement.getAttribute('data-theme') ?? 'dark'
    const nextTheme = currentTheme === 'dark' ? 'light' : 'dark'
    document.documentElement.setAttribute('data-theme', nextTheme)
    window.localStorage.setItem('theme', nextTheme)
  }, [])

  useEffect(() => {
    const savedTheme = window.localStorage.getItem('theme')
    if (savedTheme) {
      document.documentElement.setAttribute('data-theme', savedTheme)
    }
  }, [])

  const handleLogout = useCallback(async () => {
    try {
      await logout()
    } finally {
      navigate('/auth/login', { replace: true })
      window.location.href = '/auth/login'
    }
  }, [navigate])

  const multiIconVisible = monitoringProfile === 'multi' && targets.length > 1
  const offlineWarningVisible = monitoringProfile === 'multi' && fleetOfflineCount > 0
  const attentionWarningVisible =
    monitoringProfile === 'multi' && fleetOfflineCount === 0 && fleetAttentionCount > 0
  const multiMonitoringIconClass = useMemo(() => {
    const classes = [location.pathname.startsWith('/multi-ups') ? 'active' : '']
    if (fleetOfflineCount > 0) {
      classes.push('has-offline')
    } else if (fleetAttentionCount > 0) {
      classes.push('has-warning')
    }
    return classes.join(' ').trim()
  }, [fleetAttentionCount, fleetOfflineCount, location.pathname])
  const multiMonitoringTitle = useMemo(() => {
    if (fleetOfflineCount > 0) {
      return `Multi-UPS Monitoring (${fleetOfflineCount} offline)`
    }
    if (fleetAttentionCount > 0) {
      return `Multi-UPS Monitoring (${fleetAttentionCount} attention)`
    }
    return 'Multi-UPS Monitoring'
  }, [fleetAttentionCount, fleetOfflineCount])
  const isTargetSelectorInteractive = monitoringProfile === 'multi' && targets.length > 1
  const settingsView = new URLSearchParams(location.search).get('view') === 'system' ? 'system' : 'target'
  const isSettingsTargetRoute =
    (location.pathname.startsWith('/settings') || location.pathname.startsWith('/options')) &&
    settingsView !== 'system'

  useEffect(() => {
    if (!isTargetMenuOpen) {
      return
    }

    function handleOutsideClick(event: MouseEvent) {
      const target = event.target
      if (!(target instanceof Node)) {
        return
      }
      if (!targetMenuRef.current?.contains(target)) {
        setIsTargetMenuOpen(false)
      }
    }

    document.addEventListener('mousedown', handleOutsideClick)
    return () => {
      document.removeEventListener('mousedown', handleOutsideClick)
    }
  }, [isTargetMenuOpen])

  useEffect(() => {
    setIsTargetMenuOpen(false)
  }, [location.pathname, location.search])

  return (
    <header className="header_top">
      <div className="header_top-status_container">
        <div className="header_top-status_bar">
          <div className="header_top-status_info">
            <div className="header_top-ups_info" ref={targetMenuRef}>
              <button
                type="button"
                className={[
                  'header_top-model',
                  'header_target_selector_button',
                  isTargetSelectorInteractive ? 'is-interactive' : '',
                ].join(' ').trim()}
                onClick={() => {
                  if (isTargetSelectorInteractive) {
                    setIsTargetMenuOpen((open) => !open)
                  }
                }}
                title="Select monitored UPS"
                aria-expanded={isTargetSelectorInteractive ? isTargetMenuOpen : undefined}
                aria-haspopup={isTargetSelectorInteractive ? 'menu' : undefined}
              >
                <span>{activeTarget?.name ?? bootstrapTargetName ?? 'Primary UPS'}</span>
                <i
                  className="fas fa-chevron-down"
                  aria-hidden="true"
                  style={{ display: isTargetSelectorInteractive ? 'inline-flex' : 'none' }}
                />
              </button>
              <div
                className="header_target_selector_menu"
                style={{ display: isTargetSelectorInteractive && isTargetMenuOpen ? 'block' : 'none' }}
                role="menu"
              >
                {targets.map((target) => (
                  <button
                    key={target.id}
                    type="button"
                    role="menuitemradio"
                    aria-checked={target.id === activeTargetId}
                    className={[
                      'header_target_selector_item',
                      target.id === activeTargetId ? 'is-active' : '',
                    ].join(' ').trim()}
                    onClick={() => void handleTargetSelect(target.id)}
                  >
                    {`${target.name} (${target.ups_name}@${target.host})`}
                  </button>
                ))}
              </div>
              <span className="header_top-serial">{metrics.serial}</span>
            </div>

            <h3>
              <i className="fas fa-plug" aria-hidden="true" />
              <span>{metrics.status}</span>
            </h3>

            <span className="header_top-battery">
              <i className="fas fa-battery-three-quarters" aria-hidden="true" />
              <span>{metrics.batteryCharge}</span>
            </span>

            <span className="header_top-load">
              <i className="fas fa-gauge-high" aria-hidden="true" />
              <span>{metrics.load}</span>
            </span>

            <span className="header_top-power">
              <i className="fas fa-bolt" aria-hidden="true" />
              <span>{metrics.power}</span>
            </span>

            <div className="header_top-clock">
              <span>{formatClock(currentTimestamp, clockTimezone, clockFormat)}</span>
            </div>

            <div className="header_top-system_stats">
              <span className="header_top-cpu" title="CPU Usage">
                <i className="fas fa-microchip" aria-hidden="true" /> {systemStats.cpu}%
              </span>
              <span className="header_top-ram" title="RAM Usage">
                <i className="fas fa-memory" aria-hidden="true" /> {systemStats.ram}%
              </span>
            </div>

            <div className="header_top-icons">
              <button className="theme-toggle" type="button" onClick={handleThemeToggle} title="Toggle theme" aria-label="Toggle theme">
                <i className="fas fa-circle-half-stroke" aria-hidden="true" />
              </button>

              {offlineWarningVisible ? (
                <span className="header_top-notify" title={`${fleetOfflineCount} UPS target(s) offline`}>
                  <Link to="/multi-ups" className={['has-alert', location.pathname.startsWith('/multi-ups') ? 'active' : ''].join(' ').trim()}>
                    <i className="fas fa-triangle-exclamation" aria-hidden="true" />
                    <span className="sr-only">Open Multi-UPS warnings</span>
                  </Link>
                </span>
              ) : null}

              {attentionWarningVisible ? (
                <span className="header_top-notify" title={`${fleetAttentionCount} UPS target(s) in attention state`}>
                  <Link to="/multi-ups" className={['has-warning', location.pathname.startsWith('/multi-ups') ? 'active' : ''].join(' ').trim()}>
                    <i className="fas fa-circle-exclamation" aria-hidden="true" />
                    <span className="sr-only">Open Multi-UPS attention</span>
                  </Link>
                </span>
              ) : null}

              {multiIconVisible ? (
                <span className="header_top-settings" title={multiMonitoringTitle}>
                  <Link to="/multi-ups" className={multiMonitoringIconClass}>
                    <i className="fas fa-network-wired" aria-hidden="true" />
                    <span className="sr-only">Multi-UPS Monitoring</span>
                  </Link>
                </span>
              ) : null}

              <span className="header_top-settings" title="Settings">
                <Link to="/settings?view=target" className={isSettingsTargetRoute ? 'active' : ''}>
                  <i className="fas fa-cog" aria-hidden="true" />
                  <span className="sr-only">Settings</span>
                </Link>
              </span>

              <span className="header_top-logout" title="Logout">
                <button type="button" className="header_top-logout_btn" onClick={() => void handleLogout()}>
                  <i className="fas fa-sign-out-alt" aria-hidden="true" />
                  <span className="sr-only">Logout</span>
                </button>
              </span>
            </div>
          </div>
        </div>
      </div>
    </header>
  )
}
