/**
 * Validators.
 *
 * Frontend module used by Nutify React UI flows and state management.
 */

import type { ReportSettingsState, ScheduleFormState } from './types'

export function validateSendReportNow(reportSettings: ReportSettingsState): string | null {
  if (reportSettings.selectedReports.length === 0) {
    return 'Please select at least one report type'
  }
  if (!reportSettings.periodType) {
    return 'Please select a report period'
  }
  if (reportSettings.periodType === 'range' && (!reportSettings.fromDate || !reportSettings.toDate)) {
    return 'Please select both start and end dates'
  }
  if (!reportSettings.mailConfigId) {
    return 'Please select an email configuration'
  }
  return null
}

export function validateSaveSchedule(scheduleForm: ScheduleFormState): string | null {
  if (scheduleForm.selectedDays.length === 0) {
    return 'Please select at least one day'
  }
  if (!scheduleForm.time) {
    return 'Please select a time'
  }
  if (scheduleForm.reports.length === 0 && !scheduleForm.editId) {
    return 'Please select at least one report type'
  }
  if (scheduleForm.periodType === 'range' && (!scheduleForm.rangeFromDate || !scheduleForm.rangeToDate)) {
    return 'Please provide both From and To dates for range period'
  }
  if (!scheduleForm.mailConfigId) {
    return 'Please select an email configuration'
  }
  return null
}

export function validateTestSchedule(scheduleForm: ScheduleFormState): string | null {
  if (!scheduleForm.mailConfigId) {
    return 'Please select an email configuration'
  }
  if (scheduleForm.reports.length === 0) {
    return 'Please select at least one report type'
  }
  if (scheduleForm.periodType === 'range' && (!scheduleForm.rangeFromDate || !scheduleForm.rangeToDate)) {
    return 'Please select both From and To dates for custom range'
  }
  return null
}
