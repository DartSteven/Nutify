export type InterfaceSkin = 'classic' | 'next'
export type ColorTheme = 'light' | 'dark'

export type AppearancePreference = {
  skin: InterfaceSkin
  color: ColorTheme
}

export const APPEARANCE_SKIN_STORAGE_KEY = 'nutify.appearance.skin'
export const APPEARANCE_COLOR_STORAGE_KEY = 'theme'
export const APPEARANCE_EVENT = 'nutify:appearance-changed'

function normalizeSkin(value: unknown): InterfaceSkin {
  return String(value ?? '').trim().toLowerCase() === 'next' ? 'next' : 'classic'
}

function normalizeColor(value: unknown): ColorTheme {
  return String(value ?? '').trim().toLowerCase() === 'light' ? 'light' : 'dark'
}

export function getAppearancePreference(): AppearancePreference {
  if (typeof window === 'undefined') {
    return { skin: 'classic', color: 'dark' }
  }

  let storedSkin: string | null = null
  let storedColor: string | null = null
  try {
    storedSkin = window.localStorage.getItem(APPEARANCE_SKIN_STORAGE_KEY)
    storedColor = window.localStorage.getItem(APPEARANCE_COLOR_STORAGE_KEY)
  } catch {
    // Browser storage can be unavailable in strict privacy contexts.
  }

  return {
    skin: normalizeSkin(storedSkin),
    color: normalizeColor(storedColor),
  }
}

export function applyAppearance(preference: AppearancePreference, persist = true): AppearancePreference {
  const normalized = {
    skin: normalizeSkin(preference.skin),
    color: normalizeColor(preference.color),
  }

  document.documentElement.setAttribute('data-ui-skin', normalized.skin)
  document.documentElement.setAttribute('data-theme', normalized.color)

  if (persist) {
    try {
      window.localStorage.setItem(APPEARANCE_SKIN_STORAGE_KEY, normalized.skin)
      window.localStorage.setItem(APPEARANCE_COLOR_STORAGE_KEY, normalized.color)
    } catch {
      // Apply for current page even when persistence is unavailable.
    }
    window.dispatchEvent(new CustomEvent(APPEARANCE_EVENT, { detail: normalized }))
  }

  return normalized
}

export function initializeAppearance(): AppearancePreference {
  const preference = getAppearancePreference()
  return applyAppearance(preference, false)
}
