/**
 * Operationssection.
 *
 * Frontend module used by Nutify React UI flows and state management.
 */

import { useEffect, useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { getOperationSettings, saveOperationSettings } from '../../../lib/api/settings'
import { getRenamerCatalog } from '../../../lib/api/multiNut'
import { useAppStore } from '../../../store/appStore'
import { OperationsComputationTable } from './operations/OperationsComputationTable'

type AlertState = {
  tone: 'success' | 'danger'
  text: string
} | null

type OperationsSnapshot = {
  measuredPowerMetricKey: string
  loadMetricKey: string
  nominalPowerMetricKey: string
  realpowerFormula: string
  powerCalibrationFactor: number
  energyFormula: string
  costFormula: string
  co2Formula: string
}

function toSnapshot(payload: Awaited<ReturnType<typeof getOperationSettings>> | undefined): OperationsSnapshot {
  if (!payload) {
    return {
      measuredPowerMetricKey: 'ups_realpower',
      loadMetricKey: 'ups_load',
      nominalPowerMetricKey: 'ups_realpower_nominal',
      realpowerFormula: '(load_percent / 100.0) * nominal_power_w',
      powerCalibrationFactor: 1.0,
      energyFormula: 'power_w * delta_hours',
      costFormula: '(energy_wh / 1000.0) * price_per_kwh',
      co2Formula: '(energy_wh / 1000.0) * co2_factor',
    }
  }

  return {
    measuredPowerMetricKey: payload.measured_power_metric_key || 'ups_realpower',
    loadMetricKey: payload.load_metric_key || 'ups_load',
    nominalPowerMetricKey: payload.nominal_power_metric_key || 'ups_realpower_nominal',
    realpowerFormula: payload.realpower_formula || '(load_percent / 100.0) * nominal_power_w',
    powerCalibrationFactor: Number(payload.power_calibration_factor ?? 1.0),
    energyFormula: payload.energy_formula || 'power_w * delta_hours',
    costFormula: payload.cost_formula || '(energy_wh / 1000.0) * price_per_kwh',
    co2Formula: payload.co2_formula || '(energy_wh / 1000.0) * co2_factor',
  }
}

function sanitizeMetricKey(value: string): string {
  return String(value || '')
    .trim()
    .replace(/\s+/g, '')
    .toLowerCase()
}

function dedupeStrings(values: string[]): string[] {
  const seen = new Set<string>()
  const result: string[] = []

  values.forEach((value) => {
    const normalized = String(value || '').trim()
    if (!normalized) return

    const key = normalized.toLowerCase()
    if (seen.has(key)) return

    seen.add(key)
    result.push(normalized)
  })

  return result
}

function toFiniteNumber(value: unknown): number | null {
  const parsed = Number(value)
  if (!Number.isFinite(parsed)) {
    return null
  }
  return parsed
}

function readMetricValue(metrics: Record<string, unknown>, metricKey: string): number | null {
  const normalized = sanitizeMetricKey(metricKey)
  if (!normalized) {
    return null
  }

  const candidates = [
    normalized,
    normalized.replace(/\./g, '_'),
    normalized.replace(/_/g, '.'),
  ]

  for (const key of candidates) {
    if (!(key in metrics)) {
      continue
    }
    const parsed = toFiniteNumber(metrics[key])
    if (parsed !== null) {
      return parsed
    }
  }

  return null
}

function formatWattPreview(value: number): string {
  if (value >= 100) {
    return `${value.toFixed(1)} W`
  }
  return `${value.toFixed(2)} W`
}

export function OperationsSection() {
  const queryClient = useQueryClient()
  const activeTargetId = useAppStore((state) => state.activeTargetId)
  const targets = useAppStore((state) => state.targets)
  const hasActiveTarget = typeof activeTargetId === 'number' && activeTargetId > 0

  const [measuredPowerMetricKey, setMeasuredPowerMetricKey] = useState('ups_realpower')
  const [loadMetricKey, setLoadMetricKey] = useState('ups_load')
  const [nominalPowerMetricKey, setNominalPowerMetricKey] = useState('ups_realpower_nominal')
  const [realpowerFormula, setRealpowerFormula] = useState('(load_percent / 100.0) * nominal_power_w')
  const [powerCalibrationFactor, setPowerCalibrationFactor] = useState(1.0)
  const [energyFormula, setEnergyFormula] = useState('power_w * delta_hours')
  const [costFormula, setCostFormula] = useState('(energy_wh / 1000.0) * price_per_kwh')
  const [co2Formula, setCo2Formula] = useState('(energy_wh / 1000.0) * co2_factor')
  const [latestRealtimeMetrics, setLatestRealtimeMetrics] = useState<Record<string, unknown>>({})
  const [alert, setAlert] = useState<AlertState>(null)

  const operationsQuery = useQuery({
    queryKey: ['settings', 'operations', activeTargetId],
    queryFn: () => getOperationSettings(activeTargetId),
  })

  const sourceKeysQuery = useQuery({
    queryKey: ['settings', 'operations', 'source-keys', activeTargetId],
    queryFn: async () => {
      if (!hasActiveTarget || activeTargetId === null) {
        return [] as string[]
      }

      const catalog = await getRenamerCatalog(activeTargetId)
      return dedupeStrings(catalog.source_keys || [])
    },
    enabled: hasActiveTarget,
    staleTime: 30_000,
  })

  const enabledTargets = useMemo(
    () => (targets || []).filter((target) => target.enabled !== false),
    [targets],
  )

  const activeTargetLabel = useMemo(() => {
    if (!hasActiveTarget || !enabledTargets.length) {
      return 'No active UPS target'
    }
    const match = enabledTargets.find((target) => target.id === activeTargetId)
    if (!match) {
      return `Target #${activeTargetId}`
    }
    const host = match.host || '-'
    return `${match.name} (${match.ups_name}@${host})`
  }, [activeTargetId, enabledTargets, hasActiveTarget])

  const initialSnapshot = useMemo(() => toSnapshot(operationsQuery.data), [operationsQuery.data])

  useEffect(() => {
    setMeasuredPowerMetricKey(initialSnapshot.measuredPowerMetricKey)
    setLoadMetricKey(initialSnapshot.loadMetricKey)
    setNominalPowerMetricKey(initialSnapshot.nominalPowerMetricKey)
    setRealpowerFormula(initialSnapshot.realpowerFormula)
    setPowerCalibrationFactor(initialSnapshot.powerCalibrationFactor)
    setEnergyFormula(initialSnapshot.energyFormula)
    setCostFormula(initialSnapshot.costFormula)
    setCo2Formula(initialSnapshot.co2Formula)
  }, [initialSnapshot])

  const sourceMetricOptions = useMemo(
    () =>
      dedupeStrings([
        measuredPowerMetricKey,
        loadMetricKey,
        nominalPowerMetricKey,
        'ups_realpower',
        'ups_load',
        'ups_realpower_nominal',
        ...(sourceKeysQuery.data || []),
      ]),
    [loadMetricKey, measuredPowerMetricKey, nominalPowerMetricKey, sourceKeysQuery.data],
  )

  const realpowerFormulaOptions = useMemo(
    () =>
      dedupeStrings([
        'load_percent',
        'nominal_power_w',
        'ups.load',
        'ups.realpower.nominal',
        ...sourceMetricOptions,
      ]),
    [sourceMetricOptions],
  )

  const energyFormulaOptions = useMemo(() => ['power_w', 'delta_hours', 'energy_wh'], [])
  const costFormulaOptions = useMemo(() => ['energy_wh', 'price_per_kwh', 'cost'], [])
  const co2FormulaOptions = useMemo(() => ['energy_wh', 'co2_factor', 'co2_kg'], [])

  useEffect(() => {
    const onRealtimeMessage = (event: Event) => {
      const detail = (event as CustomEvent<unknown>).detail
      if (!detail || typeof detail !== 'object' || Array.isArray(detail)) {
        return
      }
      setLatestRealtimeMetrics(detail as Record<string, unknown>)
    }

    window.addEventListener('websocket_message', onRealtimeMessage as EventListener)
    return () => {
      window.removeEventListener('websocket_message', onRealtimeMessage as EventListener)
    }
  }, [])

  const calibrationPreviewText = useMemo(() => {
    const directMeasured = readMetricValue(latestRealtimeMetrics, measuredPowerMetricKey)
    const loadPercent = readMetricValue(latestRealtimeMetrics, loadMetricKey)
    const nominalPower = readMetricValue(latestRealtimeMetrics, nominalPowerMetricKey)

    if (loadPercent === null || nominalPower === null) {
      if (directMeasured !== null) {
        return `Measured: ${formatWattPreview(Math.max(0, directMeasured))} | Fallback preview: waiting for load/nominal`
      }
      return 'Fallback preview: waiting for realtime UPS values (load + nominal power)'
    }

    const fallbackBase = Math.max(0, (loadPercent / 100) * nominalPower)
    const calibrated = Math.max(0, fallbackBase * (Number.isFinite(powerCalibrationFactor) ? powerCalibrationFactor : 1))
    if (directMeasured !== null) {
      return `Fallback preview: ${formatWattPreview(calibrated)} | Measured now: ${formatWattPreview(Math.max(0, directMeasured))}`
    }

    return `Fallback preview: ${formatWattPreview(calibrated)} (measured power missing)`
  }, [latestRealtimeMetrics, loadMetricKey, measuredPowerMetricKey, nominalPowerMetricKey, powerCalibrationFactor])

  const saveMutation = useMutation({
    mutationFn: () =>
      saveOperationSettings(
        {
          measured_power_metric_key: sanitizeMetricKey(measuredPowerMetricKey),
          load_metric_key: sanitizeMetricKey(loadMetricKey),
          nominal_power_metric_key: sanitizeMetricKey(nominalPowerMetricKey),
          realpower_formula: realpowerFormula.trim(),
          power_calibration_factor: Number.isFinite(powerCalibrationFactor) ? powerCalibrationFactor : 1.0,
          energy_formula: energyFormula.trim(),
          cost_formula: costFormula.trim(),
          co2_formula: co2Formula.trim(),
        },
        activeTargetId,
      ),
    onSuccess: async () => {
      setAlert({ tone: 'success', text: 'Operations formulas saved successfully.' })
      await queryClient.invalidateQueries({ queryKey: ['settings', 'operations', activeTargetId] })
    },
    onError: (error: unknown) => {
      const text = error instanceof Error ? error.message : 'Unable to save operation settings'
      setAlert({ tone: 'danger', text })
    },
  })

  const resetForm = () => {
    setMeasuredPowerMetricKey(initialSnapshot.measuredPowerMetricKey)
    setLoadMetricKey(initialSnapshot.loadMetricKey)
    setNominalPowerMetricKey(initialSnapshot.nominalPowerMetricKey)
    setRealpowerFormula(initialSnapshot.realpowerFormula)
    setPowerCalibrationFactor(initialSnapshot.powerCalibrationFactor)
    setEnergyFormula(initialSnapshot.energyFormula)
    setCostFormula(initialSnapshot.costFormula)
    setCo2Formula(initialSnapshot.co2Formula)
    setAlert(null)
  }

  return (
    <div className="combined_card">
      <div className="card_header">
        <div className="notification_header">
          <h2>Operations</h2>
          <div className="options_nutify_actions">
            <button
              type="reset"
              form="operationsConfigForm"
              className="options_btn options_btn_secondary"
              disabled={operationsQuery.isLoading || saveMutation.isPending}
            >
              <i className="fas fa-undo" /> Reset
            </button>
            <button
              type="submit"
              form="operationsConfigForm"
              className="options_btn options_btn_primary"
              disabled={operationsQuery.isLoading || saveMutation.isPending}
            >
              <i className="fas fa-save" /> {saveMutation.isPending ? 'Saving...' : 'Save Changes'}
            </button>
          </div>
        </div>
        <p className="card_subtitle">
          Configure how Nutify calculates real power, energy, cost, and CO2 using UPS variables and editable formulas.
        </p>
        <p className="card_subtitle" style={{ marginTop: '6px' }}>
          Target scope is controlled by the TopBar UPS selector.
        </p>
      </div>

      <form
        id="operationsConfigForm"
        onSubmit={(event) => {
          event.preventDefault()
          saveMutation.mutate()
        }}
        onReset={(event) => {
          event.preventDefault()
          resetForm()
        }}
      >
        <div className="options_card" style={{ marginBottom: '14px' }}>
          <div className="card_header">
            <h2>How to use this page</h2>
            <p className="card_subtitle">
              This section controls only computation logic. It does not change UPS hardware settings.
            </p>
          </div>
          <div className="p-4">
            <p className="card_subtitle" style={{ marginBottom: '8px' }}>
              Select the UPS from TopBar, then pick variables for measured power, load and nominal power.
            </p>
            <p className="card_subtitle" style={{ marginBottom: '8px' }}>
              If measured real power is missing, tune calibration until Nutify matches your UPS display or wall meter.
            </p>
            <p className="card_subtitle" style={{ marginBottom: '8px' }}>
              For each formula use one mode only: <strong>Manual</strong> (free formula) or <strong>Guided</strong> (dropdown variable builder).
            </p>
            <p className="card_subtitle" style={{ marginBottom: '8px' }}>
              Save changes, then verify Main, Energy, Power, Battery and Voltage values for the same target.
            </p>
            <p className="card_subtitle" style={{ marginBottom: 0 }}>
              Active target: <strong>{activeTargetLabel}</strong>. Variable suggestions come from live/source UPS payload keys for this target.
              {sourceKeysQuery.isLoading ? ' Loading source keys...' : ''}
              {!sourceKeysQuery.isLoading ? ` Available keys: ${sourceMetricOptions.length}` : ''}
            </p>
          </div>
        </div>

        <div className="options_card">
          <div className="card_header">
            <h2>Computation rows</h2>
            <p className="card_subtitle">One row per mapping/formula. Update the value column and save.</p>
          </div>
          <div className="p-4">
            <OperationsComputationTable
              measuredPowerMetricKey={measuredPowerMetricKey}
              onMeasuredPowerMetricKeyChange={setMeasuredPowerMetricKey}
              loadMetricKey={loadMetricKey}
              onLoadMetricKeyChange={setLoadMetricKey}
              nominalPowerMetricKey={nominalPowerMetricKey}
              onNominalPowerMetricKeyChange={setNominalPowerMetricKey}
              realpowerFormula={realpowerFormula}
              onRealpowerFormulaChange={setRealpowerFormula}
              realpowerFormulaOptions={realpowerFormulaOptions}
              powerCalibrationFactor={powerCalibrationFactor}
              onPowerCalibrationFactorChange={setPowerCalibrationFactor}
              calibrationPreviewText={calibrationPreviewText}
              energyFormula={energyFormula}
              onEnergyFormulaChange={setEnergyFormula}
              energyFormulaOptions={energyFormulaOptions}
              costFormula={costFormula}
              onCostFormulaChange={setCostFormula}
              costFormulaOptions={costFormulaOptions}
              co2Formula={co2Formula}
              onCo2FormulaChange={setCo2Formula}
              co2FormulaOptions={co2FormulaOptions}
              sourceMetricOptions={sourceMetricOptions}
            />

            <div className="card_subtitle" style={{ marginTop: '10px' }}>
              Supported formula variables: load_percent, nominal_power_w, power_w, delta_hours, energy_wh, price_per_kwh, co2_factor.
            </div>
          </div>
        </div>

        <div id="operationsStatus" className={`options_alert ${alert ? '' : 'hidden'}`}>
          {alert ? `${alert.tone === 'danger' ? 'Error: ' : ''}${alert.text}` : ''}
        </div>
      </form>
    </div>
  )
}
