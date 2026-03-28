/**
 * Operationscomputationtable.
 *
 * Frontend module used by Nutify React UI flows and state management.
 */

import { useEffect, useMemo, useState } from 'react'
import {
  type FormulaMode,
  type GuidedBinding,
  FormulaModeSwitch,
  GuidedFormulaRow,
  buildCo2Formula,
  buildCostFormula,
  buildEnergyFormula,
  buildRealPowerFormula,
  resolveGuidedBinding,
} from './FormulaBuilders'

type OperationsComputationTableProps = {
  measuredPowerMetricKey: string
  onMeasuredPowerMetricKeyChange: (value: string) => void
  loadMetricKey: string
  onLoadMetricKeyChange: (value: string) => void
  nominalPowerMetricKey: string
  onNominalPowerMetricKeyChange: (value: string) => void
  realpowerFormula: string
  onRealpowerFormulaChange: (value: string) => void
  realpowerFormulaOptions: string[]
  powerCalibrationFactor: number
  onPowerCalibrationFactorChange: (value: number) => void
  calibrationPreviewText: string
  energyFormula: string
  onEnergyFormulaChange: (value: string) => void
  energyFormulaOptions: string[]
  costFormula: string
  onCostFormulaChange: (value: string) => void
  costFormulaOptions: string[]
  co2Formula: string
  onCo2FormulaChange: (value: string) => void
  co2FormulaOptions: string[]
  sourceMetricOptions: string[]
}


