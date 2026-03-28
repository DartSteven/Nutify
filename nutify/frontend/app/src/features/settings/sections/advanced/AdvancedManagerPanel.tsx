/**
 * Advancedmanagerpanel.
 *
 * Frontend module used by Nutify React UI flows and state management.
 */

import { useMemo, useRef, useState } from 'react'

import type { MultiNutTarget } from '../../../../lib/api/multiNut'
import { composeTargetLocation, type AlertState, type TargetForm } from './advancedNutHelpers'
import { AdvancedTargetLocationFields } from './AdvancedTargetLocationFields'
import { AdvancedScriptInfoModal } from './AdvancedScriptInfoModal'

type AdvancedManagerPanelProps = {
  active: boolean
  monitoringProfile: 'single' | 'multi'
  fleetAlert: AlertState
  targetForm: TargetForm
  canSaveTarget: boolean
  targets: MultiNutTarget[]
  onTargetFormChange: (updater: (prev: TargetForm) => TargetForm) => void
  onResetTargetForm: () => void
  onSaveTarget: () => Promise<void>
  onTestTarget: () => Promise<void>
  onEditTarget: (target: MultiNutTarget) => void
  onToggleTarget: (targetId: number, enabled: boolean) => Promise<void>
  onSetPrimaryTarget: (targetId: number) => Promise<void>
  onPollTargetNow: (targetId: number) => Promise<void>
  onDownloadNotifyCmdScript: (target: MultiNutTarget) => Promise<void>
  onDeleteTarget: (targetId: number, targetName: string) => Promise<void>
}

function renderOptionalAlert(alert: AlertState) {
  if (!alert) return null
  return <div className={`options_alert options_alert_${alert.tone}`}>{alert.message}</div>
}

