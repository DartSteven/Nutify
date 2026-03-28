/**
 * Approuter.
 *
 * Frontend module used by Nutify React UI flows and state management.
 */

import { useMemo } from 'react'
import { Navigate, Outlet, RouterProvider, createBrowserRouter } from 'react-router-dom'

import { DashboardLayout } from '../layouts/DashboardLayout'
import { AuthLayout } from '../layouts/AuthLayout'
import { SetupLayout } from '../layouts/SetupLayout'
import { MainPage } from '../../features/main/MainPage'
import { MultiUpsPage } from '../../features/multi_ups/MultiUpsPage'
import { EnergyPage } from '../../features/energy/EnergyPage'
import { PowerPage } from '../../features/power/PowerPage'
import { BatteryPage } from '../../features/battery/BatteryPage'
import { VoltagePage } from '../../features/voltage/VoltagePage'
import { EventsPage } from '../../features/events/EventsPage'
import { UpsInfoPage } from '../../features/ups_info/UpsInfoPage'
import { UpsCmdPage } from '../../features/upscmd/UpsCmdPage'
import { UpsRwPage } from '../../features/upsrw/UpsRwPage'
import { SettingsPage } from '../../features/settings/SettingsPage'
import { LoginPage } from '../../features/auth/LoginPage'
import { SetupPage } from '../../features/auth/SetupPage'
import { AdminPage } from '../../features/auth/AdminPage'
import { WizardPage } from '../../features/setup/WizardPage'
import { ApiDocsPage } from '../../features/api/ApiDocsPage'
import { ReportsPage } from '../../features/reports/ReportsPage'
import { useAppStore } from '../../store/appStore'
import { useBrowserLocationKey } from './useBrowserLocationKey'

function AuthGuard() {
  const bootstrap = useAppStore((state) => state.bootstrap)

  if (!bootstrap) {
    return null
  }

  const authDisabled = bootstrap.auth.disabled
  const loginConfigured = bootstrap.auth.configured
  const authenticated = bootstrap.auth.authenticated

  if (!authDisabled && !loginConfigured) {
    return <Navigate to="/auth/setup" replace />
  }

  if (!authDisabled && !authenticated) {
    return <Navigate to="/auth/login" replace />
  }

  return <Outlet />
}

function SetupGuard() {
  const bootstrap = useAppStore((state) => state.bootstrap)

  if (!bootstrap) {
    return null
  }

  if (bootstrap.runtime.status !== 'unconfigured') {
    return <Navigate to="/" replace />
  }

  return <Outlet />
}

function buildRouter() {
  return createBrowserRouter([
    {
      element: <SetupGuard />,
      children: [
        {
          element: <SetupLayout />,
          children: [
            { path: '/nut_config/welcome', element: <Navigate to="/nut_config/setup/wizard" replace /> },
            { path: '/nut_config/setup/wizard', element: <WizardPage /> },
            { path: '/nut_config/setup/timezone', element: <Navigate to="/nut_config/setup/wizard" replace /> },
            { path: '/nut_config/setup/timezone_page', element: <Navigate to="/nut_config/setup/wizard" replace /> },
          ],
        },
      ],
    },
    {
      element: <AuthLayout />,
      children: [
        { path: '/auth/login', element: <LoginPage /> },
        { path: '/auth/setup', element: <SetupPage /> },
      ],
    },
    {
      element: <AuthGuard />,
      children: [
        {
          element: <DashboardLayout />,
          children: [
            { path: '/', element: <MainPage /> },
            { path: '/index', element: <MainPage /> },
            { path: '/websocket-test', element: <MainPage /> },
            { path: '/multi-ups', element: <MultiUpsPage /> },
            { path: '/energy', element: <EnergyPage /> },
            { path: '/power', element: <PowerPage /> },
            { path: '/battery', element: <BatteryPage /> },
            { path: '/voltage', element: <VoltagePage /> },
            { path: '/events', element: <EventsPage /> },
            { path: '/events/view', element: <EventsPage /> },
            { path: '/ups_info', element: <UpsInfoPage /> },
            { path: '/upscmd', element: <UpsCmdPage /> },
            { path: '/upsrw', element: <UpsRwPage /> },
            { path: '/upsrw/preview', element: <UpsRwPage /> },
            { path: '/settings', element: <SettingsPage /> },
            { path: '/settings/system', element: <SettingsPage /> },
            { path: '/settings/advanced', element: <SettingsPage /> },
            { path: '/settings/backup', element: <SettingsPage /> },
            { path: '/options', element: <SettingsPage /> },
            { path: '/options/database', element: <SettingsPage /> },
            { path: '/options/logs', element: <SettingsPage /> },
            { path: '/options/system', element: <SettingsPage /> },
            { path: '/auth/admin', element: <AdminPage /> },
            { path: '/api', element: <ApiDocsPage /> },
            { path: '/reports', element: <ReportsPage /> },
            { path: '/reports/new', element: <ReportsPage /> },
            { path: '/reports/generate', element: <ReportsPage /> },
            { path: '/reports/edit/:scheduleId', element: <ReportsPage /> },
          ],
        },
      ],
    },
    { path: '*', element: <Navigate to="/" replace /> },
  ])
}

export function AppRouter() {
  const locationKey = useBrowserLocationKey()
  const router = useMemo(() => buildRouter(), [locationKey])

  return <RouterProvider key={locationKey} router={router} />
}
