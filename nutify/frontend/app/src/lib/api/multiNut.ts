/**
 * Multinut.
 *
 * Frontend module used by Nutify React UI flows and state management.
 */

import { z } from 'zod'

import { requestJson } from './client'
import { ApiError } from './client'

const targetSchema = z.object({
  id: z.number(),
  name: z.string(),
  ups_name: z.string(),
  host: z.string(),
  port: z.number().optional(),
  enabled: z.boolean().optional(),
  is_primary: z.boolean().optional(),
  location_enabled: z.boolean().optional(),
  location: z.string().optional(),
  location_country: z.string().optional(),
  location_region: z.string().optional(),
  location_city: z.string().optional(),
  location_postal_code: z.string().optional(),
  location_address: z.string().optional(),
  location_latitude: z.number().nullable().optional(),
  location_longitude: z.number().nullable().optional(),
  last_test_status: z.boolean().nullable().optional(),
  last_test_error: z.string().nullable().optional(),
  policy: z.object({
    polling_interval: z.number().optional(),
    retention_days: z.number().optional(),
    db_strategy: z.string().optional(),
    shard_granularity: z.string().optional(),
    notify_scope: z.string().optional(),
    separate_db_path: z.string().nullable().optional(),
  }).optional(),
}).passthrough()

const stateSchema = z.object({
  success: z.boolean(),
  data: z.object({
    monitoring_profile: z.enum(['single', 'multi']).default('single'),
    multi_enabled: z.boolean().optional(),
    enabled_targets: z.number().optional(),
    active_target_id: z.number().nullable().optional(),
  }),
})

const targetsSchema = z.object({
  success: z.boolean(),
  data: z.array(targetSchema),
})

const overviewSchema = z.object({
  success: z.boolean(),
  data: z.array(z.record(z.string(), z.unknown())),
})

const renamerCatalogSchema = z.object({
  success: z.boolean(),
  data: z.object({
    target_id: z.number(),
    target: z.record(z.string(), z.unknown()),
    source_origin: z.string(),
    source_keys: z.array(z.string()),
    rows: z.array(
      z.object({
        canonical_key: z.string(),
        canonical_dot_key: z.string(),
        current_source: z.string(),
        suggested_source: z.string(),
        selected_source: z.string(),
        status: z.string(),
        source_options: z.array(z.string()),
      }),
    ),
    mapping_count: z.number(),
  }),
})

export type MultiNutTarget = z.infer<typeof targetSchema>
export type RenamerCatalog = z.infer<typeof renamerCatalogSchema>['data']
export type RenamerRow = RenamerCatalog['rows'][number]

export type MultiNutTargetPayload = {
  name: string
  ups_name: string
  host: string
  port: number
  nut_mode: 'standalone' | 'netserver' | 'netclient'
  db_strategy: 'shared' | 'sharded' | 'separate'
  shard_granularity: 'month' | 'day'
  separate_db_path: string | null
  polling_interval: number
  retention_days: number
  notify_scope: 'global' | 'mail' | 'ntfy' | 'webhook' | 'none'
  enabled: boolean
  is_primary: boolean
  location_enabled?: boolean
  location?: string
  location_country?: string
  location_region?: string
  location_city?: string
  location_postal_code?: string
  location_address?: string
  location_latitude?: number | null
  location_longitude?: number | null
}

const mutableResultSchema = z.object({ success: z.boolean() }).passthrough()
const targetDetailsSchema = z.object({
  success: z.boolean(),
  data: z.record(z.string(), z.unknown()),
})

export async function getMultiNutState() {
  const payload = await requestJson('/api/multi-nut/state', stateSchema)
  return payload.data
}

export async function getTargets(includeDisabled = false): Promise<MultiNutTarget[]> {
  const payload = await requestJson(
    `/api/multi-nut/targets?include_disabled=${includeDisabled ? 'true' : 'false'}`,
    targetsSchema,
  )
  return payload.data
}

