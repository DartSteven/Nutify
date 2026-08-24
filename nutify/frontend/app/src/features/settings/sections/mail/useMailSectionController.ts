/** Mail settings section controller for providers, notifications, and report scheduling. */

import { useEffect, useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  createReportSchedule,
  deleteReportSchedule,
  getMailConfigs,
  getMailProviders,
  getNotificationSettings,
  getReportSchedules,
  saveMailConfig,
  testEmailNotification,
  testMailRawConfig,
  testReportSchedule,
  updateMailConfig,
  updateMailConfigEnabled,
  updateNotificationSetting,
  updateReportSchedule,
} from '../../../../lib/api/settings'
import { useAppStore } from '../../../../store/appStore'
import { DEFAULT_MAIL_FORM, DEFAULT_SCHEDULE_FORM } from './constants'
import type { MailFormState, ScheduleFormState, StatusAlert } from './types'
import {
  createDefaultReportSettings,
  fillScheduleForm,
  normalizeMailConfigs,
  normalizeNotificationSelections,
  normalizeProviderMap,
  normalizeSchedules,
  notifyUser,
  toggleListNumber,
  toggleListString,
} from './utils'
import { validateSaveSchedule, validateSendReportNow, validateTestSchedule } from './validators'
import { deleteMailConfigById, editMailConfigById } from './configHandlers'

