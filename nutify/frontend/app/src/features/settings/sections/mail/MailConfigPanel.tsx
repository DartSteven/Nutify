/**
 * Mailconfigpanel.
 *
 * Frontend module used by Nutify React UI flows and state management.
 */

import type { MailConfigRow, MailFormState, ProviderMap, StatusAlert } from './types'
import { emailOptionLabel, providerDisplayName } from './utils'

type MailConfigPanelProps = {
  isFormVisible: boolean
  showSummary: boolean
  saveVisible: boolean
  isSaving: boolean
  isTesting: boolean
  form: MailFormState
  providers: ProviderMap
  configs: MailConfigRow[]
  status: StatusAlert
  onShowAdd: () => void
  onCancel: () => void
  onProviderChange: (provider: string) => void
  onFieldChange: <K extends keyof MailFormState>(field: K, value: MailFormState[K]) => void
  onTest: () => void
  onSave: () => void
  onEditConfig: (configId: number) => void
  onDeleteConfig: (configId: number) => void
  onToggleConfigEnabled: (configId: number, enabled: boolean) => void
}

function providerOptions(providers: ProviderMap): Array<{ key: string; label: string }> {
  return Object.entries(providers).map(([key, provider]) => ({
    key,
    label: provider.displayName || key,
  }))
}

