/**
 * Settingspage.
 *
 * Frontend module used by Nutify React UI flows and state management.
 */

import { useMemo } from 'react'
import { useLocation, useNavigate, useSearchParams } from 'react-router-dom'

import { useAppStore } from '../../store/appStore'
import { PowerFlowSection } from './sections/PowerFlowSection'
import { ProviderSection } from './sections/ProviderSection'
import { NotifySection } from './sections/NotifySection'
import { ReporterSection } from './sections/ReporterSection'
import { DatabaseSection } from './sections/DatabaseSection'
import { LogsSection } from './sections/LogsSection'
import { AdvancedNutSection } from './sections/AdvancedNutSection'
import { RenamerSection } from './sections/RenamerSection'
import { OperationsSection } from './sections/OperationsSection'
import { AdminSection } from './sections/AdminSection'
import { AboutSection } from './sections/AboutSection'

type SettingsScope = 'target' | 'system'

type SettingsTab = {
  id: string
  label: string
  icon: string
  scope: SettingsScope
  legacyDataTab: string
  legacyContentId: string
}

const SETTINGS_TABS: SettingsTab[] = [
  {
    id: 'notify',
    label: 'Notify',
    icon: 'fa-envelope',
    scope: 'target',
    legacyDataTab: 'Notify',
    legacyContentId: 'Notify_tab',
  },
  {
    id: 'reporter',
    label: 'Reporter',
    icon: 'fa-file-alt',
    scope: 'target',
    legacyDataTab: 'Reporter',
    legacyContentId: 'Reporter_tab',
  },
  {
    id: 'powerflow',
    label: 'PowerFlow',
    icon: 'fa-sliders-h',
    scope: 'target',
    legacyDataTab: 'variables',
    legacyContentId: 'variables_tab',
  },
  {
    id: 'provider',
    label: 'Provider',
    icon: 'fa-plug',
    scope: 'system',
    legacyDataTab: 'Provider',
    legacyContentId: 'Provider_tab',
  },
  {
    id: 'advanced',
    label: 'Advanced',
    icon: 'fa-cogs',
    scope: 'system',
    legacyDataTab: 'Advanced',
    legacyContentId: 'Advanced_tab',
  },
  {
    id: 'admin',
    label: 'Admin',
    icon: 'fa-user-shield',
    scope: 'system',
    legacyDataTab: 'Admin',
    legacyContentId: 'Admin_tab',
  },
  {
    id: 'database',
    label: 'Database',
    icon: 'fa-database',
    scope: 'system',
    legacyDataTab: 'Database',
    legacyContentId: 'Database_tab',
  },
  {
    id: 'log',
    label: 'Log',
    icon: 'fa-box',
    scope: 'system',
    legacyDataTab: 'Log',
    legacyContentId: 'Log_tab',
  },
  {
    id: 'renamer',
    label: 'Remapper',
    icon: 'fa-exchange-alt',
    scope: 'system',
    legacyDataTab: 'Renamer',
    legacyContentId: 'Renamer_tab',
  },
  {
    id: 'operations',
    label: 'Operations',
    icon: 'fa-calculator',
    scope: 'system',
    legacyDataTab: 'Operations',
    legacyContentId: 'Operations_tab',
  },
  {
    id: 'about',
    label: 'About',
    icon: 'fa-home-user',
    scope: 'system',
    legacyDataTab: 'About',
    legacyContentId: 'About_tab',
  },
]

const TAB_ALIASES: Record<string, string> = {
  variables: 'powerflow',
  logs: 'log',
  workspace: 'advanced',
  email: 'provider',
  extranotifs: 'provider',
  telegram: 'provider',
  webhook: 'provider',
  notifications: 'notify',
  reporting: 'reporter',
  report: 'reporter',
  remapper: 'renamer',
  options: 'powerflow',
}

const TAB_PERMISSION_ALIASES: Record<string, string[]> = {
  provider: ['provider', 'email', 'extranotifs', 'telegram', 'webhook'],
  notify: ['notify', 'email', 'extranotifs', 'telegram', 'webhook'],
  reporter: ['reporter', 'report', 'email'],
}

function normalizeTabId(value: string | null): string | null {
  if (!value) {
    return null
  }
  const normalized = value.trim().toLowerCase()
  if (!normalized) {
    return null
  }
  if (SETTINGS_TABS.some((tab) => tab.id === normalized)) {
    return normalized
  }
  if (TAB_ALIASES[normalized]) {
    return TAB_ALIASES[normalized]
  }
  return null
}

