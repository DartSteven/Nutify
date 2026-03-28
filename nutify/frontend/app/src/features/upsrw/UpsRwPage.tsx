/**
 * Upsrwpage.
 *
 * Frontend module used by Nutify React UI flows and state management.
 */

import { useCallback, useEffect, useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { io } from 'socket.io-client'

import { withTarget } from '../../lib/api/client'
import { getVariableConfig } from '../../lib/api/settings'
import { useAppStore } from '../../store/appStore'

type UpsVariable = {
  name: string
  value: string
  description: string
  type: string
  max_length: string
}

type VariableHistoryEntry = {
  name: string
  old_value: string
  new_value: string
  timestamp: string | null
  success: boolean
}

function asRecord(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    return {}
  }
  return value as Record<string, unknown>
}

function asArray(value: unknown): unknown[] {
  return Array.isArray(value) ? value : []
}

function normalizeVariables(payload: unknown): UpsVariable[] {
  const body = asRecord(payload)
  const rows = asArray(body.variables)

  return rows
    .map((item) => {
      const row = asRecord(item)
      const name = String(row.name ?? '').trim()
      if (!name) {
        return null
      }
      return {
        name,
        value: String(row.value ?? ''),
        description: String(row.description ?? ''),
        type: String(row.type ?? ''),
        max_length: String(row.max_length ?? ''),
      }
    })
    .filter((item): item is UpsVariable => item !== null)
}

function normalizeHistory(payload: unknown): VariableHistoryEntry[] {
  const body = asRecord(payload)
  const rows = asArray(body.history)

  return rows.map((item) => {
    const row = asRecord(item)
    return {
      name: String(row.name ?? ''),
      old_value: String(row.old_value ?? ''),
      new_value: String(row.new_value ?? ''),
      timestamp: row.timestamp ? String(row.timestamp) : null,
      success: Boolean(row.success),
    }
  })
}

function formatHistoryTimestamp(timestamp: string | null, timezone: string): string {
  if (!timestamp) {
    return '-'
  }

  const date = new Date(timestamp)
  if (Number.isNaN(date.getTime())) {
    return timestamp
  }

  return date.toLocaleString([], { timeZone: timezone })
}

