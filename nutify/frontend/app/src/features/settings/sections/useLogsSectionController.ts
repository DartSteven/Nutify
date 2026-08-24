/**
 * Uselogssectioncontroller.
 *
 * Frontend module used by Nutify React UI flows and state management.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from 'react'

import { clearLogs, getLogSettings, getLogs, getLogsDownloadUrl, saveLogSettings } from '../../../lib/api/settings'
import { notifyUser } from './mail/utils'

export type AlertState = {
  tone: 'success' | 'danger'
  message: string
} | null

export type LogSettingsState = {
  log: boolean
  level: string
  werkzeug: boolean
}

type LogLine = {
  content: string
  file: string
  line_number: number
  level?: string
}

type LogsData = {
  lines: LogLine[]
  total_files: number
  total_size: number
  has_more: boolean
}

function escapeHtml(value: string): string {
  return value
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;')
}

function formatBytes(bytes: number): string {
  if (bytes <= 0) return '0 Bytes'
  const units = ['Bytes', 'KB', 'MB', 'GB']
  const index = Math.floor(Math.log(bytes) / Math.log(1024))
  return `${(bytes / (1024 ** index)).toFixed(2)} ${units[index]}`
}

function parseLogSettings(payload: unknown): LogSettingsState {
  if (!payload || typeof payload !== 'object') {
    return { log: true, level: 'INFO', werkzeug: false }
  }
  const data = (payload as { data?: unknown }).data
  if (!data || typeof data !== 'object') {
    return { log: true, level: 'INFO', werkzeug: false }
  }
  const row = data as Record<string, unknown>
  return {
    log: Boolean(row.log),
    level: String(row.level ?? 'INFO'),
    werkzeug: Boolean(row.werkzeug),
  }
}

function parseLogs(payload: unknown): LogsData {
  if (!payload || typeof payload !== 'object') {
    return { lines: [], total_files: 0, total_size: 0, has_more: false }
  }
  const data = (payload as { data?: unknown }).data
  if (!data || typeof data !== 'object') {
    return { lines: [], total_files: 0, total_size: 0, has_more: false }
  }
  const row = data as Record<string, unknown>
  const rawLines = Array.isArray(row.lines) ? row.lines : []
  const lines = rawLines
    .map((entry) => {
      if (!entry || typeof entry !== 'object') return null
      const line = entry as Record<string, unknown>
      const normalized: LogLine = {
        content: String(line.content ?? ''),
        file: String(line.file ?? ''),
        line_number: Number(line.line_number ?? 0),
      }
      if (line.level !== undefined && line.level !== null) {
        normalized.level = String(line.level)
      }
      return normalized
    })
    .filter((line): line is LogLine => line !== null)

  return {
    lines,
    total_files: Number(row.total_files ?? 0),
    total_size: Number(row.total_size ?? 0),
    has_more: Boolean(row.has_more),
  }
}

function formatLogEntry(line: LogLine): string {
  const levelMatch = line.content.match(/\[(DEBUG|INFO|WARNING|ERROR)\]/i)
  const levelClass = levelMatch
    ? `log-${levelMatch[1].toLowerCase()}`
    : (line.level ? `log-${line.level.toLowerCase()}` : '')

  const timestampMatch = line.content.match(/^(\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:[Z+-]\d{2}:?\d{2})?)/)
  const timestamp = timestampMatch ? timestampMatch[1] : ''
  const content = timestamp ? line.content.substring(timestamp.length).trim() : line.content

  return `<div class="log-line ${levelClass}">
    <span class="log-file">${escapeHtml(line.file)}</span>
    <span class="log-number">#${escapeHtml(String(line.line_number))}</span>
    ${timestamp ? `<span class="log-timestamp">${escapeHtml(timestamp)}</span>` : ''}
    <span class="log-content">${escapeHtml(content)}</span>
  </div>`
}

export function useLogsSectionController() {
  const previewRef = useRef<HTMLPreElement | null>(null)
  const currentPageRef = useRef(1)
  const isLoadingRef = useRef(false)
  const [alert, setAlert] = useState<AlertState>(null)
  const [logType, setLogType] = useState('all')
  const [logLevel, setLogLevel] = useState('all')
  const [dateRange, setDateRange] = useState('today')
  const [logSettings, setLogSettings] = useState<LogSettingsState>({ log: true, level: 'INFO', werkzeug: false })
  const [javascriptLogsEnabled, setJavascriptLogsEnabled] = useState(true)
  const [hasMoreLogs, setHasMoreLogs] = useState(false)
  const [isLoadingLogs, setIsLoadingLogs] = useState(false)
  const [logsLoaded, setLogsLoaded] = useState(false)
  const [previewHtml, setPreviewHtml] = useState('')
  const [logCountText, setLogCountText] = useState('Found 0 log files')
  const [refreshBusy, setRefreshBusy] = useState(false)
  const [downloadBusy, setDownloadBusy] = useState(false)
  const [clearBusy, setClearBusy] = useState(false)
  const [saveBusy, setSaveBusy] = useState(false)

  const showAlert = useCallback((message: string, tone: 'success' | 'danger') => {
    setAlert({ message, tone })
    notifyUser(message, tone === 'danger' ? 'error' : 'success')
  }, [])

  const currentFilterQuery = useMemo(
    () => ({ type: logType, level: logLevel, range: dateRange }),
    [dateRange, logLevel, logType],
  )

  const loadLogs = useCallback(
    async (resetPage: boolean) => {
      if (isLoadingRef.current) return
      isLoadingRef.current = true
      setIsLoadingLogs(true)
      setRefreshBusy(true)
      try {
        const page = resetPage ? 1 : currentPageRef.current
        const response = await getLogs({
          ...currentFilterQuery,
          page,
          page_size: 1000,
        })
        const parsed = parseLogs(response)
        const htmlBlock = parsed.lines.map(formatLogEntry).join('')
        setLogsLoaded(true)
        setLogCountText(`Found ${parsed.total_files} log files (${formatBytes(parsed.total_size)})`)
        setHasMoreLogs(parsed.has_more)

        if (resetPage) {
          currentPageRef.current = 1
          setPreviewHtml(htmlBlock)
        } else {
          setPreviewHtml((current) => `${current}${htmlBlock}`)
        }

        if (!htmlBlock && resetPage) {
          setPreviewHtml('No logs found for selected filters')
        }
      } catch (error) {
        const message = error instanceof Error ? error.message : 'Error loading logs'
        showAlert(message, 'danger')
        if (resetPage) {
          setPreviewHtml('Error loading logs. Please try again.')
          setLogCountText('Found 0 log files')
        }
      } finally {
        isLoadingRef.current = false
        setIsLoadingLogs(false)
        setRefreshBusy(false)
      }
    },
    [currentFilterQuery, showAlert],
  )

  const loadMoreLogs = useCallback(async () => {
    if (isLoadingRef.current || !hasMoreLogs) return
    isLoadingRef.current = true
    const nextPage = currentPageRef.current + 1
    currentPageRef.current = nextPage
    setIsLoadingLogs(true)
    try {
      const response = await getLogs({
        ...currentFilterQuery,
        page: nextPage,
        page_size: 1000,
      })
      const parsed = parseLogs(response)
      const htmlBlock = parsed.lines.map(formatLogEntry).join('')
      setHasMoreLogs(parsed.has_more)
      setPreviewHtml((current) => `${current}${htmlBlock}`)
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Error loading logs'
      showAlert(message, 'danger')
    } finally {
      isLoadingRef.current = false
      setIsLoadingLogs(false)
    }
  }, [currentFilterQuery, hasMoreLogs, showAlert])

  const handleDownloadLogs = useCallback(async () => {
    if (downloadBusy) return
    setDownloadBusy(true)
    try {
      const response = await fetch(getLogsDownloadUrl(currentFilterQuery), { credentials: 'same-origin' })
      if (!response.ok) {
        throw new Error('Error downloading logs')
      }
      const blob = await response.blob()
      const linkUrl = window.URL.createObjectURL(blob)
      const downloadLink = document.createElement('a')
      downloadLink.href = linkUrl
      downloadLink.download = `logs_${new Date().toISOString()}.zip`
      document.body.appendChild(downloadLink)
      downloadLink.click()
      window.URL.revokeObjectURL(linkUrl)
      downloadLink.remove()
      showAlert('Logs downloaded successfully', 'success')
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Error downloading logs'
      showAlert(message, 'danger')
    } finally {
      setDownloadBusy(false)
    }
  }, [currentFilterQuery, downloadBusy, showAlert])

  const handleClearLogs = useCallback(async () => {
    if (clearBusy) return
    setClearBusy(true)
    try {
      const response = await clearLogs(logType)
      const message =
        response && typeof response === 'object' && typeof (response as { message?: unknown }).message === 'string'
          ? String((response as { message: string }).message)
          : 'Logs cleared successfully'
      showAlert(message, 'success')
      await loadLogs(true)
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Error clearing logs'
      showAlert(message, 'danger')
    } finally {
      setClearBusy(false)
    }
  }, [clearBusy, loadLogs, logType, showAlert])

  const updateJavascriptLogging = useCallback((enabled: boolean) => {
    const unsafeWindow = window as unknown as {
      webLogger?: { enable: (nextState: boolean) => void }
      GLOBAL_JS_LOGGING_ENABLED?: boolean
    }
    sessionStorage.setItem('GLOBAL_JS_LOGGING_ENABLED', String(enabled))
    localStorage.setItem('webLogger.enabled', String(enabled))
    unsafeWindow.GLOBAL_JS_LOGGING_ENABLED = enabled
    if (unsafeWindow.webLogger && typeof unsafeWindow.webLogger.enable === 'function') {
      unsafeWindow.webLogger.enable(enabled)
    }
  }, [])

  const handleSaveAndRestart = useCallback(async () => {
    if (saveBusy) return
    setSaveBusy(true)
    try {
      updateJavascriptLogging(javascriptLogsEnabled)
      await saveLogSettings({
        log: logSettings.log,
        level: logSettings.level,
        werkzeug: logSettings.werkzeug,
      })
      showAlert('Log configuration updated. Restart the application to apply the changes.', 'success')
      setTimeout(() => {
        void fetch('/api/restart', { method: 'POST', credentials: 'same-origin' })
          .catch(() => null)
          .finally(() => {
            showAlert('The application is restarting...', 'success')
            setTimeout(() => window.location.reload(), 3000)
          })
      }, 1000)
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Error updating log configuration'
      showAlert(message, 'danger')
    } finally {
      setSaveBusy(false)
    }
  }, [javascriptLogsEnabled, logSettings.log, logSettings.level, logSettings.werkzeug, saveBusy, showAlert, updateJavascriptLogging])

  useEffect(() => {
    void (async () => {
      try {
        const settingsPayload = await getLogSettings()
        setLogSettings(parseLogSettings(settingsPayload))
      } catch {
        // Keep defaults when server settings are unavailable.
      }
    })()
  }, [])

  useEffect(() => {
    const sessionValue = sessionStorage.getItem('GLOBAL_JS_LOGGING_ENABLED')
    if (sessionValue !== null) {
      setJavascriptLogsEnabled(sessionValue === 'true')
      return
    }
    const localValue = localStorage.getItem('webLogger.enabled') === 'true'
    sessionStorage.setItem('GLOBAL_JS_LOGGING_ENABLED', String(localValue))
    setJavascriptLogsEnabled(localValue)
  }, [])

  useEffect(() => {
    void loadLogs(true)
  }, [currentFilterQuery, loadLogs])

  const handlePreviewScroll = useCallback(() => {
    if (!previewRef.current || isLoadingLogs || !hasMoreLogs) return
    const { scrollTop, clientHeight, scrollHeight } = previewRef.current
    const distanceToBottom = scrollHeight - (scrollTop + clientHeight)
    if (distanceToBottom < 200) {
      void loadMoreLogs()
    }
  }, [hasMoreLogs, isLoadingLogs, loadMoreLogs])

  return {
    alert,
    clearBusy,
    dateRange,
    downloadBusy,
    handleClearLogs,
    handleDownloadLogs,
    handlePreviewScroll,
    handleSaveAndRestart,
    hasMoreLogs,
    isLoadingLogs,
    javascriptLogsEnabled,
    loadLogs,
    loadMoreLogs,
    logCountText,
    logLevel,
    logSettings,
    logType,
    logsLoaded,
    previewHtml,
    previewRef,
    refreshBusy,
    saveBusy,
    setDateRange,
    setJavascriptLogsEnabled,
    setLogLevel,
    setLogSettings,
    setLogType,
    showAlert,
    updateJavascriptLogging,
  }
}
