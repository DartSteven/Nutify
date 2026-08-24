/**
 * Types.
 *
 * Frontend module used by Nutify React UI flows and state management.
 */

export type AlertTone = 'success' | 'error' | 'info'

export type StatusAlert = {
  tone: AlertTone
  message: string
} | null

export type MailConfigRow = {
  id: number
  smtp_server: string
  smtp_port: string
  username: string
  from_email: string
  enabled: boolean
  provider: string
  render_mode: string
  tls: boolean
  tls_starttls: boolean
  to_email: string
}

export type ProviderInfo = {
  displayName?: string
  smtp_server?: string
  smtp_port?: string | number
  tls?: boolean
  tls_starttls?: boolean
  notes?: string
  note?: string
  requires_sender_email?: boolean
}

export type ProviderMap = Record<string, ProviderInfo>

export type MailFormState = {
  id: number | null
  provider: string
  customProviderName: string
  smtpServer: string
  smtpPort: string
  username: string
  password: string
  fromEmail: string
  toEmail: string
  renderMode: string
  useTls: boolean
  useStarttls: boolean
}

export type NotificationSelection = {
  enabled: boolean
  configId: string
}

export type NotificationSelections = Record<string, NotificationSelection>

export type ReportPeriodType = 'yesterday' | 'last_week' | 'last_month' | 'last_year' | 'range'

export type ReportSettingsState = {
  selectedReports: string[]
  periodType: ReportPeriodType
  fromDate: string
  toDate: string
  mailConfigId: string
}

export type ReportScheduleRow = {
  id: number
  time: string
  days: number[]
  reports: string[]
  email: string | null
  mail_config_id: number | null
  period_type: string
  from_date: string | null
  to_date: string | null
  enabled: boolean
}

export type ScheduleFormState = {
  editId: number | null
  selectedDays: number[]
  time: string
  reports: string[]
  periodType: ReportPeriodType
  rangeFromDate: string
  rangeToDate: string
  mailConfigId: string
}
