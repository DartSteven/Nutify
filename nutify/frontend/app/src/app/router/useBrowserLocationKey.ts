/**
 * Usebrowserlocationkey.
 *
 * Frontend module used by Nutify React UI flows and state management.
 */

import { useEffect, useState } from 'react'

const LOCATION_CHANGE_EVENT = 'nutify:browser-location-change'

let historyPatched = false
let originalPushState: History['pushState'] | null = null
let originalReplaceState: History['replaceState'] | null = null
let patchUsers = 0

function currentLocationKey(): string {
  return `${window.location.pathname}${window.location.search}${window.location.hash}`
}

function dispatchLocationChange(): void {
  window.dispatchEvent(new Event(LOCATION_CHANGE_EVENT))
}

function ensureHistoryPatched(): void {
  if (historyPatched) {
    patchUsers += 1
    return
  }

  originalPushState = window.history.pushState.bind(window.history)
  originalReplaceState = window.history.replaceState.bind(window.history)

  window.history.pushState = function pushState(...args) {
    const result = originalPushState?.(...args)
    dispatchLocationChange()
    return result
  }

  window.history.replaceState = function replaceState(...args) {
    const result = originalReplaceState?.(...args)
    dispatchLocationChange()
    return result
  }

  historyPatched = true
  patchUsers = 1
}

function releaseHistoryPatch(): void {
  if (!historyPatched) {
    return
  }

  patchUsers = Math.max(0, patchUsers - 1)
  if (patchUsers > 0) {
    return
  }

  if (originalPushState) {
    window.history.pushState = originalPushState
  }
  if (originalReplaceState) {
    window.history.replaceState = originalReplaceState
  }

  originalPushState = null
  originalReplaceState = null
  historyPatched = false
}

export function useBrowserLocationKey(): string {
  const [locationKey, setLocationKey] = useState(currentLocationKey)

  useEffect(() => {
    ensureHistoryPatched()

    const syncLocationKey = () => {
      setLocationKey(currentLocationKey())
    }

    syncLocationKey()
    window.addEventListener('popstate', syncLocationKey)
    window.addEventListener(LOCATION_CHANGE_EVENT, syncLocationKey)

    return () => {
      window.removeEventListener('popstate', syncLocationKey)
      window.removeEventListener(LOCATION_CHANGE_EVENT, syncLocationKey)
      releaseHistoryPatch()
    }
  }, [])

  return locationKey
}
