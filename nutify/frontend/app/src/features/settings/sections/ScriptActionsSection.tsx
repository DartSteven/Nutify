/**
 * Scriptactionssection.
 */

import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  createScriptAction,
  deleteScriptAction,
  getScriptActions,
  testScriptAction,
  updateScriptAction,
  type ScriptActionConfig,
} from '../../../lib/api/settings'
import { useAppStore } from '../../../store/appStore'

type FormState = {
  id: number | null
  name: string
  enabled: boolean
  trigger_event: 'ONBATT' | 'LOWBATT'
  battery_threshold: number
  cooldown_seconds: number
  script_body: string
}

const EMPTY_FORM: FormState = {
  id: null,
  name: '',
  enabled: true,
  trigger_event: 'LOWBATT',
  battery_threshold: 30,
  cooldown_seconds: 300,
  script_body: '#!/bin/sh\n# Example: /usr/local/bin/all-poweroff.sh\n',
}

export function ScriptActionsSection() {
  const activeTargetId = useAppStore((state) => state.activeTargetId)
  const targets = useAppStore((state) => state.targets)
  const [rows, setRows] = useState<ScriptActionConfig[]>([])
  const [form, setForm] = useState<FormState>(EMPTY_FORM)
  const [status, setStatus] = useState<string>('')
  const [busy, setBusy] = useState(false)

  const activeTargetName = useMemo(() => {
    const selected = targets.find((target) => Number(target.id) === Number(activeTargetId))
    return selected?.name || (activeTargetId ? `Target #${activeTargetId}` : 'active UPS target')
  }, [activeTargetId, targets])

  const load = useCallback(async () => {
    const payload = await getScriptActions(activeTargetId)
    const data = Array.isArray(payload.data) ? (payload.data as ScriptActionConfig[]) : []
    setRows(data)
  }, [activeTargetId])

  useEffect(() => {
    void load()
  }, [load])

  const resetForm = () => setForm(EMPTY_FORM)

  const save = async () => {
    setBusy(true)
    setStatus('')
    try {
      const body = {
        name: form.name,
        enabled: form.enabled,
        trigger_event: form.trigger_event,
        battery_threshold: Number(form.battery_threshold),
        cooldown_seconds: Number(form.cooldown_seconds),
        script_body: form.script_body,
      }
      if (form.id) {
        await updateScriptAction(form.id, body, activeTargetId)
        setStatus('Script action updated.')
      } else {
        await createScriptAction(body, activeTargetId)
        setStatus('Script action created.')
      }
      resetForm()
      await load()
    } catch (error) {
      setStatus(error instanceof Error ? error.message : 'Save failed')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="options_card">
      <div className="card_header">
        <h2>Script Actions</h2>
        <p className="card_subtitle">
          Run each script once when <strong>{activeTargetName}</strong> is on battery and charge reaches its threshold. It rearms after recovery.
        </p>
      </div>

      <div style={{ display: 'grid', gap: 12 }}>
        <input className="options_input" placeholder="Action name" value={form.name} onChange={(e) => setForm((p) => ({ ...p, name: e.target.value }))} />
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 10 }}>
          <select className="options_input" value={form.trigger_event} onChange={(e) => setForm((p) => ({ ...p, trigger_event: e.target.value as 'ONBATT' | 'LOWBATT' }))}>
            <option value="LOWBATT">LOWBATT</option>
            <option value="ONBATT">ONBATT</option>
          </select>
          <input className="options_input" type="number" min={0} max={100} value={form.battery_threshold} onChange={(e) => setForm((p) => ({ ...p, battery_threshold: Number(e.target.value) || 0 }))} placeholder="Battery threshold %" />
          <input className="options_input" type="number" min={0} max={86400} value={form.cooldown_seconds} onChange={(e) => setForm((p) => ({ ...p, cooldown_seconds: Number(e.target.value) || 0 }))} placeholder="Cooldown seconds" />
        </div>
        <label style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}>
          <input type="checkbox" checked={form.enabled} onChange={(e) => setForm((p) => ({ ...p, enabled: e.target.checked }))} />
          Enabled
        </label>
        <textarea className="options_input" rows={8} value={form.script_body} onChange={(e) => setForm((p) => ({ ...p, script_body: e.target.value }))} />
        <div style={{ display: 'flex', gap: 8 }}>
          <button className="options_btn" type="button" disabled={busy} onClick={() => void save()}>
            <i className="fas fa-save" /> {form.id ? 'Update' : 'Create'}
          </button>
          <button className="options_btn options_btn_secondary" type="button" onClick={resetForm}>
            <i className="fas fa-undo" /> Reset
          </button>
        </div>
        {status ? <div className="save-status-message">{status}</div> : null}
      </div>

      <div className="users-table-wrapper mt-4">
        <div className="users-table">
          <table>
            <thead>
              <tr>
                <th>Name</th>
                <th>Trigger</th>
                <th>Threshold</th>
                <th>Enabled</th>
                <th>Last Exit</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.id}>
                  <td>{row.name}</td>
                  <td>{row.trigger_event}</td>
                  <td>{row.battery_threshold}%</td>
                  <td>{row.enabled ? 'On' : 'Off'}</td>
                  <td>{row.last_exit_code ?? '-'}</td>
                  <td style={{ display: 'flex', gap: 8 }}>
                    <button className="options_btn options_btn_secondary" type="button" onClick={() => setForm({
                      id: row.id,
                      name: row.name,
                      enabled: row.enabled,
                      trigger_event: row.trigger_event,
                      battery_threshold: row.battery_threshold,
                      cooldown_seconds: row.cooldown_seconds,
                      script_body: row.script_body,
                    })}>
                      <i className="fas fa-pen" /> Edit
                    </button>
                    <button className="options_btn options_btn_secondary" type="button" onClick={async () => { await testScriptAction(row.id, activeTargetId); await load(); setStatus(`Test executed for "${row.name}".`) }}>
                      <i className="fas fa-play" /> Test
                    </button>
                    <button className="options_btn options_btn_danger" type="button" onClick={async () => { await deleteScriptAction(row.id, activeTargetId); await load(); if (form.id === row.id) resetForm() }}>
                      <i className="fas fa-trash" /> Delete
                    </button>
                  </td>
                </tr>
              ))}
              {rows.length === 0 ? (
                <tr>
                  <td colSpan={6}>No script actions configured.</td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
