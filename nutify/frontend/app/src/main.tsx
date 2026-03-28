/**
 * Main.
 *
 * Frontend module used by Nutify React UI flows and state management.
 */

import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'

import { App } from './app/App'
import { initializeLegacyNotify } from './lib/legacyNotify'
import '@fortawesome/fontawesome-free/css/all.min.css'
import './styles.css'

initializeLegacyNotify()

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
