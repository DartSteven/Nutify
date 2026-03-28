/**
 * Setuplayout.
 *
 * Frontend module used by Nutify React UI flows and state management.
 */

import { useEffect } from 'react'
import { Outlet } from 'react-router-dom'


export function SetupLayout() {
  useEffect(() => {
    document.body.classList.add('setup-body')
    const rootElement = document.getElementById('root')
    const previousRootDisplay = rootElement?.style.display ?? ''
    const previousRootWidth = rootElement?.style.width ?? ''
    const previousRootMinHeight = rootElement?.style.minHeight ?? ''

    if (rootElement) {
      rootElement.style.display = 'block'
      rootElement.style.width = '100%'
      rootElement.style.minHeight = '100vh'
    }

    return () => {
      document.body.classList.remove('setup-body')

      if (rootElement) {
        rootElement.style.display = previousRootDisplay
        rootElement.style.width = previousRootWidth
        rootElement.style.minHeight = previousRootMinHeight
      }
    }
  }, [])

  return (
    <main className="setup-main-container">
      <Outlet />
    </main>
  )
}
