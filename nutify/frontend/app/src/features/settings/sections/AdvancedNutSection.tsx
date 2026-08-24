/**
 * Advancednutsection.
 *
 * Frontend module used by Nutify React UI flows and state management.
 */

import { useEffect, useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import {
  getAdvancedNutConfig,
  getAdvancedNutDocs,
  getAdvancedNutFiles,
  getInitialSetupOptions,
  getVariableConfig,
  restartAdvancedNutServices,
  saveAdvancedNutConfig,
  saveInitialSetupOptions,
  saveVariableConfig,
} from '../../../lib/api/settings'
import {
  createTarget,
  downloadNotifyCmdScript,
  deleteTarget,
  getTargets,
  pollTargetNow,
  setPrimaryTarget,
  testTargetConnection,
  toggleTarget,
  updateTarget,
  type MultiNutTarget,
} from '../../../lib/api/multiNut'
import { useAppStore } from '../../../store/appStore'
import {
  CLOCK_FORMAT_EVENT,
  CLOCK_FORMAT_STORAGE_KEY,
  getClockFormatPreference,
  setClockFormatPreference,
  type ClockFormatPreference,
} from '../../../lib/utils/timePreferences'
import {
  DEFAULT_INITIAL_SETUP,
  DEFAULT_TARGET_FORM,
  type AlertState,
  type InitialSetupForm,
  type TargetForm,
  mapTargetToForm,
  normalizeConfig,
  normalizeDocs,
  normalizeFiles,
  normalizeInitialSetup,
  toTargetPayload,
  validateTargetLocationBeforeSave,
} from './advanced/advancedNutHelpers'
import { AdvancedDiagnosticsPanel } from './advanced/AdvancedDiagnosticsPanel'
import { AdvancedManagerPanel } from './advanced/AdvancedManagerPanel'
import { AdvancedPrimaryPanel } from './advanced/AdvancedPrimaryPanel'

type SectionKey = 'primary' | 'fleet' | 'diagnostics' | 'clock'

export function AdvancedNutSection() {
  const queryClient = useQueryClient()
  const monitoringProfile = useAppStore((state) => state.bootstrap?.monitoring.monitoring_profile ?? 'single')

  const [activeSection, setActiveSection] = useState<SectionKey>('primary')
  const [primaryCollapsed, setPrimaryCollapsed] = useState(true)

  const [primaryAlert, setPrimaryAlert] = useState<AlertState>(null)
  const [fleetAlert, setFleetAlert] = useState<AlertState>(null)
  const [initialSetupAlert, setInitialSetupAlert] = useState<AlertState>(null)
  const [clockFormat, setClockFormat] = useState<ClockFormatPreference>(() => getClockFormatPreference())

  const [selectedFile, setSelectedFile] = useState('')
  const [editorValue, setEditorValue] = useState('')

  const [targetForm, setTargetForm] = useState<TargetForm>(DEFAULT_TARGET_FORM)
  const [lastTargetConnectionTest, setLastTargetConnectionTest] = useState<{ fingerprint: string; success: boolean } | null>(null)
  const [savedTargetConnectionFingerprint, setSavedTargetConnectionFingerprint] = useState<string | null>(null)
  const [targetActionBusy, setTargetActionBusy] = useState<'save' | 'test' | null>(null)
  const [initialSetupForm, setInitialSetupForm] = useState<InitialSetupForm>(DEFAULT_INITIAL_SETUP)

  const filesQuery = useQuery({ queryKey: ['settings', 'advanced', 'files'], queryFn: getAdvancedNutFiles })
  const configQuery = useQuery({
    queryKey: ['settings', 'advanced', 'config', selectedFile],
    queryFn: () => getAdvancedNutConfig(selectedFile),
    enabled: Boolean(selectedFile),
  })
  const docsQuery = useQuery({
    queryKey: ['settings', 'advanced', 'docs', selectedFile],
    queryFn: () => getAdvancedNutDocs(selectedFile),
    enabled: Boolean(selectedFile),
  })
  const initialSetupQuery = useQuery({
    queryKey: ['settings', 'advanced', 'initial-setup'],
    queryFn: getInitialSetupOptions,
  })
  const targetsQuery = useQuery({
    queryKey: ['settings', 'advanced', 'targets'],
    queryFn: () => getTargets(true),
  })

  const files = useMemo(() => normalizeFiles(filesQuery.data), [filesQuery.data])
  const config = useMemo(() => normalizeConfig(configQuery.data), [configQuery.data])
  const docsRows = useMemo(() => normalizeDocs(docsQuery.data), [docsQuery.data])
  const targets = targetsQuery.data ?? []

  const fingerprintTargetConnection = (payload: ReturnType<typeof toTargetPayload>) =>
    JSON.stringify({
      ups_name: payload.ups_name.trim(),
      host: payload.host.trim(),
      port: Number(payload.port || 3493),
      nut_mode: payload.nut_mode,
    })

  const currentTargetPayload = toTargetPayload(targetForm)
  const isSavingTarget = targetActionBusy === 'save'
  const isTestingTarget = targetActionBusy === 'test'
  const currentTargetConnectionFingerprint = fingerprintTargetConnection(currentTargetPayload)
  const canSaveTarget =
    savedTargetConnectionFingerprint === currentTargetConnectionFingerprint ||
    (lastTargetConnectionTest?.success === true &&
      lastTargetConnectionTest.fingerprint === currentTargetConnectionFingerprint)

  useEffect(() => {
    if (!selectedFile && files.length > 0) {
      setSelectedFile(files[0].name)
    }
  }, [files, selectedFile])

  useEffect(() => {
    setEditorValue(config.content)
  }, [config.content])

  useEffect(() => {
    const normalized = normalizeInitialSetup(initialSetupQuery.data)
    setInitialSetupForm(normalized.form)
  }, [initialSetupQuery.data])

  const saveConfigMutation = useMutation({
    mutationFn: () => saveAdvancedNutConfig(selectedFile, editorValue),
    onSuccess: async () => {
      setPrimaryAlert({ tone: 'success', message: 'Configuration updated successfully.' })
      await queryClient.invalidateQueries({ queryKey: ['settings', 'advanced', 'config', selectedFile] })
    },
    onError: (error: unknown) =>
      setPrimaryAlert({ tone: 'danger', message: error instanceof Error ? error.message : 'Save failed' }),
  })

  const restartMutation = useMutation({
    mutationFn: restartAdvancedNutServices,
    onSuccess: () => setPrimaryAlert({ tone: 'success', message: 'NUT services restarted successfully.' }),
    onError: (error: unknown) =>
      setPrimaryAlert({ tone: 'danger', message: error instanceof Error ? error.message : 'Restart failed' }),
  })

  const saveInitialSetupMutation = useMutation({
    mutationFn: () =>
      saveInitialSetupOptions({
        server_name: initialSetupForm.server_name.trim(),
        timezone: initialSetupForm.timezone,
        monitoring_profile: initialSetupForm.monitoring_profile,
        ups_realpower_nominal: initialSetupForm.ups_realpower_nominal
          ? Number(initialSetupForm.ups_realpower_nominal)
          : null,
      }),
    onSuccess: async () => {
      setInitialSetupAlert({ tone: 'success', message: 'Initial setup configuration saved. Rebooting system...' })
      await queryClient.invalidateQueries({ queryKey: ['settings', 'advanced', 'initial-setup'] })
      window.setTimeout(() => {
        void fetch('/api/restart', { method: 'POST', credentials: 'same-origin' }).finally(() => {
          window.setTimeout(() => window.location.reload(), 2500)
        })
      }, 1000)
    },
    onError: (error: unknown) =>
      setInitialSetupAlert({
        tone: 'danger',
        message: error instanceof Error ? error.message : 'Failed to save initial setup configuration',
      }),
  })

  useEffect(() => {
    const syncClockFormat = () => setClockFormat(getClockFormatPreference())
    const handleStorage = (event: StorageEvent) => {
      if (!event.key || event.key === CLOCK_FORMAT_STORAGE_KEY) {
        syncClockFormat()
      }
    }

    window.addEventListener('storage', handleStorage)
    window.addEventListener(CLOCK_FORMAT_EVENT, syncClockFormat as EventListener)

    return () => {
      window.removeEventListener('storage', handleStorage)
      window.removeEventListener(CLOCK_FORMAT_EVENT, syncClockFormat as EventListener)
    }
  }, [])

  const invalidateTargets = async () => {
    await queryClient.invalidateQueries({ queryKey: ['settings', 'advanced', 'targets'] })
  }

  const onSaveTarget = async () => {
    if (targetActionBusy) return
    setTargetActionBusy('save')
    try {
      const payload = toTargetPayload(targetForm)
      if (!payload.ups_name || !payload.host) {
        throw new Error('UPS Name and Host are required')
      }
      if (!canSaveTarget) {
        throw new Error('Run a successful Test Connection before saving this target.')
      }

      const locationValidation = await validateTargetLocationBeforeSave(payload)
      if (!locationValidation.confirmed) {
        setFleetAlert({ tone: 'info', message: 'Save canceled by user.' })
        return
      }
      const validatedPayload = locationValidation.target

      let savedTargetId = Number(targetForm.id || 0)
      if (targetForm.id) {
        await updateTarget(Number(targetForm.id), validatedPayload)
      } else {
        const created = await createTarget(validatedPayload) as { data?: { target?: { id?: number } } }
        const createdId = Number(created?.data?.target?.id ?? 0)
        if (Number.isFinite(createdId) && createdId > 0) {
          savedTargetId = createdId
        }
      }

      if (!savedTargetId) {
        const refreshedTargets = await getTargets(true)
        const normalizedName = String(validatedPayload.name || '').trim().toLowerCase()
        const normalizedUpsName = String(validatedPayload.ups_name || '').trim().toLowerCase()
        const normalizedHost = String(validatedPayload.host || '').trim().toLowerCase()
        const matchedTarget = refreshedTargets.find((target) => {
          return (
            String(target.name || '').trim().toLowerCase() === normalizedName &&
            String(target.ups_name || '').trim().toLowerCase() === normalizedUpsName &&
            String(target.host || '').trim().toLowerCase() === normalizedHost
          )
        })
        if (matchedTarget) {
          savedTargetId = Number(matchedTarget.id)
        }
      }

      if (savedTargetId > 0) {
        const scopedConfig = await getVariableConfig(savedTargetId)
        const scopedTimezone = String(targetForm.timezone || scopedConfig.timezone || 'UTC').trim() || 'UTC'
        const scopedCurrency = String(targetForm.currency || scopedConfig.currency || 'EUR').trim().toUpperCase() || 'EUR'
        const scopedPrice = Number(scopedConfig.price_per_kwh)
        const scopedCo2 = Number(scopedConfig.co2_factor)
        await saveVariableConfig(
          {
            currency: scopedCurrency,
            price_per_kwh: Number.isFinite(scopedPrice) ? scopedPrice : 0.25,
            co2_factor: Number.isFinite(scopedCo2) ? scopedCo2 : 0.4,
            timezone: scopedTimezone,
            ups_realpower_nominal: scopedConfig.ups_realpower_nominal ?? null,
          },
          savedTargetId,
        )
      }

      const locationMessage = validatedPayload.location_enabled
        ? locationValidation.found
          ? ' Location validated and coordinates saved.'
          : ' Saved without validated coordinates.'
        : ''
      setFleetAlert({ tone: 'success', message: `Target saved successfully.${locationMessage}` })
      setTargetForm(DEFAULT_TARGET_FORM)
      setLastTargetConnectionTest(null)
      setSavedTargetConnectionFingerprint(null)
      await invalidateTargets()
    } catch (error) {
      setFleetAlert({ tone: 'danger', message: error instanceof Error ? error.message : 'Save failed' })
    } finally {
      setTargetActionBusy(null)
    }
  }

  const onTestTarget = async () => {
    if (targetActionBusy) return
    setTargetActionBusy('test')
    try {
      const payload = toTargetPayload(targetForm)
      const result = await testTargetConnection(payload)
      const success = Boolean(result.success)
      setLastTargetConnectionTest(
        success
          ? {
              success: true,
              fingerprint: fingerprintTargetConnection(payload),
            }
          : null,
      )
      setFleetAlert({
        tone: success ? 'success' : 'danger',
        message: String(result.message || (success ? 'Connection successful.' : 'Connection failed')),
      })
    } catch (error) {
      setLastTargetConnectionTest(null)
      setFleetAlert({
        tone: 'danger',
        message: error instanceof Error ? error.message : 'Connection test failed',
      })
    } finally {
      setTargetActionBusy(null)
    }
  }

  const onDeleteTarget = async (targetId: number, targetName: string) => {
    if (!window.confirm(`Delete target "${targetName}"? Stored snapshots for this target will also be removed.`)) {
      return
    }
    await deleteTarget(targetId)
    await invalidateTargets()
  }

  const toggleClockFormat = () => {
    const next = clockFormat === '24h' ? 'ampm' : '24h'
    setClockFormat(setClockFormatPreference(next))
  }

  return (
    <div>
      <div className="advanced_actions_row">
        <button type="button" id="advancedSectionBtnPrimary" className={`options_btn advanced_section_btn ${activeSection === 'primary' ? 'options_btn_primary' : 'options_btn_secondary'}`} onClick={() => setActiveSection('primary')}>
          <i className="fas fa-server" /> Configuration
        </button>
        <button type="button" id="advancedSectionBtnFleet" className={`options_btn advanced_section_btn ${activeSection === 'fleet' ? 'options_btn_primary' : 'options_btn_secondary'}`} onClick={() => setActiveSection('fleet')}>
          <i className="fas fa-network-wired" /> NUT Manager
        </button>
        <button type="button" id="advancedSectionBtnDiagnostics" className={`options_btn advanced_section_btn ${activeSection === 'diagnostics' ? 'options_btn_primary' : 'options_btn_secondary'}`} onClick={() => setActiveSection('diagnostics')}>
          <i className="fas fa-stethoscope" /> System Diagnostics
        </button>
        <button
          type="button"
          id="advancedClockFormatBtn"
          className={`options_btn advanced_section_btn ${activeSection === 'clock' ? 'options_btn_primary' : 'options_btn_secondary'}`}
          onClick={() => setActiveSection('clock')}
          title="TopBar clock format settings"
        >
          <i className="fas fa-clock" /> Clock
        </button>
      </div>

      <div className="options_card">
        <div className="card_header">
          <h2>Advanced Control Center</h2>
          <p className="card_subtitle">Separate primary NUT operations, target manager, and diagnostics.</p>
        </div>
      </div>

      {activeSection === 'clock' ? (
        <div className="options_card">
          <div className="card_header">
            <h2>Clock</h2>
            <p className="card_subtitle">Control TopBar time format. This is a browser preference.</p>
          </div>
          <div className="options_nutify_body">
            <div className="options_notification_card" style={{ marginBottom: 0 }}>
              <div className="options_nutify_header">
                <div className="options_nutify_icon">
                  <i className="fas fa-clock" />
                </div>
                <div className="options_nutify_title_container">
                  <span className="options_nutify_title">TopBar Clock</span>
                  <span className="options_nutify_description">
                    Choose between true 24-hour format and AM/PM format.
                  </span>
                </div>
                <div className="options_nutify_toggle" style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                  <span className="card_subtitle" style={{ margin: 0 }}>
                    {clockFormat === '24h' ? '24H' : 'AM/PM'}
                  </span>
                  <div className="toggle-switch">
                    <input
                      type="checkbox"
                      id="advancedTopbarClockToggle"
                      className="toggle-input"
                      checked={clockFormat === '24h'}
                      onChange={toggleClockFormat}
                    />
                    <label htmlFor="advancedTopbarClockToggle" className="toggle-label">
                      <span className="toggle-inner" />
                      <span className="toggle-switch-text-on">24</span>
                      <span className="toggle-switch-text-off">12</span>
                    </label>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      ) : null}

      <AdvancedPrimaryPanel
        active={activeSection === 'primary'}
        primaryCollapsed={primaryCollapsed}
        primaryAlert={primaryAlert}
        selectedFile={selectedFile}
        files={files}
        config={config}
        docsRows={docsRows}
        editorValue={editorValue}
        savePending={saveConfigMutation.isPending}
        restartPending={restartMutation.isPending}
        onToggleCollapsed={() => setPrimaryCollapsed((current) => !current)}
        onSelectFile={setSelectedFile}
        onEditorChange={setEditorValue}
        onSaveConfig={() => saveConfigMutation.mutate()}
        onRestartServices={() => restartMutation.mutate()}
      />

      <AdvancedManagerPanel
        active={activeSection === 'fleet'}
        monitoringProfile={monitoringProfile}
        fleetAlert={fleetAlert}
        targetForm={targetForm}
        canSaveTarget={canSaveTarget}
        targetSaveBusy={isSavingTarget}
        targetTestBusy={isTestingTarget}
        targets={targets}
        onTargetFormChange={(updater) =>
          setTargetForm((prev) => {
            const next = updater(prev)
            const nextFingerprint = fingerprintTargetConnection(toTargetPayload(next))
            setLastTargetConnectionTest((current) =>
              current?.fingerprint === nextFingerprint ? current : null,
            )
            return next
          })
        }
        onResetTargetForm={() => {
          setFleetAlert(null)
          setTargetForm(DEFAULT_TARGET_FORM)
          setLastTargetConnectionTest(null)
          setSavedTargetConnectionFingerprint(null)
        }}
        onSaveTarget={onSaveTarget}
        onTestTarget={onTestTarget}
        onEditTarget={async (target: MultiNutTarget) => {
          setFleetAlert(null)
          const baseForm = mapTargetToForm(target)
          setTargetForm(baseForm)
          setLastTargetConnectionTest(null)
          setSavedTargetConnectionFingerprint(fingerprintTargetConnection(toTargetPayload(baseForm)))
          try {
            const scopedConfig = await getVariableConfig(target.id)
            setTargetForm((prev) => {
              if (prev.id !== String(target.id)) {
                return prev
              }
              return {
                ...prev,
                timezone: String(scopedConfig.timezone || prev.timezone || 'UTC'),
                currency: String(scopedConfig.currency || prev.currency || 'EUR').toUpperCase(),
              }
            })
          } catch {
            // Keep default target form timezone/currency when scoped config is unavailable.
          }
        }}
        onToggleTarget={async (targetId, enabled) => {
          await toggleTarget(targetId, enabled)
          await invalidateTargets()
        }}
        onSetPrimaryTarget={async (targetId) => {
          await setPrimaryTarget(targetId)
          await invalidateTargets()
        }}
        onPollTargetNow={async (targetId) => {
          await pollTargetNow(targetId)
          await invalidateTargets()
        }}
        onDownloadNotifyCmdScript={async (target) => {
          const destinationIp = window.location.hostname || ''
          await downloadNotifyCmdScript(target.id, destinationIp)
          setFleetAlert({
            tone: 'success',
            message: `Script downloaded for target "${target.name}".`,
          })
        }}
        onDeleteTarget={onDeleteTarget}
      />

      <AdvancedDiagnosticsPanel
        active={activeSection === 'diagnostics'}
        initialSetupAlert={initialSetupAlert}
        initialSetupForm={initialSetupForm}
        savePending={saveInitialSetupMutation.isPending}
        onInitialSetupChange={(updater) => setInitialSetupForm((prev) => updater(prev))}
        onSaveInitialSetup={() => saveInitialSetupMutation.mutate()}
      />
    </div>
  )
}
