import { useEffect, useRef, useState } from 'react'

import {
  APPEARANCE_EVENT,
  applyAppearance,
  getAppearancePreference,
  type AppearancePreference,
  type ColorTheme,
  type InterfaceSkin,
} from '../lib/theme/appearance'

export function AppearanceController() {
  const [appearance, setAppearance] = useState<AppearancePreference>(() => getAppearancePreference())
  const [open, setOpen] = useState(false)
  const controllerRef = useRef<HTMLDivElement | null>(null)

  useEffect(() => {
    const closeOnOutsideClick = (event: MouseEvent) => {
      if (!controllerRef.current?.contains(event.target as Node)) setOpen(false)
    }
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setOpen(false)
    }
    const syncAppearance = () => setAppearance(getAppearancePreference())

    document.addEventListener('mousedown', closeOnOutsideClick)
    document.addEventListener('keydown', closeOnEscape)
    window.addEventListener(APPEARANCE_EVENT, syncAppearance as EventListener)
    window.addEventListener('storage', syncAppearance)

    return () => {
      document.removeEventListener('mousedown', closeOnOutsideClick)
      document.removeEventListener('keydown', closeOnEscape)
      window.removeEventListener(APPEARANCE_EVENT, syncAppearance as EventListener)
      window.removeEventListener('storage', syncAppearance)
    }
  }, [])

  const updateSkin = (skin: InterfaceSkin) => setAppearance(applyAppearance({ ...appearance, skin }))
  const updateColor = (color: ColorTheme) => setAppearance(applyAppearance({ ...appearance, color }))

  return (
    <div ref={controllerRef} className="appearance-controller">
      <button
        className="theme-toggle"
        type="button"
        onClick={() => setOpen((current) => !current)}
        title="Appearance"
        aria-label="Open appearance settings"
        aria-expanded={open}
        aria-haspopup="dialog"
      >
        <i className="fas fa-palette" aria-hidden="true" />
      </button>

      {open ? (
        <div className="appearance-popover" role="dialog" aria-label="Appearance settings">
          <div className="appearance-heading">
            <span><i className="fas fa-layer-group" aria-hidden="true" /> Appearance</span>
            <small>Browser preference</small>
          </div>

          <fieldset className="appearance-group">
            <legend>Interface</legend>
            <div className="appearance-options">
              <button className={appearance.skin === 'classic' ? 'active' : ''} type="button" onClick={() => updateSkin('classic')}>
                <strong>Classic</strong>
                <small>Stable UI</small>
              </button>
              <button className={appearance.skin === 'next' ? 'active' : ''} type="button" onClick={() => updateSkin('next')}>
                <strong>Next</strong>
                <small>New design</small>
              </button>
            </div>
          </fieldset>

          <fieldset className="appearance-group">
            <legend>Color</legend>
            <div className="appearance-options appearance-colors">
              <button className={appearance.color === 'light' ? 'active' : ''} type="button" onClick={() => updateColor('light')}>
                <i className="fas fa-sun" aria-hidden="true" /> Light
              </button>
              <button className={appearance.color === 'dark' ? 'active' : ''} type="button" onClick={() => updateColor('dark')}>
                <i className="fas fa-moon" aria-hidden="true" /> Dark
              </button>
            </div>
          </fieldset>
        </div>
      ) : null}
    </div>
  )
}
