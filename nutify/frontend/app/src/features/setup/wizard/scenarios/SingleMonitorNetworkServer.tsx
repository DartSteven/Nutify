/**
 * Singlemonitornetworkserver.
 *
 * Frontend module used by Nutify React UI flows and state management.
 */

export function SingleMonitorNetworkServer() {
  return (
    <div id="config-netserver" className="mode-config hidden">
      <h3>Configure Network UPS Server</h3>
      <p>Set up the local UPS and the network access for this server.</p>
      <div id="primary-config-summary-netserver" className="alert alert-success primary-config-collapsed-hint hidden">
        Primary UPS configured. Continue with the next UPS target.
      </div>

      <div className="wizard-form wizard-primary-two-col">
        <div id="netserver-primary-core" className="primary-core-fields">
          <div className="form-group method-picker-group">
            <label>Configuration Method:</label>
            <div className="config-method-options">
              <div className="config-method-option" id="manual-option-netserver">
                <input type="radio" id="manual-netserver" name="config-method-netserver" value="manual" />
                <div className="method-content">
                  <div className="method-icon"><i className="fas fa-edit" /></div>
                  <div className="method-info">
                    <div className="method-title">Manual Configuration</div>
                    <div className="method-desc">Enter the UPS connection details yourself.</div>
                  </div>
                </div>
              </div>
              <div className="config-method-option" id="auto-option-netserver">
                <input type="radio" id="auto-netserver" name="config-method-netserver" value="auto" />
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

        <div id="manual-config-netserver" className="config-method-section hidden wizard-manual-stack">
          <div className="wizard-detail-card">
            <div className="wizard-detail-card-title">Local + Network Service Details</div>
            <div className="form-grid-2">
              <div className="form-group">
                <label htmlFor="server_ups_driver">UPS Driver:</label>
                <select id="server_ups_driver" name="server_ups_driver" required />
                <div className="form-help">Select the appropriate driver for your UPS model.</div>
              </div>

              <div className="form-group">
                <label htmlFor="server_ups_port">Port:</label>
                <div className="input-with-button">
                  <input type="text" id="server_ups_port" name="server_ups_port" defaultValue="auto" required />
                  <button type="button" id="scan-netserver" className="scan-button hidden">
                    <i className="fas fa-search" /> Scan
                  </button>
                </div>
                <div className="form-help">Usually `auto` for USB, or a specific port like `/dev/ttyS0` for serial.</div>
                <div id="netserver-usb-port-picker" className="wizard-usb-port-picker hidden">
                  <label htmlFor="netserver_detected_usb_port">Detected USB Port:</label>
                  <div className="input-with-button">
                    <select id="netserver_detected_usb_port" name="netserver_detected_usb_port">
                      <option value="">Select a detected USB port</option>
                    </select>
                    <button type="button" id="scan-netserver-usb-ports" className="scan-button">
                      <i className="fas fa-rotate-right" /> Refresh
                    </button>
                  </div>
                  <div id="netserver-usb-port-picker-help" className="form-help">
                    Choose the detected USB port for this UPS. Selecting one fills the Port field above.
                  </div>
                </div>
              </div>
            </div>

            <div className="form-grid-2">
              <div className="form-group">
                <label htmlFor="server_address_ns">Server Address:</label>
                <input type="text" id="server_address_ns" name="server_address_ns" defaultValue="127.0.0.1" />
                <div className="form-help">IP address or hostname of this server (default: `127.0.0.1`).</div>
              </div>
              <div id="netserver-primary-name-anchor">
                <div id="netserver-primary-name-block" className="form-group">
                  <label htmlFor="server_ups_name">UPS Identifier (upsc key):</label>
                  <input type="text" id="server_ups_name" name="server_ups_name" defaultValue="ups" required />
                  <div className="form-help">Technical NUT name used by `upsc`, the part before `@host`.</div>
                </div>
              </div>
            </div>

            <div className="form-grid-2">
              <div className="form-group">
                <label htmlFor="listen_address">Listen Address:</label>
                <input type="text" id="listen_address" name="listen_address" defaultValue="0.0.0.0" required />
                <div className="form-help">IP address to listen on (`0.0.0.0` for all interfaces).</div>
              </div>
              <div className="form-group">
                <label htmlFor="listen_port">Listen Port:</label>
                <input type="text" id="listen_port" name="listen_port" defaultValue="3493" required />
                <div className="form-help">Port to listen on (default is `3493`).</div>
              </div>
            </div>

            <div className="form-grid-2">
              <div className="form-group">
                <label htmlFor="nut_admin_user">NUT Admin Username (`upsd.users`):</label>
                <input type="text" id="nut_admin_user" name="nut_admin_user" defaultValue="admin" required />
                <div className="form-help">Stored in `upsd.users` for NUT admin tools and remote commands. This is not your Nutify web login.</div>
              </div>
              <div className="form-group">
                <label htmlFor="nut_admin_password">NUT Admin Password (`upsd.users`):</label>
                <input type="password" id="nut_admin_password" name="nut_admin_password" required />
                <div className="form-help">Password stored in `upsd.users` for NUT admin access used by tools like `upscmd` and writable commands.</div>
              </div>
            </div>

            <div id="netserver-snmp-fields" className="form-grid-2 hidden">
              <div className="form-group">
                <label htmlFor="server_snmp_community">SNMP Community:</label>
                <input type="text" id="server_snmp_community" name="server_snmp_community" defaultValue="public" placeholder="public" />
                <div className="form-help">Required for `snmp-ups`.</div>
              </div>
              <div className="form-group">
                <label htmlFor="server_snmp_version">SNMP Version:</label>
                <select id="server_snmp_version" name="server_snmp_version" defaultValue="v1">
                  <option value="v1">v1</option>
                  <option value="v2c">v2c</option>
                  <option value="v3">v3</option>
                </select>
              </div>
            </div>
            <input type="hidden" id="server_ups_desc" name="server_ups_desc" defaultValue="Network UPS" />
          </div>

          <div className="wizard-detail-card">
            <div className="form-grid-2">
              <div id="netserver-primary-display-name-anchor">
                <div id="netserver-primary-display-name-block" className="form-group">
                  <label htmlFor="server_target_display_name">Target Display Name (UI label):</label>
                  <input type="text" id="server_target_display_name" name="server_target_display_name" placeholder="Gideon" />
                  <div className="form-help">Friendly name shown in the UI, reports, and target lists.</div>
                </div>
              </div>
              <div id="netserver-primary-timezone-anchor">
                <div id="netserver-primary-timezone-block" className="form-group">
                  <label htmlFor="server_timezone">Target Timezone:</label>
                  <select id="server_timezone" name="server_timezone" className="setup-timezone-select" defaultValue="UTC">
                    <option value="UTC">UTC</option>
                  </select>
                  <div className="form-help">Timezone used for this UPS target.</div>
                </div>
              </div>
            </div>
            <div className="form-grid-2 wizard-primary-manual-meta-grid">
              <div id="netserver-primary-currency-anchor">
                <div id="netserver-primary-currency-block" className="form-group">
                  <label htmlFor="server_currency">Target Currency:</label>
                  <select id="server_currency" name="server_currency" defaultValue="EUR">
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
              <div id="netserver-primary-polling-anchor">
                <div id="netserver-primary-polling-block" className="form-group compact-polling-field">
                  <label htmlFor="server_polling_interval">Polling Interval (seconds):</label>
                  <div className="compact-polling-input-row">
                    <input type="number" id="server_polling_interval" name="server_polling_interval" className="compact-polling-input" defaultValue="1" min={1} max={60} />
                    <span className="compact-polling-help">Default: 1s</span>
                  </div>
                  <div className="form-help">How often Nutify refreshes this UPS target.</div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <div id="auto-config-netserver" className="config-method-section hidden wizard-two-col-section">
          <div id="scan-results-netserver" className="scan-results hidden" />
          <div id="netserver-auto-primary-fields" className="wizard-two-col-fields wizard-auto-detect-details hidden">
            <div className="wizard-auto-detect-details-title">Target Details</div>
            <div id="netserver-auto-display-name-slot" />
            <div id="netserver-auto-name-slot" />
            <div id="netserver-auto-timezone-slot" />
            <div id="netserver-auto-currency-slot" />
            <div id="netserver-auto-polling-slot" />
          </div>
        </div>
      </div>
    </div>
  )
}
