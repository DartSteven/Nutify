/**
 * Appsidebar.
 *
 * Frontend module used by Nutify React UI flows and state management.
 */

import { NavLink, useLocation } from 'react-router-dom'

import { dashboardNav } from '../app/router/nav'

export function AppSidebar() {
  const location = useLocation()
  const settingsView = new URLSearchParams(location.search).get('view') === 'system' ? 'system' : 'target'

  const isSystemSettingsRoute =
    (location.pathname.startsWith('/settings') || location.pathname.startsWith('/options')) &&
    settingsView === 'system'

  return (
    <aside className="sidebar">
      <div className="sidebar-logo">
        <p className="page_subtitle" />
      </div>
      <nav className="sidebar-nav">
        {dashboardNav.map((item) => (
          <NavLink
            key={item.path}
            to={item.path}
            className={({ isActive }) => {
              const active =
                item.path === '/settings/system'
                  ? isSystemSettingsRoute
                  : isActive
              return ['nav-item', active ? 'active' : ''].join(' ')
            }}
            title={item.label}
          >
            <i className={`fas ${item.icon}`} aria-hidden="true" />
            <span className="nav-label">{item.label}</span>
          </NavLink>
        ))}
      </nav>
    </aside>
  )
}
