/**
 * Mailreportschedulerpanel.
 *
 * Frontend module used by Nutify React UI flows and state management.
 */

import type { MailConfigRow, ProviderMap, ReportScheduleRow, ReportSettingsState, ScheduleFormState, StatusAlert } from './types'
import { PERIOD_TYPE_OPTIONS, REPORT_TYPE_OPTIONS, SCHEDULE_DAY_OPTIONS } from './constants'
import { emailOptionLabel, formatScheduleDays, formatSchedulePeriod, parseScheduleTimeToLocal } from './utils'

type MailReportSchedulerPanelProps = {
  configs: MailConfigRow[]
  providers: ProviderMap
  reportSettings: ReportSettingsState
  reportStatus: StatusAlert
  isSendingReportNow: boolean
  onReportFieldChange: <K extends keyof ReportSettingsState>(field: K, value: ReportSettingsState[K]) => void
  onReportTypeToggle: (reportType: string) => void
  onSendReportNow: () => void
  schedules: ReportScheduleRow[]
  scheduleStatus: StatusAlert
  isScheduleModalOpen: boolean
  scheduleForm: ScheduleFormState
  scheduleModalError: string
  isSavingSchedule: boolean
  isTestingSchedule: boolean
  onOpenAddSchedule: () => void
  onCloseScheduleModal: () => void
  onScheduleFieldChange: <K extends keyof ScheduleFormState>(field: K, value: ScheduleFormState[K]) => void
  onScheduleDayToggle: (day: number) => void
  onScheduleReportToggle: (reportType: string) => void
  onSaveSchedule: () => void
  onTestSchedule: () => void
  onEditSchedule: (scheduleId: number) => void
  onDeleteSchedule: (scheduleId: number) => void
  onScheduleEnabledToggle: (scheduleId: number, enabled: boolean) => void
}

