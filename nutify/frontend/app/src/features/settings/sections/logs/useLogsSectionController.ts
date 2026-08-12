/** Logs settings section controller: filtering, pagination, clear/download and log settings. */

import { useEffect, useRef, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  clearLogs,
  getLogs,
  getLogSettings,
  getLogsDownloadUrl,
  saveLogSettings,
} from '../../../../lib/api/settings'

const PAGE_SIZE = 500
const JS_LOGGING_STORAGE_KEY = 'nutify_js_console_logging'

type AlertTone = 'success' | 'error'

type StatusAlert = {
  tone: AlertTone
  message: string
} | null

type LogSettingsState = {
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

const DEFAULT_LOG_SETTINGS: LogSettingsState = {
  log: false,
  level: 'INFO',
  werkzeug: false,
}

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' ? (value as Record<string, unknown>) : {}
}

function getMessage(payload: unknown, fallback: string): string {
  const message = asRecord(payload).message
  return typeof message === 'string' && message ? message : fallback
}

function normalizeLines(payload: unknown): { lines: LogLine[]; hasMore: boolean; totalFiles: number } {
  const data = asRecord(asRecord(payload).data)
  const rawLines = Array.isArray(data.lines) ? data.lines : []
  const lines = rawLines
    .map((row): LogLine | null => {
      const entry = asRecord(row)
      if (typeof entry.content !== 'string') return null
      return {
        content: entry.content,
        file: typeof entry.file === 'string' ? entry.file : '',
        line_number: Number(entry.line_number ?? 0),
        level: typeof entry.level === 'string' ? entry.level : undefined,
      }
    })
    .filter((row): row is LogLine => row !== null)

  return {
    lines,
    hasMore: Boolean(data.has_more),
    totalFiles: Number(data.total_files ?? 0),
  }
}

function escapeHtml(value: string): string {
  return value
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
}

function buildLineHtml(line: LogLine): string {
  const timestampMatch = line.content.match(/^\[([^\]]+)]\s*(.*)$/)
  const timestamp = timestampMatch ? timestampMatch[1] : ''
  const rest = timestampMatch ? timestampMatch[2] : line.content
  const isError = line.level === 'ERROR' || line.level === 'CRITICAL'

  return (
    '<div class="log-line">' +
    `<span class="log-file">${escapeHtml(line.file)}</span>` +
    `<span class="log-number">${line.line_number}</span>` +
    (timestamp ? `<span class="log-timestamp">${escapeHtml(timestamp)}</span>` : '') +
    `<span class="log-content${isError ? ' log-error' : ''}">${escapeHtml(rest)}</span>` +
    '</div>'
  )
}