export async function setActiveTarget(targetId: number): Promise<void> {
  await requestJson(
    '/api/multi-nut/active-target',
    z.object({ success: z.boolean() }).passthrough(),
    {
      method: 'POST',
      body: JSON.stringify({ target_id: targetId }),
    },
  )
}

export async function testTargetConnection(payload: MultiNutTargetPayload) {
  return requestJson('/api/multi-nut/targets/test', mutableResultSchema, {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export async function createTarget(payload: MultiNutTargetPayload) {
  return requestJson('/api/multi-nut/targets', mutableResultSchema, {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export async function updateTarget(targetId: number, payload: Partial<MultiNutTargetPayload>) {
  return requestJson(`/api/multi-nut/targets/${targetId}`, mutableResultSchema, {
    method: 'PUT',
    body: JSON.stringify(payload),
  })
}

export async function toggleTarget(targetId: number, enabled: boolean) {
  return requestJson(`/api/multi-nut/targets/${targetId}/toggle`, mutableResultSchema, {
    method: 'POST',
    body: JSON.stringify({ enabled }),
  })
}

export async function setPrimaryTarget(targetId: number) {
  return requestJson(`/api/multi-nut/targets/${targetId}/primary`, mutableResultSchema, {
    method: 'POST',
  })
}

export async function pollTargetNow(targetId: number) {
  return requestJson(`/api/multi-nut/targets/${targetId}/poll-now`, mutableResultSchema, {
    method: 'POST',
  })
}

export async function deleteTarget(targetId: number) {
  return requestJson(`/api/multi-nut/targets/${targetId}`, mutableResultSchema, {
    method: 'DELETE',
  })
}

export async function getTargetDetails(targetId: number) {
  const payload = await requestJson(`/api/multi-nut/targets/${targetId}`, targetDetailsSchema)
  return payload.data
}

export async function getOverview(hours = 24) {
  const payload = await requestJson(`/api/multi-nut/overview?hours=${hours}`, overviewSchema)
  return payload.data
}

export async function getRenamerCatalog(targetId: number): Promise<RenamerCatalog> {
  const payload = await requestJson(`/api/multi-nut/renamer/catalog?target_id=${targetId}`, renamerCatalogSchema)
  return payload.data
}

export async function saveRenamerMappings(
  targetId: number,
  mappings: Record<string, string>,
  replace = true,
): Promise<void> {
  await requestJson(
    '/api/multi-nut/renamer/mappings',
    z.object({ success: z.boolean() }).passthrough(),
    {
      method: 'POST',
      body: JSON.stringify({
        target_id: targetId,
        mappings,
        replace,
      }),
    },
  )
}

export async function downloadNotifyCmdScript(targetId: number, destinationIp?: string): Promise<void> {
  const params = new URLSearchParams()
  if (destinationIp && destinationIp.trim()) {
    params.set('destination_ip', destinationIp.trim())
  }

  const query = params.toString()
  const url = query
    ? `/api/multi-nut/targets/${targetId}/notifycmd-script?${query}`
    : `/api/multi-nut/targets/${targetId}/notifycmd-script`

  const response = await fetch(url, {
    method: 'GET',
    credentials: 'same-origin',
  })

  if (!response.ok) {
    let message = `HTTP ${response.status}`
    try {
      const body = await response.json()
      if (body && typeof body === 'object') {
        message = String((body as Record<string, unknown>).error || (body as Record<string, unknown>).message || message)
      }
    } catch {
      // Keep default HTTP message for non-JSON responses.
    }
    throw new ApiError(message, response.status)
  }

  const blob = await response.blob()
  const disposition = response.headers.get('Content-Disposition') || ''
  const match = disposition.match(/filename="?([^"]+)"?/i)
  const filename = match?.[1] ? String(match[1]) : `nutify_notifycmd_target_${targetId}.sh`

  const linkUrl = window.URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = linkUrl
  link.download = filename
  document.body.appendChild(link)
  link.click()
  link.remove()
  window.URL.revokeObjectURL(linkUrl)
}