export function OperationsComputationTable({
  measuredPowerMetricKey,
  onMeasuredPowerMetricKeyChange,
  loadMetricKey,
  onLoadMetricKeyChange,
  nominalPowerMetricKey,
  onNominalPowerMetricKeyChange,
  realpowerFormula,
  onRealpowerFormulaChange,
  realpowerFormulaOptions,
  powerCalibrationFactor,
  onPowerCalibrationFactorChange,
  calibrationPreviewText,
  energyFormula,
  onEnergyFormulaChange,
  energyFormulaOptions,
  costFormula,
  onCostFormulaChange,
  costFormulaOptions,
  co2Formula,
  onCo2FormulaChange,
  co2FormulaOptions,
  sourceMetricOptions,
}: OperationsComputationTableProps) {
  const [realpowerMode, setRealpowerMode] = useState<FormulaMode>('manual')
  const [energyMode, setEnergyMode] = useState<FormulaMode>('manual')
  const [costMode, setCostMode] = useState<FormulaMode>('manual')
  const [co2Mode, setCo2Mode] = useState<FormulaMode>('manual')

  const [realpowerGuided, setRealpowerGuided] = useState<GuidedBinding>({ left: 'load_percent', right: 'nominal_power_w' })
  const [energyGuided, setEnergyGuided] = useState<GuidedBinding>({ left: 'power_w', right: 'delta_hours' })
  const [costGuided, setCostGuided] = useState<GuidedBinding>({ left: 'energy_wh', right: 'price_per_kwh' })
  const [co2Guided, setCo2Guided] = useState<GuidedBinding>({ left: 'energy_wh', right: 'co2_factor' })

  const realpowerOptions = useMemo(
    () => (realpowerFormulaOptions.length > 0 ? realpowerFormulaOptions : ['load_percent', 'nominal_power_w']),
    [realpowerFormulaOptions],
  )

  const energyOptions = useMemo(
    () => (energyFormulaOptions.length > 0 ? energyFormulaOptions : ['power_w', 'delta_hours', 'energy_wh']),
    [energyFormulaOptions],
  )

  const costOptions = useMemo(
    () => (costFormulaOptions.length > 0 ? costFormulaOptions : ['energy_wh', 'price_per_kwh', 'cost']),
    [costFormulaOptions],
  )

  const co2Options = useMemo(
    () => (co2FormulaOptions.length > 0 ? co2FormulaOptions : ['energy_wh', 'co2_factor', 'co2_kg']),
    [co2FormulaOptions],
  )

  useEffect(() => {
    setRealpowerGuided(resolveGuidedBinding(realpowerFormula, realpowerOptions, 'load_percent', 'nominal_power_w'))
  }, [realpowerFormula, realpowerOptions])

  useEffect(() => {
    setEnergyGuided(resolveGuidedBinding(energyFormula, energyOptions, 'power_w', 'delta_hours'))
  }, [energyFormula, energyOptions])

  useEffect(() => {
    setCostGuided(resolveGuidedBinding(costFormula, costOptions, 'energy_wh', 'price_per_kwh'))
  }, [costFormula, costOptions])

  useEffect(() => {
    setCo2Guided(resolveGuidedBinding(co2Formula, co2Options, 'energy_wh', 'co2_factor'))
  }, [co2Formula, co2Options])

  const updateGuidedFormula = (mode: FormulaMode, setter: (value: string) => void, expression: string) => {
    if (mode === 'guided') {
      setter(expression)
    }
  }

  return (
    <table className="doc-table" style={{ tableLayout: 'fixed', width: '100%' }}>
      <thead>
        <tr>
          <th style={{ width: '14%' }}>Setting</th>
          <th style={{ width: '21%' }}>What it controls</th>
          <th style={{ width: '65%' }}>Value</th>
        </tr>
      </thead>
      <tbody>
        <tr>
          <td><strong>Measured Power Variable</strong></td>
          <td>Primary source for real-time watts when directly available in UPS data.</td>
          <td>
            <input
              id="measured_power_metric_key"
              name="measured_power_metric_key"
              list="operationsSourceKeys"
              className="options_input"
              style={{ width: '100%', fontFamily: 'var(--font-mono, monospace)' }}
              value={measuredPowerMetricKey}
              onChange={(event) => onMeasuredPowerMetricKeyChange(event.target.value)}
              placeholder="ups_realpower"
            />
          </td>
        </tr>
        <tr>
          <td><strong>Load Variable</strong></td>
          <td>Load percentage variable used by the fallback real power formula.</td>
          <td>
            <input
              id="load_metric_key"
              name="load_metric_key"
              list="operationsSourceKeys"
              className="options_input"
              style={{ width: '100%', fontFamily: 'var(--font-mono, monospace)' }}
              value={loadMetricKey}
              onChange={(event) => onLoadMetricKeyChange(event.target.value)}
              placeholder="ups_load"
            />
          </td>
        </tr>
        <tr>
          <td><strong>Nominal Power Variable</strong></td>
          <td>Nominal watts variable used with load percentage when measured watts are missing.</td>
          <td>
            <input
              id="nominal_power_metric_key"
              name="nominal_power_metric_key"
              list="operationsSourceKeys"
              className="options_input"
              style={{ width: '100%', fontFamily: 'var(--font-mono, monospace)' }}
              value={nominalPowerMetricKey}
              onChange={(event) => onNominalPowerMetricKeyChange(event.target.value)}
              placeholder="ups_realpower_nominal"
            />
          </td>
        </tr>
        <tr>
          <td><strong>Real Power Formula (W)</strong></td>
          <td>Choose manual editing or guided template with variable menus.</td>
          <td>
            <FormulaModeSwitch
              value={realpowerMode}
              onChange={(next) => {
                setRealpowerMode(next)
                if (next === 'guided') {
                  onRealpowerFormulaChange(buildRealPowerFormula(realpowerGuided))
                }
              }}
            />
            {realpowerMode === 'manual' ? (
              <input
                id="realpower_formula"
                name="realpower_formula"
                className="options_input"
                style={{ width: '100%', fontFamily: 'var(--font-mono, monospace)', fontSize: '0.95rem' }}
                value={realpowerFormula}
                onChange={(event) => onRealpowerFormulaChange(event.target.value)}
                placeholder="(load_percent / 100.0) * nominal_power_w"
              />
            ) : (
              <>
                <GuidedFormulaRow
                  leftValue={realpowerGuided.left}
                  rightValue={realpowerGuided.right}
                  options={realpowerOptions}
                  onLeftChange={(value) => {
                    const next = { ...realpowerGuided, left: value }
                    setRealpowerGuided(next)
                    updateGuidedFormula(realpowerMode, onRealpowerFormulaChange, buildRealPowerFormula(next))
                  }}
                  onRightChange={(value) => {
                    const next = { ...realpowerGuided, right: value }
                    setRealpowerGuided(next)
                    updateGuidedFormula(realpowerMode, onRealpowerFormulaChange, buildRealPowerFormula(next))
                  }}
                  leftSuffix=" / 100.0"
                  middleText=") *"
                  rightPrefix=""
                />
                <div className="card_subtitle" style={{ marginTop: '8px' }}>
                  Result: <code>{buildRealPowerFormula(realpowerGuided)}</code>
                </div>
              </>
            )}
          </td>
        </tr>
        <tr>
          <td><strong>Power Calibration Factor</strong></td>
          <td>Multiplier applied only to fallback real power when measured power is missing.</td>
          <td>
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px', flexWrap: 'wrap' }}>
              <input
                id="power_calibration_factor"
                name="power_calibration_factor"
                type="number"
                className="options_input"
                style={{
                  width: '120px',
                  minWidth: '120px',
                  fontFamily: 'var(--font-mono, monospace)',
                  fontSize: '0.95rem',
                }}
                value={powerCalibrationFactor}
                min={0.1}
                max={3}
                step={0.01}
                onChange={(event) => onPowerCalibrationFactorChange(Number(event.target.value || 1))}
                placeholder="1.00"
              />
              <span className="card_subtitle" style={{ margin: 0 }}>
                {calibrationPreviewText}
              </span>
            </div>
          </td>
        </tr>
        <tr>
          <td><strong>Energy Formula (Wh)</strong></td>
          <td>Choose manual editing or guided template with variable menus.</td>
          <td>
            <FormulaModeSwitch
              value={energyMode}
              onChange={(next) => {
                setEnergyMode(next)
                if (next === 'guided') {
                  onEnergyFormulaChange(buildEnergyFormula(energyGuided))
                }
              }}
            />
            {energyMode === 'manual' ? (
              <input
                id="energy_formula"
                name="energy_formula"
                className="options_input"
                style={{ width: '100%', fontFamily: 'var(--font-mono, monospace)', fontSize: '0.95rem' }}
                value={energyFormula}
                onChange={(event) => onEnergyFormulaChange(event.target.value)}
                placeholder="power_w * delta_hours"
              />
            ) : (
              <>
                <GuidedFormulaRow
                  leftValue={energyGuided.left}
                  rightValue={energyGuided.right}
                  options={energyOptions}
                  onLeftChange={(value) => {
                    const next = { ...energyGuided, left: value }
                    setEnergyGuided(next)
                    updateGuidedFormula(energyMode, onEnergyFormulaChange, buildEnergyFormula(next))
                  }}
                  onRightChange={(value) => {
                    const next = { ...energyGuided, right: value }
                    setEnergyGuided(next)
                    updateGuidedFormula(energyMode, onEnergyFormulaChange, buildEnergyFormula(next))
                  }}
                  leftSuffix=""
                  middleText="*"
                  rightPrefix=""
                />
                <div className="card_subtitle" style={{ marginTop: '8px' }}>
                  Result: <code>{buildEnergyFormula(energyGuided)}</code>
                </div>
              </>
            )}
          </td>
        </tr>
        <tr>
          <td><strong>Cost Formula</strong></td>
          <td>Choose manual editing or guided template with variable menus.</td>
          <td>
            <FormulaModeSwitch
              value={costMode}
              onChange={(next) => {
                setCostMode(next)
                if (next === 'guided') {
                  onCostFormulaChange(buildCostFormula(costGuided))
                }
              }}
            />
            {costMode === 'manual' ? (
              <input
                id="cost_formula"
                name="cost_formula"
                className="options_input"
                style={{ width: '100%', fontFamily: 'var(--font-mono, monospace)', fontSize: '0.95rem' }}
                value={costFormula}
                onChange={(event) => onCostFormulaChange(event.target.value)}
                placeholder="(energy_wh / 1000.0) * price_per_kwh"
              />
            ) : (
              <>
                <GuidedFormulaRow
                  leftValue={costGuided.left}
                  rightValue={costGuided.right}
                  options={costOptions}
                  onLeftChange={(value) => {
                    const next = { ...costGuided, left: value }
                    setCostGuided(next)
                    updateGuidedFormula(costMode, onCostFormulaChange, buildCostFormula(next))
                  }}
                  onRightChange={(value) => {
                    const next = { ...costGuided, right: value }
                    setCostGuided(next)
                    updateGuidedFormula(costMode, onCostFormulaChange, buildCostFormula(next))
                  }}
                  leftSuffix=" / 1000.0"
                  middleText=") *"
                  rightPrefix=""
                />
                <div className="card_subtitle" style={{ marginTop: '8px' }}>
                  Result: <code>{buildCostFormula(costGuided)}</code>
                </div>
              </>
            )}
          </td>
        </tr>
        <tr>
          <td><strong>CO2 Formula</strong></td>
          <td>Choose manual editing or guided template with variable menus.</td>
          <td>
            <FormulaModeSwitch
              value={co2Mode}
              onChange={(next) => {
                setCo2Mode(next)
                if (next === 'guided') {
                  onCo2FormulaChange(buildCo2Formula(co2Guided))
                }
              }}
            />
            {co2Mode === 'manual' ? (
              <input
                id="co2_formula"
                name="co2_formula"
                className="options_input"
                style={{ width: '100%', fontFamily: 'var(--font-mono, monospace)', fontSize: '0.95rem' }}
                value={co2Formula}
                onChange={(event) => onCo2FormulaChange(event.target.value)}
                placeholder="(energy_wh / 1000.0) * co2_factor"
              />
            ) : (
              <>
                <GuidedFormulaRow
                  leftValue={co2Guided.left}
                  rightValue={co2Guided.right}
                  options={co2Options}
                  onLeftChange={(value) => {
                    const next = { ...co2Guided, left: value }
                    setCo2Guided(next)
                    updateGuidedFormula(co2Mode, onCo2FormulaChange, buildCo2Formula(next))
                  }}
                  onRightChange={(value) => {
                    const next = { ...co2Guided, right: value }
                    setCo2Guided(next)
                    updateGuidedFormula(co2Mode, onCo2FormulaChange, buildCo2Formula(next))
                  }}
                  leftSuffix=" / 1000.0"
                  middleText=") *"
                  rightPrefix=""
                />
                <div className="card_subtitle" style={{ marginTop: '8px' }}>
                  Result: <code>{buildCo2Formula(co2Guided)}</code>
                </div>
              </>
            )}
          </td>
        </tr>
      </tbody>
      <datalist id="operationsSourceKeys">
        {sourceMetricOptions.map((option) => (
          <option key={option} value={option} />
        ))}
      </datalist>
    </table>
  )
}
