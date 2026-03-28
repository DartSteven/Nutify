/**
 * Usesetupwizardruntime.
 *
 * Frontend module used by Nutify React UI flows and state management.
 */

import { useEffect } from 'react'
import { destroyNutifySetupWizard, initNutifySetupWizard } from './wizardRuntime'

type AssetTag = {
  id: string
  src: string
}

type StylesheetTag = {
  id: string
  href: string
}

const CODEMIRROR_BASE = `${import.meta.env.BASE_URL}vendor/codemirror/`
const SCRIPT_ASSETS: AssetTag[] = [
  { id: 'nutify-setup-codemirror-core', src: `${CODEMIRROR_BASE}codemirror.min.js` },
  { id: 'nutify-setup-codemirror-shell', src: `${CODEMIRROR_BASE}shell.min.js` },
]

const STYLE_ASSETS: StylesheetTag[] = [
  { id: 'nutify-setup-codemirror-style', href: `${CODEMIRROR_BASE}codemirror.min.css` },
  { id: 'nutify-setup-codemirror-theme', href: `${CODEMIRROR_BASE}monokai.min.css` },
]

function ensureStylesheet({ id, href }: StylesheetTag) {
  const existing = document.getElementById(id) as HTMLLinkElement | null
  if (existing) {
    return
  }
  const link = document.createElement('link')
  link.id = id
  link.rel = 'stylesheet'
  link.href = href
  document.head.appendChild(link)
}

function ensureScript({ id, src }: AssetTag): Promise<void> {
  const existing = document.getElementById(id) as HTMLScriptElement | null
  if (existing?.dataset.loaded === 'true') {
    return Promise.resolve()
  }
  if (existing) {
    return new Promise((resolve, reject) => {
      existing.addEventListener('load', () => resolve(), { once: true })
      existing.addEventListener('error', () => reject(new Error(`Failed to load ${src}`)), { once: true })
    })
  }
  return new Promise((resolve, reject) => {
    const script = document.createElement('script')
    script.id = id
    script.src = src
    script.async = false
    script.onload = () => {
      script.dataset.loaded = 'true'
      resolve()
    }
    script.onerror = () => reject(new Error(`Failed to load ${src}`))
    document.body.appendChild(script)
  })
}

export function useSetupWizardRuntime() {
  useEffect(() => {
    let mounted = true

    async function init() {
      STYLE_ASSETS.forEach(ensureStylesheet)
      for (const asset of SCRIPT_ASSETS) {
        await ensureScript(asset)
      }
      if (!mounted) {
        return
      }
      initNutifySetupWizard()
    }

    init().catch((error) => {
      console.error('[setup] Failed to initialize setup wizard runtime', error)
    })

    return () => {
      mounted = false
      destroyNutifySetupWizard()
    }
  }, [])
}
