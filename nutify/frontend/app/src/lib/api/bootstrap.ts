/**
 * Bootstrap.
 *
 * Frontend module used by Nutify React UI flows and state management.
 */

import { z } from 'zod'

import { requestJson } from './client'
import type { BootstrapPayload } from '../../types/bootstrap'

const bootstrapSchema = z.object({
  success: z.literal(true),
  data: z.object({
    route: z.string(),
    request_path: z.string(),
    timezone: z.string(),
    auth: z.object({
      configured: z.boolean(),
      authenticated: z.boolean(),
      disabled: z.boolean(),
      current_user: z
        .object({
          id: z.number().optional(),
          username: z.string().optional(),
          role: z.string().optional(),
          is_admin: z.boolean().optional(),
          is_authenticated: z.boolean().optional(),
          last_login: z.string().nullable().optional(),
          created_at: z.string().nullable().optional(),
          options_tabs: z.record(z.string(), z.boolean()).optional(),
        })
        .nullable(),
    }),
    runtime: z.object({
      status: z.string(),
      message: z.string(),
      updated_at: z.string(),
    }),
    monitoring: z.object({
      monitoring_profile: z.enum(['single', 'multi']),
      multi_nut_enabled: z.boolean(),
      multi_nut_target_count: z.number(),
      active_target_id: z.number().nullable(),
      active_target: z.record(z.string(), z.unknown()).nullable(),
    }),
    settings: z
      .object({
        settings_view: z.enum(['target', 'system']),
        is_admin: z.boolean(),
        options_tabs: z.record(z.string(), z.boolean()),
      })
      .optional(),
    react_bundle_available: z.boolean(),
  }),
})

export async function getBootstrap(pathname: string): Promise<BootstrapPayload> {
  const encodedPath = encodeURIComponent(pathname)
  const payload = await requestJson(
    `/api/frontend/bootstrap?path=${encodedPath}`,
    bootstrapSchema,
  )

  return payload.data as BootstrapPayload
}