export function useMailSectionController() {
  const queryClient = useQueryClient()
  const activeTargetId = useAppStore((state) => state.activeTargetId)
  const [status, setStatus] = useState<StatusAlert>(null)
  const [optionsStatus, setOptionsStatus] = useState<StatusAlert>(null)
  const [reportStatus, setReportStatus] = useState<StatusAlert>(null)
  const [scheduleStatus, setScheduleStatus] = useState<StatusAlert>(null)
  const [form, setForm] = useState<MailFormState>(DEFAULT_MAIL_FORM)
  const [isFormVisible, setIsFormVisible] = useState(false)
  const [saveVisible, setSaveVisible] = useState(false)
  const [testBusyEventType, setTestBusyEventType] = useState<string | null>(null)
  const [reportSettings, setReportSettings] = useState(createDefaultReportSettings)
  const [isScheduleModalOpen, setIsScheduleModalOpen] = useState(false)
  const [scheduleForm, setScheduleForm] = useState<ScheduleFormState>(DEFAULT_SCHEDULE_FORM)
  const [scheduleModalError, setScheduleModalError] = useState('')
  const providersQuery = useQuery({
    queryKey: ['settings', 'mail', 'providers', activeTargetId],
    queryFn: () => getMailProviders(activeTargetId),
  })
  const configsQuery = useQuery({
    queryKey: ['settings', 'mail', activeTargetId],
    queryFn: () => getMailConfigs(activeTargetId),
  })
  const notificationsQuery = useQuery({
    queryKey: ['settings', 'mail', 'notifications', activeTargetId],
    queryFn: () => getNotificationSettings(activeTargetId),
  })
  const schedulesQuery = useQuery({
    queryKey: ['settings', 'mail', 'schedules', activeTargetId],
    queryFn: () => getReportSchedules(activeTargetId),
  })
  const providers = useMemo(() => normalizeProviderMap(providersQuery.data), [providersQuery.data])
  const configs = useMemo(() => normalizeMailConfigs(configsQuery.data), [configsQuery.data])
  const schedules = useMemo(() => normalizeSchedules(schedulesQuery.data), [schedulesQuery.data])
  const [selections, setSelections] = useState(() => normalizeNotificationSelections(null))
  useEffect(() => {
    setSelections(normalizeNotificationSelections(notificationsQuery.data))
  }, [notificationsQuery.data])
  useEffect(() => {
    const storedMailConfigId = window.localStorage.getItem('report_email_id') || ''
    if (!storedMailConfigId) return
    if (configs.some((config) => String(config.id) === storedMailConfigId)) {
      setReportSettings((prev) => ({ ...prev, mailConfigId: storedMailConfigId }))
    }
  }, [configs])

  const refreshMailArea = async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ['settings', 'mail', activeTargetId] }),
      queryClient.invalidateQueries({ queryKey: ['settings', 'mail', 'notifications', activeTargetId] }),
      queryClient.invalidateQueries({ queryKey: ['settings', 'mail', 'schedules', activeTargetId] }),
    ])
  }
  const saveMutation = useMutation({
    mutationFn: async () => {
      const providerValue = form.provider || form.customProviderName.trim()
      if (!providerValue && form.customProviderName.trim()) throw new Error('Custom provider name is required')
      const payload: Record<string, unknown> = {
        smtp_server: form.smtpServer.trim(),
        smtp_port: Number(form.smtpPort),
        smtp_username: form.username.trim(),
        smtp_password: form.password,
        provider: providerValue,
        email_provider: providerValue,
        use_tls: form.useTls,
        use_starttls: form.useStarttls,
        from_email: form.fromEmail.trim(),
        to_email: form.toEmail.trim(),
        render_mode: form.renderMode,
        enabled: true,
      }
      if (form.id) return updateMailConfig(form.id, payload, activeTargetId)
      return saveMailConfig(payload, activeTargetId)
    },
    onSuccess: async () => {
      setStatus({ tone: 'success', message: 'Email configuration saved successfully' })
      notifyUser('Email configuration saved successfully', 'success')
      setIsFormVisible(false)
      setSaveVisible(false)
      setForm(DEFAULT_MAIL_FORM)
      await refreshMailArea()
    },
    onError: (error: unknown) => {
      const message = error instanceof Error ? error.message : 'Error saving email configuration'
      setStatus({ tone: 'error', message })
      notifyUser(message, 'error')
    },
  })
  const formTestMutation = useMutation({
    mutationFn: async () => {
      const providerValue = form.provider || form.customProviderName.trim()
      return testMailRawConfig(
        {
          id: form.id,
          smtp_server: form.smtpServer.trim(),
          smtp_port: Number(form.smtpPort),
          smtp_username: form.username.trim(),
          smtp_password: form.password,
          provider: providerValue,
          email_provider: providerValue,
          use_tls: form.useTls,
          use_starttls: form.useStarttls,
          from_email: form.fromEmail.trim(),
          to_email: form.toEmail.trim() || form.fromEmail.trim() || form.username.trim(),
          render_mode: form.renderMode,
        },
        activeTargetId,
      )
    },
    onSuccess: (payload) => {
      if (payload.success) {
        setStatus({ tone: 'success', message: 'Test email sent successfully' })
        setSaveVisible(true)
        notifyUser('Test email sent successfully', 'success')
      } else {
        const message = typeof payload.message === 'string' ? payload.message : 'Failed to send test email'
        setStatus({ tone: 'error', message })
        setSaveVisible(false)
        notifyUser(message, 'error')
      }
    },
    onError: (error: unknown) => {
      const message = error instanceof Error ? error.message : 'Failed to send test email'
      setStatus({ tone: 'error', message })
      setSaveVisible(false)
      notifyUser(message, 'error')
    },
  })
  const toggleEnabledMutation = useMutation({
    mutationFn: (input: { configId: number; enabled: boolean }) =>
      updateMailConfigEnabled(input.configId, input.enabled, activeTargetId),
    onSuccess: async (_, variables) => {
      setStatus({ tone: 'success', message: `Configuration ${variables.enabled ? 'enabled' : 'disabled'} successfully` })
      await refreshMailArea()
    },
    onError: (error: unknown) => {
      const message = error instanceof Error ? error.message : 'Failed to update configuration status'
      setStatus({ tone: 'error', message })
    },
  })
  const notificationMutation = useMutation({
    mutationFn: (input: { eventType: string; enabled: boolean; idEmail: number | null }) =>
      updateNotificationSetting(input.eventType, input.enabled, input.idEmail, activeTargetId),
    onSuccess: async (_, variables) => {
      if (variables.enabled) {
        setOptionsStatus({ tone: 'success', message: `Email for ${variables.eventType} notifications set` })
      } else {
        setOptionsStatus(null)
      }
      await queryClient.invalidateQueries({ queryKey: ['settings', 'mail', 'notifications', activeTargetId] })
    },
    onError: (error: unknown) => {
      const message = error instanceof Error ? error.message : 'Failed to update notification setting'
      setOptionsStatus({ tone: 'error', message })
    },
  })
  const sendReportNowMutation = useMutation({
    mutationFn: () =>
      testReportSchedule({
        reports: reportSettings.selectedReports,
        period_type: reportSettings.periodType,
        from_date: reportSettings.periodType === 'range' ? reportSettings.fromDate : undefined,
        to_date: reportSettings.periodType === 'range' ? reportSettings.toDate : undefined,
        mail_config_id: Number(reportSettings.mailConfigId),
      }, activeTargetId),
    onSuccess: (payload) => {
      if (payload.success) {
        setReportStatus({ tone: 'success', message: 'Report sent successfully' })
        notifyUser('Report sent successfully', 'success')
      } else {
        const message = typeof payload.message === 'string' ? payload.message : 'Failed to send report'
        setReportStatus({ tone: 'error', message })
        notifyUser(message, 'error')
      }
    },
    onError: (error: unknown) => {
      const message = error instanceof Error ? error.message : 'Failed to send report'
      setReportStatus({ tone: 'error', message })
      notifyUser(message, 'error')
    },
  })
  const saveScheduleMutation = useMutation({
    mutationFn: async () => {
      const payload = {
        days: [...scheduleForm.selectedDays],
        time: scheduleForm.time,
        reports: [...scheduleForm.reports],
        period_type: scheduleForm.periodType,
        enabled: true,
        mail_config_id: Number(scheduleForm.mailConfigId),
        from_date: scheduleForm.periodType === 'range' ? scheduleForm.rangeFromDate : undefined,
        to_date: scheduleForm.periodType === 'range' ? scheduleForm.rangeToDate : undefined,
      }
      if (scheduleForm.editId) return updateReportSchedule(scheduleForm.editId, payload, activeTargetId)
      return createReportSchedule(payload, activeTargetId)
    },
    onSuccess: async () => {
      setScheduleStatus({ tone: 'success', message: 'Schedule saved successfully' })
      notifyUser('Schedule saved successfully', 'success')
      setIsScheduleModalOpen(false)
      setScheduleForm(DEFAULT_SCHEDULE_FORM)
      setScheduleModalError('')
      await queryClient.invalidateQueries({ queryKey: ['settings', 'mail', 'schedules', activeTargetId] })
    },
    onError: (error: unknown) => {
      const message = error instanceof Error ? error.message : 'Error saving schedule'
      setScheduleModalError(message)
    },
  })
  const testScheduleMutation = useMutation({
    mutationFn: () =>
      testReportSchedule({
        reports: [...scheduleForm.reports],
        period_type: scheduleForm.periodType,
        mail_config_id: Number(scheduleForm.mailConfigId),
        from_date: scheduleForm.periodType === 'range' ? scheduleForm.rangeFromDate : undefined,
        to_date: scheduleForm.periodType === 'range' ? scheduleForm.rangeToDate : undefined,
      }, activeTargetId),
    onSuccess: (payload) => {
      if (payload.success) {
        setScheduleStatus({ tone: 'success', message: 'Test reports sent successfully' })
        notifyUser('Test reports sent successfully', 'success')
      } else {
        const message = typeof payload.message === 'string' ? payload.message : 'Error sending test reports'
        setScheduleModalError(message)
      }
    },
    onError: (error: unknown) => {
      const message = error instanceof Error ? error.message : 'Error sending test reports'
      setScheduleModalError(message)
    },
  })
  const updateScheduleEnabledMutation = useMutation({
    mutationFn: (input: { scheduleId: number; enabled: boolean }) =>
      updateReportSchedule(input.scheduleId, { enabled: input.enabled }, activeTargetId),
    onSuccess: async (_, variables) => {
      setScheduleStatus({ tone: 'success', message: `Schedule ${variables.enabled ? 'enabled' : 'disabled'} successfully` })
      await queryClient.invalidateQueries({ queryKey: ['settings', 'mail', 'schedules', activeTargetId] })
    },
    onError: () => setScheduleStatus({ tone: 'error', message: 'Error updating schedule status' }),
  })

  const deleteScheduleMutation = useMutation({
    mutationFn: (scheduleId: number) => deleteReportSchedule(scheduleId, activeTargetId),
    onSuccess: async () => {
      setScheduleStatus({ tone: 'success', message: 'Schedule deleted successfully' })
      await queryClient.invalidateQueries({ queryKey: ['settings', 'mail', 'schedules', activeTargetId] })
    },
    onError: (error: unknown) => {
      const message = error instanceof Error ? error.message : 'Error deleting schedule'
      setScheduleStatus({ tone: 'error', message })
    },
  })

  const handleProviderChange = (provider: string) => {
    const providerInfo = providers[provider]
    setForm((prev) => ({
      ...prev,
      provider,
      smtpServer: providerInfo?.smtp_server ? String(providerInfo.smtp_server) : prev.smtpServer,
      smtpPort: providerInfo?.smtp_port ? String(providerInfo.smtp_port) : prev.smtpPort,
      useTls: providerInfo?.tls ?? prev.useTls,
      useStarttls: providerInfo?.tls_starttls ?? prev.useStarttls,
      fromEmail: providerInfo?.requires_sender_email ? prev.fromEmail : '',
      customProviderName: provider ? '' : prev.customProviderName,
    }))
  }
  const handleShowAddForm = () => {
    setForm(DEFAULT_MAIL_FORM)
    setSaveVisible(false)
    setStatus(null)
    setIsFormVisible(true)
  }
  const handleEditConfig = async (configId: number) => {
    try {
      await editMailConfigById({
        configId,
        activeTargetId,
        providers,
        setForm,
        setSaveVisible,
        setIsFormVisible,
        setStatus,
      })
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Failed to load configuration'
      setStatus({ tone: 'error', message })
    }
  }
  const handleDeleteConfig = async (configId: number) => {
    if (!window.confirm('Are you sure you want to delete this email configuration?')) {
      return
    }
    try {
      await deleteMailConfigById({ configId, activeTargetId, refreshMailArea, setStatus })
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Failed to delete email configuration'
      setStatus({ tone: 'error', message })
      notifyUser(message, 'error')
    }
  }
  const handleConfigSelect = (eventType: string, configId: string) => {
    const parsedConfigId = Number(configId)
    const validConfigId = Number.isFinite(parsedConfigId) && parsedConfigId > 0
    if (!validConfigId) {
      setSelections((prev) => ({ ...prev, [eventType]: { enabled: false, configId: '' } }))
      notificationMutation.mutate({ eventType, enabled: false, idEmail: null })
      return
    }
    const normalizedConfigId = String(parsedConfigId)
    setSelections((prev) => ({ ...prev, [eventType]: { enabled: true, configId: normalizedConfigId } }))
    notificationMutation.mutate({ eventType, enabled: true, idEmail: parsedConfigId })
  }
  const handleNotificationEnabledChange = (eventType: string, enabled: boolean) => {
    const current = selections[eventType] ?? { enabled: false, configId: '' }
    const parsedConfigId = Number(current.configId)
    const hasValidConfig = Number.isFinite(parsedConfigId) && parsedConfigId > 0
    if (enabled && !hasValidConfig) {
      setOptionsStatus({ tone: 'error', message: 'Please select an email configuration first' })
      return
    }
    if (!enabled) {
      setSelections((prev) => ({ ...prev, [eventType]: { enabled: false, configId: '' } }))
      notificationMutation.mutate({ eventType, enabled: false, idEmail: null })
      return
    }
    setSelections((prev) => ({ ...prev, [eventType]: { enabled: true, configId: String(parsedConfigId) } }))
    notificationMutation.mutate({ eventType, enabled: true, idEmail: parsedConfigId })
  }
  const handleNotificationTest = async (eventType: string) => {
    const selected = selections[eventType]
    const parsedConfigId = Number(selected?.configId)
    const hasValidConfig = Number.isFinite(parsedConfigId) && parsedConfigId > 0
    if (!hasValidConfig) {
      setOptionsStatus({ tone: 'error', message: 'Please select an email configuration first' })
      return
    }
    try {
      setTestBusyEventType(eventType)
      const payload = await testEmailNotification(eventType, parsedConfigId, activeTargetId)
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
      setTestBusyEventType(null)
    }
  }
  const handleSendReportNow = () => {
    const validationError = validateSendReportNow(reportSettings)
    if (validationError) {
      setReportStatus({ tone: 'error', message: validationError })
      return
    }
    window.localStorage.setItem('report_email_id', reportSettings.mailConfigId)
    sendReportNowMutation.mutate()
  }
  const handleOpenAddSchedule = () => {
    setScheduleForm(DEFAULT_SCHEDULE_FORM)
    setScheduleModalError('')
    setIsScheduleModalOpen(true)
  }
  const handleEditSchedule = (scheduleId: number) => {
    const schedule = schedules.find((item) => item.id === scheduleId)
    if (!schedule) {
      setScheduleStatus({ tone: 'error', message: 'Schedule not found' })
      return
    }
    setScheduleForm(fillScheduleForm(schedule))
    setScheduleModalError('')
    setIsScheduleModalOpen(true)
  }
  const handleSaveSchedule = () => {
    const validationError = validateSaveSchedule(scheduleForm)
    if (validationError) {
      setScheduleModalError(validationError)
      return
    }
    setScheduleModalError('')
    saveScheduleMutation.mutate()
  }
  const handleTestSchedule = () => {
    const validationError = validateTestSchedule(scheduleForm)
    if (validationError) {
      setScheduleModalError(validationError)
      return
    }
    setScheduleModalError('')
    testScheduleMutation.mutate()
  }
  return {
    providers,
    configs,
    selections,
    schedules,
    form,
    reportSettings,
    scheduleForm,
    isFormVisible,
    saveVisible,
    isScheduleModalOpen,
    status,
    optionsStatus,
    reportStatus,
    scheduleStatus,
    scheduleModalError,
    testBusyEventType,
    saveMutation,
    formTestMutation,
    sendReportNowMutation,
    saveScheduleMutation,
    testScheduleMutation,
    handleProviderChange,
    handleShowAddForm,
    handleEditConfig,
    handleDeleteConfig,
    handleConfigSelect,
    handleNotificationEnabledChange,
    handleNotificationTest,
    handleSendReportNow,
    handleOpenAddSchedule,
    handleEditSchedule,
    handleSaveSchedule,
    handleTestSchedule,
    setForm,
    setSaveVisible,
    setIsFormVisible,
    setReportSettings,
    setIsScheduleModalOpen,
    setScheduleModalError,
    setScheduleForm,
    toggleEnabledMutation,
    updateScheduleEnabledMutation,
    deleteScheduleMutation,
    toggleListString,
    toggleListNumber,
    defaults: {
      mailForm: DEFAULT_MAIL_FORM,
      scheduleForm: DEFAULT_SCHEDULE_FORM,
    },
  }
}