function resolveSettingsView(
  pathname: string,
  queryView: string | null,
  bootstrapView?: 'target' | 'system',
): SettingsScope {
  if (queryView === 'system' || queryView === 'target') {
    return queryView
  }
  if (pathname.startsWith('/settings/system') || pathname.startsWith('/options/system')) {
    return 'system'
  }
  if (
    pathname.startsWith('/options/database')
    || pathname.startsWith('/options/logs')
    || pathname.startsWith('/options/log')
    || pathname.startsWith('/options/renamer')
    || pathname.startsWith('/options/operations')
  ) {
    return 'system'
  }
  if (bootstrapView === 'system' || bootstrapView === 'target') {
    return bootstrapView
  }
  return 'target'
}

function resolveTabFromRoute(pathname: string, searchTab: string | null): string | null {
  const explicitTab = normalizeTabId(searchTab)
  if (explicitTab) {
    return explicitTab
  }
  if (pathname.startsWith('/options/database')) return 'database'
  if (pathname.startsWith('/options/logs') || pathname.startsWith('/options/log')) return 'log'
  if (pathname.startsWith('/options/renamer')) return 'renamer'
  if (pathname.startsWith('/options/operations')) return 'operations'
  if (pathname.startsWith('/settings/advanced')) return 'advanced'
  return null
}

function renderTab(tabId: string) {
  switch (tabId) {
    case 'provider':
      return <ProviderSection />
    case 'notify':
      return <NotifySection />
    case 'reporter':
      return <ReporterSection />
    case 'database':
      return <DatabaseSection />
    case 'log':
      return <LogsSection />
    case 'advanced':
      return <AdvancedNutSection />
    case 'renamer':
      return <RenamerSection />
    case 'operations':
      return <OperationsSection />
    case 'admin':
      return <AdminSection />
    case 'about':
      return <AboutSection />
    case 'powerflow':
    default:
      return <PowerFlowSection />
  }
}

export function SettingsPage() {
  const navigate = useNavigate()
  const location = useLocation()
  const [searchParams] = useSearchParams()
  const bootstrap = useAppStore((state) => state.bootstrap)

  const isAdmin = Boolean(bootstrap?.settings?.is_admin)
  const optionsTabs = bootstrap?.settings?.options_tabs ?? {}

  const settingsView = useMemo(
    () =>
      resolveSettingsView(
        location.pathname,
        searchParams.get('view'),
        bootstrap?.settings?.settings_view,
      ),
    [bootstrap?.settings?.settings_view, location.pathname, searchParams],
  )

  const visibleTabs = useMemo(
    () =>
      SETTINGS_TABS.filter((tab) => {
        if (tab.scope !== settingsView) {
          return false
        }
        if (tab.id === 'about') {
          return true
        }
        if (isAdmin) {
          return true
        }
        const permissionKeys = TAB_PERMISSION_ALIASES[tab.id] ?? [tab.id]
        return permissionKeys.some((key) => Boolean(optionsTabs[key]))
      }),
    [isAdmin, optionsTabs, settingsView],
  )

  const activeTab = useMemo(() => {
    const fromRoute = resolveTabFromRoute(location.pathname, searchParams.get('tab'))
    if (fromRoute && visibleTabs.some((tab) => tab.id === fromRoute)) {
      return fromRoute
    }
    return visibleTabs[0]?.id ?? null
  }, [location.pathname, searchParams, visibleTabs])

  const handleTabClick = (tabId: string, scope: SettingsScope) => {
    const params = new URLSearchParams()
    params.set('view', scope)
    params.set('tab', tabId)
    navigate(`/settings?${params.toString()}`)
  }

  if (!activeTab) {
    return (
      <section className="page">
        <article className="options_card">
          <p className="text-sm text-slate-400">
            No settings tabs are available for your account in this scope.
          </p>
        </article>
      </section>
    )
  }

  return (
    <section className="page" data-settings-view={settingsView}>
      <div className="options_tabs">
        {visibleTabs.map((tab) => (
          <button
            key={tab.id}
            type="button"
            className={['options_tab_button', activeTab === tab.id ? 'active' : ''].join(' ').trim()}
            data-tab={tab.legacyDataTab}
            data-settings-scope={tab.scope}
            onClick={() => handleTabClick(tab.id, tab.scope)}
          >
            <i className={`fas ${tab.icon}`} aria-hidden="true" />
            <span>{tab.label}</span>
          </button>
        ))}
      </div>

      {visibleTabs.map((tab) => (
        <div
          key={tab.id}
          id={tab.legacyContentId}
          className={['options_tab_content', activeTab === tab.id ? 'active' : 'hidden'].join(' ').trim()}
        >
          {activeTab === tab.id ? renderTab(tab.id) : null}
        </div>
      ))}
    </section>
  )
}