export function AdvancedManagerPanel({
  active,
  monitoringProfile,
  fleetAlert,
  targetForm,
  canSaveTarget,
  targets,
  onTargetFormChange,
  onResetTargetForm,
  onSaveTarget,
  onTestTarget,
  onEditTarget,
  onToggleTarget,
  onSetPrimaryTarget,
  onPollTargetNow,
  onDownloadNotifyCmdScript,
  onDeleteTarget,
}: AdvancedManagerPanelProps) {
  const editorRef = useRef<HTMLDivElement | null>(null)
  const [editorVisible, setEditorVisible] = useState(false)
  const [pollingInfoOpen, setPollingInfoOpen] = useState(false)
  const [scriptInfoTarget, setScriptInfoTarget] = useState<MultiNutTarget | null>(null)
  const computedLocation = useMemo(() => composeTargetLocation(targetForm), [targetForm])
  const timezoneOptions = useMemo(() => {
    const fallback = [
      'UTC',
      'Europe/Rome',
      'Europe/London',
      'America/New_York',
      'America/Los_Angeles',
      'Asia/Tokyo',
      'Australia/Sydney',
    ]
    try {
      const intl = Intl as typeof Intl & { supportedValuesOf?: (type: string) => string[] }
      if (typeof intl.supportedValuesOf === 'function') {
        return Array.from(new Set([...fallback, ...intl.supportedValuesOf('timeZone')])).sort((left, right) =>
          left.localeCompare(right),
        )
      }
    } catch {
      // Keep fallback when browser timezone catalog is unavailable.
    }
    return fallback
  }, [])
  const isRemoteMode = targetForm.nut_mode === 'netclient'
  const isNetworkServerMode = targetForm.nut_mode === 'netserver'
  const connectionSectionTitle = isRemoteMode ? 'Remote Connection Details' : 'Local Connection Details'
  const hostLabel = isRemoteMode ? 'Remote Server' : 'Host'
  const hostPlaceholder = isRemoteMode ? '10.10.10.10' : '127.0.0.1'
  const hostHelp = isRemoteMode
    ? 'IP address or hostname of the remote NUT server.'
    : isNetworkServerMode
      ? 'Host where this local NUT server is exposed (usually 127.0.0.1).'
      : 'Host used for local UPS reads (usually 127.0.0.1).'
  const portHelp = isRemoteMode
    ? 'Port of the remote NUT server (default is 3493).'
    : isNetworkServerMode
      ? 'Port exposed by this local NUT server (default is 3493).'
      : 'Port for local NUT reads (default is 3493).'

  const scrollToEditor = () => {
    window.setTimeout(() => {
      editorRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
    }, 50)
  }

  const openEditorForNew = () => {
    onResetTargetForm()
    setEditorVisible(true)
    scrollToEditor()
  }

  const openEditorForExisting = (target: MultiNutTarget) => {
    onEditTarget(target)
    setEditorVisible(true)
    scrollToEditor()
  }

  const closeEditor = () => {
    onResetTargetForm()
    setEditorVisible(false)
  }

  const renderTargets = () => {
    if (targets.length === 0) {
      return <p className="card_subtitle">No target configured.</p>
    }

    return targets.map((target) => {
      const policy = (target as unknown as { policy?: Record<string, unknown> }).policy ?? {}

      return (
        <div className="options_notification_card nut_manager_target_card" key={target.id}>
          <div className="nut_manager_target_row">
            <div className="nut_manager_target_main">
              <span className="nut_manager_target_name">{target.name}</span>
              <span className="nut_manager_target_connection">
                {target.ups_name}@{target.host}{target.port !== 3493 ? `:${target.port}` : ''}
              </span>
            </div>
            <div className="nut_manager_target_meta">
              <span><strong>Status:</strong> {target.enabled ? 'Enabled' : 'Disabled'}</span>
              <span><strong>Role:</strong> {target.is_primary ? 'Primary' : 'Secondary'}</span>
              <span><strong>Polling:</strong> {String(policy.polling_interval || 1)}s</span>
              <span>
                <strong>Location:</strong>{' '}
                {target.location_enabled && String(target.location || '').trim()
                  ? String(target.location)
                  : 'Disabled'}
              </span>
            </div>
          </div>
          <div className="nut_manager_target_actions">
            <button className="options_btn" type="button" onClick={() => openEditorForExisting(target)}><i className="fas fa-edit" /> Edit</button>
            <button className="options_btn" type="button" onClick={() => void onToggleTarget(target.id, !Boolean(target.enabled))}><i className="fas fa-power-off" /> {target.enabled ? 'Disable' : 'Enable'}</button>
            <button className="options_btn" type="button" onClick={() => void onSetPrimaryTarget(target.id)}><i className="fas fa-star" /> Set Primary</button>
            <button className="options_btn" type="button" onClick={() => void onPollTargetNow(target.id)}><i className="fas fa-network-wired" /> Poll Now</button>
            <button className="options_btn" type="button" onClick={() => void onDownloadNotifyCmdScript(target)}><i className="fas fa-file-code" /> Generate Script</button>
            <button className="options_btn options_btn_secondary" type="button" onClick={() => setScriptInfoTarget(target)} title={`Script info for ${target.name}`}>
              <i className="fas fa-info-circle" />
            </button>
            {!target.is_primary ? (
              <button className="options_btn options_btn_secondary" type="button" onClick={() => void onDeleteTarget(target.id, target.name)}><i className="fas fa-trash" /> Delete</button>
            ) : null}
          </div>
        </div>
      )
    })
  }

  return (
    <div id="advancedSectionFleet" className={`advanced_section_panel ${active ? '' : 'hidden'}`} style={{ display: active ? 'block' : 'none' }}>
      <div className="options_card mt-4" id="multiNutWizardCard">
        <div className="card_header">
          <div className="notification_header">
            <h2>NUT Manager</h2>
            <div className="nut_manager_header_actions">
              <button type="button" id="multiNutNewBtn" className="options_btn options_btn_primary" onClick={openEditorForNew}>
                <i className="fas fa-plus" /> Add Target
              </button>
            </div>
          </div>
          <p className="card_subtitle">
            {monitoringProfile === 'multi'
              ? 'Manage all fleet targets with per-target polling and location metadata.'
              : 'Single-monitor profile still uses the same target manager. Keep one primary target enabled.'}
          </p>
        </div>
        <div className="p-4" id="multiNutAlertContainer">{renderOptionalAlert(fleetAlert)}</div>
      </div>
      <div className="options_card mt-4" id="multiNutTargetsCard">
        <div className="card_header">
          <h2>Configured Targets</h2>
          <p className="card_subtitle">Enable, disable, edit, promote or remove target definitions.</p>
        </div>
        <div id="multiNutTargetsList" className="p-4">{renderTargets()}</div>
      </div>
      <div ref={editorRef} className={`options_card mt-4 ${editorVisible ? '' : 'hidden'}`} id="multiNutEditorCard">
        <div className="card_header">
          <div className="notification_header">
            <h2>{targetForm.id ? 'Edit Target' : 'Add Target'}</h2>
            <div className="nut_manager_header_actions">
              <button
                type="button"
                className="options_btn options_btn_primary"
                onClick={() => void onSaveTarget()}
                disabled={!canSaveTarget}
                title={canSaveTarget ? 'Save target' : 'Run Test Connection successfully before saving'}
              >
                <i className="fas fa-save" /> Save Target
              </button>
              <button type="button" className="options_btn" onClick={() => void onTestTarget()}>
                <i className="fas fa-network-wired" /> Test Connection
              </button>
              <button type="button" className="options_btn options_btn_secondary" onClick={closeEditor}>
                <i className="fas fa-times" /> Close
              </button>
            </div>
          </div>
        </div>
        {!canSaveTarget ? (
          <div className="p-4">
            <div className="options_alert options_alert_info">
              Run <strong>Test Connection</strong> successfully before saving this target.
            </div>
          </div>
        ) : null}
        <div className="p-4">
          <form id="multiNutWizardForm" className="nut_manager_editor_form" onSubmit={(event) => event.preventDefault()}>
            <input type="hidden" id="multi_target_id" value={targetForm.id} readOnly />
            <div className="nut_manager_editor_section">
              <div className="options_mail_form_grid">
                <div className="options_mail_form_group">
                  <label htmlFor="multi_name"><i className="fas fa-tag" /> Target Display Name (UI label)</label>
                  <input type="text" id="multi_name" className="options_input" placeholder="Remote Rack UPS" value={targetForm.name} onChange={(event) => onTargetFormChange((prev) => ({ ...prev, name: event.target.value }))} />
                  <div className="card_subtitle" style={{ margin: 0 }}>Friendly name shown in UI, reports, and target lists.</div>
                </div>
                <div className="options_mail_form_group">
                  <label htmlFor="multi_ups_name"><i className="fas fa-server" /> UPS Identifier (upsc key)</label>
                  <input type="text" id="multi_ups_name" className="options_input" placeholder="ups" value={targetForm.ups_name} onChange={(event) => onTargetFormChange((prev) => ({ ...prev, ups_name: event.target.value }))} />
                  <div className="card_subtitle" style={{ margin: 0 }}>Technical NUT name used by `upsc`, before `@host`.</div>
                </div>
                <div className="options_mail_form_group">
                  <label htmlFor="multi_nut_mode"><i className="fas fa-cogs" /> NUT Mode</label>
                  <select
                    id="multi_nut_mode"
                    className="options_input"
                    value={targetForm.nut_mode}
                    onChange={(event) =>
                      onTargetFormChange((prev) => {
                        const nextMode = event.target.value as TargetForm['nut_mode']
                        const normalizedHost = String(prev.host || '').trim()
                        const nextHost = normalizedHost || (nextMode === 'netclient' ? '' : '127.0.0.1')
                        return { ...prev, nut_mode: nextMode, host: nextHost }
                      })
                    }
                  >
                    <option value="netclient">netclient</option>
                    <option value="standalone">standalone</option>
                    <option value="netserver">netserver</option>
                  </select>
                  <div className="card_subtitle" style={{ margin: 0 }}>
                    {isRemoteMode
                      ? 'Remote target monitored from another NUT host.'
                      : isNetworkServerMode
                        ? 'Local UPS shared as a NUT network server.'
                        : 'Local UPS monitored directly on this host.'}
                  </div>
                </div>
              </div>
            </div>
            <div className="nut_manager_editor_section">
              <div className="card_subtitle" style={{ marginTop: 0, marginBottom: '8px' }}>
                {connectionSectionTitle}
              </div>
              <div className="options_mail_form_grid" style={{ gridTemplateColumns: 'repeat(2, 1fr)' }}>
                <div className="options_mail_form_group">
                  <label htmlFor="multi_host"><i className="fas fa-globe" /> {hostLabel}</label>
                  <input
                    type="text"
                    id="multi_host"
                    className="options_input"
                    placeholder={hostPlaceholder}
                    value={targetForm.host}
                    onChange={(event) => onTargetFormChange((prev) => ({ ...prev, host: event.target.value }))}
                  />
                  <div className="card_subtitle" style={{ margin: 0 }}>{hostHelp}</div>
                </div>
                <div className="options_mail_form_group">
                  <label htmlFor="multi_port"><i className="fas fa-network-wired" /> Port</label>
                  <input type="number" id="multi_port" className="options_input" value={targetForm.port} min={1} max={65535} onChange={(event) => onTargetFormChange((prev) => ({ ...prev, port: Number(event.target.value || 3493) }))} />
                  <div className="card_subtitle" style={{ margin: 0 }}>{portHelp}</div>
                </div>
              </div>
            </div>
            <div className="nut_manager_editor_section">
              <div className="options_mail_form_grid">
                <div className="options_mail_form_group">
                  <label htmlFor="multi_polling_interval" className="nut_manager_inline_label">
                    <span><i className="fas fa-clock" /> Polling Interval (seconds)</span>
                    <button
                      type="button"
                      className="nut_manager_inline_info_btn"
                      title="How polling interval works"
                      onClick={() => setPollingInfoOpen(true)}
                    >
                      <i className="fas fa-info-circle" />
                    </button>
                  </label>
                  <input type="number" id="multi_polling_interval" className="options_input" value={targetForm.polling_interval} min={1} max={60} onChange={(event) => onTargetFormChange((prev) => ({ ...prev, polling_interval: Number(event.target.value || 1) }))} />
                </div>
                <div className="options_mail_form_group">
                  <label htmlFor="multi_timezone"><i className="fas fa-globe" /> Target Timezone</label>
                  <select
                    id="multi_timezone"
                    className="options_input"
                    value={targetForm.timezone}
                    onChange={(event) => onTargetFormChange((prev) => ({ ...prev, timezone: event.target.value }))}
                  >
                    {timezoneOptions.map((timezone) => (
                      <option key={timezone} value={timezone}>{timezone}</option>
                    ))}
                  </select>
                </div>
                <div className="options_mail_form_group">
                  <label htmlFor="multi_currency"><i className="fas fa-coins" /> Target Currency</label>
                  <select
                    id="multi_currency"
                    className="options_input"
                    value={targetForm.currency}
                    onChange={(event) => onTargetFormChange((prev) => ({ ...prev, currency: event.target.value }))}
                  >
                    <option value="EUR">EUR</option>
                    <option value="USD">USD</option>
                    <option value="GBP">GBP</option>
                    <option value="JPY">JPY</option>
                    <option value="AUD">AUD</option>
                    <option value="CAD">CAD</option>
                    <option value="CHF">CHF</option>
                    <option value="CNY">CNY</option>
                    <option value="INR">INR</option>
                  </select>
                </div>
              </div>
              <div className="card_subtitle" style={{ marginTop: '-4px', marginBottom: '2px' }}>
                Database strategy is currently shared-only. Advanced strategy controls will be added in a future update.
              </div>
            </div>
            <div className="nut_manager_editor_section">
              <div className="nut_manager_editor_checklist">
                <label className="nut_manager_checkbox_wrap" htmlFor="multi_enabled">
                  <input type="checkbox" id="multi_enabled" checked={targetForm.enabled} onChange={(event) => onTargetFormChange((prev) => ({ ...prev, enabled: event.target.checked }))} />
                  <span>Enable target</span>
                </label>
                <label className="nut_manager_checkbox_wrap" htmlFor="multi_is_primary">
                  <input type="checkbox" id="multi_is_primary" checked={targetForm.is_primary} onChange={(event) => onTargetFormChange((prev) => ({ ...prev, is_primary: event.target.checked }))} />
                  <span>Set as primary target</span>
                </label>
              </div>
            </div>
            <AdvancedTargetLocationFields
              targetForm={targetForm}
              computedLocation={computedLocation}
              onTargetFormChange={onTargetFormChange}
            />
          </form>
        </div>
      </div>
      {pollingInfoOpen ? (
        <div
          className="modal"
          style={{ display: 'block' }}
          onClick={(event) => event.target === event.currentTarget && setPollingInfoOpen(false)}
        >
          <div className="modal-content options_card">
            <div className="modal-header">
              <h5 className="modal-title">Polling Interval Details</h5>
              <button type="button" className="modal-close" onClick={() => setPollingInfoOpen(false)}>
                <i className="fas fa-times" />
              </button>
            </div>
            <div className="modal-body">
              <p>
                Polling interval controls how often Nutify runs <code>upsc</code> for this target.
                Example: <strong>1 second</strong> means one UPS read every second.
              </p>
              <ul>
                <li>Each polling cycle fetches fresh UPS values for this target.</li>
                <li>Realtime pages are updated immediately from the in-memory stream.</li>
                <li>With 1 second polling you generate about 60 samples per minute for that UPS.</li>
                <li>Those samples feed minute, hour, day, month and year historical rollups.</li>
                <li>Lower intervals improve precision but increase CPU, I/O and database growth.</li>
              </ul>
              <p>
                Recommended baseline: <strong>3-5 seconds</strong> for normal home monitoring.
                Use 1 second only when you really need very fine-grained troubleshooting.
              </p>
            </div>
            <div className="modal-footer">
              <button
                type="button"
                className="options_btn options_btn_secondary modal-close"
                onClick={() => setPollingInfoOpen(false)}
              >
                Close
              </button>
            </div>
          </div>
        </div>
      ) : null}
      {scriptInfoTarget ? (
        <AdvancedScriptInfoModal
          target={scriptInfoTarget}
          onClose={() => setScriptInfoTarget(null)}
        />
      ) : null}
    </div>
  )
}
