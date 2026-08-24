/**
 * Singlemonitorstandalone.
 *
 * Frontend module used by Nutify React UI flows and state management.
 */

import { SnmpFields } from '../components/SnmpFields'

export function SingleMonitorStandalone() {
  return (
    <div id="config-standalone" className="mode-config hidden">
      <h3>Configure Local UPS</h3>
      <p>Set up the UPS connected directly to this server.</p>
      <div id="primary-config-summary-standalone" className="alert alert-success primary-config-collapsed-hint hidden">
        Primary UPS configured. Continue with the next UPS target.
      </div>

      <div className="wizard-form wizard-primary-two-col">
        <div id="standalone-primary-core" className="primary-core-fields">
          <div className="form-group method-picker-group">
            <label>Configuration Method:</label>
            <div className="config-method-options">
              <div className="config-method-option" id="manual-option-standalone">
                <input type="radio" id="manual-standalone" name="config-method-standalone" value="manual" />
                <div className="method-content">
                  <div className="method-icon"><i className="fas fa-edit" /></div>
                  <div className="method-info">
                    <div className="method-title">Manual Configuration</div>
                    <div className="method-desc">Enter the UPS connection details yourself.</div>
                  </div>
                </div>
              </div>
              <div className="config-method-option" id="auto-option-standalone">
                <input type="radio" id="auto-standalone" name="config-method-standalone" value="auto" />
                <div className="method-content">
                  <div className="method-icon"><i className="fas fa-magic" /></div>
                  <div className="method-info">
                    <div className="method-title">Auto-detect with nut-scanner</div>
                    <div className="method-desc">Scan this server and pick a detected UPS device.</div>
                  </div>
                </div>
              </div>
            </div>
            <div className="form-help">Choose how you want to set up this local UPS.</div>
          </div>
        </div>

        <div id="manual-config-standalone" className="config-method-section hidden wizard-manual-stack">
          <div className="wizard-detail-card">
            <div className="wizard-detail-card-title">Local Connection Details</div>
            <div className="form-grid-2">
              <div className="form-group">
                <label htmlFor="ups_driver">UPS Driver:</label>
                <select id="ups_driver" name="ups_driver" required />
                <div className="form-help">Select the appropriate driver for your UPS model.</div>
              </div>

              <div className="form-group">
                <label id="ups_port_label" htmlFor="ups_port">Port/Device:</label>
                <div className="input-with-button">
                  <input type="text" id="ups_port" name="ups_port" defaultValue="auto" required />
                  <button type="button" id="scan-standalone" className="scan-button hidden">
                    <i className="fas fa-search" /> Scan
                  </button>
                </div>
                <div id="ups_port_help" className="form-help">Use `auto` for USB, or enter the local device path required by the selected driver.</div>
                <div id="standalone-usb-port-picker" className="wizard-usb-port-picker hidden">
                  <label htmlFor="standalone_detected_usb_port">Detected USB Port:</label>
                  <div className="input-with-button">
                    <select id="standalone_detected_usb_port" name="standalone_detected_usb_port">
                      <option value="">Select a detected USB port</option>
                    </select>
                    <button type="button" id="scan-standalone-usb-ports" className="scan-button">
                      <i className="fas fa-rotate-right" /> Refresh
                    </button>
                  </div>
                  <div id="standalone-usb-port-picker-help" className="form-help">
                    Choose the detected USB port for this UPS. Selecting one fills the Port field above.
                  </div>
                </div>
              </div>
            </div>

            <div className="form-grid-2">
              <div className="form-group">
                <label htmlFor="server_address">Local NUT Server Address:</label>
                <input type="text" id="server_address" name="server_address" defaultValue="127.0.0.1" />
                <div className="form-help">Address of Nutify's local NUT service, not the UPS network address. Usually `127.0.0.1`.</div>
              </div>
              <div id="standalone-primary-name-anchor">
                <div id="standalone-primary-name-block" className="form-group">
                  <label htmlFor="ups_name">
                    UPS Identifier (upsc key):
                    <div className="tooltip">
                      <i className="fas fa-info-circle info-icon" />
                      <span className="tooltip-text">Technical NUT name used by `upsc`, the part before `@host`.</span>
                    </div>
                  </label>
                  <input type="text" id="ups_name" name="ups_name" defaultValue="ups" required />
                  <div className="form-help">Technical NUT name used by `upsc`, the part before `@host`.</div>
                </div>
              </div>
            </div>

            <SnmpFields containerId="standalone-snmp-fields" />
            <input type="hidden" id="ups_desc" name="ups_desc" defaultValue="Local UPS" />
          </div>

          <div className="wizard-detail-card">
            <div className="form-grid-2">
              <div id="standalone-primary-display-name-anchor">
                <div id="standalone-primary-display-name-block" className="form-group">
                  <label htmlFor="ups_target_display_name">Target Display Name (UI label):</label>
                  <input type="text" id="ups_target_display_name" name="ups_target_display_name" placeholder="Gideon" />
                  <div className="form-help">Friendly name shown in the UI, reports, and target lists.</div>
                </div>
              </div>
              <div id="standalone-primary-timezone-anchor">
                <div id="standalone-primary-timezone-block" className="form-group">
                  <label htmlFor="ups_timezone">Target Timezone:</label>
                  <select id="ups_timezone" name="ups_timezone" className="setup-timezone-select" defaultValue="UTC">
                    <option value="UTC">UTC</option>
                  </select>
                  <div className="form-help">Timezone used for this UPS target.</div>
                </div>
              </div>
            </div>
            <div className="form-grid-2 wizard-primary-manual-meta-grid">
              <div id="standalone-primary-currency-anchor">
                <div id="standalone-primary-currency-block" className="form-group">
                  <label htmlFor="ups_currency">Target Currency:</label>
                  <select id="ups_currency" name="ups_currency" defaultValue="EUR">
                    <option value="EUR">EUR</option>
                    <option value="USD">USD</option>
                    <option value="GBP">GBP</option>
                    <option value="JPY">JPY</option>
                    <option value="AUD">AUD</option>
                    <option value="CAD">CAD</option>
                    <option value="CHF">CHF</option>
                    <option value="CNY">CNY</option>
                    <option value="INR">INR</option>
                  </select>
                  <div className="form-help">Currency used for this UPS target.</div>
                </div>
              </div>
              <div id="standalone-primary-polling-anchor">
                <div id="standalone-primary-polling-block" className="form-group compact-polling-field">
                  <label htmlFor="ups_polling_interval">Polling Interval (seconds):</label>
                  <div className="compact-polling-input-row">
                    <input type="number" id="ups_polling_interval" name="ups_polling_interval" className="compact-polling-input" defaultValue="1" min={1} max={60} />
                    <span className="compact-polling-help">Default: 1s</span>
                  </div>
                  <div className="form-help">How often Nutify refreshes this UPS target.</div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <div id="auto-config-standalone" className="config-method-section hidden wizard-two-col-section">
          <div id="scan-results-standalone" className="scan-results hidden" />
          <div id="standalone-auto-primary-fields" className="wizard-two-col-fields wizard-auto-detect-details hidden">
            <div className="wizard-auto-detect-details-title">Target Details</div>
            <div id="standalone-auto-display-name-slot" />
            <div id="standalone-auto-name-slot" />
            <div id="standalone-auto-timezone-slot" />
            <div id="standalone-auto-currency-slot" />
            <div id="standalone-auto-polling-slot" />
          </div>
        </div>
      </div>
    </div>
  )
}
