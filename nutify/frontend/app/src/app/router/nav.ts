/**
 * Nav.
 *
 * Frontend module used by Nutify React UI flows and state management.
 */

export type NavItem = {
  path: string
  label: string
  icon: string
}

export const dashboardNav: NavItem[] = [
  { path: '/', label: 'Home', icon: 'fa-home' },
  { path: '/energy', label: 'Energy', icon: 'fa-plug' },
  { path: '/power', label: 'Power', icon: 'fa-bolt' },
  { path: '/battery', label: 'Battery', icon: 'fa-battery-full' },
  { path: '/voltage', label: 'Voltage', icon: 'fa-chart-line' },
  { path: '/ups_info', label: 'Info', icon: 'fa-info-circle' },
  { path: '/upscmd', label: 'Command', icon: 'fa-terminal' },
  { path: '/upsrw', label: 'Settings', icon: 'fa-edit' },
  { path: '/events', label: 'Events', icon: 'fa-bell' },
  { path: '/settings/system', label: 'System', icon: 'fa-sliders-h' },
]
