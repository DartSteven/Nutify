/**
 * Wizardstepreviewlegacy.
 *
 * Frontend module used by Nutify React UI flows and state management.
 */

export function WizardStepReviewLegacy() {
  return (
    <div className="wizard-step-content hidden" id="step-5">
      <h3>Review Your Configuration</h3>
      <p>Review the generated NUT configuration before you apply it.</p>

      <div className="config-summary" />

      <div className="form-group">
        <label htmlFor="show-config">Configuration Preview:</label>
        <div className="config-tabs">
          <button className="config-tab active" data-file="nut.conf">nut.conf</button>
          <button className="config-tab" data-file="ups.conf">ups.conf</button>
          <button className="config-tab" data-file="upsd.conf">upsd.conf</button>
          <button className="config-tab" data-file="upsd.users">upsd.users</button>
          <button className="config-tab" data-file="upsmon.conf">upsmon.conf</button>
          <button id="edit-config-btn" className="edit-btn">
            <i className="fas fa-edit" /> Edit
          </button>
        </div>
        <div id="config-preview-container">
          <pre className="config-preview" id="config-preview" />
          <div id="config-editor-container" className="hidden">
            <textarea id="config-editor" />
          </div>
          <div id="editor-actions" className="hidden">
            <button id="save-edit-btn" className="nav-btn save-btn">
              <i className="fas fa-save" /> Save Changes
            </button>
            <button id="cancel-edit-btn" className="nav-btn cancel-btn">
              <i className="fas fa-times" /> Cancel
            </button>
          </div>
        </div>
      </div>

      <div className="form-group">
        <button id="test-config-btn" className="nav-btn next-btn">
          <i className="fas fa-check-circle" /> Test Configuration
        </button>
        <div id="test-result" className="hidden" />
      </div>
    </div>
  )
}
