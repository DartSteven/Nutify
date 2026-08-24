/**
 * Setuplayout.
 *
 * Frontend module used by Nutify React UI flows and state management.
 */

import { useLayoutEffect } from 'react'
import { Outlet } from 'react-router-dom'

function restoreAttribute(element: HTMLElement, name: string, value: string | null) {
  if (value === null) {
    element.removeAttribute(name)
  } else {
    element.setAttribute(name, value)
  }
}

export function SetupLayout() {
  useLayoutEffect(() => {
    document.body.classList.add('setup-body')
    const documentRoot = document.documentElement
    const rootElement = document.getElementById('root')
    const previousTheme = documentRoot.getAttribute('data-theme')
    const previousSkin = documentRoot.getAttribute('data-ui-skin')
    const previousRootDisplay = rootElement?.style.display ?? ''
    const previousRootWidth = rootElement?.style.width ?? ''
    const previousRootMinHeight = rootElement?.style.minHeight ?? ''

    // Setup is an invariant light surface, independent from saved dashboard appearance.
    documentRoot.setAttribute('data-theme', 'light')
    documentRoot.setAttribute('data-ui-skin', 'classic')

    if (rootElement) {
      rootElement.style.display = 'block'
      rootElement.style.width = '100%'
      rootElement.style.minHeight = '100vh'
    }

    return () => {
      document.body.classList.remove('setup-body')
      restoreAttribute(documentRoot, 'data-theme', previousTheme)
      restoreAttribute(documentRoot, 'data-ui-skin', previousSkin)

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
