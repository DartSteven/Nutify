/**
 * Wizardstepcompletelegacy.
 *
 * Frontend module used by Nutify React UI flows and state management.
 */

export function WizardStepCompleteLegacy() {
  return (
    <div className="wizard-step-content hidden" id="step-6">
      <div className="complete-message hidden" id="complete-success">
        <div className="text-center">
          <i className="fas fa-check-circle success-icon" />
          <h3>Configuration Complete!</h3>
          <p>Your NUT configuration was applied successfully.</p>
          <p><strong>Restart the server to finish setup.</strong></p>

          <div className="wizard-actions text-center">
            <button id="restart-server-btn" className="nav-btn finish-btn">
              <i className="fas fa-sync" /> Restart Server
            </button>
          </div>
        </div>
      </div>

      <div className="complete-message hidden" id="complete-error">
        <div className="text-center">
          <i className="fas fa-exclamation-circle error-icon" />
          <h3>Configuration Failed</h3>
          <p>Nutify could not apply the generated configuration:</p>
          <div className="alert alert-error" id="error-message" />

          <div className="wizard-actions text-center">
            <button className="nav-btn back-btn" id="restart-btn">
              <i className="fas fa-redo" /> Start Over
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
