/**
 * Mailnotificationspanel.
 *
 * Frontend module used by Nutify React UI flows and state management.
 */

import { LegacyNotificationGrid, type LegacyNotificationSelection } from '../shared/LegacyNotificationGrid'
import type { MailConfigRow, ProviderMap, StatusAlert } from './types'
import { emailOptionLabel } from './utils'

type MailNotificationsPanelProps = {
  configs: MailConfigRow[]
  providers: ProviderMap
  selections: Record<string, LegacyNotificationSelection>
  testBusyEventType: string | null
  status: StatusAlert
  onConfigChange: (eventType: string, configId: string) => void
  onEnabledChange: (eventType: string, enabled: boolean) => void
  onTest: (eventType: string) => void
}

export function MailNotificationsPanel(props: MailNotificationsPanelProps) {
  const {
    configs,
    providers,
    selections,
    testBusyEventType,
    status,
    onConfigChange,
    onEnabledChange,
    onTest,
  } = props

  const configOptions = configs.map((config) => ({
    value: String(config.id),
    label: emailOptionLabel(config, providers),
  }))

  return (
    <div id="notification_settings_section" className="options_card">
      <div className="card_header">
        <div className="notification_header">
          <h2>Email Notifications</h2>
        </div>
        <p className="card_subtitle">Configure which events should trigger email notifications</p>
      </div>
      <div id="options_nutify_status" className={`options_alert ${status ? '' : 'hidden'}`}>
        {status?.message || ''}
      </div>
      <LegacyNotificationGrid
        prefix="notify"
        selectClassName="options_email_select"
        checkboxClassName="options_nutify_checkbox"
        testClassName="options_nutify_test"
        emptyOptionLabel="Select email"
        configOptions={configOptions}
        selections={selections}
        testBusyEventType={testBusyEventType}
        onConfigChange={onConfigChange}
        onEnabledChange={onEnabledChange}
        onTest={onTest}
      />
    </div>
  )
}
