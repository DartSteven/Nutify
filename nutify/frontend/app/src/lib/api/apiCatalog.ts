/**
 * Apicatalog.
 *
 * Frontend module used by Nutify React UI flows and state management.
 */

import { z } from 'zod'

import { requestJson } from './client'

const apiRouteSchema = z.object({
  path: z.string(),
  methods: z.array(z.string()).min(1),
  endpoint: z.string(),
  module: z.string(),
  function_name: z.string(),
  summary: z.string(),
  group_key: z.string(),
  group_label: z.string(),
  path_params: z.array(z.string()),
  supports_get: z.boolean(),
  access_kind: z.string(),
  access_label: z.string(),
  access_detail: z.string(),
})

const apiGroupSchema = z.object({
  key: z.string(),
  label: z.string(),
  route_count: z.number(),
  routes: z.array(apiRouteSchema),
})

const apiCatalogEnvelopeSchema = z.object({
  success: z.literal(true),
  data: z.object({
    generated_at: z.string(),
    total_routes: z.number(),
    total_groups: z.number(),
    groups: z.array(apiGroupSchema),
  }),
})

export type ApiCatalogRoute = z.infer<typeof apiRouteSchema>
export type ApiCatalogGroup = z.infer<typeof apiGroupSchema>
export type ApiCatalog = z.infer<typeof apiCatalogEnvelopeSchema>['data']

export async function getApiCatalog(): Promise<ApiCatalog> {
  const payload = await requestJson('/api/frontend/catalog', apiCatalogEnvelopeSchema)
  return payload.data
}