export function UpsRwPage() {
  const bootstrapTimezone = useAppStore((state) => state.bootstrap?.timezone ?? 'UTC')
  const activeTargetId = useAppStore((state) => state.activeTargetId)
  const { data: variableConfig } = useQuery({
    queryKey: ['upsrw', 'variable-config', activeTargetId],
    queryFn: () => getVariableConfig(activeTargetId),
    staleTime: 10_000,
    refetchInterval: 30_000,
  })
  const timezone = useMemo(() => {
    const scopedTimezone = String(variableConfig?.timezone ?? '').trim()
    return scopedTimezone || bootstrapTimezone
  }, [bootstrapTimezone, variableConfig?.timezone])

  const [variables, setVariables] = useState<UpsVariable[]>([])
  const [history, setHistory] = useState<VariableHistoryEntry[]>([])
  const [socketConnected, setSocketConnected] = useState(false)

  const [editModalOpen, setEditModalOpen] = useState(false)
  const [clearModalOpen, setClearModalOpen] = useState(false)
  const [infoModalOpen, setInfoModalOpen] = useState(false)

  const [selectedVariable, setSelectedVariable] = useState<UpsVariable | null>(null)
  const [newValue, setNewValue] = useState('')

  const loadVariables = useCallback(async () => {
    try {
      const response = await fetch(withTarget('/api/upsrw/list', activeTargetId), {
        credentials: 'same-origin',
      })
      const payload = (await response.json()) as unknown
      const body = asRecord(payload)
      if (!response.ok || body.success === false) {
        throw new Error(String(body.error ?? body.message ?? `HTTP ${response.status}`))
      }
      setVariables(normalizeVariables(payload))
    } catch {
      setVariables([])
    }
  }, [activeTargetId])

  const loadHistory = useCallback(async () => {
    try {
      const response = await fetch(withTarget('/api/upsrw/history', activeTargetId), {
        credentials: 'same-origin',
      })
      const payload = (await response.json()) as unknown
      const body = asRecord(payload)
      if (!response.ok || body.success === false) {
        throw new Error(String(body.error ?? body.message ?? `HTTP ${response.status}`))
      }
      setHistory(normalizeHistory(payload))
    } catch {
      setHistory([])
    }
  }, [activeTargetId])

  const refreshAll = useCallback(async () => {
    await Promise.all([loadVariables(), loadHistory()])
  }, [loadHistory, loadVariables])

  useEffect(() => {
    void refreshAll()
  }, [refreshAll])

  useEffect(() => {
    const socket = io({
      withCredentials: true,
      transports: ['websocket', 'polling'],
    })

    socket.on('connect', () => {
      setSocketConnected(true)
      document.body.classList.add('socket-connected')
    })

    socket.on('disconnect', () => {
      setSocketConnected(false)
      document.body.classList.remove('socket-connected')
    })

    socket.on('connect_error', () => {
      setSocketConnected(false)
      document.body.classList.remove('socket-connected')
    })

    socket.on('variable_update', (payload: unknown) => {
      const body = asRecord(payload)
      const variableName = String(body.name ?? '').trim()
      const variableValue = String(body.value ?? '')
      if (!variableName) {
        return
      }
      setVariables((previous) =>
        previous.map((entry) => (entry.name === variableName ? { ...entry, value: variableValue } : entry)),
      )
    })

    socket.on('history_update', (payload: unknown) => {
      if (!Array.isArray(payload)) {
        void loadHistory()
        return
      }
      setHistory(normalizeHistory({ history: payload }))
    })

    return () => {
      document.body.classList.remove('socket-connected')
      socket.disconnect()
    }
  }, [loadHistory])

  const openEditModal = (variable: UpsVariable) => {
    setSelectedVariable(variable)
    setNewValue(variable.value)
    setEditModalOpen(true)
  }

  const openInfoModal = (variable: UpsVariable) => {
    setSelectedVariable(variable)
    setInfoModalOpen(true)
  }

  const closeAllModals = () => {
    setEditModalOpen(false)
    setClearModalOpen(false)
    setInfoModalOpen(false)
    setSelectedVariable(null)
  }

  const saveVariable = async () => {
    if (!selectedVariable) {
      return
    }

    try {
      const response = await fetch(withTarget('/api/upsrw/set', activeTargetId), {
        method: 'POST',
        credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: selectedVariable.name,
          value: newValue,
        }),
      })

      const payload = (await response.json()) as unknown
      const body = asRecord(payload)

      if (!response.ok || body.success === false) {
        throw new Error(String(body.error ?? body.message ?? `HTTP ${response.status}`))
      }

      closeAllModals()
      await refreshAll()
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : 'Error during saving'
      window.alert(`Error: ${message}`)
    }
  }

  const clearHistory = async () => {
    try {
      const response = await fetch(withTarget('/api/upsrw/clear-history', activeTargetId), {
        method: 'POST',
        credentials: 'same-origin',
      })

      const payload = (await response.json()) as unknown
      const body = asRecord(payload)
      if (!response.ok || body.success === false) {
        throw new Error(String(body.error ?? body.message ?? `HTTP ${response.status}`))
      }

      setHistory([])
      setClearModalOpen(false)
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : 'Error clearing history'
      window.alert(`Error: ${message}`)
    }
  }

  const variableCards = useMemo(() => {
    if (variables.length === 0) {
      return (
        <div className="stat_card mini">
          <div className="stat-content">
            <div className="stat-header">
              <span className="stat-label">No writable variables available</span>
            </div>
          </div>
        </div>
      )
    }

    return variables.map((variable) => (
      <div key={variable.name} className="stat_card mini" data-variable={variable.name}>
        <div className="stat-icon">
          <i className="fas fa-cog" />
        </div>
        <div className="stat-content">
          <div className="stat-header">
            <span className="stat-label">{variable.name}</span>
          </div>
          <div className="stat-value variable-value">{variable.value}</div>
          <div className="stat-actions">
            <div className="button-group">
              <button className="btn-primary btn-small info-button" type="button" onClick={() => openInfoModal(variable)}>
                <i className="fas fa-info-circle" />
              </button>
              <button className="btn-primary execute-button" type="button" onClick={() => openEditModal(variable)}>
                Modify
              </button>
            </div>
          </div>
        </div>
      </div>
    ))
  }, [variables])

  return (
    <div className="page upsrw_page">
      <div className="page_header">
        <div className="page_title">
          <h1>UPS Variables</h1>
          <p className="page_subtitle">UPS Variable Management and Control</p>
        </div>
      </div>

      <div className="stats_grid">
        <div className="stat_card">
          <div className="stat-icon">
            <i className="fas fa-exclamation-triangle" />
          </div>
          <div className="stat-content">
            <div className="stat-header">
              <span className="stat-label">Attention - UPS Variable Modification</span>
            </div>
            <p>This page allows you to modify UPS variables. Improper use can cause:</p>
            <ul>
              <li>System malfunctions</li>
              <li>Hardware damage</li>
              <li>Unexpected behaviors</li>
            </ul>
          </div>
        </div>

        <div className="stat_card">
          <div className="stat-icon">
            <i className="fas fa-info-circle" />
          </div>
          <div className="stat-content">
            <div className="stat-header">
              <span className="stat-label">UPS Variable Management</span>
            </div>
            <p>This interface allows you to:</p>
            <ul>
              <li>View current variables</li>
              <li>Modify variable values</li>
              <li>Monitor changes</li>
              <li>Restore default values</li>
            </ul>
          </div>
        </div>
      </div>

      <div className="combined_card">
        <div className="combined_header">
          <h2>Available Variables</h2>
          <button id="refreshVariables" className="btn-primary" type="button" onClick={() => void loadVariables()}>
            <i className="fas fa-sync" /> Refresh
          </button>
        </div>
        <div id="variablesList" className="stats_grid">
          {variableCards}
        </div>
      </div>
      <br />
      <div className="combined_card">
        <div className="combined_header">
          <h2>Modification History</h2>
          <button id="clearHistory" className="btn-primary btn-small" type="button" onClick={() => setClearModalOpen(true)}>
            <i className="fas fa-eraser" /> Clear
          </button>
        </div>
        <div id="modificationHistory" className="command-log-container">
          {history.map((entry, index) => (
            <div key={`${entry.name}-${entry.timestamp ?? 'none'}-${index}`} className="upscmd_log-entry">
              <div className="upscmd_log-time">{formatHistoryTimestamp(entry.timestamp, timezone)}</div>
              <div className="upscmd_log-content">
                <div className="upscmd_log-command">
                  <strong>{entry.name}</strong>
                </div>
                <div className="upscmd_log-details">
                  {entry.old_value} {'\u2192'} {entry.new_value}
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>

      <div className="upscmd_socket-status">
        <span className={socketConnected ? 'socket_connected' : 'socket_connected hidden'}>🟢 Socket Connected</span>
        <span className={socketConnected ? 'socket_disconnected hidden' : 'socket_disconnected'}>🔴 Socket Disconnected</span>
      </div>

      {editModalOpen ? (
        <div id="editModal" className="modal" style={{ display: 'block' }} onClick={(event) => event.target === event.currentTarget && closeAllModals()}>
          <div className="modal-content">
            <div className="modal-header">
              <h3 id="editModalLabel">Edit Variable</h3>
            </div>
            <div className="modal-body">
              <form id="editForm" onSubmit={(event) => event.preventDefault()}>
                <div className="form-group">
                  <label>Variable Name:</label>
                  <span id="variableName">{selectedVariable?.name ?? ''}</span>
                </div>
                <div className="form-group">
                  <label>Current Value:</label>
                  <span id="currentValue">{selectedVariable?.value ?? ''}</span>
                </div>
                <div className="form-group">
                  <label htmlFor="newValue">New Value:</label>
                  <input id="newValue" type="text" required value={newValue} onChange={(event) => setNewValue(event.target.value)} />
                </div>
              </form>
            </div>
            <div className="modal-footer">
              <button type="button" className="btn-primary" id="saveVariable" onClick={() => void saveVariable()}>
                Execute
              </button>
              <button type="button" className="btn-primary modal-close" onClick={() => closeAllModals()}>
                Close
              </button>
            </div>
          </div>
        </div>
      ) : null}

      {clearModalOpen ? (
        <div id="clearConfirmModal" className="modal" style={{ display: 'block' }} onClick={(event) => event.target === event.currentTarget && closeAllModals()}>
          <div className="modal-content">
            <div className="modal-header">
              <h3>Confirm Delete</h3>
            </div>
            <div className="modal-body">
              <p>Are you sure you want to delete the modification history?</p>
              <p>This operation cannot be undone.</p>
            </div>
            <div className="modal-footer">
              <button type="button" className="btn-primary" id="confirmClear" onClick={() => void clearHistory()}>
                Delete
              </button>
              <button type="button" className="btn-primary modal-close" onClick={() => closeAllModals()}>
                Cancel
              </button>
            </div>
          </div>
        </div>
      ) : null}

      {infoModalOpen ? (
        <div id="infoModal" className="modal" style={{ display: 'block' }} onClick={(event) => event.target === event.currentTarget && closeAllModals()}>
          <div className="modal-content">
            <div className="modal-header">
              <h3>Variable Information</h3>
            </div>
            <div className="modal-body">
              <h4 id="infoTitle" className="mb-3">
                {selectedVariable?.name ?? ''}
              </h4>
              <p id="infoDescription" className="mb-3">
                {selectedVariable?.description ?? ''}
              </p>
              <div className="warning-section">
                <i className="fas fa-exclamation-triangle" />
                <span id="infoWarning">
                  Type: {selectedVariable?.type ?? ''} <br />
                  Maximum length: {selectedVariable?.max_length ?? ''} <br />
                  Current value: {selectedVariable?.value ?? ''}
                </span>
              </div>
            </div>
            <div className="modal-footer">
              <button type="button" className="btn-primary modal-close" onClick={() => closeAllModals()}>
                Close
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  )
}
