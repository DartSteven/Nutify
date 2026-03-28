/**
 * Powerflowsection.
 *
 * Frontend module used by Nutify React UI flows and state management.
 */

import { useEffect, useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { getVariableConfig, saveVariableConfig } from '../../../lib/api/settings'
import { getAllUpsData } from '../../../lib/api/ups'
import { useAppStore } from '../../../store/appStore'

type AlertState = {
  tone: 'success' | 'danger'
  text: string
} | null

type VariablesSnapshot = {
  currency: string
  pricePerKwh: string
  co2Factor: string
  timezone: string
  upsRealpowerNominal: string
}

const CURRENCY_OPTIONS: Array<{ code: string; label: string }> = [
  { code: 'EUR', label: 'Euro (EUR)' },
  { code: 'USD', label: 'US Dollar (USD)' },
  { code: 'GBP', label: 'British Pound (GBP)' },
  { code: 'JPY', label: 'Japanese Yen (JPY)' },
  { code: 'AUD', label: 'Australian Dollar (AUD)' },
  { code: 'CAD', label: 'Canadian Dollar (CAD)' },
  { code: 'CHF', label: 'Swiss Franc (CHF)' },
  { code: 'CNY', label: 'Chinese Yuan (CNY)' },
  { code: 'INR', label: 'Indian Rupee (INR)' },
  { code: 'NZD', label: 'New Zealand Dollar (NZD)' },
  { code: 'BRL', label: 'Brazilian Real (BRL)' },
  { code: 'RUB', label: 'Russian Ruble (RUB)' },
  { code: 'KRW', label: 'South Korean Won (KRW)' },
  { code: 'PLN', label: 'Polish Zloty (PLN)' },
]

const CURRENCY_ICON_MAP: Record<string, string> = {
  EUR: 'fa-euro-sign',
  USD: 'fa-dollar-sign',
  GBP: 'fa-pound-sign',
  JPY: 'fa-yen-sign',
  AUD: 'fa-dollar-sign',
  CAD: 'fa-dollar-sign',
  CHF: 'fa-franc-sign',
  CNY: 'fa-yen-sign',
  INR: 'fa-rupee-sign',
  NZD: 'fa-dollar-sign',
  BRL: 'fa-money-bill',
  RUB: 'fa-ruble-sign',
  KRW: 'fa-won-sign',
  PLN: 'fa-zloty-sign',
}

const CURRENCY_SYMBOL_MAP: Record<string, string> = {
  EUR: 'EUR',
  USD: 'USD',
  GBP: 'GBP',
  JPY: 'JPY',
  AUD: 'AUD',
  CAD: 'CAD',
  CHF: 'CHF',
  CNY: 'CNY',
  INR: 'INR',
  NZD: 'NZD',
  BRL: 'BRL',
  RUB: 'RUB',
  KRW: 'KRW',
  PLN: 'PLN',
}

const FALLBACK_TIMEZONES = [
  'UTC',
  'Europe/Rome',
  'Europe/London',
  'America/New_York',
  'America/Los_Angeles',
  'Asia/Tokyo',
  'Australia/Sydney',
]

const TIMEZONE_GROUPS = [
  'UTC',
  'Africa',
  'America',
  'Antarctica',
  'Asia',
  'Atlantic',
  'Australia',
  'Europe',
  'Indian',
  'Pacific',
]

function getTimezoneOptions(): string[] {
  const intl = Intl as typeof Intl & { supportedValuesOf?: (type: string) => string[] }
  const runtimeTimezones = typeof intl.supportedValuesOf === 'function' ? intl.supportedValuesOf('timeZone') : []
  return [...new Set([...FALLBACK_TIMEZONES, ...runtimeTimezones])].sort((left, right) => left.localeCompare(right))
}

function groupTimezones(timezones: string[]) {
  return TIMEZONE_GROUPS.map((group) => ({
    group,
    values: timezones.filter((timezone) => timezone === group || timezone.startsWith(`${group}/`)),
  })).filter((entry) => entry.values.length > 0)
}

function toSnapshot(payload: Awaited<ReturnType<typeof getVariableConfig>> | undefined): VariablesSnapshot {
  if (!payload) {
    return {
      currency: 'EUR',
      pricePerKwh: '0.2500',
      co2Factor: '0.4000',
      timezone: 'UTC',
      upsRealpowerNominal: '',
    }
  }

  return {
    currency: payload.currency || 'EUR',
    pricePerKwh: Number(payload.price_per_kwh || 0).toFixed(4),
    co2Factor: Number(payload.co2_factor || 0).toFixed(4),
    timezone: payload.timezone || 'UTC',
    upsRealpowerNominal:
      payload.ups_realpower_nominal !== null && payload.ups_realpower_nominal !== undefined
        ? String(payload.ups_realpower_nominal)
        : '',
  }
}

function parseDecimal(raw: string): number {
  const normalized = String(raw || '')
    .trim()
    .replace(',', '.')
  const parsed = Number(normalized)
  return Number.isFinite(parsed) ? parsed : 0
}

function normalizeNominalPower(rawValue: string): number | null {
  const trimmed = String(rawValue || '').trim()
  if (!trimmed) {
    return null
  }

  const parsed = Number(trimmed)
  if (!Number.isFinite(parsed) || !Number.isInteger(parsed) || parsed <= 0) {
    throw new Error('UPS nominal power must be a positive integer.')
  }

  return parsed
}

function extractLiveNominalPower(payload: Record<string, unknown> | undefined): number | null {
  if (!payload) {
    return null
  }

  const candidates = [
    payload['ups.realpower.nominal'],
    payload.ups_realpower_nominal,
    payload.input_realpower_nominal,
    payload.UPS_REALPOWER_NOMINAL,
  ]

  for (const candidate of candidates) {
    const parsed = Number(candidate)
    if (Number.isFinite(parsed) && parsed > 0) {
      return Math.round(parsed)
    }
  }

  return null
}

export function PowerFlowSection() {
  const queryClient = useQueryClient()
  const monitoringProfile = useAppStore((state) => state.bootstrap?.monitoring.monitoring_profile ?? 'single')
  const activeTargetId = useAppStore((state) => state.activeTargetId)
  const targets = useAppStore((state) => state.targets)

  const enabledTargets = useMemo(() => targets.filter((target) => target.enabled !== false), [targets])

  const resolvedTargetId = useMemo(() => {
    if (monitoringProfile === 'multi') {
      const numericTargetId = Number(activeTargetId)
      return Number.isFinite(numericTargetId) && numericTargetId > 0 ? numericTargetId : null
    }
    return activeTargetId
  }, [activeTargetId, monitoringProfile])

  const hasScopedTarget =
    monitoringProfile !== 'multi' || (Number.isFinite(Number(resolvedTargetId)) && Number(resolvedTargetId) > 0)

  const activeTargetName = useMemo(() => {
    const targetName = enabledTargets.find((target) => Number(target.id) === Number(resolvedTargetId))?.name
    if (targetName) {
      return targetName
    }
    if (resolvedTargetId) {
      return `Target #${resolvedTargetId}`
    }
    if (monitoringProfile === 'multi') {
      return 'No target selected'
    }
    return 'Primary target'
  }, [enabledTargets, monitoringProfile, resolvedTargetId])

  const [currency, setCurrency] = useState('EUR')
  const [kwhCost, setKwhCost] = useState('0.2500')
  const [co2Factor, setCo2Factor] = useState('0.4000')
  const [timezone, setTimezone] = useState('UTC')
  const [upsRealpowerNominal, setUpsRealpowerNominal] = useState('')
  const [alert, setAlert] = useState<AlertState>(null)

  const timezoneGroups = useMemo(() => groupTimezones(getTimezoneOptions()), [])

  const configQuery = useQuery({
    queryKey: ['settings', 'variables', resolvedTargetId],
    queryFn: () => getVariableConfig(resolvedTargetId),
    enabled: hasScopedTarget,
  })

  const liveSnapshotQuery = useQuery({
    queryKey: ['settings', 'powerflow-live-snapshot', resolvedTargetId],
    queryFn: () => getAllUpsData(resolvedTargetId),
    enabled: hasScopedTarget,
    refetchInterval: 30_000,
  })

  const initialSnapshot = useMemo(() => toSnapshot(configQuery.data), [configQuery.data])
  const liveNominalPower = useMemo(
    () => extractLiveNominalPower(liveSnapshotQuery.data),
    [liveSnapshotQuery.data],
  )

  useEffect(() => {
    setCurrency(initialSnapshot.currency)
    setKwhCost(initialSnapshot.pricePerKwh)
    setCo2Factor(initialSnapshot.co2Factor)
    setTimezone(initialSnapshot.timezone)
    setUpsRealpowerNominal(initialSnapshot.upsRealpowerNominal)
  }, [initialSnapshot])

  const saveMutation = useMutation({
    mutationFn: () => {
      if (!hasScopedTarget) {
        throw new Error('Select a target before saving PowerFlow settings.')
      }

      const payload: {
        currency: string
        price_per_kwh: number
        co2_factor: number
        timezone: string
        ups_realpower_nominal?: number | null
      } = {
        currency,
        price_per_kwh: parseDecimal(kwhCost),
        co2_factor: parseDecimal(co2Factor),
        timezone,
      }

      const trimmedNominal = String(upsRealpowerNominal || '').trim()
      const previousNominal = String(initialSnapshot.upsRealpowerNominal || '').trim()
      if (trimmedNominal) {
        payload.ups_realpower_nominal = normalizeNominalPower(trimmedNominal)
      } else if (previousNominal) {
        payload.ups_realpower_nominal = null
      }

      return saveVariableConfig(payload, resolvedTargetId)
    },
    onSuccess: async () => {
      setAlert({ tone: 'success', text: 'PowerFlow settings saved successfully.' })
      await queryClient.invalidateQueries({ queryKey: ['settings', 'variables', resolvedTargetId] })
    },
    onError: (error: unknown) => {
      const text = error instanceof Error ? error.message : 'Unable to save PowerFlow settings'
      setAlert({ tone: 'danger', text })
    },
  })

  const resetForm = () => {
    setCurrency(initialSnapshot.currency)
    setKwhCost(initialSnapshot.pricePerKwh)
    setCo2Factor(initialSnapshot.co2Factor)
    setTimezone(initialSnapshot.timezone)
    setUpsRealpowerNominal(initialSnapshot.upsRealpowerNominal)
    setAlert(null)
  }

  const currencyIcon = CURRENCY_ICON_MAP[currency] || 'fa-money-bill'
  const currencySymbol = CURRENCY_SYMBOL_MAP[currency] || currency

  return (
    <div className="combined_card">
      <div className="card_header">
        <div className="notification_header">
          <h2>PowerFlow</h2>
          <div className="options_nutify_actions">
            <button
              type="reset"
              form="variablesConfigForm"
              className="options_btn options_btn_secondary"
              disabled={configQuery.isLoading || saveMutation.isPending || !hasScopedTarget}
            >
              <i className="fas fa-undo" /> Reset
            </button>
            <button
              type="submit"
              form="variablesConfigForm"
              className="options_btn options_btn_primary"
              disabled={configQuery.isLoading || saveMutation.isPending || !hasScopedTarget}
            >
              <i className="fas fa-save" /> {saveMutation.isPending ? 'Saving...' : 'Save Changes'}
            </button>
          </div>
        </div>
        <p className="card_subtitle">
          {monitoringProfile === 'multi'
            ? `PowerFlow settings for ${activeTargetName}. Target selection is controlled from the TopBar UPS selector.`
            : 'PowerFlow settings for your primary UPS: currency, costs, timezone and nominal power fallback.'}
        </p>
      </div>

      <form
        id="variablesConfigForm"
        onSubmit={(event) => {
          event.preventDefault()
          saveMutation.mutate()
        }}
        onReset={(event) => {
          event.preventDefault()
          resetForm()
        }}
      >
        {!hasScopedTarget ? (
          <p className="card_subtitle">Select a UPS from the TopBar target menu to edit PowerFlow settings.</p>
        ) : (
          <>
            <div className="stats_grid stats_grid--three">
              <div className="stat_card">
                <div className="stat-icon">
                  <i id="currencyIcon" className={`fas ${currencyIcon}`} />
                </div>
                <div className="stat-content">
                  <label htmlFor="currency">Currency</label>
                  <select
                    id="currency"
                    name="currency"
                    value={currency}
                    onChange={(event) => setCurrency(event.target.value)}
                    required
                  >
                    {CURRENCY_OPTIONS.map((option) => (
                      <option key={option.code} value={option.code}>
                        {option.label}
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              <div className="stat_card">
                <div className="stat-icon">
                  <i className="fas fa-bolt" />
                </div>
                <div className="stat-content">
                  <label htmlFor="kwh_cost">Cost per kWh</label>
                  <div className="input-with-icon">
                    <input
                      type="number"
                      id="kwh_cost"
                      name="kwh_cost"
                      value={kwhCost}
                      onChange={(event) => setKwhCost(event.target.value)}
                      step="0.001"
                      min="0"
                      required
                    />
                    <span id="currencySymbol">{currencySymbol}</span>
                  </div>
                </div>
              </div>

              <div className="stat_card">
                <div className="stat-icon">
                  <i className="fas fa-leaf" />
                </div>
                <div className="stat-content">
                  <label htmlFor="co2_factor">CO₂ Factor</label>
                  <div className="input-with-icon">
                    <input
                      type="number"
                      id="co2_factor"
                      name="co2_factor"
                      value={co2Factor}
                      onChange={(event) => setCo2Factor(event.target.value)}
                      step="0.001"
                      min="0"
                      required
                    />
                    <span>kg/kWh</span>
                  </div>
                </div>
              </div>
            </div>

            <div className="stats_grid" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))' }}>
              <div className="stat_card">
                <div className="stat-icon">
                  <i className="fas fa-globe" />
                </div>
                <div className="stat-content">
                  <label htmlFor="target_timezone">Timezone</label>
                  <select
                    id="target_timezone"
                    className="options_input form-select dropdown-below"
                    value={timezone}
                    onChange={(event) => setTimezone(event.target.value)}
                  >
                    {timezoneGroups.map((group) => (
                      <optgroup key={group.group} label={group.group}>
                        {group.values.map((timezoneOption) => (
                          <option key={timezoneOption} value={timezoneOption}>
                            {timezoneOption}
                          </option>
                        ))}
                      </optgroup>
                    ))}
                  </select>
                </div>
              </div>

              <div className="stat_card">
                <div className="stat-icon">
                  <i className="fas fa-plug-circle-bolt" />
                </div>
                <div className="stat-content">
                  <label htmlFor="target_ups_realpower_nominal">UPS Nominal Power Fallback (W)</label>
                  <div className="input-with-icon">
                    <input
                      type="number"
                      id="target_ups_realpower_nominal"
                      className="options_input"
                      placeholder={liveNominalPower ? `Detected by UPS: ${liveNominalPower}` : 'e.g. 900'}
                      min={1}
                      value={upsRealpowerNominal}
                      onChange={(event) => setUpsRealpowerNominal(event.target.value)}
                    />
                    <span>W</span>
                  </div>
                  <p className="card_subtitle" style={{ marginTop: '8px', marginBottom: 0 }}>
                    {liveNominalPower
                      ? `Live UPS value detected: ${liveNominalPower} W. Leave this empty unless you want a manual fallback stored in PowerFlow.`
                      : 'Optional manual fallback used only when the UPS does not expose `ups.realpower.nominal` in live data.'}
                  </p>
                </div>
              </div>
            </div>
          </>
        )}

        <div id="variablesStatus" className={`options_alert ${alert ? '' : 'hidden'}`}>
          {alert ? alert.text : ''}
        </div>
      </form>
    </div>
  )
}
