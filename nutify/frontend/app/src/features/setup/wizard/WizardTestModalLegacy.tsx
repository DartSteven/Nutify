/**
 * Wizardtestmodallegacy.
 *
 * Frontend module used by Nutify React UI flows and state management.
 */

export function WizardTestModalLegacy() {
  return (
    <>
      <div id="test-modal" className="modal">
        <div className="modal-content">
          <div className="modal-header">
            <h3 className="modal-title">Test Configuration Result</h3>
            <button className="modal-close" id="test-modal-close">&times;</button>
          </div>
          <div className="modal-body">
            <p id="test-message" />
            <div id="multi-target-test-list" className="hidden" />
            <div className="upsc-output" id="upsc-output" />
            <div id="missing-realpower-form" className="missing-var-form hidden">
              <div className="alert alert-warning">
                <i className="fas fa-exclamation-triangle" /> Variable <strong>ups.realpower.nominal</strong> is missing but recommended. Please enter it:
              </div>
              <div className="form-group">
                <label htmlFor="ups-realpower-nominal">UPS Nominal Power (Watts):</label>
                <input type="number" id="ups-realpower-nominal" name="ups_realpower_nominal" min={1} placeholder="e.g. 900" />
                <div className="form-help">The rated power capacity of your UPS in Watts</div>
              </div>
            </div>
          </div>
          <div className="modal-footer">
            <button className="nav-btn next-btn" id="close-modal-btn">Close</button>
          </div>
        </div>
      </div>

      <div id="target-detail-modal" className="modal">
        <div className="modal-content">
          <div className="modal-header">
            <h3 className="modal-title" id="target-detail-title">Target Test Details</h3>
            <button className="modal-close" id="target-detail-modal-close">&times;</button>
          </div>
          <div className="modal-body">
            <p id="target-detail-message" />
            <div className="upsc-output" id="target-detail-output" />
          </div>
          <div className="modal-footer">
            <button className="nav-btn next-btn" id="target-detail-close-btn">Close</button>
          </div>
        </div>
      </div>

      <div id="nominal-power-modal" className="modal">
        <div className="modal-content">
          <div className="modal-header">
            <h3 className="modal-title" id="nominal-power-modal-title">UPS Nominal Power Required</h3>
            <button className="modal-close" id="nominal-power-modal-close">&times;</button>
          </div>
          <div className="modal-body">
            <p id="nominal-power-modal-message" className="alert alert-warning">
              ups.realpower.nominal was not found for this target. Insert the nominal UPS power in Watts.
            </p>
            <div className="form-group">
              <label htmlFor="nominal-power-modal-input">UPS Nominal Power (W):</label>
              <input type="number" id="nominal-power-modal-input" min={1} placeholder="e.g. 900" />
              <div className="form-help">This value is saved per target and used only when UPS does not provide ups.realpower.nominal.</div>
            </div>
          </div>
          <div className="modal-footer">
            <button className="nav-btn back-btn" id="nominal-power-modal-cancel-btn">Cancel</button>
            <button className="nav-btn next-btn" id="nominal-power-modal-save-btn">Save</button>
          </div>
        </div>
      </div>
    </>
  )
}
