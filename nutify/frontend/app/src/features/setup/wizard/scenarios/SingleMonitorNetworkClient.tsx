/**
 * Singlemonitornetworkclient.
 *
 * Frontend module used by Nutify React UI flows and state management.
 */

export function SingleMonitorNetworkClient() {
  return (
    <div id="config-netclient" className="mode-config hidden">
      <h3>Configure Remote UPS Connection</h3>
      <p>Enter the remote NUT server details for this UPS.</p>

      <div className="wizard-form wizard-manual-stack">
        <div className="wizard-detail-card">
          <div className="wizard-detail-card-title">Remote Connection Details</div>
          <div className="form-grid-3 wizard-single-remote-top-grid">
            <div className="form-group">
              <label htmlFor="remote_host">Remote Server:</label>
              <input type="text" id="remote_host" name="remote_host" placeholder="10.10.10.10" required />
              <div className="form-help">IP address or hostname of the remote NUT server.</div>
            </div>
            <div className="form-group">
              <label htmlFor="remote_port">Remote Port:</label>
              <input type="number" id="remote_port" name="remote_port" defaultValue="3493" min={1} max={65535} />
              <div className="form-help">Port of the remote NUT server (default is 3493).</div>
            </div>
            <div className="form-group">
              <label htmlFor="remote_ups_name">UPS Identifier (upsc key):</label>
              <input type="text" id="remote_ups_name" name="remote_ups_name" defaultValue="ups" required />
              <div className="form-help">Technical NUT name used by `upsc`, the part before `@host`.</div>
            </div>
          </div>

          <div className="form-grid-2">
            <div className="form-group">
              <label htmlFor="remote_user">Username:</label>
              <input type="text" id="remote_user" name="remote_user" defaultValue="monuser" />
              <div className="form-help">Username for accessing the remote UPS.</div>
            </div>

            <div className="form-group">
              <label htmlFor="remote_password">Password:</label>
              <input type="password" id="remote_password" name="remote_password" />
              <div className="form-help">Password for accessing the remote UPS.</div>
            </div>
          </div>
        </div>

        <div className="wizard-detail-card wizard-single-remote-overview-card">
          <div className="form-grid-2">
            <div className="form-group">
              <label htmlFor="remote_target_display_name">Target Display Name (UI label):</label>
              <input type="text" id="remote_target_display_name" name="remote_target_display_name" placeholder="Gideon" />
              <div className="form-help">Friendly name shown in the UI, reports, and target lists.</div>
            </div>
            <div className="form-group">
              <label htmlFor="remote_timezone">Target Timezone:</label>
              <select id="remote_timezone" name="remote_timezone" className="setup-timezone-select" defaultValue="UTC">
                <option value="UTC">UTC</option>
              </select>
              <div className="form-help">Timezone used for this UPS target.</div>
            </div>
          </div>

          <div className="wizard-single-remote-bottom-grid">
            <div className="form-group">
              <label htmlFor="remote_currency">Target Currency:</label>
              <select id="remote_currency" name="remote_currency" defaultValue="EUR">
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
              <label htmlFor="remote_polling_interval">Polling Interval (seconds):</label>
              <div className="compact-polling-input-row">
                <input type="number" id="remote_polling_interval" name="remote_polling_interval" className="compact-polling-input" defaultValue="1" min={1} max={60} />
              </div>
              <div className="form-help">How often Nutify refreshes this UPS target.</div>
            </div>
          </div>

          <div className="form-group wizard-single-location-toggle-row">
            <label className="wizard-inline-check-label">
              <input type="checkbox" id="remote_location_enabled" name="remote_location_enabled" /> Location
            </label>
            <div className="form-help">Enable address details for maps, reports, and map views.</div>
          </div>
        </div>

        <div id="remote-location-fields" className="hidden wizard-detail-card">
          <div className="wizard-detail-card-title">Location Details</div>
          <div className="form-grid-2">
            <div className="form-group">
              <label htmlFor="remote_location_country">Country:</label>
              <input type="text" id="remote_location_country" name="remote_location_country" placeholder="United States" />
            </div>
            <div className="form-group">
              <label htmlFor="remote_location_region">State/Region:</label>
              <input type="text" id="remote_location_region" name="remote_location_region" placeholder="New York" />
            </div>
          </div>
          <div className="form-grid-2">
            <div className="form-group">
              <label htmlFor="remote_location_city">City:</label>
              <input type="text" id="remote_location_city" name="remote_location_city" placeholder="New York" />
            </div>
            <div className="form-group">
              <label htmlFor="remote_location_postal_code">Postal Code:</label>
              <input type="text" id="remote_location_postal_code" name="remote_location_postal_code" placeholder="10004" />
            </div>
          </div>
          <div className="form-group">
            <label htmlFor="remote_location_address">Street Address:</label>
            <input type="text" id="remote_location_address" name="remote_location_address" placeholder="Liberty Island" />
            <div className="form-help">Address details used in reports and map views.</div>
          </div>
          <div className="form-group">
            <label htmlFor="remote_location">Location (computed):</label>
            <input type="text" id="remote_location" name="remote_location" readOnly />
            <div className="form-help">This is generated automatically from the fields above.</div>
          </div>
        </div>
      </div>
    </div>
  )
}
