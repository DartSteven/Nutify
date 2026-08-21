/**
 * Uselogssectioncontroller.
 *
 * Frontend module used by Nutify React UI flows and state management.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from 'react'

import {
  clearLogs,
  getLogSettings,
  getLogs,
  getLogsDownloadUrl,
  saveLogSettings,
} from '../../../../lib/api/settings'

type AlertTone = 'success' | 'danger'

type StatusAlert = {
  message: string
  tone: AlertTone
} | null

type LogSettings = {
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

type NormalizedLogs = {
  lines: LogLine[]
  total_files: number
  total_size: number
  has_more: boolean
}

const DEFAULT_LOG_SETTINGS: LogSettings = {
  log: true,
  level: 'INFO',
  werkzeug: false,
}

function notifyUser(message: string, tone: 'success' | 'error' | 'info'): void {
  const unsafeWindow = window as unknown as {
    notify?: (text: string, level: string, timeout?: number) => void
  }
  if (typeof unsafeWindow.notify === 'function') {
    unsafeWindow.notify(message, tone, 5000)
  }
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
  if (bytes <= 0) {
    return '0 Bytes'
  }
  const units = ['Bytes', 'KB', 'MB', 'GB']
  const exponent = Math.floor(Math.log(bytes) / Math.log(1024))
  return `${(bytes / 1024 ** exponent).toFixed(2)} ${units[exponent]}`
}

function normalizeLogSettings(payload: unknown): LogSettings {
  if (!payload || typeof payload !== 'object') {
    return { ...DEFAULT_LOG_SETTINGS }
  }
  const data = (payload as { data?: unknown }).data
  if (!data || typeof data !== 'object') {
    return { ...DEFAULT_LOG_SETTINGS }
  }
  const row = data as Record<string, unknown>
  return {
    log: Boolean(row.log),
    level: String(row.level ?? 'INFO'),
    werkzeug: Boolean(row.werkzeug),
  }
}

function normalizeLogs(payload: unknown): NormalizedLogs {
  const empty: NormalizedLogs = { lines: [], total_files: 0, total_size: 0, has_more: false }
  if (!payload || typeof payload !== 'object') {
    return empty
  }
  const data = (payload as { data?: unknown }).data
  if (!data || typeof data !== 'object') {
    return empty
  }
  const row = data as Record<string, unknown>
  return {
    lines: (Array.isArray(row.lines) ? row.lines : [])
      .map((entry) => {
        if (!entry || typeof entry !== 'object') {
          return null
        }
        const raw = entry as Record<string, unknown>
        const line: LogLine = {
          content: String(raw.content ?? ''),
          file: String(raw.file ?? ''),
          line_number: Number(raw.line_number ?? 0),
        }
        if (raw.level !== undefined && raw.level !== null) {
          line.level = String(raw.level)
        }
        return line
      })
      .filter((line): line is LogLine => line !== null),
    total_files: Number(row.total_files ?? 0),
    total_size: Number(row.total_size ?? 0),
    has_more: Boolean(row.has_more),
  }
}

function renderLogLine(line: LogLine): string {
  const levelMatch = line.content.match(/\[(DEBUG|INFO|WARNING|ERROR)\]/i)
  const levelClass = levelMatch
    ? `log-${levelMatch[1].toLowerCase()}`
    : line.level
      ? `log-${line.level.toLowerCase()}`
      : ''
  const timestampMatch = line.content.match(
    /^(\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:[Z+-]\d{2}:?\d{2})?)/,
  )
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
  const pageRef = useRef(1)
  const loadingRef = useRef(false)

  const [alert, setAlert] = useState<StatusAlert>(null)
  const [logType, setLogType] = useState('all')
  const [logLevel, setLogLevel] = useState('all')
  const [dateRange, setDateRange] = useState('today')
  const [logSettings, setLogSettings] = useState<LogSettings>(DEFAULT_LOG_SETTINGS)
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

  const showAlert = useCallback((message: string, tone: AlertTone) => {
    setAlert({ message, tone })
    notifyUser(message, tone === 'danger' ? 'error' : 'success')
  }, [])

  const logQuery = useMemo(
    () => ({ type: logType, level: logLevel, range: dateRange }),
    [dateRange, logLevel, logType],
  )

  const loadLogs = useCallback(
    async (reset: boolean) => {
      if (loadingRef.current) {
        return
      }
      loadingRef.current = true
      setIsLoadingLogs(true)
      setRefreshBusy(true)
      try {
        const page = reset ? 1 : pageRef.current
        const normalized = normalizeLogs(await getLogs({ ...logQuery, page, page_size: 1000 }))
        const html = normalized.lines.map(renderLogLine).join('')
        setLogsLoaded(true)
        setLogCountText(`Found ${normalized.total_files} log files (${formatBytes(normalized.total_size)})`)
        setHasMoreLogs(normalized.has_more)
        if (reset) {
          pageRef.current = 1
          setPreviewHtml(html)
        } else {
          setPreviewHtml((prev) => `${prev}${html}`)
        }
        if (!html && reset) {
          setPreviewHtml('No logs found for selected filters')
        }
      } catch (error) {
        const message = error instanceof Error ? error.message : 'Error loading logs'
        showAlert(message, 'danger')
        if (reset) {
          setPreviewHtml('Error loading logs. Please try again.')
          setLogCountText('Found 0 log files')
        }
      } finally {
        loadingRef.current = false
        setIsLoadingLogs(false)
        setRefreshBusy(false)
      }
    },
    [logQuery, showAlert],
  )

  const loadMoreLogs = useCallback(async () => {
    if (loadingRef.current || !hasMoreLogs) {
      return
    }
    loadingRef.current = true
    const nextPage = pageRef.current + 1
    pageRef.current = nextPage
    setIsLoadingLogs(true)
    try {
      const normalized = normalizeLogs(await getLogs({ ...logQuery, page: nextPage, page_size: 1000 }))
      const html = normalized.lines.map(renderLogLine).join('')
      setHasMoreLogs(normalized.has_more)
      setPreviewHtml((prev) => `${prev}${html}`)
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Error loading logs'
      showAlert(message, 'danger')
    } finally {
      loadingRef.current = false
      setIsLoadingLogs(false)
    }
  }, [hasMoreLogs, logQuery, showAlert])

  const handleDownloadLogs = useCallback(async () => {
    if (downloadBusy) {
      return
    }
    setDownloadBusy(true)
    try {
      const response = await fetch(getLogsDownloadUrl(logQuery), { credentials: 'same-origin' })
      if (!response.ok) {
        throw new Error('Error downloading logs')
      }
      const blob = await response.blob()
      const url = window.URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = `logs_${new Date().toISOString()}.zip`
      document.body.appendChild(link)
      link.click()
      window.URL.revokeObjectURL(url)
      link.remove()
      showAlert('Logs downloaded successfully', 'success')
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Error downloading logs'
      showAlert(message, 'danger')
    } finally {
      setDownloadBusy(false)
    }
  }, [downloadBusy, logQuery, showAlert])

  const handleClearLogs = useCallback(async () => {
    if (clearBusy) {
      return
    }
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
    const globalWindow = window as unknown as {
      GLOBAL_JS_LOGGING_ENABLED?: boolean
      webLogger?: { enable?: (value: boolean) => void }
    }
    sessionStorage.setItem('GLOBAL_JS_LOGGING_ENABLED', String(enabled))
    localStorage.setItem('webLogger.enabled', String(enabled))
    globalWindow.GLOBAL_JS_LOGGING_ENABLED = enabled
    if (globalWindow.webLogger && typeof globalWindow.webLogger.enable === 'function') {
      globalWindow.webLogger.enable(enabled)
    }
  }, [])

  const handleSaveAndRestart = useCallback(async () => {
    if (saveBusy) {
      return
    }
    setSaveBusy(true)
    try {
      updateJavascriptLogging(javascriptLogsEnabled)
      await saveLogSettings({ log: logSettings.log, level: logSettings.level, werkzeug: logSettings.werkzeug })
      showAlert('Log configuration updated. Restart the application to apply the changes.', 'success')
      setTimeout(() => {
        fetch('/api/restart', { method: 'POST', credentials: 'same-origin' })
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
  }, [
    javascriptLogsEnabled,
    logSettings.level,
    logSettings.log,
    logSettings.werkzeug,
    saveBusy,
    showAlert,
    updateJavascriptLogging,
  ])

  useEffect(() => {
    void (async () => {
      try {
        setLogSettings(normalizeLogSettings(await getLogSettings()))
      } catch {
        // Keep default log settings when the request fails.
      }
    })()
  }, [])

  useEffect(() => {
    const stored = sessionStorage.getItem('GLOBAL_JS_LOGGING_ENABLED')
    if (stored !== null) {
      setJavascriptLogsEnabled(stored === 'true')
      return
    }
    const enabled = localStorage.getItem('webLogger.enabled') === 'true'
    sessionStorage.setItem('GLOBAL_JS_LOGGING_ENABLED', String(enabled))
    setJavascriptLogsEnabled(enabled)
  }, [])

  useEffect(() => {
    void loadLogs(true)
  }, [loadLogs])

  const handlePreviewScroll = useCallback(() => {
    if (!previewRef.current || isLoadingLogs || !hasMoreLogs) {
      return
    }
    const { scrollTop, clientHeight, scrollHeight } = previewRef.current
    if (scrollHeight - (scrollTop + clientHeight) < 200) {
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
