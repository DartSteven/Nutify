/**
 * Bootstrap.
 *
 * Frontend module used by Nutify React UI flows and state management.
 */

export type MonitoringProfile = 'single' | 'multi'

export type RuntimeState = {
  status: 'healthy' | 'degraded' | 'critical' | 'unconfigured' | string
  message: string
  updated_at: string
}

export type BootstrapUser = {
  id?: number
  username?: string
  role?: string
  is_admin?: boolean
  is_authenticated?: boolean
  last_login?: string | null
  created_at?: string | null
  options_tabs?: Record<string, boolean>
}

export type BootstrapAuth = {
  configured: boolean
  authenticated: boolean
  disabled: boolean
  current_user: BootstrapUser | null
}

export type BootstrapMonitoring = {
  monitoring_profile: MonitoringProfile
  multi_nut_enabled: boolean
  multi_nut_target_count: number
  active_target_id: number | null
  active_target: Record<string, unknown> | null
}

export type BootstrapPayload = {
  route: string
  request_path: string
  timezone: string
  auth: BootstrapAuth
  runtime: RuntimeState
  monitoring: BootstrapMonitoring
  settings?: {
    settings_view: 'target' | 'system'
    is_admin: boolean
    options_tabs: Record<string, boolean>
  }
  react_bundle_available: boolean
}
