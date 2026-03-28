/**
 * Dashboardlayout.
 *
 * Frontend module used by Nutify React UI flows and state management.
 */

import { useEffect } from 'react'
import { Outlet } from 'react-router-dom'

import { AppSidebar } from '../../components/AppSidebar'
import { AppTopbar } from '../../components/AppTopbar'

export function DashboardLayout() {
  useEffect(() => {
    document.body.classList.remove('setup-body')

    const rootElement = document.getElementById('root')
    if (rootElement) {
      rootElement.style.display = ''
      rootElement.style.width = ''
      rootElement.style.minHeight = ''
    }

    document.querySelectorAll('.countdown-overlay, .countdown-container').forEach((node) => {
      node.parentElement?.removeChild(node)
    })
  }, [])

  return (
    <>
      <AppSidebar />
      <main className="main-content">
        <AppTopbar />
        <Outlet />
      </main>
    </>
  )
}
