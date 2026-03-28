/**
 * Admin.
 *
 * Frontend module used by Nutify React UI flows and state management.
 */

type JsonRecord = Record<string, unknown>

async function requestAdminJson(url: string, options: RequestInit = {}): Promise<JsonRecord> {
  const response = await fetch(url, {
    credentials: 'same-origin',
    headers: {
      'Content-Type': 'application/json',
      ...(options.headers ?? {}),
    },
    ...options,
  })

  const payload = (await response.json().catch(() => ({}))) as JsonRecord
  if (!response.ok) {
    const message =
      (typeof payload.error === 'string' && payload.error) ||
      (typeof payload.message === 'string' && payload.message) ||
      `HTTP ${response.status}`
    throw new Error(message)
  }
  return payload
}

export type AdminUser = {
  id: number
  username: string
  role: string
  is_admin: boolean
  last_login: string | null
  created_at: string | null
}

export type UserOptionsTabs = {
  email: boolean
  extranotifs: boolean
  webhook: boolean
  powerflow: boolean
  options: boolean
  database: boolean
  log: boolean
  advanced: boolean
  renamer: boolean
  operations: boolean
  admin: boolean
}

export type UserPagePermissions = {
  home: boolean
  energy: boolean
  power: boolean
  battery: boolean
  voltage: boolean
  info: boolean
  command: boolean
  settings: boolean
  events: boolean
  options: boolean
}

const DEFAULT_OPTIONS_TABS: UserOptionsTabs = {
  email: false,
  extranotifs: false,
  webhook: false,
  powerflow: false,
  options: false,
  database: false,
  log: false,
  advanced: false,
  renamer: false,
  operations: false,
  admin: false,
}

const DEFAULT_PAGE_PERMISSIONS: UserPagePermissions = {
  home: false,
  energy: false,
  power: false,
  battery: false,
  voltage: false,
  info: false,
  command: false,
  settings: false,
  events: false,
  options: false,
}

function normalizeOptionsTabs(value: unknown): UserOptionsTabs {
  if (!value || typeof value !== 'object') {
    return { ...DEFAULT_OPTIONS_TABS }
  }
  const row = value as Record<string, unknown>
  return {
    email: Boolean(row.email),
    extranotifs: Boolean(row.extranotifs),
    webhook: Boolean(row.webhook),
    powerflow: Boolean(row.powerflow),
    options: Boolean(row.options),
    database: Boolean(row.database),
    log: Boolean(row.log),
    advanced: Boolean(row.advanced),
    renamer: Boolean(row.renamer),
    operations: Boolean(row.operations),
    admin: Boolean(row.admin),
  }
}

function normalizePermissions(value: unknown): UserPagePermissions {
  if (!value || typeof value !== 'object') {
    return { ...DEFAULT_PAGE_PERMISSIONS }
  }
  const row = value as Record<string, unknown>
  return {
    home: Boolean(row.home),
    energy: Boolean(row.energy),
    power: Boolean(row.power),
    battery: Boolean(row.battery),
    voltage: Boolean(row.voltage),
    info: Boolean(row.info),
    command: Boolean(row.command),
    settings: Boolean(row.settings),
    events: Boolean(row.events),
    options: Boolean(row.options),
  }
}

export async function listAdminUsers(): Promise<AdminUser[]> {
  const payload = await requestAdminJson('/auth/api/admin/users')
  const users = Array.isArray(payload.users) ? payload.users : []
  return users.map((item) => {
    const row = item as JsonRecord
    return {
      id: Number(row.id),
      username: String(row.username ?? ''),
      role: String(row.role ?? 'user'),
      is_admin: Boolean(row.is_admin),
      last_login: typeof row.last_login === 'string' ? row.last_login : null,
      created_at: typeof row.created_at === 'string' ? row.created_at : null,
    }
  })
}

export async function createAdminUser(input: { username: string; password: string; role: 'administrator' | 'user' }) {
  return requestAdminJson('/auth/api/admin/users', {
    method: 'POST',
    body: JSON.stringify(input),
  })
}

export async function updateUserRole(userId: number, role: 'administrator' | 'user') {
  return requestAdminJson(`/auth/api/admin/users/${userId}/role`, {
    method: 'PUT',
    body: JSON.stringify({ role }),
  })
}

export async function updateUserPassword(userId: number, newPassword: string) {
  return requestAdminJson(`/auth/api/admin/users/${userId}/password`, {
    method: 'PUT',
    body: JSON.stringify({ new_password: newPassword }),
  })
}

export async function deleteAdminUser(userId: number) {
  return requestAdminJson(`/auth/api/admin/users/${userId}`, {
    method: 'DELETE',
  })
}

export async function getUserOptionsTabs(userId: number): Promise<UserOptionsTabs> {
  const payload = await requestAdminJson(`/auth/api/admin/users/${userId}/options-tabs`)
  return normalizeOptionsTabs(payload.options_tabs)
}

export async function updateUserOptionsTabs(userId: number, optionsTabs: UserOptionsTabs) {
  return requestAdminJson(`/auth/api/admin/users/${userId}/options-tabs`, {
    method: 'POST',
    body: JSON.stringify({ options_tabs: optionsTabs }),
  })
}

export async function getUserPermissions(userId: number): Promise<UserPagePermissions> {
  const payload = await requestAdminJson(`/auth/api/admin/users/${userId}/permissions`)
  return normalizePermissions(payload.permissions)
}

export async function updateUserPermissions(userId: number, permissions: UserPagePermissions) {
  return requestAdminJson(`/auth/api/admin/users/${userId}/permissions`, {
    method: 'POST',
    body: JSON.stringify({ permissions }),
  })
}

export async function changeOwnPassword(currentPassword: string, newPassword: string) {
  return requestAdminJson('/auth/api/change-password', {
    method: 'POST',
    body: JSON.stringify({
      current_password: currentPassword,
      new_password: newPassword,
    }),
  })
}

export async function changeOwnUsername(newUsername: string, password: string) {
  return requestAdminJson('/auth/api/change-username', {
    method: 'POST',
    body: JSON.stringify({
      new_username: newUsername,
      password,
    }),
  })
}
