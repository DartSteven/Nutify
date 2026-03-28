/**
 * Wizardpage.
 *
 * Frontend module used by Nutify React UI flows and state management.
 */

import { useAppStore } from '../../store/appStore'
import { WizardStepAdmin } from './wizard/WizardStepAdmin'
import { WizardStepCompleteLegacy } from './wizard/WizardStepCompleteLegacy'
import { WizardStepConfiguration } from './wizard/WizardStepConfiguration'
import { WizardStepProfileTopology } from './wizard/WizardStepProfileTopology'
import { WizardStepReviewLegacy } from './wizard/WizardStepReviewLegacy'
import { WizardStepServerIdentity } from './wizard/WizardStepServerIdentity'
import { WizardTestModalLegacy } from './wizard/WizardTestModalLegacy'
import { useSetupWizardRuntime } from './wizard/useSetupWizardRuntime'
import './wizard/wizard.css'

const SETUP_LOGO_SRC = `${import.meta.env.BASE_URL}Nutify-Logo.png`

export function WizardPage() {
  const bootstrap = useAppStore((state) => state.bootstrap)
  const authDisabled = Boolean(bootstrap?.auth.disabled)

  useSetupWizardRuntime()

  return (
    <div className="setup-container" data-auth-disabled={authDisabled ? 'true' : 'false'}>
      <div className="setup-header">
        <img src={SETUP_LOGO_SRC} alt="Nutify Logo" className="setup-logo" />
        <h1 className="setup-title">NUT Configuration Wizard</h1>
        <div className="setup-intro">
          <p>This wizard will help you configure Network UPS Tools (NUT) to work with your UPS devices.</p>
        </div>
      </div>

      <div className="setup-card">
        <div className="card-heading">
          <i className="fas fa-cogs" />
          <h2>Simple Setup</h2>
        </div>
        <div className="card-content">
          <div className="wizard-steps">
            <div className={`step active${authDisabled ? ' hidden' : ''}`} data-step="1">
              <div className="step-number">1</div>
              <div className="step-label">Admin Setup</div>
            </div>
            <div className="step" data-step="2">
              <div className="step-number">2</div>
              <div className="step-label">Server Identity</div>
            </div>
            <div className="step" data-step="3">
              <div className="step-number">3</div>
              <div className="step-label">Profile &amp; Topology</div>
            </div>
            <div className="step" data-step="4">
              <div className="step-number">4</div>
              <div className="step-label">Configuration</div>
            </div>
            <div className="step" data-step="5">
              <div className="step-number">5</div>
              <div className="step-label">Review</div>
            </div>
            <div className="step" data-step="6">
              <div className="step-number">6</div>
              <div className="step-label">Complete</div>
            </div>
          </div>

          <div id="alerts-container" />

          <WizardStepAdmin hidden={authDisabled} />
          <WizardStepServerIdentity />
          <WizardStepProfileTopology />
          <WizardStepConfiguration />
          <WizardStepReviewLegacy />
          <WizardStepCompleteLegacy />

          <div className="wizard-actions">
            <button className="nav-btn back-btn hidden" id="prev-btn">
              <i className="fas fa-arrow-left" /> Back
            </button>
            <div id="wizard-extra-actions" className="wizard-extra-actions hidden" />
            <button className="nav-btn next-btn" id="next-btn">
              Next <i className="fas fa-arrow-right" />
            </button>
            <button className="nav-btn finish-btn hidden" id="save-btn">
              <i className="fas fa-save" /> Save Configuration
            </button>
          </div>
        </div>
      </div>

      <WizardTestModalLegacy />
    </div>
  )
}
