/**
 * Main.
 *
 * Frontend module used by Nutify React UI flows and state management.
 */

import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'

import { App } from './app/App'
import { initializeLegacyNotify } from './lib/legacyNotify'
import { initializeAppearance } from './lib/theme/appearance'
import '@fortawesome/fontawesome-free/css/all.min.css'
import './styles.css'
import './design-system/appearance-controller.css'
import './design-system/foundation.css'
import './design-system/shell.css'
import './design-system/components.css'
import './design-system/feature-surfaces.css'

initializeLegacyNotify()
initializeAppearance()

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
