/**
 * Auth.
 *
 * Frontend module used by Nutify React UI flows and state management.
 */

import { z } from 'zod'

import { requestJson } from './client'

const authStatusSchema = z.object({
  authenticated: z.boolean(),
  login_configured: z.boolean().optional(),
  user: z
    .object({
      id: z.number().optional(),
      username: z.string().optional(),
      role: z.string().optional(),
    })
    .nullable()
    .optional(),
  permissions: z.record(z.string(), z.boolean()).optional(),
})

const authEnvelope = z.object({
  success: z.boolean().optional(),
  data: z.any().optional(),
  error: z.string().optional(),
  message: z.string().optional(),
  authenticated: z.boolean().optional(),
  login_configured: z.boolean().optional(),
  user: authStatusSchema.shape.user,
  permissions: authStatusSchema.shape.permissions,
})

const oidcConfigSchema = z.object({
  enabled: z.boolean(),
  configuration_error: z.boolean().optional().default(false),
  auto_redirect: z.boolean().optional().default(false),
  login_url: z.string(),
  provider_name: z.string(),
  button_label: z.string(),
})

export type AuthStatus = z.infer<typeof authStatusSchema>
export type OidcConfig = z.infer<typeof oidcConfigSchema>

export async function getOidcConfig(): Promise<OidcConfig> {
  try {
    return await requestJson('/auth/api/oidc', oidcConfigSchema)
  } catch {
    return {
      enabled: false,
      configuration_error: false,
      auto_redirect: false,
      login_url: '/auth/oidc/login',
      provider_name: 'SSO',
      button_label: 'Sign in with SSO',
    }
  }
}

export async function getAuthStatus(): Promise<AuthStatus> {
  const payload = await requestJson('/auth/api/status', authEnvelope)

  if (payload.data && typeof payload.data === 'object') {
    const parsed = authStatusSchema.safeParse(payload.data)
    if (parsed.success) {
      return parsed.data
    }
  }

  const parsed = authStatusSchema.safeParse(payload)
  if (parsed.success) {
    return parsed.data
  }

  return {
    authenticated: false,
    login_configured: false,
    user: null,
    permissions: {},
  }
}

export async function login(username: string, password: string): Promise<void> {
  await requestJson(
    '/auth/api/login',
    z.object({ success: z.boolean() }).passthrough(),
    {
      method: 'POST',
      body: JSON.stringify({ username, password }),
    },
  )
}

export async function forgotPassword(
  username: string,
  newPassword: string,
  confirmPassword: string,
  recoveryKey: string,
): Promise<void> {
  await requestJson(
    '/auth/api/forgot-password',
    z.object({ success: z.boolean().optional() }).passthrough(),
    {
      method: 'POST',
      body: JSON.stringify({
        username,
        new_password: newPassword,
        confirm_password: confirmPassword,
        recovery_key: recoveryKey,
      }),
    },
  )
}

export async function logout(): Promise<void> {
  await requestJson(
    '/auth/api/logout',
    z.object({ success: z.boolean() }).passthrough(),
    {
      method: 'POST',
      body: JSON.stringify({}),
    },
  )
}

export async function setupAdmin(username: string, password: string, confirmPassword: string): Promise<void> {
  const params = new URLSearchParams({
    username,
    password,
    confirm_password: confirmPassword,
  })

  const response = await fetch('/auth/setup', {
    method: 'POST',
    credentials: 'same-origin',
    headers: {
      'Content-Type': 'application/x-www-form-urlencoded',
    },
    body: params.toString(),
  })

  if (!response.ok) {
    throw new Error(`Setup failed with HTTP ${response.status}`)
  }
}
