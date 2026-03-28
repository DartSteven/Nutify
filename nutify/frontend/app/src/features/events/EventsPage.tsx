/**
 * Eventspage.
 *
 * Frontend module used by Nutify React UI flows and state management.
 */

import { useCallback, useEffect, useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'

import { withTarget } from '../../lib/api/client'
import { getVariableConfig } from '../../lib/api/settings'
import { useAppStore } from '../../store/appStore'
import {
  buildStats,
  formatDateTime,
  formatEventType,
  getEventDurationLabel,
  normalizeRows,
  parseDate,
  type EventsApiRow,
  type NotificationPermission,
  type StatsSnapshot,
} from './helpers'

function notify(message: string, type: 'success' | 'error' | 'warning' | 'info') {
  const notifyFn = (window as Window & { notify?: (text: string, level: string, timeout?: number) => void }).notify
  if (typeof notifyFn === 'function') {
    notifyFn(message, type, 5000)
    return
  }
  if (type === 'error') {
    window.alert(message)
  }
}

export function EventsPage() {
  const bootstrapTimezone = useAppStore((state) => state.bootstrap?.timezone ?? 'UTC')
  const activeTargetId = useAppStore((state) => state.activeTargetId)

  const { data: variableConfig } = useQuery({
    queryKey: ['events', 'variable-config', activeTargetId],
    queryFn: () => getVariableConfig(activeTargetId),
    staleTime: 10_000,
    refetchInterval: 30_000,
  })

  const timezone = useMemo(() => {
    const scopedTimezone = String(variableConfig?.timezone ?? '').trim()
    return scopedTimezone || bootstrapTimezone
  }, [bootstrapTimezone, variableConfig?.timezone])

  const [eventsData, setEventsData] = useState<EventsApiRow[]>([])
  const [eventTypeFilter, setEventTypeFilter] = useState('all')
  const [timeFilter, setTimeFilter] = useState('24h')
  const [searchValue, setSearchValue] = useState('')
  const [selectedEventIds, setSelectedEventIds] = useState<number[]>([])
  const [stats, setStats] = useState<StatsSnapshot>({
    totalEvents: 0,
    todayEvents: 0,
    batteryTimeLabel: '0m 0s',
    lastEventLabel: '-',
  })
  const [notificationPermission, setNotificationPermission] = useState<NotificationPermission>(
    typeof Notification !== 'undefined' ? Notification.permission : 'default',
  )
  const notificationsEnabled = notificationPermission === 'granted'

  const updateEventsTable = useCallback(async () => {
    try {
      const response = await fetch(withTarget('/api/table/events?rows=50', activeTargetId), {
        credentials: 'same-origin',
      })

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`)
      }

      const payload = (await response.json()) as unknown
      const rows = normalizeRows(payload)
      setEventsData(rows)
      setStats(buildStats(rows, timezone))
    } catch {
      notify('Error loading events', 'error')
    }
  }, [activeTargetId, timezone])

  useEffect(() => {
    void updateEventsTable()
    const timer = window.setInterval(() => void updateEventsTable(), 30_000)
    return () => {
      window.clearInterval(timer)
    }
  }, [updateEventsTable])

  const filteredEvents = useMemo(() => {
    const searchText = searchValue.trim().toLowerCase()
    const now = Date.now()
    let minTimestamp = 0

    if (timeFilter === '1h') {
      minTimestamp = now - 60 * 60 * 1000
    } else if (timeFilter === '24h') {
      minTimestamp = now - 24 * 60 * 60 * 1000
    } else if (timeFilter === '7d') {
      minTimestamp = now - 7 * 24 * 60 * 60 * 1000
    } else if (timeFilter === '30d') {
      minTimestamp = now - 30 * 24 * 60 * 60 * 1000
    }

    return eventsData.filter((eventRow) => {
      if (eventTypeFilter !== 'all' && eventRow.event_type !== eventTypeFilter) {
        return false
      }

      const startDate = parseDate(eventRow.timestamp_utc_begin)
      if (minTimestamp > 0 && startDate && startDate.getTime() < minTimestamp) {
        return false
      }

      if (!searchText) {
        return true
      }

      const haystack = `${eventRow.event_type} ${formatEventType(eventRow.event_type)}`.toLowerCase()
      return haystack.includes(searchText)
    })
  }, [eventTypeFilter, eventsData, searchValue, timeFilter])

  const allFilteredSelected =
    filteredEvents.length > 0 && filteredEvents.every((row) => selectedEventIds.includes(row.id))

  const toggleSelectAll = (checked: boolean) => {
    if (checked) {
      const merged = new Set([...selectedEventIds, ...filteredEvents.map((row) => row.id)])
      setSelectedEventIds(Array.from(merged))
      return
    }
    const filteredIds = new Set(filteredEvents.map((row) => row.id))
    setSelectedEventIds((previous) => previous.filter((id) => !filteredIds.has(id)))
  }

  const toggleRowSelection = (rowId: number, checked: boolean) => {
    setSelectedEventIds((previous) => {
      if (checked) {
        return previous.includes(rowId) ? previous : [...previous, rowId]
      }
      return previous.filter((id) => id !== rowId)
    })
  }

  const acknowledgeEvent = async (eventId: number) => {
    try {
      const response = await fetch(withTarget(`/api/events/acknowledge/${eventId}`, activeTargetId), {
        method: 'POST',
        credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json' },
      })
      const payload = (await response.json()) as { success?: boolean; message?: string }
      if (!response.ok || payload.success === false) {
        throw new Error(payload.message ?? `HTTP ${response.status}`)
      }
      await updateEventsTable()
      notify('Event updated successfully', 'success')
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : 'Error updating event status'
      notify(message, 'error')
    }
  }

  const deleteEvent = async (eventId: number) => {
    if (!window.confirm('Are you sure you want to delete this event?')) {
      return
    }
    try {
      const response = await fetch(withTarget(`/api/events/delete/${eventId}`, activeTargetId), {
        method: 'DELETE',
        credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json' },
      })
      const payload = (await response.json()) as { success?: boolean; message?: string }
      if (!response.ok || payload.success === false) {
        throw new Error(payload.message ?? `HTTP ${response.status}`)
      }
      await updateEventsTable()
      notify('Event deleted successfully', 'success')
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : 'Error deleting event'
      notify(message, 'error')
    }
  }

  const acknowledgeSelectedEvents = async () => {
    if (selectedEventIds.length === 0) {
      notify('Select at least one event', 'warning')
      return
    }
    try {
      const response = await fetch(withTarget('/api/events/acknowledge/bulk', activeTargetId), {
        method: 'POST',
        credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ event_ids: selectedEventIds }),
      })
      const payload = (await response.json()) as { success?: boolean; message?: string }
      if (!response.ok || payload.success === false) {
        throw new Error(payload.message ?? `HTTP ${response.status}`)
      }
      setSelectedEventIds([])
      await updateEventsTable()
      notify('Events updated successfully', 'success')
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : 'Error updating events'
      notify(message, 'error')
    }
  }

  const deleteSelectedEvents = async () => {
    if (selectedEventIds.length === 0) {
      notify('Select at least one event', 'warning')
      return
    }
    if (!window.confirm('Are you sure you want to delete the selected events?')) {
      return
    }
    try {
      const response = await fetch(withTarget('/api/events/delete/bulk', activeTargetId), {
        method: 'DELETE',
        credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ event_ids: selectedEventIds }),
      })
      const payload = (await response.json()) as { success?: boolean; message?: string }
      if (!response.ok || payload.success === false) {
        throw new Error(payload.message ?? `HTTP ${response.status}`)
      }
      setSelectedEventIds([])
      await updateEventsTable()
      notify('Events deleted successfully', 'success')
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : 'Error deleting events'
      notify(message, 'error')
    }
  }

  const clearAllStats = () => {
    if (!window.confirm('Are you sure you want to reset the statistics counters?')) {
      return
    }
    setStats({
      totalEvents: 0,
      todayEvents: 0,
      batteryTimeLabel: '0m 0s',
      lastEventLabel: '-',
    })
    notify('Statistics reset successfully', 'success')
  }

  const requestNotificationPermission = async () => {
    if (!('Notification' in window)) {
      notify('Desktop notifications are not supported in this browser', 'warning')
      return
    }
    if (!window.isSecureContext) {
      notify('Notifications require a secure connection (HTTPS)', 'warning')
      return
    }

    try {
      const permission = (await Notification.requestPermission()) as NotificationPermission
      setNotificationPermission(permission)

      if (permission === 'granted') {
        notify('Notifications enabled successfully', 'success')
      } else if (permission === 'denied') {
        notify('Notifications blocked', 'error')
      }
    } catch {
      notify('Error requesting notification permission', 'error')
    }
  }

  return (
    <div className="events_container">
      <div className="events_header">
        <h2 className="events_title">UPS Events</h2>
        <div className="events_actions">
          <button
            id="toggleNotifications"
            className={[
              'options_btn',
              notificationPermission === 'default' || notificationsEnabled
                ? 'options_btn_primary'
                : 'options_btn_secondary',
            ].join(' ')}
            type="button"
            onClick={() => void requestNotificationPermission()}
          >
            <i className="fas fa-bell" />
            {notificationPermission === 'default'
              ? ' Notifications'
              : ` Notifications ${notificationsEnabled ? 'On' : 'Off'}`}
          </button>
          <button id="clearEvents" className="options_btn options_btn_secondary" type="button" onClick={clearAllStats}>
            <i className="fas fa-trash" />
            Clear All
          </button>
        </div>
      </div>

      <div className="stats_grid">
        <div className="stat_card">
          <div className="stat-icon">
            <i className="fas fa-list" />
          </div>
          <div className="stat-content">
            <div className="stat-header">
              <span className="stat-label">Total Events</span>
            </div>
            <span id="totalEvents" className="stat-value">
              {stats.totalEvents}
            </span>
          </div>
        </div>
        <div className="stat_card">
          <div className="stat-icon">
            <i className="fas fa-calendar-day" />
          </div>
          <div className="stat-content">
            <div className="stat-header">
              <span className="stat-label">Today's Events</span>
            </div>
            <span id="todayEvents" className="stat-value">
              {stats.todayEvents}
            </span>
          </div>
        </div>
        <div className="stat_card">
          <div className="stat-icon">
            <i className="fas fa-clock" />
          </div>
          <div className="stat-content">
            <div className="stat-header">
              <span className="stat-label">Battery Time</span>
            </div>
            <span id="batteryTime" className="stat-value">
              {stats.batteryTimeLabel}
            </span>
          </div>
        </div>
        <div className="stat_card">
          <div className="stat-icon">
            <i className="fas fa-history" />
          </div>
          <div className="stat-content">
            <div className="stat-header">
              <span className="stat-label">Last Event</span>
            </div>
            <span id="lastEvent" className="stat-value">
              {stats.lastEventLabel}
            </span>
          </div>
        </div>
      </div>

      <div className="events_filters">
        <div className="events_filter_group">
          <label htmlFor="eventTypeFilter">Event Type</label>
          <select id="eventTypeFilter" value={eventTypeFilter} onChange={(event) => setEventTypeFilter(event.target.value)}>
            <option value="all">All Types</option>
            <option value="ONBATT">On Battery</option>
            <option value="ONLINE">Online</option>
            <option value="LOWBATT">Low Battery</option>
            <option value="COMMOK">Comm OK</option>
            <option value="COMMBAD">Comm Bad</option>
            <option value="SHUTDOWN">Shutdown</option>
            <option value="REPLBATT">Replace Battery</option>
            <option value="NOCOMM">No Communication</option>
            <option value="NOPARENT">No Parent</option>
          </select>
        </div>
        <div className="events_filter_group">
          <label htmlFor="timeFilter">Time Range</label>
          <select id="timeFilter" value={timeFilter} onChange={(event) => setTimeFilter(event.target.value)}>
            <option value="24h">Last 24 Hours</option>
            <option value="7d">Last 7 Days</option>
            <option value="30d">Last 30 Days</option>
            <option value="all">All Time</option>
          </select>
        </div>
        <div className="events_filter_group">
          <label htmlFor="searchInput">Search</label>
          <input
            id="searchInput"
            type="text"
            placeholder="Search events..."
            value={searchValue}
            onChange={(event) => setSearchValue(event.target.value)}
          />
        </div>
      </div>

      <div className="events_actions" style={{ marginTop: '1rem' }}>
        <button id="acknowledgeSelectedBtn" className="options_btn options_btn_primary" type="button" onClick={() => void acknowledgeSelectedEvents()}>
          <i className="fas fa-check" />
          Mark Selected as Seen
        </button>
        <button id="deleteSelectedBtn" className="options_btn options_btn_secondary" type="button" onClick={() => void deleteSelectedEvents()}>
          <i className="fas fa-trash" />
          Delete Selected
        </button>
      </div>

      <div className="events_table_container">
        <table className="events_table">
          <thead>
            <tr>
              <th>
                <input id="selectAll" type="checkbox" checked={allFilteredSelected} onChange={(event) => toggleSelectAll(event.target.checked)} />
              </th>
              <th>Time</th>
              <th>Event</th>
              <th>Status</th>
              <th>Duration</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody id="eventsTableBody">
            {filteredEvents.map((row) => (
              <tr key={row.id}>
                <td>
                  <input
                    className="event-checkbox"
                    type="checkbox"
                    value={row.id}
                    checked={selectedEventIds.includes(row.id)}
                    onChange={(event) => toggleRowSelection(row.id, event.target.checked)}
                  />
                </td>
                <td>{formatDateTime(row.timestamp_utc_begin, timezone)}</td>
                <td>
                  <span className={`event_badge ${row.event_type.toLowerCase()}`}>{formatEventType(row.event_type)}</span>
                </td>
                <td>
                  <span className={`status-badge ${row.acknowledged ? 'seen' : 'new'}`}>{row.acknowledged ? 'Seen' : 'New'}</span>
                </td>
                <td>{getEventDurationLabel(row)}</td>
                <td>
                  <div className="event_actions">
                    {!row.acknowledged ? (
                      <button className="event_action_btn" type="button" onClick={() => void acknowledgeEvent(row.id)}>
                        <i className="fas fa-check" />
                      </button>
                    ) : null}
                    <button className="event_action_btn" type="button" onClick={() => void deleteEvent(row.id)}>
                      <i className="fas fa-trash" />
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
