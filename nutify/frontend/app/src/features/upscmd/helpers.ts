/**
 * Helpers.
 *
 * Frontend module used by Nutify React UI flows and state management.
 */

export type CommandApiItem = {
  name: string
  description: string
  type?: string
}

export type CommandStats = {
  total: number
  successful: number
  failed: number
}

export type CommandLog = {
  command: string
  success: boolean
  output: string
  timestamp: string | null
}

export const DEFAULT_STATS: CommandStats = {
  total: 0,
  successful: 0,
  failed: 0,
}

export function asRecord(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    return {}
  }
  return value as Record<string, unknown>
}

export function asArray(value: unknown): unknown[] {
  return Array.isArray(value) ? value : []
}

export function normalizeCommands(payload: unknown): CommandApiItem[] {
  const body = asRecord(payload)
  const rawCommands = asArray(body.commands)

  return rawCommands
    .map((item) => {
      if (typeof item === 'string') {
        return { name: item, description: item }
      }
      const row = asRecord(item)
      const name = String(row.name ?? '')
      if (!name) {
        return null
      }
      return {
        name,
        description: String(row.description ?? name),
        type: row.type ? String(row.type) : undefined,
      }
    })
    .filter((item): item is CommandApiItem => item !== null)
}

export function normalizeStats(payload: unknown): CommandStats {
  const body = asRecord(payload)
  return {
    total: Number(body.total ?? 0),
    successful: Number(body.successful ?? 0),
    failed: Number(body.failed ?? 0),
  }
}

export function normalizeLogs(payload: unknown): CommandLog[] {
  const body = asRecord(payload)
  const logs = asArray(body.logs)
  return logs.map((item) => {
    const row = asRecord(item)
    return {
      command: String(row.command ?? ''),
      success: Boolean(row.success),
      output: String(row.output ?? ''),
      timestamp: row.timestamp ? String(row.timestamp) : null,
    }
  })
}

function parseTimestamp(value: string): Date | null {
  const trimmed = value.trim()
  if (!trimmed) {
    return null
  }

  const normalized = /[zZ]$/.test(trimmed) || /[+-]\d{2}:\d{2}$/.test(trimmed)
    ? trimmed
    : `${trimmed}Z`

  const date = new Date(normalized)
  if (Number.isNaN(date.getTime())) {
    return null
  }

  return date
}

export function formatLogTimestamp(timestamp: string | null, timezone: string): string {
  if (!timestamp) {
    return '-'
  }
  const date = parseTimestamp(timestamp)
  if (!date) {
    return timestamp
  }
  try {
    return date.toLocaleString([], { timeZone: timezone })
  } catch {
    return date.toLocaleString()
  }
}
