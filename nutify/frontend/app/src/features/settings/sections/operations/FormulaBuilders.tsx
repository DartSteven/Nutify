/**
 * Formulabuilders.
 *
 * Frontend module used by Nutify React UI flows and state management.
 */

export type FormulaMode = 'manual' | 'guided'

export type GuidedBinding = {
  left: string
  right: string
}

export function extractIdentifiers(expression: string): string[] {
  const matches = String(expression || '').match(/[A-Za-z_][A-Za-z0-9_.]*/g) || []
  const skip = new Set(['max', 'min', 'abs', 'round'])
  return matches.filter((token) => !skip.has(token))
}

export function resolveGuidedBinding(
  expression: string,
  options: string[],
  fallbackLeft: string,
  fallbackRight: string,
): GuidedBinding {
  const tokens = extractIdentifiers(expression)
  const allowed = new Set(options)

  const left = tokens.find((token) => allowed.has(token)) || fallbackLeft
  const right = tokens.find((token) => allowed.has(token) && token !== left) || fallbackRight

  return {
    left: allowed.has(left) ? left : fallbackLeft,
    right: allowed.has(right) ? right : fallbackRight,
  }
}

export function FormulaModeSwitch({
  value,
  onChange,
}: {
  value: FormulaMode
  onChange: (next: FormulaMode) => void
}) {
  return (
    <div style={{ display: 'flex', gap: '8px', marginBottom: '8px' }}>
      <button
        type="button"
        className={value === 'manual' ? 'options_btn options_btn_primary' : 'options_btn options_btn_secondary'}
        style={{ padding: '7px 12px' }}
        onClick={() => onChange('manual')}
      >
        Manual
      </button>
      <button
        type="button"
        className={value === 'guided' ? 'options_btn options_btn_primary' : 'options_btn options_btn_secondary'}
        style={{ padding: '7px 12px' }}
        onClick={() => onChange('guided')}
      >
        Guided
      </button>
    </div>
  )
}

export function GuidedFormulaRow({
  leftValue,
  rightValue,
  options,
  onLeftChange,
  onRightChange,
  leftSuffix,
  middleText,
  rightPrefix,
}: {
  leftValue: string
  rightValue: string
  options: string[]
  onLeftChange: (value: string) => void
  onRightChange: (value: string) => void
  leftSuffix: string
  middleText: string
  rightPrefix: string
}) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
      <span className="card_subtitle" style={{ margin: 0 }}>(</span>
      <select
        className="options_input"
        value={leftValue}
        onChange={(event) => onLeftChange(event.target.value)}
        style={{ width: '250px', maxWidth: '100%' }}
      >
        {options.map((option) => (
          <option key={`left-${option}`} value={option}>
            {option}
          </option>
        ))}
      </select>
      <span className="card_subtitle" style={{ margin: 0 }}>{leftSuffix}</span>
      <span className="card_subtitle" style={{ margin: 0 }}>{middleText}</span>
      <span className="card_subtitle" style={{ margin: 0 }}>{rightPrefix}</span>
      <select
        className="options_input"
        value={rightValue}
        onChange={(event) => onRightChange(event.target.value)}
        style={{ width: '250px', maxWidth: '100%' }}
      >
        {options.map((option) => (
          <option key={`right-${option}`} value={option}>
            {option}
          </option>
        ))}
      </select>
    </div>
  )
}

export function buildRealPowerFormula(binding: GuidedBinding): string {
  return `(${binding.left} / 100.0) * ${binding.right}`
}

export function buildEnergyFormula(binding: GuidedBinding): string {
  return `${binding.left} * ${binding.right}`
}

export function buildCostFormula(binding: GuidedBinding): string {
  return `(${binding.left} / 1000.0) * ${binding.right}`
}

export function buildCo2Formula(binding: GuidedBinding): string {
  return `(${binding.left} / 1000.0) * ${binding.right}`
}
