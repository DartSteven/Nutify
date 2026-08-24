/**
 * Periodtoolbar.
 *
 * Frontend module used by Nutify React UI flows and state management.
 */

import { useEffect, useRef, useState, type ChangeEvent } from 'react'

import {
  ROLLING_PERIOD_OPTIONS,
  resolveRollingPeriod,
  type RollingPeriodPreset,
} from '../lib/utils/reportPeriods'

export type PeriodMode = 'realtime' | 'today' | 'day' | 'range'
type QuickPresetMode = RollingPeriodPreset
type ModeOptionValue = PeriodMode | QuickPresetMode

export type PeriodSelection = {
  mode: PeriodMode
  fromTime: string
  toTime: string
  selectedDate: string
  rangeFrom: string
  rangeTo: string
}

type PeriodToolbarProps = {
  value: PeriodSelection
  onChange: (value: PeriodSelection) => void
  onApply?: () => void
  includeRealtime?: boolean
  disabled?: boolean
}

function nowHHMM() {
  const now = new Date()
  const hours = String(now.getHours()).padStart(2, '0')
  const minutes = String(now.getMinutes()).padStart(2, '0')
  return `${hours}:${minutes}`
}

function todayIso() {
  const now = new Date()
  const year = now.getFullYear()
  const month = String(now.getMonth() + 1).padStart(2, '0')
  const day = String(now.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

function resolveQuickPreset(mode: QuickPresetMode): { rangeFrom: string; rangeTo: string } {
  const range = resolveRollingPeriod(mode)
  return { rangeFrom: range.from, rangeTo: range.to }
}

export function createDefaultPeriodSelection(): PeriodSelection {
  const today = todayIso()
  return {
    mode: 'today',
    fromTime: '00:00',
    toTime: nowHHMM(),
    selectedDate: today,
    rangeFrom: today,
    rangeTo: today,
  }
}

export function createRealtimeWindow() {
  const now = new Date()
  const start = new Date(now.getTime() - 5 * 60 * 1000)
  const fromHours = String(start.getHours()).padStart(2, '0')
  const fromMinutes = String(start.getMinutes()).padStart(2, '0')
  const toHours = String(now.getHours()).padStart(2, '0')
  const toMinutes = String(now.getMinutes()).padStart(2, '0')
  return {
    fromTime: `${fromHours}:${fromMinutes}`,
    toTime: `${toHours}:${toMinutes}`,
  }
}

export function formatPeriodLabel(period: PeriodSelection) {
  if (period.mode === 'realtime') {
    return 'Real Time'
  }
  if (period.mode === 'day') {
    return `Day ${period.selectedDate}`
  }
  if (period.mode === 'range') {
    return `${period.rangeFrom} to ${period.rangeTo}`
  }
  return `Today (${period.fromTime} - ${period.toTime})`
}

export function PeriodToolbar({
  value,
  onChange,
  onApply,
  includeRealtime = true,
  disabled = false,
}: PeriodToolbarProps) {
  const modeOptions: Array<{ value: ModeOptionValue; label: string }> = includeRealtime
    ? [
        { value: 'realtime', label: 'Realtime' },
        { value: 'today', label: 'Today' },
        ...ROLLING_PERIOD_OPTIONS,
        { value: 'day', label: 'Select Day' },
        { value: 'range', label: 'Date Range' },
      ]
    : [
        { value: 'today', label: 'Today' },
        ...ROLLING_PERIOD_OPTIONS,
        { value: 'day', label: 'Select Day' },
        { value: 'range', label: 'Date Range' },
      ]

  const patch = (updates: Partial<PeriodSelection>) => {
    onChange({
      ...value,
      ...updates,
    })
  }

  const onModeChange = (event: ChangeEvent<HTMLSelectElement>) => {
    const nextMode = event.target.value as ModeOptionValue
    if (nextMode === 'last_week' || nextMode === 'last_month' || nextMode === 'last_year') {
      const preset = resolveQuickPreset(nextMode)
      onChange({
        ...value,
        mode: 'range',
        rangeFrom: preset.rangeFrom,
        rangeTo: preset.rangeTo,
      })
      return
    }
    patch({ mode: nextMode as PeriodMode })
  }

  return (
    <div className="card-base space-y-3">
      <div className="grid gap-3 md:grid-cols-5">
        <label className="field-group">
          <span className="field-label">Period</span>
          <select className="input-base" value={value.mode} onChange={onModeChange} disabled={disabled}>
            {modeOptions.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>

        {value.mode === 'today' ? (
          <>
            <label className="field-group">
              <span className="field-label">From</span>
              <input
                className="input-base"
                type="time"
                value={value.fromTime}
                onChange={(event) => patch({ fromTime: event.target.value })}
                disabled={disabled}
              />
            </label>
            <label className="field-group">
              <span className="field-label">To</span>
              <input
                className="input-base"
                type="time"
                value={value.toTime}
                onChange={(event) => patch({ toTime: event.target.value })}
                disabled={disabled}
              />
            </label>
          </>
        ) : null}

        {value.mode === 'day' ? (
          <label className="field-group md:col-span-2">
            <span className="field-label">Selected day</span>
            <input
              className="input-base"
              type="date"
              value={value.selectedDate}
              onChange={(event) => patch({ selectedDate: event.target.value })}
              disabled={disabled}
            />
          </label>
        ) : null}

        {value.mode === 'range' ? (
          <>
            <label className="field-group">
              <span className="field-label">From date</span>
              <input
                className="input-base"
                type="date"
                value={value.rangeFrom}
                onChange={(event) => patch({ rangeFrom: event.target.value })}
                disabled={disabled}
              />
            </label>
            <label className="field-group">
              <span className="field-label">To date</span>
              <input
                className="input-base"
                type="date"
                value={value.rangeTo}
                onChange={(event) => patch({ rangeTo: event.target.value })}
                disabled={disabled}
              />
            </label>
          </>
        ) : null}
      </div>

      {onApply ? (
        <div className="flex justify-end">
          <button className="btn-primary" type="button" onClick={onApply} disabled={disabled}>
            Apply
          </button>
        </div>
      ) : null}
    </div>
  )
}

type PeriodCompactControlProps = {
  value: PeriodSelection
  onChange: (value: PeriodSelection) => void
  onApply?: (value: PeriodSelection) => void
  displayValue?: PeriodSelection
  includeRealtime?: boolean
  disabled?: boolean
}

function formatCompactSummary(period: PeriodSelection) {
  if (period.mode === 'realtime') {
    return 'Real Time'
  }
  if (period.mode === 'day') {
    return `Day ${period.selectedDate}`
  }
  if (period.mode === 'range') {
    return `${period.rangeFrom} - ${period.rangeTo}`
  }
  return `Today (${period.fromTime} - ${period.toTime})`
}

export function PeriodCompactControl({
  value,
  onChange,
  onApply,
  displayValue,
  includeRealtime = true,
  disabled = false,
}: PeriodCompactControlProps) {
  const wrapperRef = useRef<HTMLDivElement>(null)
  const [isOpen, setIsOpen] = useState(false)
  const shownValue = displayValue ?? value

  const modeOptions: Array<{ value: ModeOptionValue; label: string }> = includeRealtime
    ? [
        { value: 'realtime', label: 'Real Time' },
        { value: 'today', label: 'Today' },
        ...ROLLING_PERIOD_OPTIONS,
        { value: 'day', label: 'Select Day' },
        { value: 'range', label: 'Date Range' },
      ]
    : [
        { value: 'today', label: 'Today' },
        ...ROLLING_PERIOD_OPTIONS,
        { value: 'day', label: 'Select Day' },
        { value: 'range', label: 'Date Range' },
      ]

  const patch = (updates: Partial<PeriodSelection>) => {
    onChange({
      ...value,
      ...updates,
    })
  }

  useEffect(() => {
    if (!isOpen) {
      return
    }

    function handleOutsideClick(event: MouseEvent) {
      const target = event.target
      if (!(target instanceof Node)) {
        return
      }
      if (!wrapperRef.current?.contains(target)) {
        setIsOpen(false)
      }
    }

    document.addEventListener('mousedown', handleOutsideClick)
    return () => {
      document.removeEventListener('mousedown', handleOutsideClick)
    }
  }, [isOpen])

  const emitApply = (nextValue: PeriodSelection) => {
    onApply?.(nextValue)
    setIsOpen(false)
  }

  const handleModeSelect = (mode: ModeOptionValue) => {
    if (mode === 'last_week' || mode === 'last_month' || mode === 'last_year') {
      const preset = resolveQuickPreset(mode)
      const nextValue: PeriodSelection = {
        ...value,
        mode: 'range',
        rangeFrom: preset.rangeFrom,
        rangeTo: preset.rangeTo,
      }
      patch(nextValue)
      emitApply(nextValue)
      return
    }

    const nextValue: PeriodSelection = {
      ...value,
      mode: mode as PeriodMode,
    }

    if (mode === 'today') {
      nextValue.fromTime = nextValue.fromTime || '00:00'
      nextValue.toTime = nowHHMM()
    }

    patch(nextValue)

    if (mode === 'realtime') {
      emitApply(nextValue)
    }
  }

  const applyToday = () => {
    emitApply({
      ...value,
      mode: 'today',
      fromTime: value.fromTime || '00:00',
      toTime: value.toTime || nowHHMM(),
    })
  }

  const applyDay = () => {
    if (!value.selectedDate) {
      return
    }
    emitApply({
      ...value,
      mode: 'day',
    })
  }

  const applyRange = () => {
    if (!value.rangeFrom || !value.rangeTo) {
      return
    }
    emitApply({
      ...value,
      mode: 'range',
    })
  }

  const showToday = value.mode === 'today'
  const showDay = value.mode === 'day'
  const showRange = value.mode === 'range'
  const showRealtime = value.mode === 'realtime'

  return (
    <div ref={wrapperRef} className="date_range">
      <button
        type="button"
        className="date-range-btn"
        aria-haspopup="menu"
        aria-expanded={isOpen}
        onClick={() => setIsOpen((open) => !open)}
        disabled={disabled}
      >
        <i className="fas fa-calendar" aria-hidden="true" />
        <span className="selected-range">{formatCompactSummary(shownValue)}</span>
        <i className="fas fa-chevron-down" aria-hidden="true" />
      </button>

      <div className={['date-range-dropdown', isOpen ? '' : 'hidden'].join(' ').trim()}>
        <div className="range-options">
          {modeOptions.map((option) => {
            const isActive = value.mode === option.value
            return (
              <a
                key={option.value}
                href="#"
                data-range={option.value}
                className={isActive ? 'active' : ''}
                onClick={(event) => {
                  event.preventDefault()
                  handleModeSelect(option.value)
                }}
              >
                {option.label}
              </a>
            )
          })}
        </div>

        <div className={['time-range-selector', showToday ? '' : 'hidden'].join(' ').trim()}>
          <div className="time-inputs">
            <div className="time-input-group">
              <label>From:</label>
              <input
                type="time"
                value={value.fromTime}
                onChange={(event) => patch({ fromTime: event.target.value })}
                disabled={disabled}
              />
            </div>
            <div className="time-input-group">
              <label>To:</label>
              <input
                type="time"
                value={value.toTime}
                onChange={(event) => patch({ toTime: event.target.value })}
                disabled={disabled}
              />
            </div>
          </div>
          <div className="time-actions">
            <button className="btn-primary" type="button" onClick={applyToday} disabled={disabled}>
              Apply
            </button>
          </div>
        </div>

        <div className={['day-selector', showDay ? '' : 'hidden'].join(' ').trim()}>
          <div className="day-input-group">
            <input
              className="date-picker"
              type="date"
              value={value.selectedDate}
              onChange={(event) => patch({ selectedDate: event.target.value })}
              disabled={disabled}
            />
          </div>
          <div className="day-actions">
            <button className="btn-primary" type="button" onClick={applyDay} disabled={disabled}>
              Apply
            </button>
          </div>
        </div>

        <div className={['range-selector', showRange ? '' : 'hidden'].join(' ').trim()}>
          <div className="range-inputs">
            <div className="range-input-group">
              <label>From:</label>
              <input
                className="date-picker"
                type="date"
                value={value.rangeFrom}
                onChange={(event) => patch({ rangeFrom: event.target.value })}
                disabled={disabled}
              />
            </div>
            <div className="range-input-group">
              <label>To:</label>
              <input
                className="date-picker"
                type="date"
                value={value.rangeTo}
                onChange={(event) => patch({ rangeTo: event.target.value })}
                disabled={disabled}
              />
            </div>
          </div>
          <div className="range-actions">
            <button className="btn-primary" type="button" onClick={applyRange} disabled={disabled}>
              Apply
            </button>
          </div>
        </div>

        <div className={['realtime-selector', showRealtime ? '' : 'hidden'].join(' ').trim()} />
      </div>
    </div>
  )
}
