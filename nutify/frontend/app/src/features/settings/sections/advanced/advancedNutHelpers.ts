/**
 * Advancednuthelpers.
 *
 * Frontend module used by Nutify React UI flows and state management.
 */

import type { MultiNutTarget, MultiNutTargetPayload } from '../../../../lib/api/multiNut'

export type Tone = 'success' | 'danger' | 'info'

export type AlertState = {
  tone: Tone
  message: string
} | null

export type AdvancedNutFile = {
  name: string
  description: string
}

export type TargetForm = MultiNutTargetPayload & {
  id: string
  retention_enabled: boolean
  timezone: string
  currency: string
}

export type InitialSetupForm = {
  server_name: string
  timezone: string
  monitoring_profile: 'single' | 'multi'
  ups_realpower_nominal: string
}

type InitialSetupState = {
  form: InitialSetupForm
  timezones: string[]
}

export const POLLING_OPTIONS = [1, ...Array.from({ length: 30 }, (_, index) => 2 + index * 2)]

export const DEFAULT_TARGET_FORM: TargetForm = {
  id: '',
  name: '',
  ups_name: '',
  host: '',
  port: 3493,
  nut_mode: 'netclient',
  db_strategy: 'shared',
  shard_granularity: 'month',
  separate_db_path: null,
  polling_interval: 1,
  retention_days: 30,
  retention_enabled: false,
  timezone: 'UTC',
  currency: 'EUR',
  notify_scope: 'global',
  enabled: true,
  is_primary: false,
  location_enabled: false,
  location: '',
  location_country: '',
  location_region: '',
  location_city: '',
  location_postal_code: '',
  location_address: '',
  location_latitude: null,
  location_longitude: null,
}

export const DEFAULT_INITIAL_SETUP: InitialSetupForm = {
  server_name: 'UPS',
  timezone: 'Europe/Rome',
  monitoring_profile: 'single',
  ups_realpower_nominal: '',
}

export const COMMON_TIMEZONES = [
  'Europe/Rome',
  'Europe/London',
  'America/New_York',
  'America/Los_Angeles',
  'Asia/Tokyo',
  'Australia/Sydney',
  'UTC',
]

const TIMEZONE_GROUPS = [
  'Africa',
  'America',
  'Antarctica',
  'Asia',
  'Atlantic',
  'Australia',
  'Europe',
  'Indian',
  'Pacific',
  'UTC',
]

export function normalizeFiles(payload: unknown): AdvancedNutFile[] {
  if (!payload || typeof payload !== 'object') return []
  const rows = (payload as { files?: unknown }).files
  if (!Array.isArray(rows)) return []
  return rows
    .map((entry) => {
      if (!entry || typeof entry !== 'object') return null
      const row = entry as Record<string, unknown>
      const name = String(row.name ?? '').trim()
      if (!name) return null
      return {
        name,
        description: String(row.description ?? ''),
      } satisfies AdvancedNutFile
    })
    .filter((entry): entry is AdvancedNutFile => entry !== null)
}

export function normalizeConfig(payload: unknown): {
  content: string
  description: string
  path: string
  modified: string
} {
  if (!payload || typeof payload !== 'object') {
    return { content: '', description: '', path: '', modified: '' }
  }
  const config = (payload as { config?: unknown }).config
  if (!config || typeof config !== 'object') {
    return { content: '', description: '', path: '', modified: '' }
  }
  const row = config as Record<string, unknown>
  return {
    content: String(row.content ?? ''),
    description: String(row.description ?? ''),
    path: String(row.path ?? ''),
    modified: String(row.modified ?? ''),
  }
}

export function normalizeDocs(payload: unknown): Array<{ key: string; description: string }> {
  if (!payload || typeof payload !== 'object') return []
  const documentation = (payload as { documentation?: unknown }).documentation
  if (!documentation || typeof documentation !== 'object') return []
  return Object.entries(documentation as Record<string, unknown>).map(([key, value]) => {
    if (typeof value === 'string') {
      return { key, description: value }
    }
    if (value && typeof value === 'object') {
      const row = value as Record<string, unknown>
      const example = row.example ? ` Example: ${String(row.example)}` : ''
      return {
        key,
        description: `${String(row.description ?? '')}${example}`.trim(),
      }
    }
    return { key, description: '' }
  })
}

function fallbackTimezones(): string[] {
  const intl = Intl as typeof Intl & { supportedValuesOf?: (type: string) => string[] }
  const dynamic = typeof intl.supportedValuesOf === 'function' ? intl.supportedValuesOf('timeZone') : []
  const merged = [...new Set([...COMMON_TIMEZONES, ...dynamic])]
  return merged.sort((left, right) => left.localeCompare(right))
}

