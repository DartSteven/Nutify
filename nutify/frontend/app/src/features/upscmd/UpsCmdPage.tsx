/**
 * Upscmdpage.
 *
 * Frontend module used by Nutify React UI flows and state management.
 */

import { useCallback, useEffect, useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { io } from 'socket.io-client'

import { withTarget } from '../../lib/api/client'
import { getVariableConfig } from '../../lib/api/settings'
import { useAppStore } from '../../store/appStore'
import { detailsForCommand, iconForCommand } from './commandPresentation'
import {
  asArray,
  asRecord,
  DEFAULT_STATS,
  formatLogTimestamp,
  normalizeCommands,
  normalizeLogs,
  normalizeStats,
  type CommandApiItem,
  type CommandLog,
  type CommandStats,
} from './helpers'

export function UpsCmdPage() {
  const bootstrapTimezone = useAppStore((state) => state.bootstrap?.timezone ?? 'UTC')
  const activeTargetId = useAppStore((state) => state.activeTargetId)
  const { data: variableConfig } = useQuery({
    queryKey: ['upscmd', 'variable-config', activeTargetId],
    queryFn: () => getVariableConfig(activeTargetId),
    staleTime: 10_000,
    refetchInterval: 30_000,
  })
  const timezone = useMemo(() => {
    const scopedTimezone = String(variableConfig?.timezone ?? '').trim()
    return scopedTimezone || bootstrapTimezone
  }, [bootstrapTimezone, variableConfig?.timezone])
  const [commands, setCommands] = useState<CommandApiItem[]>([])
  const [stats, setStats] = useState<CommandStats>(DEFAULT_STATS)
  const [logs, setLogs] = useState<CommandLog[]>([])
  const [socketConnected, setSocketConnected] = useState(false)
  const [currentCommand, setCurrentCommand] = useState<string | null>(null)
  const [clearModalOpen, setClearModalOpen] = useState(false)
  const [infoCommand, setInfoCommand] = useState<string | null>(null)
  const [confirmModalOpen, setConfirmModalOpen] = useState(false)
  const [isExecuting, setIsExecuting] = useState(false)
  const [executionResult, setExecutionResult] = useState<{ success: boolean; output: string } | null>(null)

  const loadCommands = useCallback(async () => {
    const response = await fetch(withTarget('/api/upscmd/list', activeTargetId), {
      credentials: 'same-origin',
    })
    const payload = (await response.json()) as unknown
    const body = asRecord(payload)
    if (!response.ok || body.success === false) {
      throw new Error(String(body.error ?? `HTTP ${response.status}`))
    }
    setCommands(normalizeCommands(payload))
  }, [activeTargetId])

  const loadStats = useCallback(async () => {
    const response = await fetch(withTarget('/api/upscmd/stats', activeTargetId), {
      credentials: 'same-origin',
    })
    const payload = (await response.json()) as unknown
    const body = asRecord(payload)
    if (!response.ok || body.success === false) {
      throw new Error(String(body.error ?? `HTTP ${response.status}`))
    }
    setStats(normalizeStats(payload))
  }, [activeTargetId])

  const loadLogs = useCallback(async () => {
    const response = await fetch(withTarget('/api/upscmd/logs', activeTargetId), {
      credentials: 'same-origin',
    })
    const payload = (await response.json()) as unknown
    const body = asRecord(payload)
    if (!response.ok || body.success === false) {
      throw new Error(String(body.error ?? `HTTP ${response.status}`))
    }
    setLogs(normalizeLogs(payload))
  }, [activeTargetId])

  const refreshAll = useCallback(async () => {
    await Promise.all([loadCommands(), loadStats(), loadLogs()])
  }, [loadCommands, loadLogs, loadStats])

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

    socket.on('command_stats_update', (eventPayload: unknown) => {
      setStats(normalizeStats(eventPayload))
    })

    socket.on('command_logs_update', (eventPayload: unknown) => {
      const body = asRecord(eventPayload)
      const rawLogs = asArray(body)
      if (rawLogs.length > 0) {
        setLogs(
          rawLogs.map((item) => {
            const row = asRecord(item)
            return {
              command: String(row.command ?? ''),
              success: Boolean(row.success),
              output: String(row.output ?? ''),
              timestamp: row.timestamp ? String(row.timestamp) : null,
            }
          }),
        )
      }
    })

    socket.on('command_executed', (eventPayload: unknown) => {
      const body = asRecord(eventPayload)
      setExecutionResult({
        success: Boolean(body.success),
        output: String(body.output ?? ''),
      })
      void refreshAll()
    })

    return () => {
      document.body.classList.remove('socket-connected')
      socket.disconnect()
    }
  }, [refreshAll])

  const selectedCommandDetails = useMemo(() => {
    if (!currentCommand) {
      return null
    }
    return detailsForCommand(currentCommand)
  }, [currentCommand])

  const infoCommandDetails = useMemo(() => {
    if (!infoCommand) {
      return null
    }
    return detailsForCommand(infoCommand)
  }, [infoCommand])

  const openCommandModal = (commandName: string) => {
    setCurrentCommand(commandName)
    setExecutionResult(null)
    setConfirmModalOpen(true)
  }

  const executeCurrentCommand = async () => {
    if (!currentCommand || isExecuting) {
      return
    }

    setIsExecuting(true)
    try {
      const response = await fetch(withTarget('/api/upscmd/execute', activeTargetId), {
        method: 'POST',
        credentials: 'same-origin',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ command: currentCommand }),
      })

      const payload = (await response.json()) as unknown
      const body = asRecord(payload)
      const success = Boolean(body.success)
      const output = String(body.output ?? body.error ?? '')

      setExecutionResult({ success, output })
      await refreshAll()

      if (success && !currentCommand.startsWith('test.')) {
        window.setTimeout(() => {
          setConfirmModalOpen(false)
          setCurrentCommand(null)
          setExecutionResult(null)
        }, 5000)
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Command execution failed'
      setExecutionResult({ success: false, output: message })
    } finally {
      setIsExecuting(false)
    }
  }

  const clearCommandLogs = async () => {
    try {
      const response = await fetch(withTarget('/api/upscmd/clear/logs', activeTargetId), {
        method: 'POST',
        credentials: 'same-origin',
      })
      const payload = (await response.json()) as unknown
      const body = asRecord(payload)
      if (!response.ok || body.success === false) {
        throw new Error(String(body.error ?? `HTTP ${response.status}`))
      }
      await refreshAll()
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Error clearing logs'
      window.alert(message)
    } finally {
      setClearModalOpen(false)
    }
  }

  return (
    <div className="page">
      <div className="page_header">
        <div className="page_title">
          <h1>UPS Commands</h1>
          <p className="page_subtitle">UPS Management and Command Control</p>
        </div>
      </div>

      <div className="stats_grid">
        <div className="stat_card">
          <div className="stat-icon">
            <i className="fas fa-exclamation-triangle" />
          </div>
          <div className="stat-content">
            <div className="stat-header">
              <span className="stat-label">Attention - UPS Command Area</span>
            </div>
            <p>This page allows you to send direct commands to the UPS. Improper use can cause:</p>
            <ul>
              <li>Immediate system shutdown</li>
              <li>Data loss</li>
              <li>Hardware damage</li>
            </ul>
          </div>
        </div>

        <div className="stat_card">
          <div className="stat-icon">
            <i className="fas fa-info-circle" />
          </div>
          <div className="stat-content">
            <div className="stat-header">
              <span className="stat-label">UPS Command Management</span>
            </div>
            <p>This interface allows you to send direct commands to the UPS to control functions such as:</p>
            <ul>
              <li>Beeper management</li>
              <li>Battery test</li>
              <li>Load control</li>
              <li>Shutdown operations</li>
            </ul>
          </div>
        </div>
      </div>

      <div className="combined_card">
        <div className="combined_header">
          <h2>Available Commands</h2>
          <button id="refreshCommands" className="btn-primary" type="button" onClick={() => void loadCommands()}>
            <i className="fas fa-sync" /> Refresh
          </button>
        </div>
        <div id="commandsList" className="stats_grid">
          {commands.map((command) => {
            const details = detailsForCommand(command.name)
            return (
              <div key={command.name} className="stat_card">
                <div className="stat-icon">
                  <i className={`fas ${iconForCommand(command.name)}`} />
                </div>
                <div className="stat-content">
                  <div className="stat-header">
                    <span className="stat-label">{details.title}</span>
                  </div>
                  <p className="stat-description">{details.description}</p>
                  <div className="stat-actions">
                    <div className="button-group">
                      <button className="btn-primary btn-small info-button" type="button" onClick={() => setInfoCommand(command.name)}>
                        <i className="fas fa-info-circle" />
                      </button>
                      <button className="btn-primary execute-button" type="button" onClick={() => openCommandModal(command.name)}>
                        Execute
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            )
          })}
        </div>
      </div>
      <br />

      <div className="combined_card">
        <div className="combined_header">
          <div style={{ display: 'flex', gap: '1rem', alignItems: 'center', justifyContent: 'space-between', width: '100%' }}>
            <h2>Command Statistics</h2>
            <button id="clearLogs" className="btn-primary btn-small" type="button" onClick={() => setClearModalOpen(true)}>
              <i className="fas fa-eraser" /> Clear
            </button>
          </div>
        </div>
        <div className="stats_grid">
          <div className="stat_card mini">
            <div className="stat-icon">
              <i className="fas fa-terminal" />
            </div>
            <div className="stat-content">
              <div className="stat-header">
                <span className="stat-label">Total Commands</span>
              </div>
              <span id="totalCommands" className="stat-value">
                {stats.total}
              </span>
            </div>
          </div>
          <div className="stat_card mini">
            <div className="stat-icon">
              <i className="fas fa-check-circle" />
            </div>
            <div className="stat-content">
              <div className="stat-header">
                <span className="stat-label">Successful Commands</span>
              </div>
              <span id="successfulCommands" className="stat-value">
                {stats.successful}
              </span>
            </div>
          </div>
          <div className="stat_card mini">
            <div className="stat-icon">
              <i className="fas fa-times-circle" />
            </div>
            <div className="stat-content">
              <div className="stat-header">
                <span className="stat-label">Failed Commands</span>
              </div>
              <span id="failedCommands" className="stat-value">
                {stats.failed}
              </span>
            </div>
          </div>
        </div>

        <div className="combined_header" style={{ marginTop: '1rem' }}>
          <h3>Recent Commands Log</h3>
        </div>
        <div id="commandLog" className="command-log-container">
          {logs.map((entry, index) => (
            <div key={`${entry.command}-${entry.timestamp ?? 'none'}-${index}`} className={`log-entry ${entry.success ? 'log-success' : 'log-error'}`}>
              <div className="log-time">{formatLogTimestamp(entry.timestamp, timezone)}</div>
              <div className="log-content">
                <div className="log-command">
                  <strong>{entry.command}</strong>
                  <span className={`log-status ${entry.success ? 'text-success' : 'text-danger'}`}>[{entry.success ? 'Success' : 'Error'}]</span>
                </div>
                {entry.output ? <div className="log-details">{entry.output}</div> : null}
              </div>
            </div>
          ))}
        </div>
      </div>

      {confirmModalOpen ? (
        <div id="confirmModal" className="modal" style={{ display: 'block' }} onClick={(event) => event.target === event.currentTarget && setConfirmModalOpen(false)}>
          <div className="modal-content">
            <div className="modal-header">
              <h3 id="confirmModalLabel">{selectedCommandDetails?.title ?? 'Confirm Command'}</h3>
            </div>
            <div className="modal-body" id="modalBody">
              {executionResult ? (
                <div className="command-execution-status">
                  <div className="mb-2">
                    <i className={`fas fa-${executionResult.success ? 'check' : 'times'}-circle ${executionResult.success ? 'text-success' : 'text-danger'}`} />{' '}
                    {executionResult.success ? 'Command executed successfully' : 'Error in execution'}
                  </div>
                  {executionResult.output ? <div className="live-log p-2 bg-light">{executionResult.output}</div> : null}
                </div>
              ) : (
                <div className="command-confirmation">
                  <p>{selectedCommandDetails?.description ?? ''}</p>
                  <div className="command-warning">
                    <i className="fas fa-exclamation-triangle" />
                    <p>{selectedCommandDetails?.warning ?? ''}</p>
                  </div>
                  <p className="command-execute-confirm">Are you sure you want to execute this command?</p>
                </div>
              )}
            </div>
            <div className="modal-footer">
              {!executionResult ? (
                <button type="button" className="upscmd_btn upscmd_btn-primary" id="confirmCommand" disabled={isExecuting} onClick={() => void executeCurrentCommand()}>
                  {isExecuting ? (
                    <>
                      <i className="fas fa-spinner fa-spin" /> In execution...
                    </>
                  ) : (
                    'Execute'
                  )}
                </button>
              ) : null}
              <button type="button" className="upscmd_btn upscmd_btn-secondary modal-close" onClick={() => setConfirmModalOpen(false)}>
                Close
              </button>
            </div>
          </div>
        </div>
      ) : null}

      {clearModalOpen ? (
        <div id="clearConfirmModal" className="modal" style={{ display: 'block' }} onClick={(event) => event.target === event.currentTarget && setClearModalOpen(false)}>
          <div className="modal-content">
            <div className="modal-header">
              <h3>Confirm Delete</h3>
            </div>
            <div className="modal-body">
              <p>Are you sure you want to delete all command logs?</p>
              <p>This operation cannot be undone.</p>
            </div>
            <div className="modal-footer">
              <button type="button" className="upscmd_btn upscmd_btn-danger" id="confirmClear" onClick={() => void clearCommandLogs()}>
                Clear
              </button>
              <button type="button" className="upscmd_btn upscmd_btn-secondary modal-close" onClick={() => setClearModalOpen(false)}>
                Cancel
              </button>
            </div>
          </div>
        </div>
      ) : null}

      {infoCommand && infoCommandDetails ? (
        <div id="infoModal" className="modal" style={{ display: 'block' }} onClick={(event) => event.target === event.currentTarget && setInfoCommand(null)}>
          <div className="modal-content">
            <div className="modal-header">
              <h3>Command Information</h3>
            </div>
            <div className="modal-body">
              <h4 id="infoTitle" className="mb-3">
                {infoCommandDetails.title}
              </h4>
              <p id="infoDescription" className="mb-3">
                {infoCommandDetails.description}
              </p>
              <div className="upscmd_warning-section">
                <i className="fas fa-exclamation-triangle" />
                <span id="infoWarning">{infoCommandDetails.warning}</span>
              </div>
            </div>
            <div className="modal-footer">
              <button type="button" className="upscmd_btn upscmd_btn-secondary modal-close" onClick={() => setInfoCommand(null)}>
                Close
              </button>
            </div>
          </div>
        </div>
      ) : null}

      <div className="upscmd_socket-status">
        <span className={socketConnected ? 'socket_connected' : 'socket_connected hidden'}>🟢 Socket Connected</span>
        <span className={socketConnected ? 'socket_disconnected hidden' : 'socket_disconnected'}>🔴 Socket Disconnected</span>
      </div>
    </div>
  )
}