export function MailConfigPanel(props: MailConfigPanelProps) {
  const {
    isFormVisible,
    showSummary,
    saveVisible,
    isSaving,
    isTesting,
    form,
    providers,
    configs,
    status,
    onShowAdd,
    onCancel,
    onProviderChange,
    onFieldChange,
    onTest,
    onSave,
    onEditConfig,
    onDeleteConfig,
    onToggleConfigEnabled,
  } = props

  const providerNotes =
    form.provider && providers[form.provider]
      ? providers[form.provider].notes || providers[form.provider].note || ''
      : ''

  return (
    <>
      <div className="options_card" id="addEmailConfigContainer" style={{ display: isFormVisible ? 'none' : 'block' }}>
        <div className="card_header">
          <div className="notification_header">
            <h2>Email Configuration</h2>
            <button type="button" id="addEmailConfigBtn" className="options_btn" onClick={onShowAdd}>
              <i className="fas fa-plus" /> Add Configuration
            </button>
          </div>
          <p className="card_subtitle">Configure email settings for notifications</p>
        </div>
      </div>

      <div className="options_card" id="emailConfigFormCard" style={{ display: isFormVisible ? 'block' : 'none' }}>
        <div className="card_header">
          <div className="notification_header">
            <h2>Email Configuration</h2>
            <div id="providerSelectorContainer" className="options_mail_form_group" style={{ margin: 0 }}>
              <select
                id="email_provider"
                name="email_provider"
                className="form-select"
                value={form.provider}
                onChange={(event) => onProviderChange(event.target.value)}
              >
                <option value="">Custom Configuration</option>
                {providerOptions(providers).map((provider) => (
                  <option key={provider.key} value={provider.key}>
                    {provider.label}
                  </option>
                ))}
              </select>
            </div>
          </div>
          <p className="card_subtitle">Configure email settings for notifications</p>
        </div>

        <form id="emailConfigForm" onSubmit={(event) => event.preventDefault()}>
          <input type="hidden" id="email_config_id" name="email_config_id" value={form.id ?? ''} readOnly />

          <div
            id="custom_provider_container"
            style={{ display: form.provider ? 'none' : 'block', maxWidth: '800px', marginBottom: '15px' }}
          >
            <div className="options_mail_form_group">
              <label htmlFor="custom_provider_name">
                <i className="fas fa-tag" /> <span>Name Provider</span>
              </label>
              <input
                type="text"
                id="custom_provider_name"
                name="custom_provider_name"
                placeholder="e.g. My Custom Email Provider"
                value={form.customProviderName}
                onChange={(event) => onFieldChange('customProviderName', event.target.value)}
              />
            </div>
          </div>

          <div className="options_mail_form_grid">
            <div className="options_mail_form_group">
              <label htmlFor="smtp_server">
                <i className="fas fa-server" /> <span id="smtp_server_label">SMTP Server</span>
              </label>
              <input
                type="text"
                id="smtp_server"
                name="smtp_server"
                placeholder="e.g. smtp.gmail.com"
                required
                value={form.smtpServer}
                onChange={(event) => onFieldChange('smtpServer', event.target.value)}
              />
            </div>

            <div className="options_mail_form_group">
              <label htmlFor="smtp_port">
                <i className="fas fa-network-wired" /> <span id="smtp_port_label">SMTP Port</span>
              </label>
              <input
                type="number"
                id="smtp_port"
                name="smtp_port"
                placeholder="e.g. 587"
                required
                value={form.smtpPort}
                onChange={(event) => onFieldChange('smtpPort', event.target.value)}
              />
            </div>

            <div className="options_mail_form_group">
              <div className="checkbox-container">
                <input
                  type="checkbox"
                  id="use_tls"
                  name="use_tls"
                  checked={form.useTls}
                  onChange={(event) => onFieldChange('useTls', event.target.checked)}
                />
                <label htmlFor="use_tls">
                  <i className="fas fa-lock" /> Use TLS/SSL
                </label>
              </div>
            </div>
          </div>

          <div className="options_mail_form_grid">
            <div className="options_mail_form_group">
              <label htmlFor="smtp_username">
                <i className="fas fa-user-shield" /> <span id="username_label">Username</span>
              </label>
              <input
                type="text"
                id="smtp_username"
                name="smtp_username"
                value={form.username}
                onChange={(event) => onFieldChange('username', event.target.value)}
              />
            </div>

            <div className="options_mail_form_group">
              <label htmlFor="smtp_password">
                <i className="fas fa-key" /> <span id="password_label">Password</span>
              </label>
              <input
                type="password"
                id="smtp_password"
                name="smtp_password"
                autoComplete="new-password"
                placeholder="*************"
                value={form.password}
                onChange={(event) => onFieldChange('password', event.target.value)}
              />
            </div>

            <div className="options_mail_form_group">
              <div className="checkbox-container">
                <input
                  type="checkbox"
                  id="use_starttls"
                  name="use_starttls"
                  checked={form.useStarttls}
                  onChange={(event) => onFieldChange('useStarttls', event.target.checked)}
                />
                <label htmlFor="use_starttls">
                  <i className="fas fa-shield-alt" /> Use STARTTLS
                </label>
              </div>
            </div>
          </div>

          <div className="options_mail_form_grid">
            <div className="options_mail_form_group" style={{ display: 'block' }}>
              <label htmlFor="from_email">
                <i className="fas fa-envelope" />
                <span id="from_email_label">{form.provider && providers[form.provider]?.requires_sender_email ? 'From Email (Required)' : 'From Email'}</span>
              </label>
              <input
                type="email"
                id="from_email"
                name="from_email"
                placeholder="Sender email address"
                required={Boolean(form.provider && providers[form.provider]?.requires_sender_email)}
                value={form.fromEmail}
                onChange={(event) => onFieldChange('fromEmail', event.target.value)}
              />
            </div>
            <input type="hidden" id="from_name" name="from_name" value={form.fromEmail} readOnly />

            <div className="options_mail_form_group">
              <label htmlFor="to_email">
                <i className="fas fa-paper-plane" /> Email to send Test Email and Notifications
              </label>
              <input
                type="email"
                id="to_email"
                name="to_email"
                placeholder="Email address for receiving test emails and notifications"
                value={form.toEmail}
                onChange={(event) => onFieldChange('toEmail', event.target.value)}
              />
            </div>

            <div className="options_mail_form_group">
              <label htmlFor="mail_render_mode">
                <i className="fas fa-palette" /> Message Format
              </label>
              <select
                id="mail_render_mode"
                name="mail_render_mode"
                value={form.renderMode}
                onChange={(event) => onFieldChange('renderMode', event.target.value)}
              >
                <option value="graphic">Graphic Card (HTML)</option>
                <option value="text">Plain Text</option>
              </select>
            </div>
          </div>

          <div
            id="provider_notes"
            className="provider-notes-container"
            style={{ display: providerNotes ? 'block' : 'none', marginBottom: '20px' }}
          >
            <i className="fas fa-info-circle" /> <span className="provider-notes-text">{providerNotes}</span>
          </div>

          <div id="configurationButtons" className="options_mail_buttons">
            <button type="button" id="testEmailBtn" className="options_btn" disabled={isTesting} onClick={onTest}>
              <i className="fas fa-paper-plane" />
              <span className="btn-text" style={{ display: isTesting ? 'none' : 'inline' }}>
                Test Email
              </span>
              <span className={`btn-loader ${isTesting ? '' : 'hidden'}`}>
                <i className="fas fa-spinner fa-spin" />
              </span>
            </button>
            <button
              type="button"
              id="saveEmailConfigBtn"
              className="options_btn"
              style={{ display: saveVisible ? 'inline-flex' : 'none' }}
              disabled={isSaving}
              onClick={onSave}
            >
              <i className="fas fa-save" /> Save Configuration
            </button>
            <button type="button" id="cancelEmailConfigBtn" className="options_btn" onClick={onCancel}>
              <i className="fas fa-times" /> Cancel
            </button>
          </div>

          <div id="configurationStatus" className="options_mail_config_status hidden">
            <p>Email configured successfully</p>
            <p className="provider-info">
              <span id="summary_provider" />
              <span id="summary_email" />
            </p>
            <button type="button" id="reconfigureBtn">
              <i className="fas fa-cog" />
              Reconfigure
            </button>
          </div>

          <div id="emailStatus" className={`options_alert ${status ? '' : 'hidden'}`}>
            {status?.message || ''}
          </div>
          <div id="lastTestInfo" className="options_mail_test_info" />
        </form>
      </div>

      <div id="emailConfigListCard" style={{ display: showSummary ? 'block' : 'none' }}>
        <div className="options_card mt-4" id="emailConfigSummary">
          <div className="card_header">
            <h2>Configured Emails</h2>
            <p className="card_subtitle">Your email configurations</p>
          </div>

          <div id="emailConfigsContainer">
            <div className="email_config_summary" id="emailConfigList">
              {configs.length === 0 ? (
                <div className="empty-state">No email configurations found. Click "Add Configuration" to create one.</div>
              ) : (
                configs.map((config) => {
                  const provider = providerDisplayName(config.provider, providers)
                  const statusClass = config.enabled ? 'status-enabled' : 'status-disabled'
                  const statusText = config.enabled ? 'Enabled' : 'Disabled'
                  const formatText = String(config.render_mode || '').toLowerCase() === 'text'
                    ? 'Plain Text'
                    : 'Graphic Card (HTML)'
                  const toggleClass = config.enabled ? 'options_btn_primary' : 'options_btn_secondary'
                  const toggleText = config.enabled ? 'Disable' : 'Enable'
                  return (
                    <div key={config.id} className="email_config_row" data-id={config.id}>
                      <div className="email_config_info">
                        <div className="email_provider_info">
                          <i className="fas fa-plug" /> <span>{provider}</span>
                        </div>
                        <div className="email_address_info">
                          <i className="fas fa-at" /> <span>{config.to_email || 'No recipient configured'}</span>
                        </div>
                        <div className="email_format_info">
                          <i className="fas fa-palette" /> <span>{formatText}</span>
                        </div>
                        <div className={`email_status_info ${statusClass}`}>
                          <i className={`fas ${config.enabled ? 'fa-check-circle' : 'fa-times-circle'}`} /> <span>{statusText}</span>
                        </div>
                      </div>
                      <div className="email_config_actions">
                        <button
                          type="button"
                          className={`options_btn ${toggleClass}`}
                          onClick={() => onToggleConfigEnabled(config.id, !config.enabled)}
                        >
                          <i className={`fas ${config.enabled ? 'fa-toggle-on' : 'fa-toggle-off'}`} /> {toggleText}
                        </button>
                        <button type="button" className="options_btn options_btn_secondary edit-config-btn" onClick={() => onEditConfig(config.id)}>
                          <i className="fas fa-cog" /> Edit
                        </button>
                        <button
                          type="button"
                          className="options_btn options_btn_secondary delete-config-btn"
                          onClick={() => onDeleteConfig(config.id)}
                        >
                          <i className="fas fa-trash" /> Delete
                        </button>
                      </div>
                    </div>
                  )
                })
              )}
            </div>
          </div>
        </div>
      </div>

      <input type="hidden" id="report_email_options_cache" value={configs.map((cfg) => emailOptionLabel(cfg, providers)).join('|')} readOnly />
    </>
  )
}
