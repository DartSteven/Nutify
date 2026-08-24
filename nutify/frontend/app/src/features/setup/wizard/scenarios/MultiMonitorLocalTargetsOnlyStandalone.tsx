/**
 * Multimonitorlocaltargetsonlystandalone.
 *
 * Frontend module used by Nutify React UI flows and state management.
 */

import { SnmpFields } from '../components/SnmpFields'

export function MultiMonitorLocalTargetsOnlyStandalone() {
  return (
    <div id="multi-targets-section" className="mode-config hidden">
      <div id="multi-target-progress" className="form-help hidden" style={{ marginBottom: '14px' }}>
        Configured targets: 0
      </div>

      <div className="wizard-form">
        <div id="multi-target-local-fields" className="wizard-detail-card">
          <div className="wizard-detail-card-title">Local Connection Details</div>
          <div className="form-grid-3">
            <div className="form-group" id="multi-target-connection-type-group">
              <label htmlFor="multi_target_connection_type">Connection Type:</label>
              <select id="multi_target_connection_type">
                <option value="local_usb_serial">Local USB/Serial UPS</option>
              </select>
              <div className="form-help">Choose how this UPS is connected.</div>
            </div>
            <div className="form-group">
              <label htmlFor="multi_target_local_driver">Local Driver:</label>
              <input type="text" id="multi_target_local_driver" defaultValue="usbhid-ups" />
              <div className="form-help">NUT driver used on this host for the local UPS.</div>
            </div>
            <div className="form-group">
              <label id="multi_target_local_port_label" htmlFor="multi_target_local_port">Port/Device:</label>
              <input type="text" id="multi_target_local_port" defaultValue="auto" placeholder="auto or device/IP" />
              <div id="multi_target_local_port_help" className="form-help">Use `auto` for USB, or enter the local device path required by the selected driver.</div>
            </div>
          </div>

          <div id="multi-target-usb-port-picker" className="wizard-usb-port-picker hidden">
            <label htmlFor="multi_target_detected_usb_port">Detected USB Port:</label>
            <div className="input-with-button">
              <select id="multi_target_detected_usb_port" name="multi_target_detected_usb_port">
                <option value="">Select a detected USB port</option>
              </select>
              <button type="button" id="scan-multi-target-usb-ports" className="scan-button">
                <i className="fas fa-sync-alt" /> Refresh
              </button>
            </div>
            <div id="multi-target-usb-port-picker-help" className="form-help">
              Choose the detected USB device for this target. Selecting one fills the Port field above.
            </div>
          </div>

          <div className="form-grid-2">
            <div id="multi-target-general-ups-slot">
              <div id="multi-target-ups-name-block" className="form-group">
                <label htmlFor="multi_target_ups_name">UPS Identifier (upsc key):</label>
                <input type="text" id="multi_target_ups_name" placeholder="ups" defaultValue="ups" />
                <div className="form-help">Technical NUT name used by `upsc`, the part before `@host`.</div>
              </div>
            </div>
            <div className="form-group">
              <label htmlFor="multi_target_local_desc">UPS Description (optional):</label>
              <input type="text" id="multi_target_local_desc" placeholder="Local UPS target" />
              <div className="form-help">Optional diagnostics label. It does not replace the UPS Identifier.</div>
            </div>
          </div>

          <SnmpFields containerId="multi-target-snmp-fields" idPrefix="multi_target_" />

          <div className="alert alert-info">
            <i className="fas fa-info-circle" /> Local targets are added to this host NUT configuration and monitored locally.
          </div>
        </div>

        <div className="wizard-detail-card multi-target-overview-card">
          <div className="form-grid-2">
            <div className="form-group">
              <label htmlFor="multi_target_name">Target Display Name (UI label):</label>
              <input type="text" id="multi_target_name" placeholder="Gideon" />
              <div className="form-help">Friendly name shown in the UI, reports, and target lists.</div>
            </div>
            <div className="form-group">
              <label htmlFor="multi_target_timezone">Target Timezone:</label>
              <select id="multi_target_timezone" className="setup-timezone-select" defaultValue="UTC">
                <option value="UTC">UTC</option>
              </select>
              <div className="form-help">Timezone used for this UPS target.</div>
            </div>
          </div>

          <div className="multi-target-overview-bottom-grid">
            <div className="form-group">
              <label htmlFor="multi_target_currency">Target Currency:</label>
              <select id="multi_target_currency" defaultValue="EUR">
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
            <div className="form-group compact-polling-field">
              <label htmlFor="multi_target_polling_interval">Polling Interval (seconds):</label>
              <div className="compact-polling-input-row">
                <input type="number" id="multi_target_polling_interval" className="compact-polling-input" defaultValue="1" min={1} max={60} />
                <span className="compact-polling-help">1-60s</span>
              </div>
              <div className="form-help">How often Nutify refreshes this target.</div>
            </div>
            <div className="form-group multi-target-primary-toggle">
              <label htmlFor="multi_target_primary" className="multi-target-primary-label">Set as primary dashboard target</label>
              <label className="wizard-inline-check-label multi-target-primary-check">
                <input type="checkbox" id="multi_target_primary" />
              </label>
              <div className="form-help">Use this target as the default active UPS in the UI.</div>
            </div>
          </div>

          <div className="form-group multi-target-location-toggle-row">
            <label className="wizard-inline-check-label">
              <input type="checkbox" id="multi_target_location_enabled" /> Location
            </label>
            <div className="form-help">Enable address details for maps, reports, and fleet views.</div>
          </div>
        </div>

        <div id="multi-target-location-fields" className="hidden wizard-detail-card">
          <div className="wizard-detail-card-title">Location Details</div>
          <div className="form-grid-2">
            <div className="form-group">
              <label htmlFor="multi_target_location_country">Country:</label>
              <input type="text" id="multi_target_location_country" placeholder="United States" />
            </div>
            <div className="form-group">
              <label htmlFor="multi_target_location_region">State/Region:</label>
              <input type="text" id="multi_target_location_region" placeholder="New York" />
            </div>
          </div>
          <div className="form-grid-2">
            <div className="form-group">
              <label htmlFor="multi_target_location_city">City:</label>
              <input type="text" id="multi_target_location_city" placeholder="New York" />
            </div>
            <div className="form-group">
              <label htmlFor="multi_target_location_postal_code">Postal Code:</label>
              <input type="text" id="multi_target_location_postal_code" placeholder="10004" />
            </div>
          </div>
          <div className="form-group">
            <label htmlFor="multi_target_location_address">Street Address:</label>
            <input type="text" id="multi_target_location_address" placeholder="Liberty Island" />
            <div id="multi-target-location-suggestions" className="multi-target-location-suggestions hidden" />
            <div className="form-help">Start typing to get validated address suggestions.</div>
          </div>
          <div className="form-group">
            <label htmlFor="multi_target_location">Location (computed):</label>
            <input type="text" id="multi_target_location" placeholder="Liberty Island, New York, New York, 10004, United States" readOnly />
            <div className="form-help">This is generated automatically from the fields above.</div>
          </div>
        </div>

        <div id="multi-target-actions-anchor">
          <div className="multi-target-actions">
            <button type="button" className="nav-btn back-btn" id="multi-target-reset-btn">
              <i className="fas fa-eraser" /> Reset Fields
            </button>
            <button type="button" className="nav-btn next-btn hidden" id="multi-target-add-btn" disabled style={{ display: 'none' }}>
              <i className="fas fa-save" /> Save Target
            </button>
            <button type="button" className="nav-btn" id="multi-target-test-btn">
              <i className="fas fa-network-wired" /> Test Target
            </button>
          </div>
        </div>
        <div id="multi-target-test-status" className="form-help" style={{ marginTop: '8px' }}>
          Target test required before saving.
        </div>
        <div id="multi-target-flow-hint" className="form-help hidden" style={{ marginTop: '8px' }} />

        <div className="multi-targets-list">
          <h4>Configured Targets</h4>
          <div id="multi-targets-empty" className="alert alert-warning">No additional targets configured yet.</div>
          <div id="multi-targets-list" />
        </div>
      </div>
    </div>
  )
}
