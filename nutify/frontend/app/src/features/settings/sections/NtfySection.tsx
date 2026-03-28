/**
 * Ntfysection.
 *
 * Frontend module used by Nutify React UI flows and state management.
 */

import { testNtfyConfig } from '../../../lib/api/settings'
import { LegacyNotificationGrid } from './shared/LegacyNotificationGrid'
import { useNtfySectionController } from './ntfy/useNtfySectionController'

type NtfySectionProps = {
  showProviderConfig?: boolean
  showNotifications?: boolean
}

export function NtfySection({
  showProviderConfig = true,
  showNotifications = true,
}: NtfySectionProps = {}) {
  const {
    activeTargetId,
    status,
    optionsStatus,
    isFormVisible,
    form,
    saveVisible,
    eventTestBusy,
    formTestBusy,
    selections,
    configs,
    configOptions,
    saveMutation,
    deleteMutation,
    setDefaultMutation,
    handleAddConfig,
    handleEditConfig,
    handleTestForm,
    handleConfigChange,
    handleEnabledChange,
    handleEventTest,
    setForm,
    setSaveVisible,
    setIsFormVisible,
    defaults,
  } = useNtfySectionController()

  const hasConfigs = configs.length > 0
  const showMissingProviderCard = showNotifications && !showProviderConfig && !hasConfigs

  return (
    <>
      <div className="options_card" id="addNtfyConfigContainer" style={{ display: showProviderConfig && !isFormVisible ? 'block' : 'none' }}>
        <div className="card_header">
          <div className="notification_header">
            <h2>Ntfy Configuration</h2>
            <button type="button" id="addNtfyConfigBtn" className="options_btn" onClick={handleAddConfig}>
              <i className="fas fa-plus" /> Add Ntfy Configuration
            </button>
          </div>
          <p className="card_subtitle">Configure Ntfy for push notifications to your devices</p>
        </div>
      </div>

      <div className="options_card" id="ntfyConfigFormCard" style={{ display: showProviderConfig && isFormVisible ? 'block' : 'none' }}>
        <div className="ntfy-form-header">
          <h2>Ntfy Configuration</h2>
          <select
            id="ntfy_server_type"
            name="ntfy_server_type"
            value={form.serverType}
            onChange={(event) => setForm((prev) => ({ ...prev, serverType: event.target.value }))}
          >
            <option value="ntfy.sh">ntfy.sh (Official)</option>
            <option value="custom">Self-hosted</option>
          </select>
        </div>
        <p className="ntfy-form-description">Configure Ntfy for push notifications to your devices</p>

        <form id="ntfyConfigForm" onSubmit={(event) => event.preventDefault()}>
          <input type="hidden" id="ntfy_config_id" name="ntfy_config_id" value={form.id ?? ''} readOnly />
          <div
            id="custom_server_container"
            className="ntfy-form-field"
            style={{ display: form.serverType === 'custom' ? 'block' : 'none' }}
          >
            <div className="ntfy-form-field-inner">
              <i className="fas fa-globe" />
              <label htmlFor="ntfy_custom_server">Server URL</label>
              <input
                type="text"
                id="ntfy_custom_server"
                name="ntfy_custom_server"
                placeholder="https://your-ntfy-server.com"
                value={form.customServer}
                onChange={(event) => setForm((prev) => ({ ...prev, customServer: event.target.value }))}
              />
            </div>
          </div>

          <div className="ntfy-form-row">
            <div className="ntfy-form-field">
              <div className="ntfy-form-field-inner">
                <i className="fas fa-tag" />
                <label htmlFor="ntfy_topic">Topic</label>
                <input
                  type="text"
                  id="ntfy_topic"
                  name="ntfy_topic"
                  placeholder="my-ups-notifications"
                  value={form.topic}
                  onChange={(event) => setForm((prev) => ({ ...prev, topic: event.target.value }))}
                  required
                />
              </div>
            </div>
            <div className="ntfy-form-field">
              <div className="ntfy-form-field-inner">
                <i className="fas fa-exclamation-circle" />
                <label htmlFor="ntfy_priority">Priority</label>
                <select
                  id="ntfy_priority"
                  name="ntfy_priority"
                  value={form.priority}
                  onChange={(event) => setForm((prev) => ({ ...prev, priority: event.target.value }))}
                >
                  <option value="1">1 (Min)</option>
                  <option value="2">2 (Low)</option>
                  <option value="3">3 (Default)</option>
                  <option value="4">4 (High)</option>
                  <option value="5">5 (Max)</option>
                </select>
              </div>
            </div>
            <div className="ntfy-form-field">
              <div className="ntfy-form-field-inner">
                <i className="fas fa-palette" />
                <label htmlFor="ntfy_render_mode">Message Format</label>
                <select
                  id="ntfy_render_mode"
                  name="ntfy_render_mode"
                  value={form.renderMode}
                  onChange={(event) => setForm((prev) => ({ ...prev, renderMode: event.target.value }))}
                >
                  <option value="graphic">Graphic Card (Rich Text)</option>
                  <option value="text">Plain Text</option>
                </select>
              </div>
            </div>
          </div>

          <hr className="ntfy-form-divider" />

          <div className="ntfy-form-row">
            <div className="ntfy-form-field checkbox-field">
              <div className="ntfy-form-field-inner checkbox">
                <i className="fas fa-lock" />
                <label>
                  <input
                    type="checkbox"
                    id="ntfy_use_auth"
                    name="ntfy_use_auth"
                    checked={form.useAuth}
                    onChange={(event) => setForm((prev) => ({ ...prev, useAuth: event.target.checked }))}
                  />
                  <span>Use Auth</span>
                </label>
              </div>
            </div>
            <div className="ntfy-form-field auth-field" style={{ display: form.useAuth ? 'block' : 'none' }}>
              <div className="ntfy-form-field-inner">
                <i className="fas fa-user" />
                <label htmlFor="ntfy_username">Username</label>
                <input
                  type="text"
                  id="ntfy_username"
                  name="ntfy_username"
                  value={form.username}
                  onChange={(event) => setForm((prev) => ({ ...prev, username: event.target.value }))}
                />
              </div>
            </div>
            <div className="ntfy-form-field auth-field" style={{ display: form.useAuth ? 'block' : 'none' }}>
              <div className="ntfy-form-field-inner">
                <i className="fas fa-key" />
                <label htmlFor="ntfy_password">Password</label>
                <input
                  type="password"
                  id="ntfy_password"
                  name="ntfy_password"
                  placeholder="*************"
                  autoComplete="new-password"
                  value={form.password}
                  onChange={(event) => setForm((prev) => ({ ...prev, password: event.target.value }))}
                />
              </div>
            </div>
            <div className="ntfy-form-field checkbox-field">
              <div className="ntfy-form-field-inner checkbox">
                <i className="fas fa-tags" />
                <label>
                  <input
                    type="checkbox"
                    id="ntfy_use_tags"
                    name="ntfy_use_tags"
                    checked={form.useTags}
                    onChange={(event) => setForm((prev) => ({ ...prev, useTags: event.target.checked }))}
                  />
                  <span>Use Event Tags</span>
                </label>
              </div>
            </div>
          </div>

          <hr className="ntfy-form-divider" />

          <div className="ntfy-info-container">
            <i className="fas fa-info-circle" />
            <span>
              Configure <a href="https://ntfy.sh" target="_blank" rel="noreferrer">Ntfy</a> to receive instant push notifications on your devices. Download the Ntfy app from
              {' '}
              <a href="https://play.google.com/store/apps/details?id=io.heckel.ntfy" target="_blank" rel="noreferrer">Google Play</a>,
              {' '}
              <a href="https://f-droid.org/en/packages/io.heckel.ntfy/" target="_blank" rel="noreferrer">F-Droid</a>, or the
              {' '}
              <a href="https://apps.apple.com/us/app/ntfy/id1625396347" target="_blank" rel="noreferrer">App Store</a>.
            </span>
          </div>

          <div className="ntfy-actions">
            <button type="button" id="testNtfyBtn" className="options_btn options_btn_secondary" onClick={handleTestForm}>
              <i className="fas fa-paper-plane" />
              <span className="btn-text" style={{ display: formTestBusy ? 'none' : 'inline' }}>
                Test Notification
              </span>
              <span className={`btn-loader ${formTestBusy ? '' : 'hidden'}`}>
                <i className="fas fa-spinner fa-spin" />
              </span>
            </button>
            <button
              type="button"
              id="saveNtfyConfigBtn"
              className="options_btn"
              style={{ display: saveVisible ? 'inline-flex' : 'none' }}
              onClick={() => saveMutation.mutate()}
              disabled={saveMutation.isPending}
            >
              <i className="fas fa-save" /> Save Configuration
            </button>
            <button
              type="button"
              id="cancelNtfyConfigBtn"
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
            id="ntfyConfigurationStatus"
            className={`options_mail_config_status ${configs.length > 0 && !isFormVisible ? '' : 'hidden'}`}
          >
            <p>Ntfy configured successfully</p>
            <button
              type="button"
              id="reconfigureNtfyBtn"
              onClick={() => {
                setIsFormVisible(true)
                setSaveVisible(false)
              }}
            >
              <i className="fas fa-cog" />
              Reconfigure
            </button>
          </div>

          <div id="ntfyStatus" className={`options_alert ${status ? '' : 'hidden'}`}>
            {status ? status.message : ''}
          </div>
        </form>
      </div>

      <div className="options_card mt-4" id="ntfyConfigSummary" style={{ display: showProviderConfig && hasConfigs ? 'block' : 'none' }}>
        <div className="card_header">
          <div className="notification_header">
            <h2>Configured Ntfy Services</h2>
          </div>
          <p className="card_subtitle">Your Ntfy configurations</p>
        </div>
        <div className="email_config_summary" id="ntfyConfigList">
          {configs.length === 0 ? (
            <div className="empty-state">No Ntfy configurations found. Click "Add Ntfy Configuration" to create one.</div>
          ) : (
            configs.map((config) => (
              <div className="email_config_row" data-id={config.id} id={`ntfy-config-${config.id}`} key={config.id}>
                <div className="email_config_info">
                  <div className="email_provider_info">
                    <i className="fas fa-globe" /> <span>{config.server_type === 'ntfy.sh' ? 'ntfy.sh' : config.server}</span>
                    {config.is_default ? (
                      <span className="default-badge">
                        <i className="fas fa-check-circle" /> Default
                      </span>
                    ) : null}
                  </div>
                  <div className="email_address_info">
                    <i className="fas fa-tag" /> <span>{config.topic || 'No topic configured'}</span>
                  </div>
                </div>
                <div className="email_config_actions">
                  <button type="button" className="options_btn options_btn_secondary" onClick={() => testNtfyConfig(config.id, activeTargetId)}>
                    <i className="fas fa-paper-plane" /> Test
                  </button>
                  <button type="button" className="options_btn options_btn_secondary" onClick={() => handleEditConfig(config.id)}>
                    <i className="fas fa-cog" /> Edit
                  </button>
                  <button
                    type="button"
                    className="options_btn options_btn_secondary"
                    onClick={() => {
                      if (window.confirm('Are you sure you want to delete this Ntfy configuration?')) {
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
                      id={`ntfy-default-${config.id}`}
                      onClick={() => setDefaultMutation.mutate(config.id)}
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
              <h2>Ntfy Provider Required</h2>
            </div>
            <p className="card_subtitle">
              Configure at least one Ntfy provider in the Provider tab before enabling Ntfy notifications.
            </p>
          </div>
        </div>
      ) : null}

      <div className="options_card mt-4" style={{ display: showNotifications && hasConfigs ? 'block' : 'none' }}>
        <div className="card_header">
          <div className="notification_header">
            <h2>Ntfy Notifications</h2>
          </div>
          <p className="card_subtitle">Configure which events should trigger Ntfy notifications</p>
        </div>
        <div id="options_ntfy_status" className={`options_alert ${optionsStatus ? '' : 'hidden'}`}>
          {optionsStatus ? optionsStatus.message : ''}
        </div>

        <LegacyNotificationGrid
          prefix="ntfy"
          selectClassName="options_ntfy_select"
          checkboxClassName="options_ntfy_checkbox"
          testClassName="options_ntfy_test"
          emptyOptionLabel="Select Ntfy config"
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
