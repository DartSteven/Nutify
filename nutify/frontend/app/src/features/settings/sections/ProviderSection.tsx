/**
 * Providersection.
 *
 * Frontend module used by Nutify React UI flows and state management.
 */

import { useState } from 'react'

import { MailSection } from './MailSection'
import { NtfySection } from './NtfySection'
import { TelegramSection } from './TelegramSection'
import { WebhookSection } from './WebhookSection'

type ProviderTabId = 'mail' | 'ntfy' | 'telegram' | 'webhook'

type ProviderTab = {
  id: ProviderTabId
  label: string
  icon: string
}

const PROVIDER_TABS: ProviderTab[] = [
  {
    id: 'mail',
    label: 'Mail',
    icon: 'fa-envelope',
  },
  {
    id: 'ntfy',
    label: 'Ntfy',
    icon: 'fa-bell',
  },
  {
    id: 'telegram',
    label: 'Telegram',
    icon: 'fa-paper-plane',
  },
  {
    id: 'webhook',
    label: 'Webhook',
    icon: 'fa-link',
  },
]

export function ProviderSection() {
  const [activeProvider, setActiveProvider] = useState<ProviderTabId>('mail')

  return (
    <>
      <div className="options_tabs provider_tabs_card">
        <div className="provider_tabs_buttons">
          {PROVIDER_TABS.map((tab) => (
            <button
              key={tab.id}
              type="button"
              className={['options_tab_button', activeProvider === tab.id ? 'active' : ''].join(' ').trim()}
              onClick={() => setActiveProvider(tab.id)}
            >
              <i className={`fas ${tab.icon}`} aria-hidden="true" />
              <span>{tab.label}</span>
            </button>
          ))}
        </div>
        <p className="provider_tabs_hint">
          Configure one provider type at a time.
        </p>
      </div>

      {activeProvider === 'mail' ? <MailSection showNotificationsPanel={false} showReportPanel={false} /> : null}
      {activeProvider === 'ntfy' ? <NtfySection showNotifications={false} /> : null}
      {activeProvider === 'telegram' ? <TelegramSection showNotifications={false} /> : null}
      {activeProvider === 'webhook' ? <WebhookSection showNotifications={false} /> : null}
    </>
  )
}