function normalizeTimezoneList(raw: unknown): string[] {
  if (!Array.isArray(raw)) {
    return fallbackTimezones()
  }

  const cleaned = raw
    .map((value) => String(value ?? '').trim())
    .filter(Boolean)

  const merged = [...new Set([...COMMON_TIMEZONES, ...cleaned])]
  return merged.sort((left, right) => left.localeCompare(right))
}

export function normalizeInitialSetup(payload: unknown): InitialSetupState {
  const fallback: InitialSetupState = {
    form: DEFAULT_INITIAL_SETUP,
    timezones: fallbackTimezones(),
  }

  if (!payload || typeof payload !== 'object') {
    return fallback
  }

  const data = (payload as { data?: unknown }).data
  if (!data || typeof data !== 'object') {
    return fallback
  }

  const row = data as Record<string, unknown>
  return {
    form: {
      server_name: String(row.server_name ?? 'UPS'),
      timezone: String(row.timezone ?? 'Europe/Rome'),
      monitoring_profile: String(row.monitoring_profile ?? 'single').toLowerCase() === 'multi' ? 'multi' : 'single',
      ups_realpower_nominal: row.ups_realpower_nominal ? String(row.ups_realpower_nominal) : '',
    },
    timezones: normalizeTimezoneList(row.timezones),
  }
}

export function groupTimezones(timezones: string[]): Array<{ label: string; values: string[] }> {
  return TIMEZONE_GROUPS.map((label) => ({
    label,
    values: timezones.filter((timezone) => timezone === label || timezone.startsWith(`${label}/`)),
  })).filter((group) => group.values.length > 0)
}

function normalizeLocationPart(value: unknown): string {
  return String(value ?? '').trim()
}

function composeLocationString(parts: Array<string>): string {
  return parts.filter(Boolean).join(', ')
}

export function composeTargetLocation(form: Pick<
  TargetForm,
  | 'location_enabled'
  | 'location_country'
  | 'location_region'
  | 'location_city'
  | 'location_postal_code'
  | 'location_address'
  | 'location'
>): string {
  if (!form.location_enabled) {
    return ''
  }
  const computed = composeLocationString([
    normalizeLocationPart(form.location_address),
    normalizeLocationPart(form.location_city),
    normalizeLocationPart(form.location_region),
    normalizeLocationPart(form.location_postal_code),
    normalizeLocationPart(form.location_country),
  ])
  return computed || normalizeLocationPart(form.location)
}

export function mapTargetToForm(target: MultiNutTarget): TargetForm {
  const policy = (target as unknown as { policy?: Record<string, unknown> }).policy ?? {}
  const policyRetentionDays = Number(policy.retention_days || 0)
  const retentionEnabled = policyRetentionDays > 0
  return {
    id: String(target.id),
    name: String(target.name || ''),
    ups_name: String(target.ups_name || ''),
    host: String(target.host || ''),
    port: Number(target.port || 3493),
    nut_mode: String((target as unknown as Record<string, unknown>).nut_mode || 'netclient') as TargetForm['nut_mode'],
    // Shared-only phase:
    // legacy policy values are intentionally ignored for now.
    db_strategy: 'shared',
    shard_granularity: 'month',
    separate_db_path: null,
    polling_interval: Number(policy.polling_interval || 1),
    retention_days: retentionEnabled ? policyRetentionDays : 30,
    retention_enabled: retentionEnabled,
    timezone: String((target as unknown as Record<string, unknown>).timezone || 'UTC'),
    currency: String((target as unknown as Record<string, unknown>).currency || 'EUR'),
    notify_scope: String(policy.notify_scope || 'global') as TargetForm['notify_scope'],
    enabled: Boolean(target.enabled),
    is_primary: Boolean(target.is_primary),
    location_enabled: Boolean(target.location_enabled),
    location: String(target.location || ''),
    location_country: String(target.location_country || ''),
    location_region: String(target.location_region || ''),
    location_city: String(target.location_city || ''),
    location_postal_code: String(target.location_postal_code || ''),
    location_address: String(target.location_address || ''),
    location_latitude:
      target.location_latitude === null || target.location_latitude === undefined
        ? null
        : Number(target.location_latitude),
    location_longitude:
      target.location_longitude === null || target.location_longitude === undefined
        ? null
        : Number(target.location_longitude),
  }
}

