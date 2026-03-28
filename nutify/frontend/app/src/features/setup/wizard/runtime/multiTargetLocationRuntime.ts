// @ts-nocheck

export function registerMultiTargetLocationRuntime(ctx) {
  const { elements, state } = ctx

  ctx.actions.readLocationDetailsFromForm = function readLocationDetailsFromForm() {
    const locationCountry = ctx.actions.normalizeLocationText(elements.multiTargetLocationCountry?.value, 120)
    const locationRegion = ctx.actions.normalizeLocationText(elements.multiTargetLocationRegion?.value, 120)
    const locationCity = ctx.actions.normalizeLocationText(elements.multiTargetLocationCity?.value, 120)
    const locationPostalCode = ctx.actions.normalizeLocationText(elements.multiTargetLocationPostalCode?.value, 40)
    const locationAddress = ctx.actions.normalizeLocationText(elements.multiTargetLocationAddress?.value, 255)
    const location = ctx.actions.composeLocationString(locationAddress, locationCity, locationRegion, locationPostalCode, locationCountry)

    return {
      location_country: locationCountry,
      location_region: locationRegion,
      location_city: locationCity,
      location_postal_code: locationPostalCode,
      location_address: locationAddress,
      location,
    }
  }

  ctx.actions.updateLocationComputedField = function updateLocationComputedField() {
    if (!elements.multiTargetLocation) {
      return
    }
    const details = ctx.actions.readLocationDetailsFromForm()
    elements.multiTargetLocation.value = details.location
    state.multiTargetDraftLocationLatitude = null
    state.multiTargetDraftLocationLongitude = null
  }

  ctx.actions.hideLocationSuggestions = function hideLocationSuggestions() {
    if (!elements.multiTargetLocationSuggestions) {
      return
    }
    elements.multiTargetLocationSuggestions.classList.add('hidden')
    elements.multiTargetLocationSuggestions.innerHTML = ''
  }

  ctx.actions.applyLocationSuggestion = function applyLocationSuggestion(suggestion) {
    if (!suggestion || typeof suggestion !== 'object') {
      return
    }
    if (elements.multiTargetLocationCountry) elements.multiTargetLocationCountry.value = String(suggestion.location_country || '')
    if (elements.multiTargetLocationRegion) elements.multiTargetLocationRegion.value = String(suggestion.location_region || '')
    if (elements.multiTargetLocationCity) elements.multiTargetLocationCity.value = String(suggestion.location_city || '')
    if (elements.multiTargetLocationPostalCode) elements.multiTargetLocationPostalCode.value = String(suggestion.location_postal_code || '')
    if (elements.multiTargetLocationAddress) elements.multiTargetLocationAddress.value = String(suggestion.location_address || '')
    ctx.actions.updateLocationComputedField()
    state.multiTargetDraftLocationLatitude = ctx.actions.coerceOptionalCoordinate(suggestion.location_latitude, -90, 90)
    state.multiTargetDraftLocationLongitude = ctx.actions.coerceOptionalCoordinate(suggestion.location_longitude, -180, 180)
    ctx.actions.hideLocationSuggestions()
  }

  ctx.actions.renderLocationSuggestions = function renderLocationSuggestions(suggestions) {
    if (!elements.multiTargetLocationSuggestions) {
      return
    }
    const rows = Array.isArray(suggestions) ? suggestions : []
    if (!rows.length) {
      ctx.actions.hideLocationSuggestions()
      return
    }
    elements.multiTargetLocationSuggestions.innerHTML = ''
    rows.forEach((suggestion) => {
      const button = document.createElement('button')
      button.type = 'button'
      button.className = 'multi-target-location-suggestion-btn'
      button.innerHTML = `
        <span class="multi-target-location-suggestion-title">${ctx.actions.escapeHtml(suggestion.location || suggestion.display_name || 'Location')}</span>
        <span class="multi-target-location-suggestion-meta">${ctx.actions.escapeHtml(suggestion.display_name || '')}</span>
      `
      button.addEventListener('click', () => ctx.actions.applyLocationSuggestion(suggestion))
      elements.multiTargetLocationSuggestions.appendChild(button)
    })
    elements.multiTargetLocationSuggestions.classList.remove('hidden')
  }

  ctx.actions.loadLocationSuggestions = async function loadLocationSuggestions() {
    if (!elements.multiTargetLocationEnabled?.checked) {
      ctx.actions.hideLocationSuggestions()
      return
    }

    const details = ctx.actions.readLocationDetailsFromForm()
    const query = details.location || details.location_address || details.location_city
    if (!query || String(query).trim().length < 3) {
      ctx.actions.hideLocationSuggestions()
      return
    }

    if (state.locationSuggestionsAbortController) {
      state.locationSuggestionsAbortController.abort()
    }
    const requestId = ++state.locationSuggestionRequestId
    const controller = new AbortController()
    state.locationSuggestionsAbortController = controller

    try {
      const response = await fetch('/nut_config/api/setup/location-suggestions', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ...details, query, limit: 6 }),
        signal: controller.signal,
      })

      const data = await response.json().catch(() => ({}))
      if (requestId !== state.locationSuggestionRequestId) {
        return
      }
      if (!response.ok || !data?.success) {
        ctx.actions.hideLocationSuggestions()
        return
      }
      ctx.actions.renderLocationSuggestions(data.suggestions || [])
    } catch (_error) {
      if (requestId === state.locationSuggestionRequestId) {
        ctx.actions.hideLocationSuggestions()
      }
    }
  }

  ctx.actions.queueLocationSuggestions = function queueLocationSuggestions() {
    if (state.locationSuggestionDebounceTimer) {
      clearTimeout(state.locationSuggestionDebounceTimer)
    }
    state.locationSuggestionDebounceTimer = setTimeout(() => {
      void ctx.actions.loadLocationSuggestions()
    }, 340)
  }

  ctx.actions.validateMultiTargetLocation = async function validateMultiTargetLocation(target, options = {}) {
    const promptOnFailure = options?.promptOnFailure !== false
    if (!target || !target.location_enabled) {
      return {
        confirmed: true,
        found: false,
        validationUnavailable: false,
        target: { ...target, location_latitude: null, location_longitude: null },
      }
    }

    const existingLatitude = ctx.actions.coerceOptionalCoordinate(target.location_latitude, -90, 90)
    const existingLongitude = ctx.actions.coerceOptionalCoordinate(target.location_longitude, -180, 180)
    if (existingLatitude !== null && existingLongitude !== null) {
      return {
        confirmed: true,
        found: true,
        validationUnavailable: false,
        target: { ...target, location_latitude: existingLatitude, location_longitude: existingLongitude },
      }
    }

    const payload = {
      location: target.location || '',
      location_country: target.location_country || '',
      location_region: target.location_region || '',
      location_city: target.location_city || '',
      location_postal_code: target.location_postal_code || '',
      location_address: target.location_address || '',
    }

    try {
      const response = await fetch('/nut_config/api/setup/validate-location', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })
      const data = await response.json().catch(() => ({}))
      const normalizedLocation = data?.normalized_location && typeof data.normalized_location === 'object' ? data.normalized_location : {}
      const latitude = ctx.actions.coerceOptionalCoordinate(normalizedLocation.location_latitude ?? data?.match?.latitude, -90, 90)
      const longitude = ctx.actions.coerceOptionalCoordinate(normalizedLocation.location_longitude ?? data?.match?.longitude, -180, 180)

      if (data?.success && data?.found && latitude !== null && longitude !== null) {
        return {
          confirmed: true,
          found: true,
          validationUnavailable: false,
          target: { ...target, location_latitude: latitude, location_longitude: longitude },
        }
      }

      const validationUnavailable = Boolean(data?.validation_unavailable) || !response.ok
      if (!promptOnFailure) {
        return {
          confirmed: true,
          found: false,
          validationUnavailable,
          target: { ...target, location_latitude: null, location_longitude: null },
        }
      }

      const confirmMessage = validationUnavailable
        ? 'Location validation service is currently unavailable. Do you want to save this target anyway?'
        : `Location "${payload.location || 'provided address'}" was not found. Do you want to save this target anyway?`
      const shouldContinue = window.confirm(confirmMessage)
      if (!shouldContinue) {
        return { confirmed: false, found: false, validationUnavailable, target }
      }
      return {
        confirmed: true,
        found: false,
        validationUnavailable,
        target: { ...target, location_latitude: null, location_longitude: null },
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : 'unknown error'
      if (!promptOnFailure) {
        return {
          confirmed: true,
          found: false,
          validationUnavailable: true,
          target: { ...target, location_latitude: null, location_longitude: null },
        }
      }
      const shouldContinue = window.confirm(`Unable to validate location right now (${message}). Do you want to save this target anyway?`)
      if (!shouldContinue) {
        return { confirmed: false, found: false, validationUnavailable: true, target }
      }
      return {
        confirmed: true,
        found: false,
        validationUnavailable: true,
        target: { ...target, location_latitude: null, location_longitude: null },
      }
    }
  }
}
