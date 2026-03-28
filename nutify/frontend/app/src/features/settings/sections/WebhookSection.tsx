/**
 * Webhooksection.
 *
 * Frontend module used by Nutify React UI flows and state management.
 */

import { testWebhookConfig } from '../../../lib/api/settings'
import { LegacyNotificationGrid } from './shared/LegacyNotificationGrid'
import { useWebhookSectionController } from './webhook/useWebhookSectionController'

type WebhookSectionProps = {
  showProviderConfig?: boolean
  showNotifications?: boolean
}

export function WebhookSection({
  showProviderConfig = true,
  showNotifications = true,
}: WebhookSectionProps = {}) {
  const {
    activeTargetId,
    status,
    optionsStatus,
    isFormVisible,
    saveVisible,
    formTestBusy,
    eventTestBusy,
    form,
    selections,
    configs,
    configOptions,
    saveMutation,
    deleteMutation,
    defaultMutation,
    handleAddConfig,
    handleServerTypeChange,
    handleEditConfig,
    handleTestForm,
    handleConfigChange,
    handleEnabledChange,
    handleEventTest,
    setForm,
    setIsFormVisible,
    setSaveVisible,
    defaults,
  } = useWebhookSectionController()

  const hasConfigs = configs.length > 0
  const showMissingProviderCard = showNotifications && !showProviderConfig && !hasConfigs

  return (
    <>
      <div className="options_card" id="addWebhookConfigContainer" style={{ display: showProviderConfig && !isFormVisible ? 'block' : 'none' }}>
        <div className="card_header">
          <div className="notification_header">
            <h2>Webhook Configuration</h2>
            <button type="button" id="addWebhookConfigBtn" className="options_btn" onClick={handleAddConfig}>
              <i className="fas fa-plus" /> Add Webhook Configuration
            </button>
          </div>
          <p className="card_subtitle">Configure webhook endpoints for system notifications</p>
        </div>
      </div>

      <div className="options_card" id="webhookConfigFormCard" style={{ display: showProviderConfig && isFormVisible ? 'block' : 'none' }}>
        <div className="ntfy-form-header">
          <h2>Webhook Configuration</h2>
          <select
            id="webhook_server_type"
            name="webhook_server_type"
            value={form.serverType}
            onChange={(event) => handleServerTypeChange(event.target.value)}
          >
            <option value="custom">Custom</option>
            <option value="discord">Discord</option>
          </select>
        </div>
        <p className="ntfy-form-description">Configure webhook endpoints for system notifications</p>

        <form id="webhookConfigForm" onSubmit={(event) => event.preventDefault()}>
          <input type="hidden" id="webhook_config_id" name="webhook_config_id" value={form.id ?? ''} readOnly />

          <div className="ntfy-form-row">
            <div className="ntfy-form-field">
              <div className="ntfy-form-field-inner">
                <i className="fas fa-tag" />
                <label htmlFor="webhook_name">Name</label>
                <input
                  type="text"
                  id="webhook_name"
                  name="webhook_name"
                  placeholder="My Webhook"
                  required
                  value={form.name}
                  onChange={(event) => setForm((prev) => ({ ...prev, name: event.target.value }))}
                />
              </div>
            </div>
            <div className="ntfy-form-field">
              <div className="ntfy-form-field-inner">
                <i className="fas fa-globe" />
                <label htmlFor="webhook_url">URL</label>
                <input
                  type="text"
                  id="webhook_url"
                  name="webhook_url"
                  placeholder="https://example.com/webhook"
                  required
                  value={form.url}
                  onChange={(event) => setForm((prev) => ({ ...prev, url: event.target.value }))}
                />
              </div>
            </div>
          </div>

          <hr className="ntfy-form-divider" />

          <div className="ntfy-form-row">
            <div className="ntfy-form-field">
              <div className="ntfy-form-field-inner">
                <i className="fas fa-code" />
                <label htmlFor="webhook_content_type">Content Type</label>
                <select
                  id="webhook_content_type"
                  name="webhook_content_type"
                  value={form.contentType}
                  onChange={(event) => setForm((prev) => ({ ...prev, contentType: event.target.value }))}
                >
                  <option value="application/json">application/json</option>
                  <option value="application/xml">application/xml</option>
                  <option value="text/plain">text/plain</option>
                  <option value="application/x-www-form-urlencoded">application/x-www-form-urlencoded</option>
                </select>
              </div>
            </div>
            <div className="ntfy-form-field">
              <div className="ntfy-form-field-inner">
                <i className="fas fa-palette" />
                <label htmlFor="webhook_render_mode">Message Format</label>
                <select
                  id="webhook_render_mode"
                  name="webhook_render_mode"
                  value={form.renderMode}
                  onChange={(event) => setForm((prev) => ({ ...prev, renderMode: event.target.value }))}
                >
                  <option value="graphic">Graphic Card Payload (Rich Text + HTML)</option>
                  <option value="text">Text Payload</option>
                </select>
              </div>
            </div>
            <div className="ntfy-form-field checkbox-field">
              <div className="ntfy-form-field-inner checkbox">
                <i className="fas fa-database" />
                <label>
                  <input
                    type="checkbox"
                    id="webhook_include_ups_data"
                    name="webhook_include_ups_data"
                    checked={form.includeUpsData}
                    onChange={(event) => setForm((prev) => ({ ...prev, includeUpsData: event.target.checked }))}
                  />
                  <span>Include UPS Data</span>
                </label>
              </div>
            </div>
            <div className="ntfy-form-field checkbox-field">
              <div className="ntfy-form-field-inner checkbox">
                <i className="fas fa-shield-alt" />
                <label>
                  <input
                    type="checkbox"
                    id="webhook_verify_ssl"
                    name="webhook_verify_ssl"
                    checked={form.verifySsl}
                    onChange={(event) => setForm((prev) => ({ ...prev, verifySsl: event.target.checked }))}
                  />
                  <span>Verify SSL certificates</span>
                </label>
                <div className="ntfy-tooltip">
                  <i className="fas fa-info-circle" />
                  <span className="ntfy-tooltiptext">Disable for self-signed certificates or when SSL verification fails</span>
                </div>
              </div>
            </div>
          </div>

          <hr className="ntfy-form-divider" />

          <div className="ntfy-form-row">
            <div className="ntfy-form-field">
              <div className="ntfy-form-field-inner">
                <i className="fas fa-lock" />
                <label htmlFor="webhook_auth_type">Authentication</label>
                <select
                  id="webhook_auth_type"
                  name="webhook_auth_type"
                  value={form.authType}
                  onChange={(event) => setForm((prev) => ({ ...prev, authType: event.target.value }))}
                >
                  <option value="none">None</option>
                  <option value="basic">Basic Auth</option>
                  <option value="bearer">Bearer Token</option>
                </select>
              </div>
            </div>
          </div>

          <div id="webhook_basic_auth_fields" style={{ display: form.authType === 'basic' ? 'block' : 'none' }}>
            <div className="ntfy-form-row">
              <div className="ntfy-form-field">
                <div className="ntfy-form-field-inner">
                  <i className="fas fa-user" />
                  <label htmlFor="webhook_auth_username">Username</label>
                  <input
                    type="text"
                    id="webhook_auth_username"
                    name="webhook_auth_username"
                    value={form.authUsername}
                    onChange={(event) => setForm((prev) => ({ ...prev, authUsername: event.target.value }))}
                  />
                </div>
              </div>
              <div className="ntfy-form-field">
                <div className="ntfy-form-field-inner">
                  <i className="fas fa-key" />
                  <label htmlFor="webhook_auth_password">Password</label>
                  <input
                    type="password"
                    id="webhook_auth_password"
                    name="webhook_auth_password"
                    autoComplete="new-password"
                    placeholder="*************"
                    value={form.authPassword}
                    onChange={(event) => setForm((prev) => ({ ...prev, authPassword: event.target.value }))}
                  />
                </div>
              </div>
            </div>
          </div>

          <div id="webhook_bearer_auth_fields" style={{ display: form.authType === 'bearer' ? 'block' : 'none' }}>
            <div className="ntfy-form-row">
              <div className="ntfy-form-field">
                <div className="ntfy-form-field-inner">
                  <i className="fas fa-key" />
                  <label htmlFor="webhook_auth_token">Token</label>
                  <input
                    type="password"
                    id="webhook_auth_token"
                    name="webhook_auth_token"
                    autoComplete="new-password"
                    placeholder="*************"
                    value={form.authToken}
                    onChange={(event) => setForm((prev) => ({ ...prev, authToken: event.target.value }))}
                  />
                </div>
              </div>
            </div>
          </div>

          <hr className="ntfy-form-divider" />

          <div className="ntfy-form-row">
            <div className="ntfy-form-field" style={{ flexGrow: 2 }}>
              <div className="ntfy-form-field-inner">
                <i className="fas fa-list" />
                <label htmlFor="webhook_custom_headers" style={{ display: 'block', marginBottom: '5px' }}>
                  Custom Headers (JSON format)
                </label>
                <textarea
                  id="webhook_custom_headers"
                  name="webhook_custom_headers"
                  rows={6}
                  style={{ minHeight: '100px', width: '100%' }}
                  placeholder='{"X-Api-Key": "your-api-key", "X-Custom-Header": "value"}'
                  value={form.customHeaders}
                  onChange={(event) => setForm((prev) => ({ ...prev, customHeaders: event.target.value }))}
                />
              </div>
            </div>
          </div>

          <div className="ntfy-info-container">
            <i className="fas fa-info-circle" />
            <span>Configure webhooks to integrate with external systems. Webhooks will send HTTP requests with event data to your specified URL.</span>
          </div>

          <div className="ntfy-actions">
            <button type="button" id="testWebhookBtn" className="options_btn options_btn_secondary" onClick={handleTestForm}>
              <i className="fas fa-paper-plane" />
              <span className="btn-text" style={{ display: formTestBusy ? 'none' : 'inline' }}>
                Test Webhook
              </span>
              <span className={`btn-loader ${formTestBusy ? '' : 'hidden'}`}>
                <i className="fas fa-spinner fa-spin" />
              </span>
            </button>
            <button
              type="button"
              id="saveWebhookConfigBtn"
              className="options_btn"
              style={{ display: saveVisible ? 'inline-flex' : 'none' }}
              onClick={() => saveMutation.mutate()}
              disabled={saveMutation.isPending}
            >
              <i className="fas fa-save" /> Save Configuration
            </button>
            <button
              type="button"
              id="cancelWebhookConfigBtn"
              className="options_btn options_btn_secondary"
              onClick={() => {
                setIsFormVisible(false)
                setSaveVisible(false)
                setForm(defaults.form)
              }}
            >
              <i className="fas fa-times" /> Cancel
            </button>
          </div>

          <div
            id="webhookConfigurationStatus"
            className={`options_mail_config_status ${configs.length > 0 && !isFormVisible ? '' : 'hidden'}`}
          >
            <p>Webhook configured successfully</p>
            <button
              type="button"
              id="reconfigureWebhookBtn"
              onClick={() => {
                setIsFormVisible(true)
                setSaveVisible(false)
              }}
            >
              <i className="fas fa-cog" />
              Reconfigure
            </button>
          </div>

          <div id="webhookStatus" className={`options_alert ${status ? '' : 'hidden'}`}>
            {status ? status.message : ''}
          </div>
        </form>
      </div>

      <div className="options_card mt-4" id="webhookConfigSummary" style={{ display: showProviderConfig && hasConfigs ? 'block' : 'none' }}>
        <div className="card_header">
          <div className="notification_header">
            <h2>Configured Webhooks</h2>
          </div>
          <p className="card_subtitle">Your webhook notification services</p>
        </div>
        <div className="email_config_summary" id="webhookConfigList">
          {configs.length === 0 ? (
            <div className="empty-state">No webhook configurations found. Click "Add Webhook Configuration" to create one.</div>
          ) : (
            configs.map((config) => (
              <div className="email_config_row" data-id={config.id} id={`webhook-config-${config.id}`} key={config.id}>
                <div className="email_config_info">
                  <div className="email_provider_info">
                    <i className="fas fa-globe" /> <span>{config.name}</span>
                    {config.is_default ? (
                      <span className="default-badge">
                        <i className="fas fa-check-circle" /> Default
                      </span>
                    ) : null}
                  </div>
                  <div className="email_address_info">
                    <i className="fas fa-link" /> <span title={config.url}>{config.url.length > 40 ? `${config.url.slice(0, 37)}...` : config.url}</span>
                  </div>
                </div>
                <div className="email_config_actions">
                  <button type="button" className="options_btn options_btn_secondary" onClick={() => testWebhookConfig(config.id, activeTargetId)}>
                    <i className="fas fa-paper-plane" /> Test
                  </button>
                  <button type="button" className="options_btn options_btn_secondary" onClick={() => handleEditConfig(config.id)}>
                    <i className="fas fa-cog" /> Edit
                  </button>
                  <button
                    type="button"
                    className="options_btn options_btn_secondary"
                    onClick={() => {
                      if (window.confirm('Are you sure you want to delete this webhook configuration?')) {
                        deleteMutation.mutate(config.id)
                      }
                    }}
                  >
                    <i className="fas fa-trash" /> Delete
                  </button>
                  {!config.is_default ? (
                    <button
                      type="button"
                      className="options_btn options_btn_secondary"
                      onClick={() => defaultMutation.mutate(config.id)}
                    >
                      <i className="fas fa-star" /> Set Default
                    </button>
                  ) : (
                    <button type="button" className="options_btn options_btn_secondary default-config" disabled>
                      <i className="fas fa-star" /> Default
                    </button>
                  )}
                </div>
              </div>
            ))
          )}
        </div>
      </div>

      {showMissingProviderCard ? (
        <div className="options_card mt-4">
          <div className="card_header">
            <div className="notification_header">
              <h2>Webhook Provider Required</h2>
            </div>
            <p className="card_subtitle">
              Configure at least one webhook provider in the Provider tab before enabling webhook notifications.
            </p>
          </div>
        </div>
      ) : null}

      <div className="options_card mt-4" style={{ display: showNotifications && hasConfigs ? 'block' : 'none' }}>
        <div className="card_header">
          <div className="notification_header">
            <h2>Webhook Notifications</h2>
          </div>
          <p className="card_subtitle">Configure which events should trigger webhook notifications</p>
        </div>
        <div id="options_webhook_status" className={`options_alert ${optionsStatus ? '' : 'hidden'}`}>
          {optionsStatus ? optionsStatus.message : ''}
        </div>

        <LegacyNotificationGrid
          prefix="webhook"
          selectClassName="options_webhook_select"
          checkboxClassName="options_webhook_checkbox"
          testClassName="options_webhook_test"
          emptyOptionLabel="Select webhook"
          configOptions={configOptions}
          selections={selections}
          testBusyEventType={eventTestBusy}
          onConfigChange={handleConfigChange}
          onEnabledChange={handleEnabledChange}
          onTest={handleEventTest}
        />
      </div>
    </>
  )
}
