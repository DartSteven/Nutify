/**
 * Usentfysectioncontroller.
 *
 * Frontend module used by Nutify React UI flows and state management.
 */

import { useEffect, useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import {
  deleteNtfyConfig,
  getNtfyConfig,
  getNtfyConfigs,
  getNtfyNotificationSettings,
  saveNtfyConfig,
  saveNtfyNotificationSetting,
  setNtfyDefaultConfig,
  testNtfyConfigEvent,
  testNtfyRawConfig,
} from '../../../../lib/api/settings'
import { useAppStore } from '../../../../store/appStore'
import type { LegacyNotificationSelection } from '../shared/LegacyNotificationGrid'
import { LEGACY_NOTIFICATION_EVENTS } from '../shared/notificationEvents'

type AlertTone = 'success' | 'error'

type StatusAlert = {
  tone: AlertTone
  message: string
} | null

type NtfyConfig = {
  id: number
  server_type: string
  server: string
  topic: string
  use_auth: boolean
  username: string
  priority: number
  use_tags: boolean
  render_mode: string
  is_default: boolean
}

type NtfyFormState = {
  id: number | null
  serverType: string
  customServer: string
  topic: string
  useAuth: boolean
  username: string
  password: string
  priority: string
  useTags: boolean
  renderMode: string
  isDefault: boolean
}

const DEFAULT_FORM: NtfyFormState = {
  id: null,
  serverType: 'ntfy.sh',
  customServer: '',
  topic: '',
  useAuth: false,
  username: '',
  password: '',
  priority: '3',
  useTags: true,
  renderMode: 'graphic',
  isDefault: false,
}

function normalizeConfigs(payload: unknown): NtfyConfig[] {
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
        server_type: String(entry.server_type ?? 'ntfy.sh'),
        server: String(entry.server ?? 'https://ntfy.sh'),
        topic: String(entry.topic ?? ''),
        use_auth: Boolean(entry.use_auth),
        username: String(entry.username ?? ''),
        priority: Number(entry.priority ?? 3),
        use_tags: Boolean(entry.use_tags),
        render_mode: String(entry.render_mode ?? 'graphic'),
        is_default: Boolean(entry.is_default),
      } satisfies NtfyConfig
    })
    .filter((row): row is NtfyConfig => row !== null)
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

function buildConfigFormValue(config: NtfyConfig): NtfyFormState {
  return {
    id: config.id,
    serverType: config.server_type || 'ntfy.sh',
    customServer: config.server_type === 'custom' ? config.server : '',
    topic: config.topic || '',
    useAuth: Boolean(config.use_auth),
    username: config.username || '',
    password: '',
    priority: String(config.priority || 3),
    useTags: Boolean(config.use_tags),
    renderMode: config.render_mode || 'graphic',
    isDefault: Boolean(config.is_default),
  }
}

function asConfigOptions(configs: NtfyConfig[]) {
  return configs.map((config) => {
    const serverDisplay = config.server_type === 'ntfy.sh' ? 'ntfy.sh' : config.server
    const suffix = config.is_default ? ' (Default)' : ''
    return {
      value: String(config.id),
      label: `${serverDisplay} - ${config.topic}${suffix}`,
    }
  })
}

