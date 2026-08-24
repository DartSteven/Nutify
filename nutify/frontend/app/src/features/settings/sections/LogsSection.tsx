/**
 * Logssection.
 *
 * Frontend module used by Nutify React UI flows and state management.
 */

import { useLogsSectionController } from './useLogsSectionController'

export function LogsSection() {
  const {
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
  } = useLogsSectionController()

  return (
    <div className="options_log_card">
      <div className="options_log_header">
        <div>
          <h2>System Logs</h2>
          <p className="options_log_subtitle">View and manage system logs</p>
        </div>
        <span id="logCount" className="log-count">{logCountText}</span>
      </div>

      <div className="stats_grid">
        <div className="stat_card">
          <div className="stat-icon">
            <i className="fas fa-toggle-on" />
          </div>
          <div className="stat-content">
            <div className="stat-label">Enable Logs</div>
            <div className="control-container">
              <div className="toggle-switch">
                <input
                  type="checkbox"
                  id="systemLogEnabled"
                  className="toggle-input"
                  checked={logSettings.log}
                  onChange={(event) => setLogSettings((state) => ({ ...state, log: event.target.checked }))}
                />
                <label htmlFor="systemLogEnabled" className="toggle-label">
                  <span className="toggle-inner" />
                  <span className="toggle-switch-text-on">ON</span>
                  <span className="toggle-switch-text-off">OFF</span>
                </label>
              </div>
            </div>
            <p className="stat-description">System events and operations</p>
          </div>
        </div>

        <div className="stat_card">
          <div className="stat-icon">
            <i className="fas fa-list" />
          </div>
          <div className="stat-content">
            <div className="stat-label">Log Level</div>
            <div className="control-container">
              <select
                id="logLevelSelect"
                className="form-select"
                value={logSettings.level}
                onChange={(event) => setLogSettings((state) => ({ ...state, level: event.target.value }))}
              >
                <option value="DEBUG">DEBUG</option>
                <option value="INFO">INFO</option>
                <option value="WARNING">WARNING</option>
                <option value="ERROR">ERROR</option>
                <option value="CRITICAL">CRITICAL</option>
              </select>
            </div>
            <p className="stat-description">Select the log level</p>
          </div>
        </div>

        <div className="stat_card">
          <div className="stat-icon">
            <i className="fas fa-tools" />
          </div>
          <div className="stat-content">
            <div className="stat-label">HTTP Access Logs</div>
            <div className="control-container">
              <div className="toggle-switch">
                <input
                  type="checkbox"
                  id="werkzeugLogEnabled"
                  className="toggle-input"
                  checked={logSettings.werkzeug}
                  onChange={(event) => setLogSettings((state) => ({ ...state, werkzeug: event.target.checked }))}
                />
                <label htmlFor="werkzeugLogEnabled" className="toggle-label">
                  <span className="toggle-inner" />
                  <span className="toggle-switch-text-on">ON</span>
                  <span className="toggle-switch-text-off">OFF</span>
                </label>
              </div>
            </div>
            <p className="stat-description">Enable built-in web server HTTP request logs</p>
          </div>
        </div>

        <div className="stat_card">
          <div className="stat-icon">
            <i className="fas fa-code" />
          </div>
          <div className="stat-content">
            <div className="stat-label">JavaScript Logs</div>
            <div className="control-container">
              <div className="toggle-switch">
                <input
                  type="checkbox"
                  id="javascriptLogEnabled"
                  className="toggle-input"
                  checked={javascriptLogsEnabled}
                  onChange={(event) => {
                    const nextState = event.target.checked
                    setJavascriptLogsEnabled(nextState)
                    updateJavascriptLogging(nextState)
                    showAlert(`JavaScript logs ${nextState ? 'enabled' : 'disabled'}`, 'success')
                  }}
                />
                <label htmlFor="javascriptLogEnabled" className="toggle-label">
                  <span className="toggle-inner" />
                  <span className="toggle-switch-text-on">ON</span>
                  <span className="toggle-switch-text-off">OFF</span>
                </label>
              </div>
            </div>
            <p className="stat-description">Enable/disable JavaScript console logs</p>
          </div>
        </div>

        <div className="stat_card">
          <div className="stat-icon">
            <i className="fas fa-save" />
          </div>
          <div className="stat-content">
            <div className="stat-label">Save & Restart</div>
            <div className="control-container">
              <button type="button" id="saveAndRestartBtn" className="options_btn" onClick={handleSaveAndRestart} disabled={saveBusy}>
                <i className={`fas ${saveBusy ? 'fa-spinner fa-spin' : 'fa-sync'}`} /> <span className="btn-text">{saveBusy ? 'Saving...' : 'Save & Restart'}</span>
              </button>
            </div>
            <p className="stat-description">Apply changes and restart the system</p>
          </div>
        </div>
      </div>

      <div id="logStatus" className={`options_alert ${alert ? `options_alert_${alert.tone}` : 'hidden'}`}>
        {alert ? alert.message : ''}
      </div>

      <div className="options_log_filters">
        <div className="options_log_filter_group">
          <label htmlFor="logType">Log Type</label>
          <select id="logType" value={logType} onChange={(event) => setLogType(event.target.value)}>
            <option value="all">All Logs</option>
            <option value="system">System Logs</option>
            <option value="database">Database Logs</option>
            <option value="ups">UPS Logs</option>
            <option value="energy">Energy Logs</option>
            <option value="web">Web Logs</option>
            <option value="mail">Mail Logs</option>
            <option value="options">Options Logs</option>
            <option value="battery">Battery Logs</option>
            <option value="upsmon">UPS Monitor Logs</option>
            <option value="socket">Socket Logs</option>
            <option value="voltage">Voltage Logs</option>
            <option value="power">Power Logs</option>
          </select>
        </div>

        <div className="options_log_filter_group">
          <label htmlFor="logLevel">Log Level</label>
          <select id="logLevel" value={logLevel} onChange={(event) => setLogLevel(event.target.value)}>
            <option value="all">All Levels</option>
            <option value="debug">Debug</option>
            <option value="info">Info</option>
            <option value="warning">Warning</option>
            <option value="error">Error</option>
          </select>
        </div>

        <div className="options_log_filter_group">
          <label htmlFor="dateRange">Date Range</label>
          <select id="dateRange" value={dateRange} onChange={(event) => setDateRange(event.target.value)}>
            <option value="today">Today</option>
            <option value="week">Last Week</option>
            <option value="month">Last Month</option>
            <option value="all">All Time</option>
          </select>
        </div>
      </div>

      <div className="options_log_actions">
        <button type="button" id="refreshLogsBtn" onClick={() => void loadLogs(true)} disabled={refreshBusy}>
          <i className={`fas ${refreshBusy ? 'fa-spinner fa-spin' : 'fa-sync'}`} />
          {refreshBusy ? ' Loading logs...' : ' Refresh'}
        </button>
        <button type="button" id="downloadLogsBtn" onClick={() => void handleDownloadLogs()} disabled={downloadBusy}>
          <i className={`fas ${downloadBusy ? 'fa-spinner fa-spin' : 'fa-download'}`} />
          {downloadBusy ? ' Downloading...' : ' Download Logs'}
        </button>
        <button type="button" id="clearLogsBtn" onClick={() => void handleClearLogs()} disabled={clearBusy}>
          <i className={`fas ${clearBusy ? 'fa-spinner fa-spin' : 'fa-trash'}`} />
          {clearBusy ? ' Clearing...' : ' Clear Logs'}
        </button>
      </div>

      <div className="options_log_preview">
        <pre
          id="logPreview"
          ref={previewRef}
          onScroll={handlePreviewScroll}
          dangerouslySetInnerHTML={{
            __html: previewHtml || (logsLoaded ? 'No logs found for selected filters' : 'Select filters to preview logs...'),
          }}
        />
        {hasMoreLogs ? (
          <div id="loadMoreLogs" className="load-more-logs">
            <button type="button" onClick={() => void loadMoreLogs()} disabled={isLoadingLogs}>
              <i className={`fas ${isLoadingLogs ? 'fa-spinner fa-spin' : 'fa-arrow-down'}`} /> Load More Logs
            </button>
          </div>
        ) : null}
      </div>
    </div>
  )
}
