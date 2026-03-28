/**
 * Advanceddiagnosticspanel.
 *
 * Frontend module used by Nutify React UI flows and state management.
 */

import type { AlertState, InitialSetupForm } from './advancedNutHelpers'

type AdvancedDiagnosticsPanelProps = {
  active: boolean
  initialSetupAlert: AlertState
  initialSetupForm: InitialSetupForm
  savePending: boolean
  onInitialSetupChange: (updater: (prev: InitialSetupForm) => InitialSetupForm) => void
  onSaveInitialSetup: () => void
}

function renderOptionalAlert(alert: AlertState) {
  if (!alert) return null
  return <div className={`options_alert options_alert_${alert.tone}`}>{alert.message}</div>
}

export function AdvancedDiagnosticsPanel({
  active,
  initialSetupAlert,
  initialSetupForm,
  savePending,
  onInitialSetupChange,
  onSaveInitialSetup,
}: AdvancedDiagnosticsPanelProps) {
  return (
    <div id="advancedSectionDiagnostics" className={`advanced_section_panel ${active ? '' : 'hidden'}`} style={{ display: active ? 'block' : 'none' }}>
      <div className="options_card mt-4">
        <div className="card_header">
          <div className="notification_header">
            <h2>Primary UPS Raw JSON</h2>
            <button
              type="button"
              id="downloadUpsJsonBtn"
              className="options_btn options_btn_primary"
              onClick={async () => {
                const button = document.getElementById('downloadUpsJsonBtn') as HTMLButtonElement | null
                if (button) {
                  button.disabled = true
                  button.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Downloading...'
                }

                try {
                  const response = await fetch('/api/ups/json', { credentials: 'same-origin' })
                  if (!response.ok) throw new Error(`HTTP ${response.status}`)
                  const data = await response.json()
                  const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
                  const url = URL.createObjectURL(blob)
                  const link = document.createElement('a')
                  link.href = url
                  link.download = `ups_data_${new Date().toISOString().replace(/[:.]/g, '-')}.json`
                  link.click()
                  URL.revokeObjectURL(url)
                } finally {
                  if (button) {
                    button.disabled = false
                    button.innerHTML = '<i class="fas fa-download"></i> Download UPS JSON'
                  }
                }
              }}
            >
              <i className="fas fa-download" /> Download UPS JSON
            </button>
          </div>
          <p className="card_subtitle">Download the complete UPS payload in JSON format for diagnostics and validation.</p>
        </div>
      </div>

      <div className="options_card mt-4">
        <div className="card_header">
          <div className="notification_header">
            <h2>Initial Setup Variables</h2>
            <button type="button" id="saveInitialSetupBtn" className="options_btn options_btn_primary" onClick={onSaveInitialSetup} disabled={savePending}>
              <i className="fas fa-save" /> Save Changes
            </button>
          </div>
          <p className="card_subtitle">Maintain global server identity and monitoring profile metadata.</p>
        </div>

        <div className="p-4">
          <div id="initialSetupAlertContainer">{renderOptionalAlert(initialSetupAlert)}</div>
          <form id="initialSetupForm" onSubmit={(event) => event.preventDefault()}>
            <div className="options_mail_form_grid">
              <div className="options_mail_form_group">
                <label htmlFor="server_name"><i className="fas fa-server" /> Server Name:</label>
                <input type="text" id="server_name" className="options_input" placeholder="Server name" value={initialSetupForm.server_name} onChange={(event) => onInitialSetupChange((prev) => ({ ...prev, server_name: event.target.value }))} />
                <p className="card_subtitle">The Server Name is used to identify the server in notifications.</p>
              </div>

              <div className="options_mail_form_group">
                <label htmlFor="monitoring_profile"><i className="fas fa-layer-group" /> Monitoring Profile:</label>
                <select id="monitoring_profile" className="options_input" value={initialSetupForm.monitoring_profile} onChange={(event) => onInitialSetupChange((prev) => ({ ...prev, monitoring_profile: event.target.value as InitialSetupForm['monitoring_profile'] }))}>
                  <option value="single">Single Monitor</option>
                  <option value="multi">Multi Monitor</option>
                </select>
                <p className="card_subtitle">Single keeps the classic one-UPS dashboard. Multi enables fleet monitoring and multi-target navigation.</p>
              </div>
            </div>
          </form>
        </div>
      </div>
    </div>
  )
}
