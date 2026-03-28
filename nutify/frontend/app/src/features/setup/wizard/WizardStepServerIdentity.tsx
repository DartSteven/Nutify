/**
 * Wizardstepserveridentity.
 *
 * Frontend module used by Nutify React UI flows and state management.
 */

export function WizardStepServerIdentity() {
  return (
    <div className="wizard-step-content hidden" id="step-2">
      <div className="text-center">
        <i className="fas fa-server setup-icon" />
        <h3>Name This Server</h3>
        <p>Set the server name shown in diagnostics, notifications, and reports.</p>
      </div>

      <div className="wizard-form">
        <div className="form-group">
          <label htmlFor="server_name">
            Server Name:
            <div className="tooltip">
              <i className="fas fa-info-circle info-icon" />
              <span className="tooltip-text">
                This is the global server identity stored in System &gt; Advanced &gt; System Diagnostics. It is also used in notifications and reports so you can recognize which Nutify server sent them.
              </span>
            </div>
          </label>
          <input type="text" id="server_name" name="server_name" defaultValue="Nutify" maxLength={100} required />
          <div className="form-help">Used in System Diagnostics, notifications, and reports.</div>
        </div>

        <div className="alert alert-info">
          <i className="fas fa-info-circle" /> Use a clear name so you can recognize this Nutify server later.
        </div>
      </div>
    </div>
  )
}