export function useNtfySectionController() {
  const queryClient = useQueryClient()
  const activeTargetId = useAppStore((state) => state.activeTargetId)

  const [status, setStatus] = useState<StatusAlert>(null)
  const [optionsStatus, setOptionsStatus] = useState<StatusAlert>(null)
  const [isFormVisible, setIsFormVisible] = useState(false)
  const [form, setForm] = useState<NtfyFormState>(DEFAULT_FORM)
  const [saveVisible, setSaveVisible] = useState(false)
  const [eventTestBusy, setEventTestBusy] = useState<string | null>(null)
  const [formTestBusy, setFormTestBusy] = useState(false)
  const [selections, setSelections] = useState<Record<string, LegacyNotificationSelection>>(() =>
    parseNotificationSelections(null),
  )

  const configsQuery = useQuery({
    queryKey: ['settings', 'ntfy', activeTargetId],
    queryFn: () => getNtfyConfigs(activeTargetId),
  })
  const settingsQuery = useQuery({
    queryKey: ['settings', 'ntfy-notification', activeTargetId],
    queryFn: () => getNtfyNotificationSettings(activeTargetId),
  })

  const configs = useMemo(() => normalizeConfigs(configsQuery.data), [configsQuery.data])
  const configOptions = useMemo(() => asConfigOptions(configs), [configs])

  useEffect(() => {
    const parsed = parseNotificationSelections(settingsQuery.data)
    setSelections(parsed)
  }, [settingsQuery.data])

  const refreshAll = async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ['settings', 'ntfy', activeTargetId] }),
      queryClient.invalidateQueries({ queryKey: ['settings', 'ntfy-notification', activeTargetId] }),
    ])
  }

  const saveMutation = useMutation({
    mutationFn: () =>
      saveNtfyConfig(
        {
          id: form.id ?? undefined,
          server_type: form.serverType,
          server: form.serverType === 'ntfy.sh' ? 'https://ntfy.sh' : form.customServer,
          topic: form.topic,
          use_auth: form.useAuth,
          username: form.username,
          password: form.password,
          priority: Number(form.priority || '3'),
          use_tags: form.useTags,
          render_mode: form.renderMode,
          is_default: form.isDefault,
        },
        activeTargetId,
      ),
    onSuccess: async () => {
      setStatus({ tone: 'success', message: 'Ntfy configuration saved successfully' })
      setForm(DEFAULT_FORM)
      setSaveVisible(false)
      setIsFormVisible(false)
      await refreshAll()
    },
    onError: (error: unknown) => {
      const message = error instanceof Error ? error.message : 'Failed to save Ntfy configuration'
      setStatus({ tone: 'error', message })
    },
  })

  const deleteMutation = useMutation({
    mutationFn: (configId: number) => deleteNtfyConfig(configId, activeTargetId),
    onSuccess: async () => {
      setStatus({ tone: 'success', message: 'Ntfy configuration deleted successfully' })
      await refreshAll()
    },
    onError: (error: unknown) => {
      const message = error instanceof Error ? error.message : 'Failed to delete Ntfy configuration'
      setStatus({ tone: 'error', message })
    },
  })

  const setDefaultMutation = useMutation({
    mutationFn: (configId: number) => setNtfyDefaultConfig(configId, activeTargetId),
    onSuccess: async () => {
      setStatus({ tone: 'success', message: 'Default Ntfy configuration updated' })
      await refreshAll()
    },
    onError: (error: unknown) => {
      const message = error instanceof Error ? error.message : 'Failed to update default Ntfy configuration'
      setStatus({ tone: 'error', message })
    },
  })

  const notificationMutation = useMutation({
    mutationFn: (input: { eventType: string; enabled: boolean; configId: string }) =>
      {
        const parsedConfigId = Number(input.configId)
        const normalizedConfigId = Number.isFinite(parsedConfigId) && parsedConfigId > 0 ? parsedConfigId : null
        return saveNtfyNotificationSetting(
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
          message: `Ntfy notifications for ${variables.eventType} events enabled`,
        })
      } else {
        setOptionsStatus(null)
      }
      await queryClient.invalidateQueries({ queryKey: ['settings', 'ntfy-notification', activeTargetId] })
    },
    onError: (error: unknown) => {
      const message = error instanceof Error ? error.message : 'Failed to update Ntfy notification setting'
      setOptionsStatus({ tone: 'error', message })
    },
  })

  const handleAddConfig = () => {
    setForm(DEFAULT_FORM)
    setSaveVisible(false)
    setStatus(null)
    setIsFormVisible(true)
  }

  const handleEditConfig = async (configId: number) => {
    try {
      const payload = await getNtfyConfig(configId, activeTargetId)
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
      setForm(buildConfigFormValue(config))
      setSaveVisible(true)
      setIsFormVisible(true)
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Failed to load configuration'
      setStatus({ tone: 'error', message })
    }
  }

  const handleTestForm = async () => {
    if (!form.topic.trim()) {
      setStatus({ tone: 'error', message: 'Please enter a topic name' })
      return
    }
    if (form.serverType === 'custom' && !form.customServer.trim()) {
      setStatus({ tone: 'error', message: 'Please enter a server URL' })
      return
    }

    try {
      setFormTestBusy(true)
      const payload = await testNtfyRawConfig(
        {
          server_type: form.serverType,
          server: form.serverType === 'ntfy.sh' ? 'https://ntfy.sh' : form.customServer,
          topic: form.topic,
          use_auth: form.useAuth,
          username: form.username,
          password: form.password,
          priority: Number(form.priority || '3'),
          use_tags: form.useTags,
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
      setOptionsStatus({ tone: 'error', message: 'Please select a Ntfy configuration first' })
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
      setOptionsStatus({ tone: 'error', message: 'Please select a Ntfy configuration first' })
      return
    }
    try {
      setEventTestBusy(eventType)
      const payload = await testNtfyConfigEvent(parsedConfigId, eventType, activeTargetId)
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
    defaults: {
      form: DEFAULT_FORM,
    },
  }
}