export function MailReportSchedulerPanel(props: MailReportSchedulerPanelProps) {
  const {
    configs,
    providers,
    reportSettings,
    reportStatus,
    isSendingReportNow,
    onReportFieldChange,
    onReportTypeToggle,
    onSendReportNow,
    schedules,
    scheduleStatus,
    isScheduleModalOpen,
    scheduleForm,
    scheduleModalError,
    isSavingSchedule,
    isTestingSchedule,
    onOpenAddSchedule,
    onCloseScheduleModal,
    onScheduleFieldChange,
    onScheduleDayToggle,
    onScheduleReportToggle,
    onSaveSchedule,
    onTestSchedule,
    onEditSchedule,
    onDeleteSchedule,
    onScheduleEnabledToggle,
  } = props

  const configOptions = configs.map((config) => ({
    value: String(config.id),
    label: emailOptionLabel(config, providers),
  }))

  const scheduleEmailLookup = new Map(configOptions.map((option) => [option.value, option.label]))

  return (
    <>
      <div className="options_card mt-4">
        <h2>Report Settings</h2>
        <div id="report_status_container" className={`options_alert ${reportStatus ? '' : 'hidden'}`}>
          {reportStatus?.message || ''}
        </div>
        <div className="card_header">
          <div className="notification_header">
            <p className="options_notification_subtitle">Configure automated report delivery</p>
            <div className="options_nutify_actions">
              <button type="button" id="sendReportNow" className="options_btn" disabled={isSendingReportNow} onClick={onSendReportNow}>
                <i className="fas fa-paper-plane" />
                <span className="btn-text" style={{ display: isSendingReportNow ? 'none' : 'inline' }}>
                  Send Report Now
                </span>
                <span className={`btn-loader ${isSendingReportNow ? '' : 'hidden'}`}>
                  <i className="fas fa-spinner fa-spin" />
                </span>
              </button>
            </div>
          </div>
        </div>

        <div className="options_notification_form">
          <div className="options_form_group">
            <label className="options_form_label">Report Types</label>
            <div className="options_checkbox_group">
              {REPORT_TYPE_OPTIONS.map((option) => (
                <div className="options_checkbox_item" key={`report-setting-${option.value}`}>
                  <input
                    type="checkbox"
                    id={`${option.value}_report`}
                    name="report_types"
                    value={option.value}
                    className={option.value === 'events' ? 'form-checkbox' : undefined}
                    checked={reportSettings.selectedReports.includes(option.value)}
                    onChange={() => onReportTypeToggle(option.value)}
                  />
                  <label htmlFor={`${option.value}_report`}>{option.label}</label>
                </div>
              ))}
            </div>
          </div>

          <div className="options_form_group">
            <label className="options_form_label">Report Period</label>
            <div className="options_date_inputs">
              <div className="options_input_group">
                <label htmlFor="report_from_date">From</label>
                <input
                  type="date"
                  id="report_from_date"
                  className="options_input"
                  value={reportSettings.fromDate}
                  onChange={(event) => onReportFieldChange('fromDate', event.target.value)}
                />
              </div>
              <div className="options_input_group">
                <label htmlFor="report_to_date">To</label>
                <input
                  type="date"
                  id="report_to_date"
                  className="options_input"
                  value={reportSettings.toDate}
                  onChange={(event) => onReportFieldChange('toDate', event.target.value)}
                />
              </div>
            </div>
          </div>

          <div className="options_form_group">
            <label className="options_form_label">Email Configuration</label>
            <div className="options_input_group">
              <select
                id="report_email_select"
                className="options_input"
                value={reportSettings.mailConfigId}
                onChange={(event) => onReportFieldChange('mailConfigId', event.target.value)}
              >
                <option value="">Select email</option>
                {configOptions.map((option) => (
                  <option key={`report-email-${option.value}`} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </div>
          </div>
        </div>
      </div>

      <div className="options_card mt-4">
        <h2>Report Scheduler</h2>
        <div className="card_header">
          <div className="notification_header">
            <p className="options_notification_subtitle">Schedule automated report delivery</p>
            <div className="options_nutify_actions">
              <button id="addSchedulerBtn" className="options_btn options_btn_primary" type="button" onClick={onOpenAddSchedule}>
                <i className="fas fa-plus" /> Add Schedule
              </button>
            </div>
          </div>
        </div>

        <div id="scheduleStatus" className={`options_alert ${scheduleStatus ? '' : 'hidden'}`}>
          {scheduleStatus?.message || ''}
        </div>

        <div id="schedulerList" className="scheduler-list">
          {schedules.length === 0 ? (
            <div className="empty-state">No scheduled reports configured</div>
          ) : (
            schedules.map((schedule) => {
              const displayEmail = schedule.email
                ? schedule.email
                : schedule.mail_config_id
                  ? scheduleEmailLookup.get(String(schedule.mail_config_id)) || `Email Config #${schedule.mail_config_id}`
                  : 'No email selected'

              return (
                <div className="schedule-item" data-schedule-id={schedule.id} key={schedule.id}>
                  <div className="schedule-info">
                    <div className="schedule-time">
                      <i className="fas fa-clock" /> {parseScheduleTimeToLocal(schedule.time)}
                    </div>
                    <div className="schedule-days">
                      <i className="fas fa-calendar" /> {formatScheduleDays(schedule.days)}
                    </div>
                    <div className="schedule-period">
                      <i className="fas fa-calendar-alt" /> {formatSchedulePeriod(schedule)}
                    </div>
                    <div className="schedule-reports">
                      <i className="fas fa-file-alt" /> {schedule.reports.join(', ') || 'No reports selected'}
                    </div>
                    <div className="schedule-email">
                      <i className="fas fa-envelope" /> {displayEmail}
                    </div>
                  </div>
                  <div className="schedule-actions">
                    <button className="options_btn options_btn_secondary edit-schedule-btn" type="button" onClick={() => onEditSchedule(schedule.id)}>
                      <i className="fas fa-edit" />
                    </button>
                    <button className="options_btn options_btn_secondary delete-schedule-btn" type="button" onClick={() => onDeleteSchedule(schedule.id)}>
                      <i className="fas fa-trash" />
                    </button>
                    <label className="schedule-toggle">
                      <input
                        type="checkbox"
                        className="enable-schedule-checkbox"
                        data-schedule-id={schedule.id}
                        checked={schedule.enabled}
                        onChange={(event) => onScheduleEnabledToggle(schedule.id, event.target.checked)}
                      />
                      Enabled
                    </label>
                  </div>
                </div>
              )
            })
          )}
        </div>
      </div>

      <div id="scheduleModal" className="modal" style={{ display: isScheduleModalOpen ? 'block' : 'none' }}>
        <div className="modal-content options_card">
          <div className="modal-header">
            <h5 className="modal-title">Schedule Report</h5>
          </div>
          <div className="modal-body">
            <div id="scheduleModalError" className={`alert alert-danger ${scheduleModalError ? '' : 'hidden'}`} style={{ display: scheduleModalError ? 'block' : 'none' }}>
              {scheduleModalError}
            </div>
            <input type="hidden" id="currentEditScheduleId" value={scheduleForm.editId ?? ''} readOnly />

            <div className="schedule-form">
              <div className="form-group">
                <label>Days</label>
                <div className="days-selector">
                  {SCHEDULE_DAY_OPTIONS.map((day) => (
                    <button
                      type="button"
                      className={`day-btn ${scheduleForm.selectedDays.includes(day.value) ? 'selected' : ''}`.trim()}
                      data-day={day.value}
                      key={`day-${day.value}`}
                      onClick={() => onScheduleDayToggle(day.value)}
                    >
                      {day.label}
                    </button>
                  ))}
                </div>
              </div>

              <div className="form-group">
                <label htmlFor="scheduleTime">Time</label>
                <input
                  type="time"
                  id="scheduleTime"
                  className="schedule-input"
                  required
                  value={scheduleForm.time}
                  onChange={(event) => onScheduleFieldChange('time', event.target.value)}
                />
              </div>

              <div className="form-group">
                <label>Report Types</label>
                <div className="report-types-grid">
                  {REPORT_TYPE_OPTIONS.map((option) => (
                    <label className="report-type-item" key={`schedule-report-${option.value}`}>
                      <input
                        type="checkbox"
                        name="report_types"
                        value={option.value}
                        checked={scheduleForm.reports.includes(option.value)}
                        onChange={() => onScheduleReportToggle(option.value)}
                      />
                      <span>{option.label}</span>
                    </label>
                  ))}
                </div>
              </div>

              <div className="form-group">
                <label htmlFor="period_type">Report Period</label>
                <select
                  id="period_type"
                  className="schedule-input"
                  value={scheduleForm.periodType}
                  onChange={(event) => onScheduleFieldChange('periodType', event.target.value as ScheduleFormState['periodType'])}
                >
                  {PERIOD_TYPE_OPTIONS.map((option) => (
                    <option key={`period-option-${option.value || 'empty'}`} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </div>

              <div id="dateRangeSelection" className="form-group" style={{ display: scheduleForm.periodType === 'range' ? 'block' : 'none' }}>
                <div className="date-range-inputs" style={{ display: 'flex', justifyContent: 'space-between', gap: '10px' }}>
                  <div className="input-group" style={{ flex: 1 }}>
                    <label htmlFor="rangeFromDate">From</label>
                    <input
                      type="date"
                      id="rangeFromDate"
                      className="schedule-input"
                      style={{ width: '100%' }}
                      value={scheduleForm.rangeFromDate}
                      onChange={(event) => onScheduleFieldChange('rangeFromDate', event.target.value)}
                    />
                  </div>
                  <div className="input-group" style={{ flex: 1 }}>
                    <label htmlFor="rangeToDate">To</label>
                    <input
                      type="date"
                      id="rangeToDate"
                      className="schedule-input"
                      style={{ width: '100%' }}
                      value={scheduleForm.rangeToDate}
                      onChange={(event) => onScheduleFieldChange('rangeToDate', event.target.value)}
                    />
                  </div>
                </div>
              </div>

              <div className="form-group">
                <label htmlFor="scheduleEmail">Select Email</label>
                <select
                  id="scheduleEmail"
                  className="options_input schedule-input"
                  value={scheduleForm.mailConfigId}
                  onChange={(event) => onScheduleFieldChange('mailConfigId', event.target.value)}
                >
                  <option value="">Select email</option>
                  {configOptions.map((option) => (
                    <option key={`schedule-email-${option.value}`} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            <div className="modal-actions">
              <button id="cancelScheduleBtn" type="button" className="options_btn options_btn_secondary" onClick={onCloseScheduleModal}>
                <i className="fas fa-times" />
                Cancel
              </button>
              <button id="testScheduleBtn" type="button" className="options_btn options_btn_secondary" disabled={isTestingSchedule} onClick={onTestSchedule}>
                <i className="fas fa-vial" />
                <span className="btn-text" style={{ display: isTestingSchedule ? 'none' : 'inline' }}>
                  Test Schedule
                </span>
                <span className={`btn-loader ${isTestingSchedule ? '' : 'hidden'}`}>
                  <i className="fas fa-spinner fa-spin" />
                </span>
              </button>
              <button id="saveScheduleBtn" type="button" className="options_btn" disabled={isSavingSchedule} onClick={onSaveSchedule}>
                <i className="fas fa-save" />
                <span className="btn-text" style={{ display: isSavingSchedule ? 'none' : 'inline' }}>
                  Save Schedule
                </span>
                <span className={`btn-loader ${isSavingSchedule ? '' : 'hidden'}`}>
                  <i className="fas fa-spinner fa-spin" />
                </span>
              </button>
            </div>
          </div>
        </div>
      </div>
    </>
  )
}
