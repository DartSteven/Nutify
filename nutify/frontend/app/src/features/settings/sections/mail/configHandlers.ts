/**
 * Confighandlers.
 *
 * Frontend module used by Nutify React UI flows and state management.
 */

import type { Dispatch, SetStateAction } from 'react'

import { deleteMailConfig, getMailConfigById } from '../../../../lib/api/settings'
import type { MailFormState, ProviderMap, StatusAlert } from './types'
import { normalizeMailConfigs, notifyUser } from './utils'

type SetStatus = (status: StatusAlert) => void

export async function editMailConfigById(input: {
  configId: number
  activeTargetId: number | null
  providers: ProviderMap
  setForm: Dispatch<SetStateAction<MailFormState>>
  setSaveVisible: (value: boolean) => void
  setIsFormVisible: (value: boolean) => void
  setStatus: SetStatus
}): Promise<void> {
  const payload = await getMailConfigById(input.configId, input.activeTargetId)
  const config = normalizeMailConfigs({ data: [(payload as { config?: unknown }).config || {}] })[0]
  if (!config) {
    input.setStatus({ tone: 'error', message: 'Configuration not found' })
    return
  }

  input.setForm(() => ({
    id: config.id,
    provider: config.provider || '',
    customProviderName: config.provider && input.providers[config.provider] ? '' : config.provider || '',
    smtpServer: config.smtp_server || '',
    smtpPort: config.smtp_port || '',
    username: config.username || '',
    password: '',
    fromEmail: config.from_email || '',
    toEmail: config.to_email || '',
    renderMode: config.render_mode || 'graphic',
    useTls: Boolean(config.tls),
    useStarttls: Boolean(config.tls_starttls),
  }))

  input.setSaveVisible(true)
  input.setIsFormVisible(true)
}

export async function deleteMailConfigById(input: {
  configId: number
  activeTargetId: number | null
  refreshMailArea: () => Promise<void>
  setStatus: SetStatus
}): Promise<void> {
  await deleteMailConfig(input.configId, input.activeTargetId)
  input.setStatus({ tone: 'success', message: 'Email configuration deleted successfully' })
  notifyUser('Email configuration deleted successfully', 'success')
  await input.refreshMailArea()
}
