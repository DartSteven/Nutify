/**
 * Usetelegramsectioncontroller.
 *
 * Frontend module used by Nutify React UI flows and state management.
 */

import { useEffect, useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import {
  deleteTelegramConfig,
  getTelegramConfig,
  getTelegramConfigs,
  getTelegramNotificationSettings,
  saveTelegramConfig,
  saveTelegramNotificationSetting,
  setTelegramDefaultConfig,
  testTelegramConfigEvent,
  testTelegramRawConfig,
} from '../../../../lib/api/settings'
import { useAppStore } from '../../../../store/appStore'
import type { LegacyNotificationSelection } from '../shared/LegacyNotificationGrid'
import { LEGACY_NOTIFICATION_EVENTS } from '../shared/notificationEvents'

type AlertTone = 'success' | 'error'

type StatusAlert = {
  tone: AlertTone
  message: string
} | null

type TelegramConfig = {
  id: number
  display_name: string
  parse_mode: string
  disable_web_preview: boolean
  render_mode: string
  is_default: boolean
}

type TelegramFormState = {
  id: number | null
  name: string
  botToken: string
  chatId: string
  messageFormat: string
  parseMode: string
  disableWebPreview: boolean
  renderMode: string
  isDefault: boolean
}

type TelegramMessageFormat = {
  value: string
  label: string
  renderMode: string
  parseMode: string
}

const TELEGRAM_MESSAGE_FORMATS: TelegramMessageFormat[] = [
  { value: 'graphic_html', label: 'Graphic Card (HTML)', renderMode: 'graphic', parseMode: 'HTML' },
  { value: 'text_plain', label: 'Text (Plain)', renderMode: 'text', parseMode: 'NONE' },
  { value: 'text_markdown', label: 'Text (Markdown)', renderMode: 'text', parseMode: 'MARKDOWN' },
  { value: 'text_markdownv2', label: 'Text (MarkdownV2)', renderMode: 'text', parseMode: 'MARKDOWNV2' },
]

function normalizeRenderMode(value: unknown): string {
  return String(value || '').trim().toLowerCase() === 'text' ? 'text' : 'graphic'
}

function normalizeParseMode(value: unknown): string {
  const parseMode = String(value || '').trim().toUpperCase()
  if (parseMode === 'MARKDOWN' || parseMode === 'MARKDOWNV2' || parseMode === 'NONE') {
    return parseMode
  }
  return 'HTML'
}

function buildMessageFormatValue(renderMode: unknown, parseMode: unknown): string {
  const normalizedRenderMode = normalizeRenderMode(renderMode)
  const normalizedParseMode = normalizeParseMode(parseMode)
  if (normalizedRenderMode === 'graphic') {
    return 'graphic_html'
  }
  const match = TELEGRAM_MESSAGE_FORMATS.find(
    (option) => option.renderMode === normalizedRenderMode && option.parseMode === normalizedParseMode,
  )
  return match ? match.value : 'text_plain'
}

function resolveMessageFormat(value: string): TelegramMessageFormat {
  const match = TELEGRAM_MESSAGE_FORMATS.find((option) => option.value === value)
  return match || TELEGRAM_MESSAGE_FORMATS[0]
}

function messageFormatLabel(renderMode: unknown, parseMode: unknown): string {
  const value = buildMessageFormatValue(renderMode, parseMode)
  const option = resolveMessageFormat(value)
  return option.label
}

const DEFAULT_FORM: TelegramFormState = {
  id: null,
  name: 'Telegram',
  botToken: '',
  chatId: '',
  messageFormat: 'graphic_html',
  parseMode: 'HTML',
  disableWebPreview: false,
  renderMode: 'graphic',
  isDefault: false,
}

function normalizeConfigs(payload: unknown): TelegramConfig[] {
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
        display_name: String(entry.display_name ?? entry.name ?? 'Telegram'),
        parse_mode: String(entry.parse_mode ?? 'HTML'),
        disable_web_preview: Boolean(entry.disable_web_preview),
        render_mode: String(entry.render_mode ?? 'graphic'),
        is_default: Boolean(entry.is_default),
      } satisfies TelegramConfig
    })
    .filter((row): row is TelegramConfig => row !== null)
}