export function useLogsSectionController() {
  const [alert, setAlert] = useState<StatusAlert>(null)
  const [logType, setLogType] = useState('all')
  const [logLevel, setLogLevel] = useState('all')
  const [dateRange, setDateRange] = useState('today')
  const [logSettings, setLogSettings] = useState<LogSettingsState>(DEFAULT_LOG_SETTINGS)
  const [javascriptLogsEnabled, setJavascriptLogsEnabled] = useState(false)

  const [lines, setLines] = useState<LogLine[]>([])
  const [page, setPage] = useState(1)
  const [hasMoreLogs, setHasMoreLogs] = useState(false)
  const [logsLoaded, setLogsLoaded] = useState(false)
  const [totalFiles, setTotalFiles] = useState(0)

  const [refreshBusy, setRefreshBusy] = useState(false)
  const [isLoadingLogs, setIsLoadingLogs] = useState(false)
  const [downloadBusy, setDownloadBusy] = useState(false)
  const [clearBusy, setClearBusy] = useState(false)
  const [saveBusy, setSaveBusy] = useState(false)

  const previewRef = useRef<HTMLPreElement>(null)

  const logSettingsQuery = useQuery({
    queryKey: ['settings', 'logs', 'settings'],
    queryFn: () => getLogSettings(),
  })

  useEffect(() => {
    const data = asRecord(logSettingsQuery.data).data
    if (!data) return
    const entry = asRecord(data)
    setLogSettings({
      log: Boolean(entry.log),
      level: typeof entry.level === 'string' ? entry.level : DEFAULT_LOG_SETTINGS.level,
      werkzeug: Boolean(entry.werkzeug),
    })
  }, [logSettingsQuery.data])

  useEffect(() => {
    setJavascriptLogsEnabled(window.localStorage.getItem(JS_LOGGING_STORAGE_KEY) === 'true')
  }, [])

  function showAlert(message: string, tone: AlertTone) {
    setAlert({ tone, message })
    window.setTimeout(() => setAlert(null), 5000)
  }

  async function loadLogs(showRefreshSpinner = false) {
    if (showRefreshSpinner) setRefreshBusy(true)
    else setIsLoadingLogs(true)
    try {
      const payload = await getLogs({ type: logType, level: logLevel, range: dateRange, page: 1, page_size: PAGE_SIZE })
      const parsed = normalizeLines(payload)
      setLines(parsed.lines)
      setPage(1)
      setHasMoreLogs(parsed.hasMore)
      setTotalFiles(parsed.totalFiles)
      setLogsLoaded(true)
    } catch (error) {
      showAlert(error instanceof Error ? error.message : 'Failed to load logs', 'error')
    } finally {
      if (showRefreshSpinner) setRefreshBusy(false)
      else setIsLoadingLogs(false)
    }
  }

  useEffect(() => {
    void loadLogs(false)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [logType, logLevel, dateRange])

  async function loadMoreLogs() {
    if (!hasMoreLogs || isLoadingLogs) return
    setIsLoadingLogs(true)
    try {
      const nextPage = page + 1
      const payload = await getLogs({
        type: logType,
        level: logLevel,
        range: dateRange,
        page: nextPage,
        page_size: PAGE_SIZE,
      })
      const parsed = normalizeLines(payload)
      setLines((previous) => [...previous, ...parsed.lines])
      setPage(nextPage)
      setHasMoreLogs(parsed.hasMore)
    } catch (error) {
      showAlert(error instanceof Error ? error.message : 'Failed to load more logs', 'error')
    } finally {
      setIsLoadingLogs(false)
    }
  }

  function handlePreviewScroll(event: React.UIEvent<HTMLPreElement>) {
    const target = event.currentTarget
    const nearBottom = target.scrollTop + target.clientHeight >= target.scrollHeight - 48
    if (nearBottom) void loadMoreLogs()
  }

  async function handleClearLogs() {
    setClearBusy(true)
    try {
      const payload = await clearLogs(logType)
      if (asRecord(payload).success === false) {
        throw new Error(getMessage(payload, 'Failed to clear logs'))
      }
      showAlert(getMessage(payload, 'Logs cleared successfully'), 'success')
      await loadLogs(true)
    } catch (error) {
      showAlert(error instanceof Error ? error.message : 'Failed to clear logs', 'error')
    } finally {
      setClearBusy(false)
    }
  }

  async function handleDownloadLogs() {
    setDownloadBusy(true)
    try {
      window.location.href = getLogsDownloadUrl({ type: logType, level: logLevel, range: dateRange })
    } finally {
      window.setTimeout(() => setDownloadBusy(false), 1000)
    }
  }

  async function handleSaveAndRestart() {
    setSaveBusy(true)
    try {
      const payload = await saveLogSettings(logSettings)
      if (asRecord(payload).success === false) {
        throw new Error(getMessage(payload, 'Failed to save log settings'))
      }
      showAlert('Log settings saved. Restarting the application...', 'success')
      window.setTimeout(() => {
        void fetch('/api/restart', { method: 'POST', credentials: 'same-origin' }).finally(() => {
          window.setTimeout(() => window.location.reload(), 2500)
        })
      }, 1000)
    } catch (error) {
      showAlert(error instanceof Error ? error.message : 'Failed to save log settings', 'error')
      setSaveBusy(false)
    }
  }

  function updateJavascriptLogging(enabled: boolean) {
    window.localStorage.setItem(JS_LOGGING_STORAGE_KEY, enabled ? 'true' : 'false')
  }

  const previewHtml = lines.map(buildLineHtml).join('')
  const logCountText = logsLoaded ? `${lines.length} entries · ${totalFiles} file${totalFiles === 1 ? '' : 's'}` : ''

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
