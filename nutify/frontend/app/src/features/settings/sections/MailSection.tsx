/**
 * Mailsection.
 *
 * Frontend module used by Nutify React UI flows and state management.
 */

import { MailConfigPanel } from './mail/MailConfigPanel'
import { MailNotificationsPanel } from './mail/MailNotificationsPanel'
import { MailReportSchedulerPanel } from './mail/MailReportSchedulerPanel'
import { useMailSectionController } from './mail/useMailSectionController'

type MailSectionProps = {
  showConfigPanel?: boolean
  showNotificationsPanel?: boolean
  showReportPanel?: boolean
}

export function MailSection({
  showConfigPanel = true,
  showNotificationsPanel = true,
  showReportPanel = true,
}: MailSectionProps = {}) {
  const {
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
    defaults,
  } = useMailSectionController()

  const showConfigDependentSections = configs.length > 0 && (!showConfigPanel || !isFormVisible)
  const showNotifications = showNotificationsPanel && showConfigDependentSections
  const showReports = showReportPanel && showConfigDependentSections
  const showMissingProviderCard = (showNotificationsPanel || showReportPanel) && !showConfigPanel && configs.length === 0

  return (
    <>
      {showConfigPanel ? (
        <MailConfigPanel
          isFormVisible={isFormVisible}
          saveVisible={saveVisible}
          isSaving={saveMutation.isPending}
          isTesting={formTestMutation.isPending}
          form={form}
          providers={providers}
          configs={configs}
          status={status}
          showSummary={showConfigDependentSections}
          onShowAdd={handleShowAddForm}
          onCancel={() => {
            setIsFormVisible(false)
            setSaveVisible(false)
            setForm(defaults.mailForm)
          }}
          onProviderChange={handleProviderChange}
          onFieldChange={(field, value) => setForm((prev) => ({ ...prev, [field]: value }))}
          onTest={() => formTestMutation.mutate()}
          onSave={() => saveMutation.mutate()}
          onEditConfig={handleEditConfig}
          onDeleteConfig={handleDeleteConfig}
          onToggleConfigEnabled={(configId, enabled) => toggleEnabledMutation.mutate({ configId, enabled })}
        />
      ) : null}

      {showMissingProviderCard ? (
        <div className="options_card mt-4">
          <div className="card_header">
            <div className="notification_header">
              <h2>Email Provider Required</h2>
            </div>
            <p className="card_subtitle">
              Configure at least one email provider in the Provider tab before editing notification or report routing.
            </p>
          </div>
        </div>
      ) : null}

      <div id="notification_dependent_sections" style={{ display: showConfigDependentSections ? 'block' : 'none' }}>
        {showNotifications ? (
          <MailNotificationsPanel
            configs={configs}
            providers={providers}
            selections={selections}
            testBusyEventType={testBusyEventType}
            status={optionsStatus}
            onConfigChange={handleConfigSelect}
            onEnabledChange={handleNotificationEnabledChange}
            onTest={handleNotificationTest}
          />
        ) : null}

        {showReports ? (
          <MailReportSchedulerPanel
            configs={configs}
            providers={providers}
            reportSettings={reportSettings}
            reportStatus={reportStatus}
            isSendingReportNow={sendReportNowMutation.isPending}
            onReportFieldChange={(field, value) => setReportSettings((prev) => ({ ...prev, [field]: value }))}
            onReportTypeToggle={(reportType) =>
              setReportSettings((prev) => ({
                ...prev,
                selectedReports: toggleListString(prev.selectedReports, reportType),
              }))
            }
            onSendReportNow={handleSendReportNow}
            schedules={schedules}
            scheduleStatus={scheduleStatus}
            isScheduleModalOpen={isScheduleModalOpen}
            scheduleForm={scheduleForm}
            scheduleModalError={scheduleModalError}
            isSavingSchedule={saveScheduleMutation.isPending}
            isTestingSchedule={testScheduleMutation.isPending}
            onOpenAddSchedule={handleOpenAddSchedule}
            onCloseScheduleModal={() => {
              setIsScheduleModalOpen(false)
              setScheduleModalError('')
            }}
            onScheduleFieldChange={(field, value) => setScheduleForm((prev) => ({ ...prev, [field]: value }))}
            onScheduleDayToggle={(day) =>
              setScheduleForm((prev) => ({
                ...prev,
                selectedDays: toggleListNumber(prev.selectedDays, day),
              }))
            }
            onScheduleReportToggle={(reportType) =>
              setScheduleForm((prev) => ({
                ...prev,
                reports: toggleListString(prev.reports, reportType),
              }))
            }
            onSaveSchedule={handleSaveSchedule}
            onTestSchedule={handleTestSchedule}
            onEditSchedule={handleEditSchedule}
            onDeleteSchedule={(scheduleId) => {
              if (window.confirm('Are you sure you want to delete this schedule?')) {
                deleteScheduleMutation.mutate(scheduleId)
              }
            }}
            onScheduleEnabledToggle={(scheduleId, enabled) => updateScheduleEnabledMutation.mutate({ scheduleId, enabled })}
          />
        ) : null}
      </div>
    </>
  )
}
