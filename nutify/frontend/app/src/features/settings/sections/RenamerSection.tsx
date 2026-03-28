/**
 * Renamersection.
 *
 * Frontend module used by Nutify React UI flows and state management.
 */

import { useCallback, useEffect, useMemo, useState } from 'react'

import { getRenamerCatalog, saveRenamerMappings, type RenamerRow } from '../../../lib/api/multiNut'
import { useAppStore } from '../../../store/appStore'
import { notifyUser } from './mail/utils'

type RenamerUiRow = RenamerRow & {
  manual_source: string
}

type AlertState = {
  tone: 'success' | 'danger'
  message: string
} | null

function normalizeRows(rows: RenamerRow[]): RenamerUiRow[] {
  return rows.map((row) => ({
    ...row,
    selected_source: String(row.selected_source || ''),
    suggested_source: String(row.suggested_source || ''),
    current_source: String(row.current_source || ''),
    source_options: Array.isArray(row.source_options) ? row.source_options : [],
    manual_source: '',
  }))
}

function matchesSearch(row: RenamerUiRow, searchTerm: string): boolean {
  const query = searchTerm.trim().toLowerCase()
  if (!query) return true
  return (
    row.canonical_key.toLowerCase().includes(query) ||
    row.canonical_dot_key.toLowerCase().includes(query) ||
    String(row.selected_source).toLowerCase().includes(query) ||
    String(row.manual_source).toLowerCase().includes(query) ||
    String(row.suggested_source).toLowerCase().includes(query) ||
    String(row.current_source).toLowerCase().includes(query)
  )
}

function statusClass(status: string): string {
  if (status === 'mapped') return 'renamer_row_status_mapped'
  if (status === 'suggested') return 'renamer_row_status_suggested'
  return 'renamer_row_status_unmapped'
}

