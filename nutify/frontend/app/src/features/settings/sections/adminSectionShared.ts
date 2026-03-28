/**
 * Adminsectionshared.
 *
 * Frontend module used by Nutify React UI flows and state management.
 */

import type { UserOptionsTabs, UserPagePermissions } from '../../../lib/api/admin'

export type MessageState = {
  tone: 'success' | 'error'
  text: string
} | null

export const OPTIONS_TAB_LABELS: Array<{ key: keyof UserOptionsTabs; label: string; icon: string }> = [
  { key: 'email', label: 'Email Configuration', icon: 'fa-envelope' },
  { key: 'extranotifs', label: 'Extranotifs', icon: 'fa-sliders-h' },
  { key: 'webhook', label: 'Webhook', icon: 'fa-globe' },
  { key: 'powerflow', label: 'PowerFlow', icon: 'fa-sliders-h' },
  { key: 'options', label: 'Options', icon: 'fa-cogs' },
  { key: 'database', label: 'Database', icon: 'fa-database' },
  { key: 'log', label: 'Log', icon: 'fa-box' },
  { key: 'advanced', label: 'Advanced', icon: 'fa-cogs' },
  { key: 'renamer', label: 'Remapper', icon: 'fa-exchange-alt' },
  { key: 'operations', label: 'Operations', icon: 'fa-calculator' },
  { key: 'admin', label: 'Admin', icon: 'fa-user-shield' },
]

export const PAGE_PERMISSION_LABELS: Array<{
  key: keyof UserPagePermissions
  label: string
  icon: string
}> = [
  { key: 'home', label: 'Home Dashboard', icon: 'fa-home' },
  { key: 'energy', label: 'Energy', icon: 'fa-bolt' },
  { key: 'power', label: 'Power', icon: 'fa-plug' },
  { key: 'battery', label: 'Battery', icon: 'fa-battery-half' },
  { key: 'voltage', label: 'Voltage', icon: 'fa-tachometer-alt' },
  { key: 'info', label: 'Info', icon: 'fa-info-circle' },
  { key: 'command', label: 'Command', icon: 'fa-terminal' },
  { key: 'events', label: 'Events', icon: 'fa-bell' },
  { key: 'settings', label: 'Settings', icon: 'fa-cog' },
  { key: 'options', label: 'Options', icon: 'fa-sliders-h' },
]

export function createDefaultOptionsTabs(): UserOptionsTabs {
  return {
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
}

export function createDefaultPagePermissions(): UserPagePermissions {
  return {
    home: true,
    energy: true,
    power: true,
    battery: true,
    voltage: true,
    info: true,
    command: false,
    settings: false,
    events: true,
    options: false,
  }
}

export function formatRole(role: string): string {
  const normalized = String(role || '').trim().toLowerCase()
  switch (normalized) {
    case 'administrator':
      return 'Administrator'
    case 'operator':
      return 'Operator'
    case 'monitor':
      return 'Monitor'
    case 'viewer':
      return 'Viewer'
    case 'user':
      return 'User'
    default:
      return 'User'
  }
}

export function roleBadgeClass(role: string): string {
  const normalized = String(role || '').trim().toLowerCase()
  switch (normalized) {
    case 'administrator':
      return 'admin-role'
    case 'operator':
      return 'operator-role'
    case 'monitor':
      return 'monitor-role'
    case 'viewer':
      return 'viewer-role'
    default:
      return 'user-role'
  }
}

export function formatDateTime(value: string): string {
  const timestamp = Date.parse(value)
  if (!Number.isFinite(timestamp)) {
    return value
  }
  return new Intl.DateTimeFormat('en-GB', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  }).format(new Date(timestamp))
}
