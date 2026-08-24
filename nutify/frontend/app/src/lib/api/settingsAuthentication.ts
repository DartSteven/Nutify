import { z } from 'zod'

import { requestJson } from './client'

export const oidcAdminConfigSchema = z.object({
  source: z.string(),
  editable: z.boolean(),
  source_error: z.string(),
  configured: z.boolean().default(false),
  enabled: z.boolean().default(false),
  issuer: z.string().default(''),
  client_id: z.string().default(''),
  client_secret: z.string().default(''),
  has_client_secret: z.boolean().default(false),
  redirect_uri: z.string().default(''),
  scopes: z.string().default('openid profile email'),
  username_claim: z.string().default('preferred_username'),
  groups_claim: z.string().default('groups'),
  admin_groups: z.string().default(''),
  user_groups: z.string().default(''),
  allow_all_users: z.boolean().default(false),
  allow_private_network: z.boolean().default(false),
  provider_name: z.string().default('SSO'),
  button_label: z.string().default('Sign in with SSO'),
  auto_redirect: z.boolean().default(false),
  discovery_status: z.string().default('untested'),
  discovery_error: z.string().default(''),
  registration_supported: z.boolean().default(false),
  verified: z.boolean().default(false),
  verified_at: z.string().nullable().default(null),
})

export type OidcAdminConfig = z.infer<typeof oidcAdminConfigSchema>

export type OidcConfigPayload = {
  issuer: string
  client_id: string
  client_secret: string
  redirect_uri: string
  scopes: string
  username_claim: string
  groups_claim: string
  admin_groups: string
  user_groups: string
  allow_all_users: boolean
  allow_private_network: boolean
  provider_name: string
  button_label: string
  auto_redirect: boolean
}

const envelopeSchema = z.object({
  success: z.boolean(),
  data: oidcAdminConfigSchema,
})

const discoveryEnvelopeSchema = z.object({
  success: z.boolean(),
  data: z.object({
    configuration: oidcAdminConfigSchema,
    registration_supported: z.boolean(),
    scopes_supported: z.array(z.string()),
    code_flow_supported: z.boolean(),
  }),
})

export async function getOidcAdminConfig(): Promise<OidcAdminConfig> {
  const result = await requestJson('/auth/api/admin/oidc', envelopeSchema)
  return result.data
}

export async function saveOidcAdminConfig(payload: OidcConfigPayload): Promise<OidcAdminConfig> {
  const result = await requestJson('/auth/api/admin/oidc', envelopeSchema, {
    method: 'PUT',
    body: JSON.stringify(payload),
  })
  return result.data
}

export async function discoverOidcProvider() {
  const result = await requestJson('/auth/api/admin/oidc/discover', discoveryEnvelopeSchema, {
    method: 'POST',
    body: '{}',
  })
  return result.data
}

export async function registerOidcClient(
  payload: OidcConfigPayload & { initial_access_token: string },
): Promise<OidcAdminConfig> {
  const result = await requestJson('/auth/api/admin/oidc/dynamic-register', envelopeSchema, {
    method: 'POST',
    body: JSON.stringify(payload),
  })
  return result.data
}

export async function setOidcEnabled(enabled: boolean): Promise<OidcAdminConfig> {
  const result = await requestJson('/auth/api/admin/oidc/enabled', envelopeSchema, {
    method: 'POST',
    body: JSON.stringify({ enabled }),
  })
  return result.data
}

export async function deleteOidcAdminConfig(): Promise<OidcAdminConfig> {
  const result = await requestJson('/auth/api/admin/oidc', envelopeSchema, { method: 'DELETE' })
  return result.data
}