export function toTargetPayload(form: TargetForm): MultiNutTargetPayload {
  const retentionDays = form.retention_enabled
    ? Math.min(3650, Math.max(1, Number(form.retention_days || 30)))
    : 0
  const normalizedLocation = composeTargetLocation(form)
  const locationEnabled = Boolean(form.location_enabled)

  return {
    name: form.name.trim(),
    ups_name: form.ups_name.trim(),
    host: form.host.trim(),
    port: Number(form.port || 3493),
    nut_mode: form.nut_mode,
    // Shared-only phase:
    db_strategy: 'shared',
    shard_granularity: 'month',
    separate_db_path: null,
    polling_interval: Number(form.polling_interval || 1),
    retention_days: retentionDays,
    notify_scope: 'global',
    enabled: Boolean(form.enabled),
    is_primary: Boolean(form.is_primary),
    location_enabled: locationEnabled,
    location: locationEnabled ? normalizedLocation : '',
    location_country: locationEnabled ? normalizeLocationPart(form.location_country) : '',
    location_region: locationEnabled ? normalizeLocationPart(form.location_region) : '',
    location_city: locationEnabled ? normalizeLocationPart(form.location_city) : '',
    location_postal_code: locationEnabled ? normalizeLocationPart(form.location_postal_code) : '',
    location_address: locationEnabled ? normalizeLocationPart(form.location_address) : '',
    location_latitude: locationEnabled ? form.location_latitude ?? null : null,
    location_longitude: locationEnabled ? form.location_longitude ?? null : null,
  }
}

function coerceOptionalCoordinate(value: unknown, min: number, max: number): number | null {
  if (value === null || value === undefined || value === '') {
    return null
  }
  const parsed = Number(value)
  if (!Number.isFinite(parsed)) {
    return null
  }
  if (parsed < min || parsed > max) {
    return null
  }
  return parsed
}

export type TargetLocationValidationResult = {
  confirmed: boolean
  found: boolean
  validationUnavailable: boolean
  target: MultiNutTargetPayload
}

export async function validateTargetLocationBeforeSave(
  target: MultiNutTargetPayload,
): Promise<TargetLocationValidationResult> {
  if (!target.location_enabled) {
    return {
      confirmed: true,
      found: false,
      validationUnavailable: false,
      target: {
        ...target,
        location_latitude: null,
        location_longitude: null,
      },
    }
  }

  const existingLatitude = coerceOptionalCoordinate(target.location_latitude, -90, 90)
  const existingLongitude = coerceOptionalCoordinate(target.location_longitude, -180, 180)
  if (existingLatitude !== null && existingLongitude !== null) {
    return {
      confirmed: true,
      found: true,
      validationUnavailable: false,
      target: {
        ...target,
        location_latitude: existingLatitude,
        location_longitude: existingLongitude,
      },
    }
  }

  const payload = {
    location: String(target.location || ''),
    location_country: String(target.location_country || ''),
    location_region: String(target.location_region || ''),
    location_city: String(target.location_city || ''),
    location_postal_code: String(target.location_postal_code || ''),
    location_address: String(target.location_address || ''),
  }

  try {
    const response = await fetch('/nut_config/api/setup/validate-location', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(payload),
    })
    const data = (await response.json().catch(() => ({}))) as Record<string, unknown>
    const normalized = data.normalized_location && typeof data.normalized_location === 'object'
      ? data.normalized_location as Record<string, unknown>
      : {}
    const match = data.match && typeof data.match === 'object'
      ? data.match as Record<string, unknown>
      : {}

    const latitude = coerceOptionalCoordinate(
      normalized.location_latitude ?? match.latitude ?? null,
      -90,
      90,
    )
    const longitude = coerceOptionalCoordinate(
      normalized.location_longitude ?? match.longitude ?? null,
      -180,
      180,
    )

    if (Boolean(data.success) && Boolean(data.found) && latitude !== null && longitude !== null) {
      return {
        confirmed: true,
        found: true,
        validationUnavailable: false,
        target: {
          ...target,
          location_latitude: latitude,
          location_longitude: longitude,
        },
      }
    }

    const validationUnavailable = Boolean(data.validation_unavailable) || !response.ok
    const confirmMessage = validationUnavailable
      ? 'Location validation service is currently unavailable. Do you want to save this target anyway?'
      : `Location "${payload.location || 'provided address'}" was not found. Do you want to save this target anyway?`
    const shouldContinue = window.confirm(confirmMessage)
    if (!shouldContinue) {
      return { confirmed: false, found: false, validationUnavailable, target }
    }

    return {
      confirmed: true,
      found: false,
      validationUnavailable,
      target: {
        ...target,
        location_latitude: null,
        location_longitude: null,
      },
    }
  } catch (error) {
    const message = error instanceof Error ? error.message : 'unknown error'
    const shouldContinue = window.confirm(
      `Unable to validate location right now (${message}). Do you want to save this target anyway?`,
    )
    if (!shouldContinue) {
      return { confirmed: false, found: false, validationUnavailable: true, target }
    }
    return {
      confirmed: true,
      found: false,
      validationUnavailable: true,
      target: {
        ...target,
        location_latitude: null,
        location_longitude: null,
      },
    }
  }
}
