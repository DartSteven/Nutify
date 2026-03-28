/**
 * Wizardstepadmin.
 *
 * Frontend module used by Nutify React UI flows and state management.
 */

type WizardStepAdminProps = {
  hidden: boolean
}

export function WizardStepAdmin({ hidden }: WizardStepAdminProps) {
  return (
    <div className={`wizard-step-content${hidden ? ' hidden' : ''}`} id="step-1">
      <div className="text-center">
        <i className="fas fa-user-shield setup-icon" />
        <h3>Create Admin Account</h3>
        <p>Choose the login you will use to access Nutify.</p>
      </div>

      <div className="wizard-form">
        <div className="form-group">
          <label htmlFor="dashboard_admin_username">
            Admin Username:
            <div className="tooltip">
              <i className="fas fa-info-circle info-icon" />
              <span className="tooltip-text">
                Choose a username for the administrator account. This will be used to login to the Nutify dashboard.
              </span>
            </div>
          </label>
          <input type="text" id="dashboard_admin_username" name="dashboard_admin_username" defaultValue="admin" required />
          <div className="form-help">Username used to sign in to Nutify.</div>
        </div>

        <div className="form-grid-2">
          <div className="form-group">
            <label htmlFor="dashboard_admin_password">
              Admin Password:
              <div className="tooltip">
                <i className="fas fa-info-circle info-icon" />
                <span className="tooltip-text">
                  Choose a strong password for the administrator account. This password will be used to login to the Nutify dashboard.
                </span>
              </div>
            </label>
            <input type="password" id="dashboard_admin_password" name="dashboard_admin_password" required />
            <div className="form-help">Password used to sign in to Nutify.</div>
          </div>

          <div className="form-group">
            <label htmlFor="dashboard_admin_password_confirm">
              Confirm Password:
              <div className="tooltip">
                <i className="fas fa-info-circle info-icon" />
                <span className="tooltip-text">Re-enter the password to confirm it's correct.</span>
              </div>
            </label>
            <input type="password" id="dashboard_admin_password_confirm" name="dashboard_admin_password_confirm" required />
            <div className="form-help">Enter the same password again.</div>
          </div>
        </div>

        <div className="alert alert-info">
          <i className="fas fa-info-circle" /> This account has full access to setup, UPS management, and settings.
        </div>
      </div>
    </div>
  )
}
