/**
 * Reportspage.
 *
 * Frontend module used by Nutify React UI flows and state management.
 */

import { useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'

import { PageHeader } from '../../components/PageHeader'
import {
  createReportSchedule,
  deleteReportSchedule,
  generateReport,
  listReportSchedules,
  sendReport,
  testReportSchedule,
  type SaveScheduleInput,
} from '../../lib/api/reports'
import { getMailConfigs } from '../../lib/api/settings'
import { useAppStore } from '../../store/appStore'
import { resolveRollingPeriod } from '../../lib/utils/reportPeriods'

type ScheduleRow = {
  id: number
  time: string
  days: string
  reports: string
  period_type: string
  enabled: boolean
  mail_config_id: number | null
}

const REPORT_OPTIONS = ['energy', 'power', 'battery', 'voltage', 'events', 'ups_info']
const REPORT_TYPE_OPTIONS = [
  { value: 'custom', label: 'Custom' },
  { value: 'yesterday', label: 'Yesterday' },
  { value: 'last_week', label: 'Last 7 Days' },
  { value: 'last_month', label: 'Last 30 Days' },
  { value: 'last_year', label: 'Last 12 Months' },
  { value: 'daily', label: 'Daily' },
  { value: 'weekly', label: 'Weekly' },
  { value: 'monthly', label: 'Monthly' },
]
const SCHEDULE_PERIOD_OPTIONS = [
  { value: 'yesterday', label: 'Yesterday' },
  { value: 'last_week', label: 'Last 7 Days' },
  { value: 'last_month', label: 'Last 30 Days' },
  { value: 'last_year', label: 'Last 12 Months' },
  { value: 'weekly', label: 'Weekly' },
  { value: 'monthly', label: 'Monthly' },
  { value: 'range', label: 'Range' },
]

function todayIsoDate() {
  return new Date().toISOString().slice(0, 10)
}

function dateInputValue(value: Date) {
  const year = value.getFullYear()
  const month = String(value.getMonth() + 1).padStart(2, '0')
  const day = String(value.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

function rangeForPreset(preset: string): { from: string; to: string } | null {
  const now = new Date()

  if (preset === 'yesterday') {
    const yesterday = new Date(now.getFullYear(), now.getMonth(), now.getDate() - 1)
    return { from: dateInputValue(yesterday), to: dateInputValue(yesterday) }
  }

  if (preset === 'last_week' || preset === 'last_month' || preset === 'last_year') {
    return resolveRollingPeriod(preset, now)
  }

  return null
}

function asScheduleRows(payload: unknown): ScheduleRow[] {
  if (!payload || typeof payload !== 'object' || Array.isArray(payload)) {
    return []
  }
  const body = payload as Record<string, unknown>
  const data = Array.isArray(body.data) ? body.data : []
  return data.map((item) => {
    const row = item as Record<string, unknown>
    return {
      id: Number(row.id ?? 0),
      time: String(row.time ?? ''),
      days: String(row.days ?? '*'),
      reports: String(row.reports ?? ''),
      period_type: String(row.period_type ?? 'yesterday'),
      enabled: Boolean(row.enabled),
      mail_config_id: Number.isFinite(Number(row.mail_config_id)) ? Number(row.mail_config_id) : null,
    }
  })
}

export function ReportsPage() {
  const activeTargetId = useAppStore((state) => state.activeTargetId)

  const [fromDate, setFromDate] = useState(todayIsoDate())
  const [toDate, setToDate] = useState(todayIsoDate())
  const [reportType, setReportType] = useState('custom')
  const [recipientList, setRecipientList] = useState('')
  const [reportHtml, setReportHtml] = useState<string>('')
  const [reportMessage, setReportMessage] = useState<string | null>(null)
  const [pendingAction, setPendingAction] = useState<string | null>(null)

  const [scheduleReports, setScheduleReports] = useState<string[]>(['energy'])
  const [scheduleTime, setScheduleTime] = useState('08:00')
  const [scheduleDays, setScheduleDays] = useState('1,2,3,4,5')
  const [schedulePeriodType, setSchedulePeriodType] = useState('yesterday')
  const [scheduleMailConfigId, setScheduleMailConfigId] = useState<number | null>(null)
  const [scheduleEnabled, setScheduleEnabled] = useState(true)

  const { data: schedulePayload, refetch: refetchSchedules } = useQuery({
    queryKey: ['reports', 'schedules', activeTargetId],
    queryFn: () => listReportSchedules(activeTargetId),
    refetchInterval: 20_000,
  })

  const { data: mailPayload } = useQuery({
    queryKey: ['reports', 'mail-configs', activeTargetId],
    queryFn: () => getMailConfigs(activeTargetId),
    refetchInterval: 30_000,
  })

  const schedules = useMemo(() => asScheduleRows(schedulePayload), [schedulePayload])
  const mailConfigs = useMemo(() => {
    const body = mailPayload as Record<string, unknown> | undefined
    const data = body && Array.isArray(body.data) ? body.data : []
    return data.map((item) => {
      const row = item as Record<string, unknown>
      const username = String(row.username ?? '').trim()
      const toEmail = String(row.to_email ?? '').trim()
      const fromEmail = String(row.from_email ?? '').trim()
      const smtpServer = String(row.smtp_server ?? '').trim()
      const fallbackLabel = toEmail || fromEmail || username || smtpServer || `Config ${String(row.id ?? '')}`
      return {
        id: Number(row.id ?? 0),
        label: fallbackLabel,
      }
    })
  }, [mailPayload])

  const schedulePayloadBase = (): SaveScheduleInput => ({
    reports: scheduleReports,
    period_type: schedulePeriodType,
    days: scheduleDays
      .split(',')
      .map((item) => Number(item.trim()))
      .filter((value) => Number.isInteger(value) && value >= 0 && value <= 6),
    time: scheduleTime,
    mail_config_id: scheduleMailConfigId ?? 0,
    enabled: scheduleEnabled,
  })

  const applyReportPreset = (preset: string) => {
    const range = rangeForPreset(preset)
    if (!range) {
      return
    }
    setFromDate(range.from)
    setToDate(range.to)
  }

  const handleGenerateReport = async () => {
    setPendingAction('generate')
    setReportMessage(null)
    try {
      const payload = await generateReport({
        from_date: `${fromDate}T00:00:00Z`,
        to_date: `${toDate}T23:59:59Z`,
        report_type: reportType,
      }, activeTargetId)
      setReportHtml(String(payload.html ?? ''))
      setReportMessage('Report generated successfully.')
    } catch (error: unknown) {
      setReportMessage(error instanceof Error ? error.message : 'Failed to generate report')
    } finally {
      setPendingAction(null)
    }
  }

  const handleSendReport = async () => {
    setPendingAction('send')
    setReportMessage(null)
    try {
      const recipients = recipientList
        .split(',')
        .map((item) => item.trim())
        .filter(Boolean)
      await sendReport({
        from_date: `${fromDate}T00:00:00Z`,
        to_date: `${toDate}T23:59:59Z`,
        report_type: reportType,
        recipients,
      }, activeTargetId)
      setReportMessage('Report sent successfully.')
    } catch (error: unknown) {
      setReportMessage(error instanceof Error ? error.message : 'Failed to send report')
    } finally {
      setPendingAction(null)
    }
  }

  const handleCreateSchedule = async () => {
    if (!scheduleMailConfigId) {
      setReportMessage('Select a mail configuration before creating a schedule.')
      return
    }
    setPendingAction('create-schedule')
    setReportMessage(null)
    try {
      await createReportSchedule(schedulePayloadBase(), activeTargetId)
      setReportMessage('Schedule created successfully.')
      await refetchSchedules()
    } catch (error: unknown) {
      setReportMessage(error instanceof Error ? error.message : 'Failed to create schedule')
    } finally {
      setPendingAction(null)
    }
  }

  const handleTestSchedule = async () => {
    if (!scheduleMailConfigId) {
      setReportMessage('Select a mail configuration before testing a schedule.')
      return
    }
    setPendingAction('test-schedule')
    setReportMessage(null)
    try {
      await testReportSchedule(schedulePayloadBase(), activeTargetId)
      setReportMessage('Test schedule sent successfully.')
    } catch (error: unknown) {
      setReportMessage(error instanceof Error ? error.message : 'Failed to test schedule')
    } finally {
      setPendingAction(null)
    }
  }

  const handleDeleteSchedule = async (scheduleId: number) => {
    setPendingAction(`delete-${scheduleId}`)
    setReportMessage(null)
    try {
      await deleteReportSchedule(scheduleId, activeTargetId)
      setReportMessage('Schedule deleted successfully.')
      await refetchSchedules()
    } catch (error: unknown) {
      setReportMessage(error instanceof Error ? error.message : 'Failed to delete schedule')
    } finally {
      setPendingAction(null)
    }
  }

  return (
    <section className="space-y-4">
      <PageHeader title="Reports" subtitle="Generate, deliver, and schedule report pipelines from React." />

      <article className="card-base space-y-4">
        <h2 className="text-xl font-semibold text-slate-100">Generate or Send Report</h2>
        <div className="grid gap-3 md:grid-cols-4">
          <label className="field-group">
            <span className="field-label">From date</span>
            <input className="input-base" type="date" value={fromDate} onChange={(event) => setFromDate(event.target.value)} />
          </label>
          <label className="field-group">
            <span className="field-label">To date</span>
            <input className="input-base" type="date" value={toDate} onChange={(event) => setToDate(event.target.value)} />
          </label>
          <label className="field-group">
            <span className="field-label">Report type</span>
            <select
              className="input-base"
              value={reportType}
              onChange={(event) => {
                const nextType = event.target.value
                setReportType(nextType)
                applyReportPreset(nextType)
              }}
            >
              {REPORT_TYPE_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>
          <label className="field-group">
            <span className="field-label">Recipients (comma separated)</span>
            <input
              className="input-base"
              value={recipientList}
              onChange={(event) => setRecipientList(event.target.value)}
              placeholder="ops@example.com,alerts@example.com"
            />
          </label>
        </div>
        <div className="flex flex-wrap gap-2 text-xs">
          {REPORT_TYPE_OPTIONS.filter((option) => option.value.startsWith('last_') || option.value === 'yesterday').map((option) => (
            <button
              key={option.value}
              className="rounded-lg border border-slate-700 px-3 py-1.5 text-slate-200 hover:border-slate-500"
              type="button"
              onClick={() => {
                setReportType(option.value)
                applyReportPreset(option.value)
              }}
            >
              {option.label}
            </button>
          ))}
        </div>
        <div className="flex flex-wrap gap-2">
          <button className="btn-primary" type="button" disabled={pendingAction === 'generate'} onClick={() => void handleGenerateReport()}>
            {pendingAction === 'generate' ? 'Generating...' : 'Generate Preview'}
          </button>
          <button className="btn-primary" type="button" disabled={pendingAction === 'send'} onClick={() => void handleSendReport()}>
            {pendingAction === 'send' ? 'Sending...' : 'Send Report'}
          </button>
        </div>
        {reportMessage ? <p className="text-sm text-slate-300">{reportMessage}</p> : null}
        <div className="max-h-[300px] overflow-auto rounded-xl border border-slate-800 bg-slate-950/70 p-3 text-xs text-slate-300">
          <pre>{reportHtml || 'No generated HTML yet.'}</pre>
        </div>
      </article>

      <article className="card-base space-y-4">
        <h2 className="text-xl font-semibold text-slate-100">Schedule Reports</h2>
        <div className="grid gap-3 md:grid-cols-3">
          <label className="field-group">
            <span className="field-label">Report modules</span>
            <select
              className="input-base"
              multiple
              value={scheduleReports}
              onChange={(event) => {
                const selected = Array.from(event.target.selectedOptions).map((option) => option.value)
                setScheduleReports(selected)
              }}
            >
              {REPORT_OPTIONS.map((option) => (
                <option key={option} value={option}>
                  {option}
                </option>
              ))}
            </select>
          </label>
          <label className="field-group">
            <span className="field-label">Period type</span>
            <select className="input-base" value={schedulePeriodType} onChange={(event) => setSchedulePeriodType(event.target.value)}>
              {SCHEDULE_PERIOD_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>
          <label className="field-group">
            <span className="field-label">Mail config</span>
            <select
              className="input-base"
              value={scheduleMailConfigId ?? ''}
              onChange={(event) => setScheduleMailConfigId(Number(event.target.value) || null)}
            >
              <option value="">Select mail config</option>
              {mailConfigs.map((config) => (
                <option key={config.id} value={config.id}>
                  {config.id} - {config.label}
                </option>
              ))}
            </select>
          </label>
          <label className="field-group">
            <span className="field-label">Schedule time</span>
            <input className="input-base" type="time" value={scheduleTime} onChange={(event) => setScheduleTime(event.target.value)} />
          </label>
          <label className="field-group">
            <span className="field-label">Week days (0-6 comma list)</span>
            <input className="input-base" value={scheduleDays} onChange={(event) => setScheduleDays(event.target.value)} />
          </label>
          <label className="field-group">
            <span className="field-label">Enabled</span>
            <select
              className="input-base"
              value={scheduleEnabled ? 'true' : 'false'}
              onChange={(event) => setScheduleEnabled(event.target.value === 'true')}
            >
              <option value="true">Enabled</option>
              <option value="false">Disabled</option>
            </select>
          </label>
        </div>
        <div className="flex flex-wrap gap-2">
          <button className="btn-primary" type="button" disabled={pendingAction === 'create-schedule'} onClick={() => void handleCreateSchedule()}>
            {pendingAction === 'create-schedule' ? 'Saving...' : 'Create Schedule'}
          </button>
          <button className="btn-primary" type="button" disabled={pendingAction === 'test-schedule'} onClick={() => void handleTestSchedule()}>
            {pendingAction === 'test-schedule' ? 'Testing...' : 'Test Schedule'}
          </button>
        </div>
        <div className="overflow-x-auto">
          <table className="min-w-full text-sm">
            <thead className="border-b border-slate-800 text-xs uppercase tracking-wide text-slate-400">
              <tr>
                <th className="px-2 py-2 text-left">ID</th>
                <th className="px-2 py-2 text-left">Time</th>
                <th className="px-2 py-2 text-left">Days</th>
                <th className="px-2 py-2 text-left">Reports</th>
                <th className="px-2 py-2 text-left">Period</th>
                <th className="px-2 py-2 text-left">Enabled</th>
                <th className="px-2 py-2 text-left">Actions</th>
              </tr>
            </thead>
            <tbody>
              {schedules.map((schedule) => (
                <tr key={schedule.id} className="border-b border-slate-900/70">
                  <td className="px-2 py-2">{schedule.id}</td>
                  <td className="px-2 py-2">{schedule.time}</td>
                  <td className="px-2 py-2">{schedule.days}</td>
                  <td className="px-2 py-2">{schedule.reports}</td>
                  <td className="px-2 py-2">{schedule.period_type}</td>
                  <td className="px-2 py-2">{schedule.enabled ? 'Yes' : 'No'}</td>
                  <td className="px-2 py-2">
                    <button
                      className="rounded-lg border border-rose-500/40 px-2 py-1 text-xs text-rose-200 hover:border-rose-400"
                      type="button"
                      disabled={pendingAction === `delete-${schedule.id}`}
                      onClick={() => void handleDeleteSchedule(schedule.id)}
                    >
                      Delete
                    </button>
                  </td>
                </tr>
              ))}
              {schedules.length === 0 ? (
                <tr>
                  <td className="px-2 py-3 text-slate-400" colSpan={7}>
                    No schedules configured.
                  </td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </div>
      </article>
    </section>
  )
}