export function RenamerSection() {
  const storeActiveTargetId = useAppStore((state) => state.activeTargetId)
  const storeTargets = useAppStore((state) => state.targets)
  const [searchValue, setSearchValue] = useState('')
  const [rows, setRows] = useState<RenamerUiRow[]>([])
  const [sourceLabel, setSourceLabel] = useState('Waiting for data source...')
  const [alert, setAlert] = useState<AlertState>(null)
  const [loadingCatalog, setLoadingCatalog] = useState(false)
  const [saving, setSaving] = useState(false)

  const showAlert = useCallback((message: string, tone: 'success' | 'danger') => {
    setAlert({ message, tone })
    notifyUser(message, tone === 'danger' ? 'error' : 'success')
  }, [])

  const enabledTargets = useMemo(
    () => (storeTargets || []).filter((target) => target.enabled !== false),
    [storeTargets],
  )

  const resolvedTargetId = useMemo(() => {
    const activeCandidate = Number(storeActiveTargetId)
    if (Number.isFinite(activeCandidate) && activeCandidate > 0) {
      return activeCandidate
    }
    if (enabledTargets.length > 0) {
      return enabledTargets[0].id
    }
    return null
  }, [enabledTargets, storeActiveTargetId])

  const activeTargetLabel = useMemo(() => {
    if (!resolvedTargetId) {
      return 'No enabled target selected'
    }
    const match = enabledTargets.find((target) => target.id === resolvedTargetId)
    if (!match) {
      return `Target #${resolvedTargetId}`
    }
    return `${match.name} (${match.ups_name}@${match.host})`
  }, [enabledTargets, resolvedTargetId])

  const loadCatalog = useCallback(
    async (targetId: number | null) => {
      if (!targetId || targetId <= 0) {
        setRows([])
        setSourceLabel('No source available.')
        return
      }
      setLoadingCatalog(true)
      setAlert(null)
      try {
        const catalog = await getRenamerCatalog(targetId)
        setRows(normalizeRows(catalog.rows))
        const sourceCount = Array.isArray(catalog.source_keys) ? catalog.source_keys.length : 0
        setSourceLabel(`Source: ${catalog.source_origin || 'none'} | Variables found: ${sourceCount}`)
      } catch (error) {
        const message = error instanceof Error ? error.message : 'Unable to load catalog'
        setRows([])
        setSourceLabel('No source available.')
        showAlert(`Unable to load catalog: ${message}`, 'danger')
      } finally {
        setLoadingCatalog(false)
      }
    },
    [showAlert],
  )

  useEffect(() => {
    void loadCatalog(resolvedTargetId)
  }, [loadCatalog, resolvedTargetId])

  const filteredRows = useMemo(() => rows.filter((row) => matchesSearch(row, searchValue)), [rows, searchValue])

  const renderStatusColor = (status: string): string => {
    if (status === 'mapped') return 'var(--success-color, #28a745)'
    if (status === 'suggested') return 'var(--warning-color, #ff9800)'
    return 'var(--text-secondary, #6c757d)'
  }

  const handleAutofill = () => {
    let updatedRows = 0
    setRows((currentRows) =>
      currentRows.map((row) => {
        if (!row.suggested_source || row.selected_source === row.suggested_source) {
          return row
        }
        updatedRows += 1
        return { ...row, selected_source: row.suggested_source, manual_source: '', status: 'suggested' }
      }),
    )
    showAlert(`Applied ${updatedRows} suggested mappings`, 'success')
  }

  const handleSaveMappings = async () => {
    const targetId = Number(resolvedTargetId)
    if (!Number.isFinite(targetId) || targetId <= 0) {
      showAlert('Select an active target from TopBar before saving mappings.', 'danger')
      return
    }

    const mappings: Record<string, string> = {}
    rows.forEach((row) => {
      const manualSource = String(row.manual_source || '').trim()
      const selectedSource = String(row.selected_source || '').trim()
      const finalSource = manualSource || selectedSource
      if (finalSource) {
        mappings[row.canonical_key] = finalSource
      }
    })

    setSaving(true)
    try {
      await saveRenamerMappings(targetId, mappings, true)
      showAlert('Canonical mapping saved successfully', 'success')
      await loadCatalog(targetId)
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Failed to save mappings'
      showAlert(`Failed to save mappings: ${message}`, 'danger')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div>
      <div className="options_card">
        <div className="card_header">
          <div className="notification_header">
            <h2>Canonical Variable Renamer</h2>
            <div style={{ display: 'flex', gap: '10px', flexWrap: 'wrap' }}>
              <button
                type="button"
                id="renamerRefreshBtn"
                className="options_btn options_btn_secondary"
                onClick={() => void loadCatalog(resolvedTargetId)}
                disabled={loadingCatalog}
              >
                <i className={`fas ${loadingCatalog ? 'fa-spinner fa-spin' : 'fa-sync'}`} /> Refresh
              </button>
              <button type="button" id="renamerAutofillBtn" className="options_btn options_btn_secondary" onClick={handleAutofill} disabled={!rows.length}>
                <i className="fas fa-magic" /> Auto-fill
              </button>
              <button type="button" id="renamerSaveBtn" className="options_btn options_btn_primary" onClick={() => void handleSaveMappings()} disabled={saving || !rows.length}>
                <i className={`fas ${saving ? 'fa-spinner fa-spin' : 'fa-save'}`} /> {saving ? 'Saving...' : 'Save Mapping'}
              </button>
            </div>
          </div>
          <p className="card_subtitle">Map canonical Nutify variables to vendor-specific UPS names. Suggestions are prefilled from live data when available.</p>
        </div>
        <div className="p-4">
          <div id="renamerAlertContainer">
            <div className={`options_alert ${alert ? `options_alert_${alert.tone}` : 'hidden'}`}>
              {alert ? alert.message : ''}
            </div>
          </div>
          <div className="options_mail_form_grid">
            <div className="options_mail_form_group">
              <label htmlFor="renamerSearchInput"><i className="fas fa-search" /> Filter Variables</label>
              <input
                type="text"
                id="renamerSearchInput"
                className="options_input"
                placeholder="Search canonical or source variable"
                value={searchValue}
                onChange={(event) => setSearchValue(event.target.value)}
              />
            </div>
            <div className="options_mail_form_group">
              <label><i className="fas fa-server" /> Active Target</label>
              <div className="card_subtitle">{activeTargetLabel}</div>
            </div>
            <div className="options_mail_form_group">
              <label><i className="fas fa-info-circle" /> Source</label>
              <div id="renamerSourceOrigin" className="card_subtitle">{sourceLabel}</div>
            </div>
          </div>
        </div>
      </div>

      <div className="options_card mt-4">
        <div className="card_header">
          <h2>Canonical Mapping Rows</h2>
          <p className="card_subtitle">One row per canonical variable. Suggested, mapped, and manual source are editable inline.</p>
        </div>
        <div id="renamerRowsContainer" className="p-4 renamer_rows_compact">
          {loadingCatalog ? <p className="card_subtitle">Loading catalog...</p> : null}
          {!loadingCatalog && filteredRows.length === 0 ? <p className="card_subtitle">No variables match the current filter.</p> : null}
          {!loadingCatalog && filteredRows.length > 0 ? (
            <div className="renamer_rows_header">
              <div className="renamer_rows_header_item">Canonical variable</div>
              <div className="renamer_rows_header_item">Suggested source</div>
              <div className="renamer_rows_header_item">Mapped source</div>
              <div className="renamer_rows_header_item">Custom source</div>
              <div className="renamer_rows_header_item renamer_rows_header_item_status">Status</div>
            </div>
          ) : null}
          {!loadingCatalog
            ? filteredRows.map((row) => (
                <div key={row.canonical_key} className="options_notification_card renamer_row_card">
                  <div className="renamer_row_inline">
                    <div className="renamer_row_canonical">
                      <div className="options_nutify_icon renamer_row_icon"><i className="fas fa-code-branch" /></div>
                      <div className="options_nutify_title_container renamer_row_title_container">
                        <span className="options_nutify_title">{row.canonical_key}</span>
                        <span className="options_nutify_description">{row.canonical_dot_key}</span>
                      </div>
                    </div>

                    <div className="renamer_row_field renamer_row_field_suggested">
                      <input
                        type="text"
                        className="options_input"
                        aria-label={`Suggested source for ${row.canonical_key}`}
                        value={row.suggested_source || 'No suggestion'}
                        readOnly
                      />
                    </div>

                    <div className="renamer_row_field renamer_row_field_mapped">
                      <select
                        className="options_input renamer-source-select"
                        aria-label={`Mapped source for ${row.canonical_key}`}
                        value={row.selected_source || ''}
                        onChange={(event) => {
                          const selectedSource = event.target.value
                          setRows((currentRows) =>
                            currentRows.map((currentRow) =>
                              currentRow.canonical_key === row.canonical_key
                                ? {
                                    ...currentRow,
                                    selected_source: selectedSource,
                                    status: selectedSource || currentRow.manual_source.trim() ? 'mapped' : (currentRow.suggested_source ? 'suggested' : 'unmapped'),
                                  }
                                : currentRow,
                            ),
                          )
                        }}
                      >
                        <option value="">-- Unmapped --</option>
                        {row.source_options.map((sourceOption) => (
                          <option key={sourceOption} value={sourceOption}>
                            {sourceOption}
                          </option>
                        ))}
                      </select>
                    </div>

                    <div className="renamer_row_field renamer_row_field_custom">
                      <input
                        type="text"
                        className="options_input"
                        aria-label={`Custom source for ${row.canonical_key}`}
                        placeholder="Type custom source key"
                        value={row.manual_source}
                        onChange={(event) => {
                          const manualSource = event.target.value
                          setRows((currentRows) =>
                            currentRows.map((currentRow) =>
                              currentRow.canonical_key === row.canonical_key
                                ? {
                                    ...currentRow,
                                    manual_source: manualSource,
                                    status: manualSource.trim() || currentRow.selected_source.trim() ? 'mapped' : (currentRow.suggested_source ? 'suggested' : 'unmapped'),
                                  }
                                : currentRow,
                            ),
                          )
                        }}
                      />
                    </div>

                    <div className="renamer_row_status_wrap">
                      <span
                        className={`renamer_row_status ${statusClass(String(row.status || 'unmapped'))}`}
                        style={{ color: renderStatusColor(String(row.status || 'unmapped')) }}
                      >
                        {`Status: ${row.status}`}
                      </span>
                    </div>
                  </div>
                </div>
              ))
            : null}
        </div>
      </div>
    </div>
  )
}
