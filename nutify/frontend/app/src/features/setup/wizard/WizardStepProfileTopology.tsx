/**
 * Wizardstepprofiletopology.
 *
 * Frontend module used by Nutify React UI flows and state management.
 */

export function WizardStepProfileTopology() {
  return (
    <div className="wizard-step-content hidden" id="step-3">
      <h3>Select Monitoring Profile</h3>
      <p>Choose how you want Nutify to monitor your UPS targets.</p>

      <div className="mode-options">
        <div className="mode-option profile-option selected" data-profile="single">
          <input type="radio" name="monitoring_profile" id="profile-single" value="single" defaultChecked />
          <div className="mode-icon">
            <i className="fas fa-tv" />
          </div>
          <div className="mode-title">Single Monitor</div>
          <div className="mode-description">Monitor one UPS with the classic Nutify layout.</div>
        </div>

        <div className="mode-option profile-option" data-profile="multi">
          <input type="radio" name="monitoring_profile" id="profile-multi" value="multi" />
          <div className="mode-icon">
            <i className="fas fa-network-wired" />
          </div>
          <div className="mode-title">Multi Monitor</div>
          <div className="mode-description">Monitor multiple UPS targets with independent settings.</div>
        </div>
      </div>

      <div id="single-profile-hint" className="alert alert-info" style={{ marginTop: '18px' }}>
        <i className="fas fa-info-circle" /> Single Monitor is the fastest way to set up one UPS.
      </div>
      <div id="multi-profile-hint" className="alert alert-info hidden" style={{ marginTop: '18px' }}>
        <i className="fas fa-info-circle" /> Multi Monitor lets you add remote and local UPS targets one by one.
      </div>

      <div id="single-mode-selection" style={{ marginTop: '24px' }}>
        <h3>Select NUT Host Mode</h3>
        <p>Choose how this server connects to your UPS.</p>

        <div className="mode-options">
          <div className="mode-option primary-mode-option" data-mode="standalone">
            <input type="radio" name="nut_mode" id="mode-standalone" value="standalone" />
            <div className="mode-icon">
              <i className="fas fa-server" />
            </div>
            <div className="mode-title">Standalone</div>
          <div className="mode-description">Your UPS is connected directly to this server.</div>
          </div>

          <div className="mode-option primary-mode-option" data-mode="netserver">
            <input type="radio" name="nut_mode" id="mode-netserver" value="netserver" />
            <div className="mode-icon">
              <i className="fas fa-network-wired" />
            </div>
            <div className="mode-title">Network Server</div>
          <div className="mode-description">Your UPS is local and will also be shared on the network.</div>
          </div>

          <div className="mode-option primary-mode-option" data-mode="netclient">
            <input type="radio" name="nut_mode" id="mode-netclient" value="netclient" />
            <div className="mode-icon">
              <i className="fas fa-desktop" />
            </div>
            <div className="mode-title">Network Client</div>
          <div className="mode-description">Connect to a UPS that already exists on another NUT server.</div>
          </div>
        </div>
      </div>

      <div id="multi-topology-selection" className="hidden" style={{ marginTop: '24px' }}>
        <h3>Select Fleet Topology</h3>
        <p>Choose which kinds of UPS targets you want to add.</p>

        <div className="mode-options">
          <div className="mode-option topology-option" data-topology="remote_only">
            <div className="mode-icon">
              <i className="fas fa-cloud" />
            </div>
            <div className="mode-title">Remote NUT Only</div>
          <div className="mode-description">All targets are remote NUT servers (`ups@host`).</div>
          </div>

          <div className="mode-option topology-option" data-topology="local_only">
            <div className="mode-icon">
              <i className="fas fa-plug" />
            </div>
            <div className="mode-title">Local Targets Only</div>
          <div className="mode-description">All targets are local UPS drivers running on this host.</div>
          </div>

          <div className="mode-option topology-option" data-topology="mixed">
            <div className="mode-icon">
              <i className="fas fa-random" />
            </div>
            <div className="mode-title">Mixed Local + Remote</div>
          <div className="mode-description">Add both local UPS targets and remote NUT servers.</div>
          </div>
        </div>

        <div id="multi-host-service-selection" className="hidden" style={{ marginTop: '16px' }}>
          <h4>Local Host Service Mode</h4>
          <p>Choose how this host should run local NUT drivers.</p>
          <div className="mode-options">
            <div className="mode-option host-mode-option selected" data-host-mode="standalone">
              <div className="mode-icon">
                <i className="fas fa-server" />
              </div>
              <div className="mode-title">Standalone</div>
              <div className="mode-description">Run local drivers on this host only.</div>
            </div>
            <div className="mode-option host-mode-option" data-host-mode="netserver">
              <div className="mode-icon">
                <i className="fas fa-network-wired" />
              </div>
              <div className="mode-title">Network Server</div>
              <div className="mode-description">Run local drivers and share them with remote NUT clients.</div>
            </div>
          </div>
        </div>

        <div id="multi-derived-host-mode" className="alert alert-info hidden" style={{ marginTop: '16px' }} />
      </div>
    </div>
  )
}
