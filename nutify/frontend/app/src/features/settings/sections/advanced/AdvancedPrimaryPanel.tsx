/**
 * Advancedprimarypanel.
 *
 * Frontend module used by Nutify React UI flows and state management.
 */

import type { AlertState, AdvancedNutFile } from './advancedNutHelpers'

type DocsRow = {
  key: string
  description: string
}

type ConfigState = {
  description: string
  path: string
  modified: string
}

type AdvancedPrimaryPanelProps = {
  active: boolean
  primaryCollapsed: boolean
  primaryAlert: AlertState
  selectedFile: string
  files: AdvancedNutFile[]
  config: ConfigState
  docsRows: DocsRow[]
  editorValue: string
  savePending: boolean
  restartPending: boolean
  onToggleCollapsed: () => void
  onSelectFile: (value: string) => void
  onEditorChange: (value: string) => void
  onSaveConfig: () => void
  onRestartServices: () => void
}

function renderOptionalAlert(alert: AlertState) {
  if (!alert) return null
  return <div className={`options_alert options_alert_${alert.tone}`}>{alert.message}</div>
}

export function AdvancedPrimaryPanel({
  active,
  primaryCollapsed,
  primaryAlert,
  selectedFile,
  files,
  config,
  docsRows,
  editorValue,
  savePending,
  restartPending,
  onToggleCollapsed,
  onSelectFile,
  onEditorChange,
  onSaveConfig,
  onRestartServices,
}: AdvancedPrimaryPanelProps) {
  return (
    <div id="advancedSectionPrimary" className={`advanced_section_panel ${active ? '' : 'hidden'}`} style={{ display: active ? 'block' : 'none' }}>
      <div className={`options_card collapse-card mt-4 ${primaryCollapsed ? '' : 'expanded'}`}>
        <div className="card_header collapse-header" onClick={onToggleCollapsed}>
          <div className="collapse-header-content">
            <h2>Show Configuration file</h2>
            <p className="card_subtitle">Directly edit the active NUT service configuration files for the primary server.</p>
          </div>
          <div className="collapse-toggle"><i className="fas fa-chevron-down" /></div>
        </div>
        <div id="advanced_alert_container" className="options_alert_container">
          {renderOptionalAlert(primaryAlert)}
        </div>
        <div className={`advanced_nut_config collapse-content ${primaryCollapsed ? 'collapsed' : ''}`}>
          <div className="advanced_selection">
            <label htmlFor="advanced_nut_file_select">Select Configuration File:</label>
            <select id="advanced_nut_file_select" className="form-select" value={selectedFile} onChange={(event) => onSelectFile(event.target.value)}>
              <option value="">Select a file</option>
              {files.map((file) => (
                <option key={file.name} value={file.name}>
                  {file.name} - {file.description}
                </option>
              ))}
            </select>
          </div>
          <div className="advanced_editor_layout">
            <div id="advanced_editor_container" className="advanced_editor_section">
              <h3>Configuration Editor</h3>
              <textarea id="advanced_editor" value={editorValue} onChange={(event) => onEditorChange(event.target.value)} />
            </div>
            <div id="advanced_docs_container" className="advanced_docs_section">
              <h3>Documentation</h3>
              {selectedFile ? (
                <div className="file-description">
                  <h3>{selectedFile}</h3>
                  <p className="file-desc">{config.description || 'Network UPS Tools configuration file'}</p>
                  <p className="file-path"><strong>Path:</strong> {config.path || 'N/A'}</p>
                  <p className="file-modified"><strong>Last Modified:</strong> {config.modified || 'N/A'}</p>
                </div>
              ) : (
                <p>Select a configuration file to view documentation.</p>
              )}
              {docsRows.length > 0 ? (
                <>
                  <h4 className="params-header">Parameter Reference</h4>
                  <table className="doc-table">
                    <thead>
                      <tr>
                        <th style={{ width: '30%' }}>Parameter</th>
                        <th style={{ width: '70%' }}>Description</th>
                      </tr>
                    </thead>
                    <tbody>
                      {docsRows.map((row) => (
                        <tr key={row.key}>
                          <td><code>{row.key}</code></td>
                          <td>{row.description || '-'}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </>
              ) : null}
            </div>
          </div>
          <div className="advanced_buttons">
            <button id="advanced_save_btn" className="options_btn" type="button" onClick={onSaveConfig} disabled={!selectedFile || savePending}>
              <i className="fas fa-save" /> Save Configuration
            </button>
            <button id="advanced_restart_btn" className="options_btn" type="button" onClick={onRestartServices} disabled={restartPending}>
              <i className="fas fa-sync" /> Save & Restart Services
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
