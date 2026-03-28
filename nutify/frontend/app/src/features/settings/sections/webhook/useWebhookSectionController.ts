/**
 * Usewebhooksectioncontroller.
 *
 * Frontend module used by Nutify React UI flows and state management.
 */

import { useEffect, useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import {
  deleteWebhookConfig,
  getWebhookConfig,
  getWebhookConfigs,
  getWebhookNotificationSettings,
  saveWebhookConfig,
  saveWebhookNotificationSetting,
  setWebhookDefaultConfig,
  testWebhookConfigEvent,
  testWebhookRawConfig,
  updateWebhookConfig,
} from '../../../../lib/api/settings'
import { useAppStore } from '../../../../store/appStore'
import type { LegacyNotificationSelection } from '../shared/LegacyNotificationGrid'
import { LEGACY_NOTIFICATION_EVENTS } from '../shared/notificationEvents'

type AlertTone = 'success' | 'error'

type StatusAlert = {
  tone: AlertTone
  message: string
} | null

type WebhookConfig = {
  id: number
  name: string
  url: string
  server_type: string
  content_type: string
  auth_type: string
  auth_username: string
  render_mode: string
  include_ups_data: boolean
  verify_ssl: boolean
  is_default: boolean
  custom_headers: string
}

type WebhookFormState = {
  id: number | null
  serverType: string
  name: string
  url: string
  contentType: string
  includeUpsData: boolean
  verifySsl: boolean
  authType: string
  authUsername: string
  authPassword: string
  authToken: string
  renderMode: string
  customHeaders: string
  isDefault: boolean
}

const DEFAULT_FORM: WebhookFormState = {
  id: null,
  serverType: 'custom',
  name: 'My Webhook',
  url: '',
  contentType: 'application/json',
  includeUpsData: true,
  verifySsl: true,
  authType: 'none',
  authUsername: '',
  authPassword: '',
  authToken: '',
  renderMode: 'graphic',
  customHeaders: '{"X-Api-Key": "your-api-key", "X-Custom-Header": "value"}',
  isDefault: false,
}

function normalizeConfigs(payload: unknown): WebhookConfig[] {
  if (!payload || typeof payload !== 'object') {
    return []
  }
  const rows = (payload as { configs?: unknown }).configs
  if (!Array.isArray(rows)) {
    return []
  }
  return rows
    .map((row) => {
      if (!row || typeof row !== 'object') {
        return null
      }
      const entry = row as Record<string, unknown>
      const id = Number(entry.id)
      if (!Number.isFinite(id)) {
        return null
      }
      return {
        id,
        name: String(entry.name ?? entry.display_name ?? 'Webhook'),
        url: String(entry.url ?? ''),
        server_type: String(entry.server_type ?? 'custom'),
        content_type: String(entry.content_type ?? 'application/json'),
        auth_type: String(entry.auth_type ?? 'none'),
        auth_username: String(entry.auth_username ?? ''),
        render_mode: String(entry.render_mode ?? 'graphic'),
        include_ups_data: Boolean(entry.include_ups_data),
        verify_ssl: Boolean(entry.verify_ssl),
        is_default: Boolean(entry.is_default),
        custom_headers: String(entry.custom_headers ?? ''),
      } satisfies WebhookConfig
    })
    .filter((row): row is WebhookConfig => row !== null)
}

function buildFormFromConfig(config: WebhookConfig): WebhookFormState {
  return {
    id: config.id,
    serverType: config.server_type || 'custom',
    name: config.name || 'Webhook',
    url: config.url || '',
    contentType: config.content_type || 'application/json',
    includeUpsData: Boolean(config.include_ups_data),
    verifySsl: Boolean(config.verify_ssl),
    authType: config.auth_type || 'none',
    authUsername: config.auth_username || '',
    authPassword: '',
    authToken: '',
    renderMode: config.render_mode || 'graphic',
    customHeaders: config.custom_headers || '',
    isDefault: Boolean(config.is_default),
  }
}

function parseNotificationSelections(payload: unknown): Record<string, LegacyNotificationSelection> {
  const selections: Record<string, LegacyNotificationSelection> = {}
  LEGACY_NOTIFICATION_EVENTS.forEach((eventMeta) => {
    selections[eventMeta.eventType] = {
      enabled: false,
      configId: '',
    }
  })

  if (!payload || typeof payload !== 'object') {
    return selections
  }

  const settings = (payload as { settings?: unknown }).settings
  if (!settings || typeof settings !== 'object') {
    return selections
  }

  Object.entries(settings as Record<string, unknown>).forEach(([eventType, raw]) => {
    if (!raw || typeof raw !== 'object') {
      return
    }
    const row = raw as Record<string, unknown>
    selections[eventType.toUpperCase()] = {
      enabled: Boolean(row.enabled),
      configId: String(row.config_id ?? ''),
    }
  })

  return selections
}

function webhookOptionLabel(config: WebhookConfig): string {
  return config.name || `Webhook #${config.id}`
}

export function useWebhookSectionController() {
  const queryClient = useQueryClient()
  const activeTargetId = useAppStore((state) => state.activeTargetId)

  const [status, setStatus] = useState<StatusAlert>(null)
  const [optionsStatus, setOptionsStatus] = useState<StatusAlert>(null)
  const [isFormVisible, setIsFormVisible] = useState(false)
  const [saveVisible, setSaveVisible] = useState(false)
  const [formTestBusy, setFormTestBusy] = useState(false)
  const [eventTestBusy, setEventTestBusy] = useState<string | null>(null)
  const [form, setForm] = useState<WebhookFormState>(DEFAULT_FORM)
  const [selections, setSelections] = useState<Record<string, LegacyNotificationSelection>>({})

  const configsQuery = useQuery({
    queryKey: ['settings', 'webhook', activeTargetId],
    queryFn: () => getWebhookConfigs(activeTargetId),
  })
  const settingsQuery = useQuery({
    queryKey: ['settings', 'webhook-notification', activeTargetId],
    queryFn: () => getWebhookNotificationSettings(activeTargetId),
  })

  const configs = useMemo(() => normalizeConfigs(configsQuery.data), [configsQuery.data])
  const configOptions = useMemo(
    () => configs.map((config) => ({ value: String(config.id), label: webhookOptionLabel(config) })),
    [configs],
  )

  useEffect(() => {
    setSelections(parseNotificationSelections(settingsQuery.data))
  }, [settingsQuery.data])

  const refreshConfigs = async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ['settings', 'webhook', activeTargetId] }),
      queryClient.invalidateQueries({ queryKey: ['settings', 'webhook-notification', activeTargetId] }),
    ])
  }

  const saveMutation = useMutation({
    mutationFn: () => {
      const payload = {
        id: form.id ?? undefined,
        server_type: form.serverType,
        name: form.name,
        url: form.url,
        content_type: form.contentType,
        auth_type: form.authType,
        auth_username: form.authUsername,
        auth_password: form.authPassword,
        auth_token: form.authToken,
        render_mode: form.renderMode,
        include_ups_data: form.includeUpsData,
        verify_ssl: form.verifySsl,
        custom_headers: form.customHeaders,
        is_default: form.isDefault,
      }
      if (form.id) {
        return updateWebhookConfig(form.id, payload, activeTargetId)
      }
      return saveWebhookConfig(payload, activeTargetId)
    },
    onSuccess: async () => {
      setStatus({ tone: 'success', message: 'Webhook configuration saved successfully' })
      setIsFormVisible(false)
      setSaveVisible(false)
      setForm(DEFAULT_FORM)
      await refreshConfigs()
    },
    onError: (error: unknown) => {
      const message = error instanceof Error ? error.message : 'Failed to save webhook configuration'
      setStatus({ tone: 'error', message })
    },
  })

  const deleteMutation = useMutation({
    mutationFn: (configId: number) => deleteWebhookConfig(configId, activeTargetId),
    onSuccess: async () => {
      setStatus({ tone: 'success', message: 'Webhook configuration deleted successfully' })
      await refreshConfigs()
    },
    onError: (error: unknown) => {
      const message = error instanceof Error ? error.message : 'Failed to delete webhook configuration'
      setStatus({ tone: 'error', message })
    },
  })

  const defaultMutation = useMutation({
    mutationFn: (configId: number) => setWebhookDefaultConfig(configId, activeTargetId),
    onSuccess: async () => {
      setStatus({ tone: 'success', message: 'Default webhook configuration updated successfully' })
      await refreshConfigs()
    },
    onError: (error: unknown) => {
      const message = error instanceof Error ? error.message : 'Failed to update default webhook configuration'
      setStatus({ tone: 'error', message })
    },
  })

  const handleServerTypeChange = (serverType: string) => {
    setForm((prev) => {
      if (serverType === 'discord') {
        return {
          ...prev,
          serverType,
          contentType: 'application/json',
          authType: 'none',
          customHeaders:
            '{"X-Title":"UPS Alert","X-Content":"UPS notification from Nutify","X-Username":"Nutify UPS Monitor"}',
        }
      }
      return { ...prev, serverType }
    })
  }

  const handleAddConfig = () => {
    setForm(DEFAULT_FORM)
    setIsFormVisible(true)
    setSaveVisible(false)
    setStatus(null)
  }

  const handleEditConfig = async (configId: number) => {
    try {
      const payload = await getWebhookConfig(configId, activeTargetId)
      const row = (payload as { config?: unknown }).config
      if (!row || typeof row !== 'object') {
        setStatus({ tone: 'error', message: 'Configuration not found' })
        return
      }
      const config = normalizeConfigs({ configs: [row] })[0]
      if (!config) {
        setStatus({ tone: 'error', message: 'Configuration not found' })
        return
      }
      setForm(buildFormFromConfig(config))
      setSaveVisible(true)
      setIsFormVisible(true)
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Failed to load webhook configuration'
      setStatus({ tone: 'error', message })
    }
  }

  const handleTestForm = async () => {
    if (!form.url.trim()) {
      setStatus({ tone: 'error', message: 'Please enter a webhook URL' })
      return
    }
    try {
      setFormTestBusy(true)
      const payload = await testWebhookRawConfig(
        {
          server_type: form.serverType,
          name: form.name,
          url: form.url,
          content_type: form.contentType,
          auth_type: form.authType,
          auth_username: form.authUsername,
          auth_password: form.authPassword,
          auth_token: form.authToken,
          render_mode: form.renderMode,
          include_ups_data: form.includeUpsData,
          verify_ssl: form.verifySsl,
          custom_headers: form.customHeaders,
        },
        activeTargetId,
      )
      if (payload.success) {
        setStatus({ tone: 'success', message: 'Test webhook sent successfully' })
        setSaveVisible(true)
      } else {
        const message = typeof payload.message === 'string' ? payload.message : 'Failed to send test webhook'
        setStatus({ tone: 'error', message })
        setSaveVisible(false)
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Failed to send test webhook'
      setStatus({ tone: 'error', message })
      setSaveVisible(false)
    } finally {
      setFormTestBusy(false)
    }
  }

  const updateEventFlag = async (eventType: string, enabled: boolean, configId: string) => {
    const parsedConfigId = Number(configId)
    const selectedConfigId = Number.isFinite(parsedConfigId) && parsedConfigId > 0 ? parsedConfigId : null
    try {
      await saveWebhookNotificationSetting(
        {
          event_type: eventType,
          enabled,
          config_id: selectedConfigId,
        },
        activeTargetId,
      )
      await queryClient.invalidateQueries({ queryKey: ['settings', 'webhook-notification', activeTargetId] })
      if (enabled) {
        setOptionsStatus({ tone: 'success', message: `Webhook notifications for ${eventType} events enabled` })
      } else {
        setOptionsStatus(null)
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Failed to update webhook notification setting'
      setOptionsStatus({ tone: 'error', message })
    }
  }

  const handleConfigChange = (eventType: string, configId: string) => {
    const parsedConfigId = Number(configId)
    const hasValidConfig = Number.isFinite(parsedConfigId) && parsedConfigId > 0
    const normalizedConfigId = hasValidConfig ? String(parsedConfigId) : ''
    setSelections((prev) => {
      const next = { ...prev }
      next[eventType] = { enabled: hasValidConfig, configId: normalizedConfigId }
      return next
    })
    updateEventFlag(eventType, hasValidConfig, normalizedConfigId)
  }

  const handleEnabledChange = (eventType: string, enabled: boolean) => {
    const current = selections[eventType] ?? { enabled: false, configId: '' }
    const parsedConfigId = Number(current.configId)
    const hasValidConfig = Number.isFinite(parsedConfigId) && parsedConfigId > 0
    if (enabled && !hasValidConfig) {
      setOptionsStatus({ tone: 'error', message: 'Please select a webhook configuration first' })
      return
    }
    const nextConfigId = enabled ? String(parsedConfigId) : ''
    setSelections((prev) => {
      const next = { ...prev }
      next[eventType] = { enabled, configId: nextConfigId }
      return next
    })
    updateEventFlag(eventType, enabled, nextConfigId)
  }

  const handleEventTest = async (eventType: string) => {
    const current = selections[eventType]
    const parsedConfigId = Number(current?.configId)
    const hasValidConfig = Number.isFinite(parsedConfigId) && parsedConfigId > 0
    if (!hasValidConfig) {
      setOptionsStatus({ tone: 'error', message: 'Please select a webhook configuration first' })
      return
    }
    try {
      setEventTestBusy(eventType)
      const payload = await testWebhookConfigEvent(parsedConfigId, eventType, activeTargetId)
      if (payload.success) {
        setOptionsStatus({ tone: 'success', message: `Test webhook for ${eventType} sent successfully` })
      } else {
        const message = typeof payload.message === 'string' ? payload.message : 'Failed to send test webhook'
        setOptionsStatus({ tone: 'error', message })
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Failed to send test webhook'
      setOptionsStatus({ tone: 'error', message })
    } finally {
      setEventTestBusy(null)
    }
  }

  return {
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
    defaults: {
      form: DEFAULT_FORM,
    },
  }
}