function parseNotificationSelections(payload: unknown): Record<string, LegacyNotificationSelection> {
  const selections: Record<string, LegacyNotificationSelection> = {}
  LEGACY_NOTIFICATION_EVENTS.forEach((eventMeta) => {
    selections[eventMeta.eventType] = { enabled: false, configId: '' }
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

function buildConfigFormValue(config: Record<string, unknown>): TelegramFormState {
  const renderMode = normalizeRenderMode(config.render_mode)
  const parseMode = normalizeParseMode(config.parse_mode)
  const messageFormat = buildMessageFormatValue(renderMode, parseMode)
  return {
    id: Number(config.id),
    name: String(config.display_name ?? config.name ?? 'Telegram'),
    botToken: String(config.bot_token ?? ''),
    chatId: String(config.chat_id ?? ''),
    messageFormat,
    parseMode,
    disableWebPreview: Boolean(config.disable_web_preview),
    renderMode,
    isDefault: Boolean(config.is_default),
  }
}

function asConfigOptions(configs: TelegramConfig[]) {
  return configs.map((config) => {
    const suffix = config.is_default ? ' (Default)' : ''
    return {
      value: String(config.id),
      label: `${config.display_name}${suffix}`,
    }
  })
}

export function useTelegramSectionController() {
  const queryClient = useQueryClient()
  const activeTargetId = useAppStore((state) => state.activeTargetId)

  const [status, setStatus] = useState<StatusAlert>(null)
  const [optionsStatus, setOptionsStatus] = useState<StatusAlert>(null)
  const [isFormVisible, setIsFormVisible] = useState(false)
  const [form, setForm] = useState<TelegramFormState>(DEFAULT_FORM)
  const [saveVisible, setSaveVisible] = useState(false)
  const [eventTestBusy, setEventTestBusy] = useState<string | null>(null)
  const [formTestBusy, setFormTestBusy] = useState(false)
  const [selections, setSelections] = useState<Record<string, LegacyNotificationSelection>>(() =>
    parseNotificationSelections(null),
  )

  const configsQuery = useQuery({
    queryKey: ['settings', 'telegram', activeTargetId],
    queryFn: () => getTelegramConfigs(activeTargetId),
  })
  const settingsQuery = useQuery({
    queryKey: ['settings', 'telegram-notification', activeTargetId],
    queryFn: () => getTelegramNotificationSettings(activeTargetId),
  })

  const configs = useMemo(() => normalizeConfigs(configsQuery.data), [configsQuery.data])
  const configOptions = useMemo(() => asConfigOptions(configs), [configs])

  const telegramMessageFormatOptions = useMemo(
    () => TELEGRAM_MESSAGE_FORMATS.map((option) => ({ value: option.value, label: option.label })),
    [],
  )

  useEffect(() => {
    const parsed = parseNotificationSelections(settingsQuery.data)
    setSelections(parsed)
  }, [settingsQuery.data])

  const refreshAll = async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ['settings', 'telegram', activeTargetId] }),
      queryClient.invalidateQueries({ queryKey: ['settings', 'telegram-notification', activeTargetId] }),
    ])
  }

  const saveMutation = useMutation({
    mutationFn: () =>
      saveTelegramConfig(
        {
          id: form.id ?? undefined,
          name: form.name,
          bot_token: form.botToken,
          chat_id: form.chatId,
          parse_mode: form.parseMode,
          disable_web_preview: form.disableWebPreview,
          render_mode: form.renderMode,
          is_default: form.isDefault,
        },
        activeTargetId,
      ),
    onSuccess: async () => {
      setStatus({ tone: 'success', message: 'Telegram configuration saved successfully' })
      setForm(DEFAULT_FORM)
      setSaveVisible(false)
      setIsFormVisible(false)
      await refreshAll()
    },
    onError: (error: unknown) => {
      const message = error instanceof Error ? error.message : 'Failed to save Telegram configuration'
      setStatus({ tone: 'error', message })
    },
  })

  const deleteMutation = useMutation({
    mutationFn: (configId: number) => deleteTelegramConfig(configId, activeTargetId),
    onSuccess: async () => {
      setStatus({ tone: 'success', message: 'Telegram configuration deleted successfully' })
      await refreshAll()
    },
    onError: (error: unknown) => {
      const message = error instanceof Error ? error.message : 'Failed to delete Telegram configuration'
      setStatus({ tone: 'error', message })
    },
  })

  const setDefaultMutation = useMutation({
    mutationFn: (configId: number) => setTelegramDefaultConfig(configId, activeTargetId),
    onSuccess: async () => {
      setStatus({ tone: 'success', message: 'Default Telegram configuration updated' })
      await refreshAll()
    },
    onError: (error: unknown) => {
      const message = error instanceof Error ? error.message : 'Failed to update default Telegram configuration'
      setStatus({ tone: 'error', message })
    },
  })

  const notificationMutation = useMutation({
    mutationFn: (input: { eventType: string; enabled: boolean; configId: string }) =>
      {
        const parsedConfigId = Number(input.configId)
        const normalizedConfigId = Number.isFinite(parsedConfigId) && parsedConfigId > 0 ? parsedConfigId : null
        return saveTelegramNotificationSetting(
          {
            event_type: input.eventType,
            enabled: input.enabled,
            config_id: normalizedConfigId,
          },
          activeTargetId,
        )
      },
    onSuccess: async (_, variables) => {
      if (variables.enabled) {
        setOptionsStatus({
          tone: 'success',
          message: `Telegram notifications for ${variables.eventType} events enabled`,
        })
      } else {
        setOptionsStatus(null)
      }
      await queryClient.invalidateQueries({ queryKey: ['settings', 'telegram-notification', activeTargetId] })
    },
    onError: (error: unknown) => {
      const message = error instanceof Error ? error.message : 'Failed to update Telegram notification setting'
      setOptionsStatus({ tone: 'error', message })
    },
  })

  const handleAddConfig = () => {
    setForm(DEFAULT_FORM)
    setSaveVisible(false)
    setStatus(null)
    setIsFormVisible(true)
  }

  const handleMessageFormatChange = (value: string) => {
    const option = resolveMessageFormat(value)
    setForm((prev) => ({
      ...prev,
      messageFormat: option.value,
      renderMode: option.renderMode,
      parseMode: option.parseMode,
    }))
  }

  const handleEditConfig = async (configId: number) => {
    try {
      const payload = await getTelegramConfig(configId, activeTargetId)
      const row = (payload as { config?: unknown }).config
      if (!row || typeof row !== 'object') {
        setStatus({ tone: 'error', message: 'Configuration not found' })
        return
      }
      setForm(buildConfigFormValue(row as Record<string, unknown>))
      setSaveVisible(true)
      setIsFormVisible(true)
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Failed to load configuration'
      setStatus({ tone: 'error', message })
    }
  }

  const handleTestForm = async () => {
    if (!form.botToken.trim()) {
      setStatus({ tone: 'error', message: 'Please enter a bot token' })
      return
    }
    if (!form.chatId.trim()) {
      setStatus({ tone: 'error', message: 'Please enter a chat ID' })
      return
    }

    try {
      setFormTestBusy(true)
      const payload = await testTelegramRawConfig(
        {
          name: form.name,
          bot_token: form.botToken,
          chat_id: form.chatId,
          parse_mode: form.parseMode,
          disable_web_preview: form.disableWebPreview,
          render_mode: form.renderMode,
          test: true,
        },
        activeTargetId,
      )
      if (payload.success) {
        setStatus({ tone: 'success', message: 'Test notification sent successfully' })
        setSaveVisible(true)
      } else {
        const message = typeof payload.message === 'string' ? payload.message : 'Failed to send test notification'
        setStatus({ tone: 'error', message })
        setSaveVisible(false)
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Failed to send test notification'
      setStatus({ tone: 'error', message })
      setSaveVisible(false)
    } finally {
      setFormTestBusy(false)
    }
  }

  const handleConfigChange = (eventType: string, configId: string) => {
    const parsedConfigId = Number(configId)
    const hasValidConfig = Number.isFinite(parsedConfigId) && parsedConfigId > 0
    const normalizedConfigId = hasValidConfig ? String(parsedConfigId) : ''
    setSelections((prev) => {
      const next = { ...prev }
      next[eventType] = {
        enabled: hasValidConfig,
        configId: normalizedConfigId,
      }
      return next
    })
    notificationMutation.mutate({ eventType, enabled: hasValidConfig, configId: normalizedConfigId })
  }

  const handleEnabledChange = (eventType: string, enabled: boolean) => {
    const current = selections[eventType] ?? { enabled: false, configId: '' }
    const parsedConfigId = Number(current.configId)
    const hasValidConfig = Number.isFinite(parsedConfigId) && parsedConfigId > 0
    if (enabled && !hasValidConfig) {
      setOptionsStatus({ tone: 'error', message: 'Please select a Telegram configuration first' })
      return
    }
    const nextConfigId = enabled ? String(parsedConfigId) : ''
    setSelections((prev) => {
      const next = { ...prev }
      next[eventType] = { enabled, configId: nextConfigId }
      return next
    })
    notificationMutation.mutate({ eventType, enabled, configId: nextConfigId })
  }

  const handleEventTest = async (eventType: string) => {
    const current = selections[eventType]
    const parsedConfigId = Number(current?.configId)
    const hasValidConfig = Number.isFinite(parsedConfigId) && parsedConfigId > 0
    if (!hasValidConfig) {
      setOptionsStatus({ tone: 'error', message: 'Please select a Telegram configuration first' })
      return
    }
    try {
      setEventTestBusy(eventType)
      const payload = await testTelegramConfigEvent(parsedConfigId, eventType, activeTargetId)
      if (payload.success) {
        setOptionsStatus({ tone: 'success', message: `Test notification for ${eventType} sent successfully` })
      } else {
        const message = typeof payload.message === 'string' ? payload.message : 'Failed to send test notification'
        setOptionsStatus({ tone: 'error', message })
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Failed to send test notification'
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
    defaults: {
      form: DEFAULT_FORM,
    },
    messageFormatLabel,
  }
}
