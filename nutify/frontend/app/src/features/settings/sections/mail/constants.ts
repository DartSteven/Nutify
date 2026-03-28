/**
 * Constants.
 *
 * Frontend module used by Nutify React UI flows and state management.
 */

import type {
  MailFormState,
  ReportSettingsState,
  ScheduleFormState,
} from './types'

export const DEFAULT_MAIL_FORM: MailFormState = {
  id: null,
  provider: '',
  customProviderName: '',
  smtpServer: '',
  smtpPort: '',
  username: '',
  password: '',
  fromEmail: '',
  toEmail: '',
  renderMode: 'graphic',
  useTls: false,
  useStarttls: false,
}

export const DEFAULT_REPORT_SETTINGS: ReportSettingsState = {
  selectedReports: [],
  fromDate: '',
  toDate: '',
  mailConfigId: '',
}

export const DEFAULT_SCHEDULE_FORM: ScheduleFormState = {
  editId: null,
  selectedDays: [],
  time: '',
  reports: [],
  periodType: 'yesterday',
  rangeFromDate: '',
  rangeToDate: '',
  mailConfigId: '',
}

export const REPORT_TYPE_OPTIONS = [
  { value: 'energy', label: 'Energy Report' },
  { value: 'battery', label: 'Battery Report' },
  { value: 'power', label: 'Power Report' },
  { value: 'voltage', label: 'Voltage Report' },
  { value: 'events', label: 'Events Report' },
]

export const PERIOD_TYPE_OPTIONS = [
  { value: '', label: 'Select Report Period' },
  { value: 'yesterday', label: 'Yesterday (00:00 - 24:00)' },
  { value: 'last_week', label: 'Last Week (Mon-Sun)' },
  { value: 'last_month', label: 'Last Month' },
  { value: 'range', label: 'Select Range' },
]

export const SCHEDULE_DAY_OPTIONS = [
  { value: 0, label: 'Sun' },
  { value: 1, label: 'Mon' },
  { value: 2, label: 'Tue' },
  { value: 3, label: 'Wed' },
  { value: 4, label: 'Thu' },
  { value: 5, label: 'Fri' },
  { value: 6, label: 'Sat' },
]
