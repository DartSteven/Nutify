/**
 * Notifysection.
 *
 * Frontend module used by Nutify React UI flows and state management.
 */

import { useMemo, useState } from 'react'

import { useAppStore } from '../../../store/appStore'
import { useMailSectionController } from './mail/useMailSectionController'
import { useNtfySectionController } from './ntfy/useNtfySectionController'
import { LEGACY_NOTIFICATION_EVENTS } from './shared/notificationEvents'
import { useTelegramSectionController } from './telegram/useTelegramSectionController'
import { useWebhookSectionController } from './webhook/useWebhookSectionController'

type SelectOption = {
  value: string
  label: string
}

type NotificationSelection = {
  enabled: boolean
  configId: string
}

export function NotifySection() {
  const activeTargetId = useAppStore((state) => state.activeTargetId)
  const targets = useAppStore((state) => state.targets)

  const mail = useMailSectionController()
  const ntfy = useNtfySectionController()
  const telegram = useTelegramSectionController()
  const webhook = useWebhookSectionController()
  const [testEventType, setTestEventType] = useState(LEGACY_NOTIFICATION_EVENTS[0]?.eventType ?? 'ONLINE')
  const [testChannel, setTestChannel] = useState<'mail' | 'ntfy' | 'telegram' | 'webhook'>('mail')

  const activeTargetName = useMemo(() => {
    const selected = targets.find((target) => Number(target.id) === Number(activeTargetId))
    if (selected?.name) {
      return selected.name
    }
    if (Number.isFinite(Number(activeTargetId)) && Number(activeTargetId) > 0) {
      return `Target #${activeTargetId}`
    }
    return 'active UPS target'
  }, [activeTargetId, targets])

  const validMailConfigs = useMemo(
    () => mail.configs.filter((config) => config.username.trim().length > 0),
    [mail.configs],
  )

  const mailOptions = useMemo<SelectOption[]>(
    () =>
      validMailConfigs.map((config) => {
        const providerLabel =
          mail.providers[config.provider]?.displayName
          || mail.providers[config.provider]?.note
          || config.provider
          || 'Mail'
        const destination = config.to_email || config.username || `Config #${config.id}`
        return {
          value: String(config.id),
          label: `${providerLabel} - ${destination}`,
        }
      }),
    [mail.providers, validMailConfigs],
  )

  const ntfyOptions = ntfy.configOptions
  const webhookOptions = webhook.configOptions

  const resolveSelection = (
    channel: 'mail' | 'ntfy' | 'telegram' | 'webhook',
    eventType: string,
  ): NotificationSelection => {
    if (channel === 'mail') {
      return (mail.selections[eventType] ?? { enabled: false, configId: '' }) as NotificationSelection
    }
    if (channel === 'ntfy') {
      return (ntfy.selections[eventType] ?? { enabled: false, configId: '' }) as NotificationSelection
    }
    if (channel === 'telegram') {
      return (telegram.selections[eventType] ?? { enabled: false, configId: '' }) as NotificationSelection
    }
    return (webhook.selections[eventType] ?? { enabled: false, configId: '' }) as NotificationSelection
  }

  const testSelection = resolveSelection(testChannel, testEventType)
  const canSendTest =
    testSelection.configId.trim().length > 0
    && Number.isFinite(Number(testSelection.configId))
  const isSendingTest =
    (testChannel === 'mail' && mail.testBusyEventType === testEventType)
    || (testChannel === 'ntfy' && ntfy.eventTestBusy === testEventType)
    || (testChannel === 'telegram' && telegram.eventTestBusy === testEventType)
    || (testChannel === 'webhook' && webhook.eventTestBusy === testEventType)

  const handleSendTest = async () => {
    if (testChannel === 'mail') {
      await mail.handleNotificationTest(testEventType)
      return
    }
    if (testChannel === 'ntfy') {
      await ntfy.handleEventTest(testEventType)
      return
    }
    if (testChannel === 'telegram') {
      await telegram.handleEventTest(testEventType)
      return
    }
    await webhook.handleEventTest(testEventType)
  }

  const renderChannelControl = (
    selection: NotificationSelection,
    options: SelectOption[],
    emptyLabel: string,
    onConfigChange: (nextConfigId: string) => void,
    onEnabledChange: (enabled: boolean) => void,
  ) => (
    <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
      <select
        className="options_input options_mail_select"
        style={{ minWidth: '170px' }}
        value={selection.configId || ''}
        onChange={(event) => onConfigChange(event.target.value)}
      >
        <option value="">{emptyLabel}</option>
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>

      <label style={{ display: 'inline-flex', alignItems: 'center', gap: '8px', margin: 0 }}>
        <input
          type="checkbox"
          checked={Boolean(selection.enabled)}
          disabled={!selection.configId}
          onChange={(event) => onEnabledChange(event.target.checked)}
        />
        <span>{selection.enabled ? 'On' : 'Off'}</span>
      </label>
    </div>
  )

  return (
    <>
      <div className="options_card">
        <div className="card_header">
          <div className="notification_header">
            <h2>Notify Routing</h2>
          </div>
          <p className="card_subtitle">
            Configure event routing for <strong>{activeTargetName}</strong>. Changes apply only to the UPS selected in TopBar.
          </p>
          <p className="card_subtitle">
            Provider configurations are managed in the <strong>Provider</strong> tab.
          </p>
        </div>
      </div>

      <div className="options_card mt-4">
        <div className="card_header">
          <div className="notification_header">
            <h2>Event Matrix</h2>
          </div>
          <p className="card_subtitle">
            For each event select a provider and enable the channel. Empty provider means channel disabled.
          </p>
        </div>

        <div className="users-table-wrapper">
          <div className="users-table">
            <table>
              <thead>
                <tr>
                  <th>Event</th>
                  <th>Mail</th>
                  <th>Ntfy</th>
                  <th>Telegram</th>
                  <th>Webhook</th>
                </tr>
              </thead>
              <tbody>
                {LEGACY_NOTIFICATION_EVENTS.map((eventMeta) => {
                  const mailSelection = (mail.selections[eventMeta.eventType] ?? {
                    enabled: false,
                    configId: '',
                  }) as NotificationSelection
                  const ntfySelection = (ntfy.selections[eventMeta.eventType] ?? {
                    enabled: false,
                    configId: '',
                  }) as NotificationSelection
                  const telegramSelection = (telegram.selections[eventMeta.eventType] ?? {
                    enabled: false,
                    configId: '',
                  }) as NotificationSelection
                  const webhookSelection = (webhook.selections[eventMeta.eventType] ?? {
                    enabled: false,
                    configId: '',
                  }) as NotificationSelection

                  return (
                    <tr key={eventMeta.eventType}>
                      <td>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                          <i className={`fas ${eventMeta.iconClass}`} />
                          <div>
                            <div>{eventMeta.title}</div>
                            <div className="card_subtitle" style={{ margin: 0 }}>
                              {eventMeta.eventType}
                            </div>
                          </div>
                        </div>
                      </td>
                      <td>
                        {renderChannelControl(
                          mailSelection,
                          mailOptions,
                          'Select mail config',
                          (nextConfigId) => mail.handleConfigSelect(eventMeta.eventType, nextConfigId),
                          (enabled) => mail.handleNotificationEnabledChange(eventMeta.eventType, enabled),
                        )}
                      </td>
                      <td>
                        {renderChannelControl(
                          ntfySelection,
                          ntfyOptions,
                          'Select Ntfy config',
                          (nextConfigId) => ntfy.handleConfigChange(eventMeta.eventType, nextConfigId),
                          (enabled) => ntfy.handleEnabledChange(eventMeta.eventType, enabled),
                        )}
                      </td>
                      <td>
                        {renderChannelControl(
                          telegramSelection,
                          telegram.configOptions,
                          'Select Telegram config',
                          (nextConfigId) => telegram.handleConfigChange(eventMeta.eventType, nextConfigId),
                          (enabled) => telegram.handleEnabledChange(eventMeta.eventType, enabled),
                        )}
                      </td>
                      <td>
                        {renderChannelControl(
                          webhookSelection,
                          webhookOptions,
                          'Select webhook',
                          (nextConfigId) => webhook.handleConfigChange(eventMeta.eventType, nextConfigId),
                          (enabled) => webhook.handleEnabledChange(eventMeta.eventType, enabled),
                        )}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </div>

        <div
          className="options_notification_card"
          style={{
            margin: '16px 8px 0',
            padding: '14px 16px',
            display: 'flex',
            alignItems: 'end',
            gap: '12px',
            flexWrap: 'nowrap',
            overflowX: 'auto',
          }}
        >
          <div className="options_nutify_title_container" style={{ minWidth: '180px' }}>
            <span className="options_nutify_title">Test Center</span>
            <span className="options_nutify_description">Single test action for selected event/channel.</span>
          </div>

          <div style={{ minWidth: '260px' }}>
            <label className="options_form_label" htmlFor="notify_test_event">
              Event
            </label>
            <select
              id="notify_test_event"
              className="options_input options_mail_select"
              value={testEventType}
              onChange={(event) => setTestEventType(event.target.value)}
            >
              {LEGACY_NOTIFICATION_EVENTS.map((eventMeta) => (
                <option key={eventMeta.eventType} value={eventMeta.eventType}>
                  {eventMeta.title}
                </option>
              ))}
            </select>
          </div>

          <div style={{ minWidth: '160px' }}>
            <label className="options_form_label" htmlFor="notify_test_channel">
              Channel
            </label>
            <select
              id="notify_test_channel"
              className="options_input options_mail_select"
              value={testChannel}
              onChange={(event) => setTestChannel(event.target.value as 'mail' | 'ntfy' | 'telegram' | 'webhook')}
            >
              <option value="mail">Mail</option>
              <option value="ntfy">Ntfy</option>
              <option value="telegram">Telegram</option>
              <option value="webhook">Webhook</option>
            </select>
          </div>

          <div style={{ minWidth: '170px' }}>
            <button
              type="button"
              className="options_btn options_btn_secondary"
              onClick={() => void handleSendTest()}
              disabled={!canSendTest || isSendingTest}
            >
              <i className="fas fa-paper-plane" /> {isSendingTest ? 'Sending...' : 'Send Test'}
            </button>
          </div>

          {!canSendTest ? (
            <p className="card_subtitle" style={{ marginBottom: 0, minWidth: '260px' }}>
              Select a provider in the matrix first.
            </p>
          ) : null}
        </div>

        {mail.optionsStatus ? (
          <div className={`options_alert ${mail.optionsStatus.tone === 'error' ? 'danger' : ''}`}>
            Mail: {mail.optionsStatus.message}
          </div>
        ) : null}
        {ntfy.optionsStatus ? (
          <div className={`options_alert ${ntfy.optionsStatus.tone === 'error' ? 'danger' : ''}`}>
            Ntfy: {ntfy.optionsStatus.message}
          </div>
        ) : null}
        {telegram.optionsStatus ? (
          <div className={`options_alert ${telegram.optionsStatus.tone === 'error' ? 'danger' : ''}`}>
            Telegram: {telegram.optionsStatus.message}
          </div>
        ) : null}
        {webhook.optionsStatus ? (
          <div className={`options_alert ${webhook.optionsStatus.tone === 'error' ? 'danger' : ''}`}>
            Webhook: {webhook.optionsStatus.message}
          </div>
        ) : null}
      </div>
    </>
  )
}
