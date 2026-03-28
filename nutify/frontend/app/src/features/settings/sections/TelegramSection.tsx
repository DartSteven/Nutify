/**
 * Telegramsection.
 *
 * Frontend module used by Nutify React UI flows and state management.
 */

import { testTelegramConfig } from '../../../lib/api/settings'
import { LegacyNotificationGrid } from './shared/LegacyNotificationGrid'
import { useTelegramSectionController } from './telegram/useTelegramSectionController'

type TelegramSectionProps = {
  showProviderConfig?: boolean
  showNotifications?: boolean
}

export function TelegramSection({
  showProviderConfig = true,
  showNotifications = true,
}: TelegramSectionProps = {}) {
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
    telegramMessageFormatOptions,
    saveMutation,
    deleteMutation,
    setDefaultMutation,
    handleAddConfig,
    handleEditConfig,
    handleTestForm,
    handleMessageFormatChange,
    handleConfigChange,
    handleEnabledChange,
    handleEventTest,
    setForm,
    setSaveVisible,
    setIsFormVisible,
    messageFormatLabel,
    defaults,
  } = useTelegramSectionController()

  const hasConfigs = configs.length > 0
  const showMissingProviderCard = showNotifications && !showProviderConfig && !hasConfigs

  return (
    <>
      <div
        className="options_card"
        id="addTelegramConfigContainer"
        style={{ display: showProviderConfig && !isFormVisible ? 'block' : 'none' }}
      >
        <div className="card_header">
          <div className="notification_header">
            <h2>Telegram Configuration</h2>
            <button type="button" id="addTelegramConfigBtn" className="options_btn" onClick={handleAddConfig}>
              <i className="fas fa-plus" /> Add Telegram Configuration
            </button>
          </div>
          <p className="card_subtitle">Configure Telegram bot notifications for UPS events</p>
        </div>
      </div>

      <div
        className="options_card"
        id="telegramConfigFormCard"
        style={{ display: showProviderConfig && isFormVisible ? 'block' : 'none' }}
      >
        <div className="ntfy-form-header">
          <h2>Telegram Configuration</h2>
        </div>
        <p className="ntfy-form-description">Configure Telegram bot token and chat destination</p>

        <form id="telegramConfigForm" onSubmit={(event) => event.preventDefault()}>
          <input type="hidden" id="telegram_config_id" name="telegram_config_id" value={form.id ?? ''} readOnly />

          <div className="ntfy-form-row">
            <div className="ntfy-form-field">
              <div className="ntfy-form-field-inner">
                <i className="fas fa-tag" />
                <label htmlFor="telegram_name">Name</label>
                <input
                  type="text"
                  id="telegram_name"
                  name="telegram_name"
                  placeholder="Telegram"
                  value={form.name}
                  onChange={(event) => setForm((prev) => ({ ...prev, name: event.target.value }))}
                  required
                />
              </div>
            </div>
            <div className="ntfy-form-field">
              <div className="ntfy-form-field-inner">
                <i className="fas fa-key" />
                <label htmlFor="telegram_bot_token">Bot Token</label>
                <input
                  type="password"
                  id="telegram_bot_token"
                  name="telegram_bot_token"
                  placeholder="123456789:ABCDEF..."
                  value={form.botToken}
                  onChange={(event) => setForm((prev) => ({ ...prev, botToken: event.target.value }))}
                  autoComplete="new-password"
                  required
                />
              </div>
            </div>
          </div>

          <div className="ntfy-form-row">
            <div className="ntfy-form-field">
              <div className="ntfy-form-field-inner">
                <i className="fas fa-hashtag" />
                <label htmlFor="telegram_chat_id">Chat ID</label>
                <input
                  type="text"
                  id="telegram_chat_id"
                  name="telegram_chat_id"
                  placeholder="-1001234567890 or user chat id"
                  value={form.chatId}
                  onChange={(event) => setForm((prev) => ({ ...prev, chatId: event.target.value }))}
                  required
                />
              </div>
            </div>
            <div className="ntfy-form-field checkbox-field">
              <div className="ntfy-form-field-inner checkbox">
                <i className="fas fa-globe" />
                <label>
                  <input
                    type="checkbox"
                    id="telegram_disable_web_preview"
                    name="telegram_disable_web_preview"
                    checked={form.disableWebPreview}
                    onChange={(event) => setForm((prev) => ({ ...prev, disableWebPreview: event.target.checked }))}
                  />
                  <span>Disable web preview</span>
                </label>
              </div>
            </div>
            <div className="ntfy-form-field">
              <div className="ntfy-form-field-inner">
                <i className="fas fa-palette" />
                <label htmlFor="telegram_message_format">Message Format</label>
                <select
                  id="telegram_message_format"
                  name="telegram_message_format"
                  value={form.messageFormat}
                  onChange={(event) => handleMessageFormatChange(event.target.value)}
                >
                  {telegramMessageFormatOptions.map((option) => (
                    <option key={`telegram-format-${option.value}`} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </div>
            </div>
          </div>

          <div className="ntfy-info-container">
            <i className="fas fa-info-circle" />
            <span>
              Create a bot with
              {' '}
              <code>@BotFather</code>
              {' '}
              and use your chat ID as destination. Use the Test button before saving.
            </span>
          </div>

          <div className="ntfy-actions">
            <button type="button" id="testTelegramBtn" className="options_btn options_btn_secondary" onClick={handleTestForm}>
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
              id="saveTelegramConfigBtn"
              className="options_btn"
              style={{ display: saveVisible ? 'inline-flex' : 'none' }}
              onClick={() => saveMutation.mutate()}
              disabled={saveMutation.isPending}
            >
              <i className="fas fa-save" /> Save Configuration
            </button>
            <button
              type="button"
              id="cancelTelegramConfigBtn"
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

          <div id="telegramStatus" className={`options_alert ${status ? '' : 'hidden'}`}>
            {status ? status.message : ''}
          </div>
        </form>
      </div>

      <div
        className="options_card mt-4"
        id="telegramConfigSummary"
        style={{ display: showProviderConfig && hasConfigs ? 'block' : 'none' }}
      >
        <div className="card_header">
          <div className="notification_header">
            <h2>Configured Telegram Bots</h2>
          </div>
          <p className="card_subtitle">Your Telegram notification services</p>
        </div>
        <div className="email_config_summary" id="telegramConfigList">
          {configs.length === 0 ? (
            <div className="empty-state">No Telegram configurations found. Click "Add Telegram Configuration" to create one.</div>
          ) : (
            configs.map((config) => (
              <div className="email_config_row" data-id={config.id} id={`telegram-config-${config.id}`} key={config.id}>
                <div className="email_config_info">
                  <div className="email_provider_info">
                    <i className="fab fa-telegram-plane" /> <span>{config.display_name}</span>
                    {config.is_default ? (
                      <span className="default-badge">
                        <i className="fas fa-check-circle" /> Default
                      </span>
                    ) : null}
                  </div>
                  <div className="email_address_info">
                    <i className="fas fa-comment-dots" /> <span>{messageFormatLabel(config.render_mode, config.parse_mode)}</span>
                  </div>
                </div>
                <div className="email_config_actions">
                  <button type="button" className="options_btn options_btn_secondary" onClick={() => testTelegramConfig(config.id, activeTargetId)}>
                    <i className="fas fa-paper-plane" /> Test
                  </button>
                  <button type="button" className="options_btn options_btn_secondary" onClick={() => handleEditConfig(config.id)}>
                    <i className="fas fa-cog" /> Edit
                  </button>
                  <button
                    type="button"
                    className="options_btn options_btn_secondary"
                    onClick={() => {
                      if (window.confirm('Are you sure you want to delete this Telegram configuration?')) {
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
              <h2>Telegram Provider Required</h2>
            </div>
            <p className="card_subtitle">
              Configure at least one Telegram provider in the Provider tab before enabling Telegram notifications.
            </p>
          </div>
        </div>
      ) : null}

      <div className="options_card mt-4" style={{ display: showNotifications && hasConfigs ? 'block' : 'none' }}>
        <div className="card_header">
          <div className="notification_header">
            <h2>Telegram Notifications</h2>
          </div>
          <p className="card_subtitle">Configure which events should trigger Telegram notifications</p>
        </div>
        <div id="options_telegram_status" className={`options_alert ${optionsStatus ? '' : 'hidden'}`}>
          {optionsStatus ? optionsStatus.message : ''}
        </div>

        <LegacyNotificationGrid
          prefix="telegram"
          selectClassName="options_ntfy_select"
          checkboxClassName="options_ntfy_checkbox"
          testClassName="options_ntfy_test"
          emptyOptionLabel="Select Telegram config"
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
