/**
 * Advancedtargetlocationfields.
 *
 * Frontend module used by Nutify React UI flows and state management.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from 'react'

import type { TargetForm } from './advancedNutHelpers'

type AdvancedTargetLocationFieldsProps = {
  targetForm: TargetForm
  computedLocation: string
  onTargetFormChange: (updater: (prev: TargetForm) => TargetForm) => void
}

type LocationSuggestion = {
  display_name: string
  location: string
  location_country: string
  location_region: string
  location_city: string
  location_postal_code: string
  location_address: string
  location_latitude: number | null
  location_longitude: number | null
}

const LOCATION_SUGGESTION_LIMIT = 6

function normalizeLocationText(value: unknown, maxLength = 120): string {
  return String(value ?? '').trim().slice(0, maxLength)
}

function coerceOptionalCoordinate(value: unknown, minimum: number, maximum: number): number | null {
  if (value === null || value === undefined || value === '') {
    return null
  }
  const parsed = Number(value)
  if (!Number.isFinite(parsed)) {
    return null
  }
  if (parsed < minimum || parsed > maximum) {
    return null
  }
  return parsed
}

function normalizeLocationSuggestion(value: unknown): LocationSuggestion | null {
  if (!value || typeof value !== 'object') {
    return null
  }
  const row = value as Record<string, unknown>
  const location = normalizeLocationText(row.location, 255)
  const displayName = normalizeLocationText(row.display_name, 255)
  const normalized: LocationSuggestion = {
    display_name: displayName || location || 'Location',
    location,
    location_country: normalizeLocationText(row.location_country, 120),
    location_region: normalizeLocationText(row.location_region, 120),
    location_city: normalizeLocationText(row.location_city, 120),
    location_postal_code: normalizeLocationText(row.location_postal_code, 40),
    location_address: normalizeLocationText(row.location_address, 255),
    location_latitude: coerceOptionalCoordinate(row.location_latitude, -90, 90),
    location_longitude: coerceOptionalCoordinate(row.location_longitude, -180, 180),
  }
  return normalized
}

export function AdvancedTargetLocationFields({
  targetForm,
  computedLocation,
  onTargetFormChange,
}: AdvancedTargetLocationFieldsProps) {
  const [suggestions, setSuggestions] = useState<LocationSuggestion[]>([])
  const [loadingSuggestions, setLoadingSuggestions] = useState(false)
  const [suggestionsHint, setSuggestionsHint] = useState('')

  const debounceTimerRef = useRef<number | null>(null)
  const suggestionsAbortRef = useRef<AbortController | null>(null)
  const requestIdRef = useRef(0)
  const suppressNextSuggestionsRef = useRef(false)
  const userEditedLocationRef = useRef(false)

  const hasResolvedCoordinates =
    coerceOptionalCoordinate(targetForm.location_latitude, -90, 90) !== null
    && coerceOptionalCoordinate(targetForm.location_longitude, -180, 180) !== null

  const locationQuery = useMemo(() => {
    const fallback = [
      normalizeLocationText(targetForm.location_address, 255),
      normalizeLocationText(targetForm.location_city, 120),
      normalizeLocationText(targetForm.location_region, 120),
      normalizeLocationText(targetForm.location_postal_code, 40),
      normalizeLocationText(targetForm.location_country, 120),
    ].filter(Boolean).join(', ')
    return normalizeLocationText(computedLocation || fallback, 255)
  }, [
    computedLocation,
    targetForm.location_address,
    targetForm.location_city,
    targetForm.location_country,
    targetForm.location_postal_code,
    targetForm.location_region,
  ])

  const clearLocationSuggestions = useCallback(() => {
    setSuggestions([])
    setLoadingSuggestions(false)
    setSuggestionsHint('')
  }, [])

  useEffect(() => {
    return () => {
      if (debounceTimerRef.current !== null) {
        window.clearTimeout(debounceTimerRef.current)
      }
      if (suggestionsAbortRef.current) {
        suggestionsAbortRef.current.abort()
      }
    }
  }, [])

  const requestLocationSuggestions = useCallback(async () => {
    if (!targetForm.location_enabled) {
      clearLocationSuggestions()
      return
    }

    if (locationQuery.trim().length < 3) {
      setSuggestions([])
      setLoadingSuggestions(false)
      setSuggestionsHint('Type at least 3 characters to get location suggestions.')
      return
    }

    if (suggestionsAbortRef.current) {
      suggestionsAbortRef.current.abort()
    }

    const requestId = ++requestIdRef.current
    const controller = new AbortController()
    suggestionsAbortRef.current = controller
    setLoadingSuggestions(true)
    setSuggestionsHint('')

    try {
      const response = await fetch('/nut_config/api/setup/location-suggestions', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          query: locationQuery,
          location_country: normalizeLocationText(targetForm.location_country, 120),
          location_region: normalizeLocationText(targetForm.location_region, 120),
          location_city: normalizeLocationText(targetForm.location_city, 120),
          location_postal_code: normalizeLocationText(targetForm.location_postal_code, 40),
          location_address: normalizeLocationText(targetForm.location_address, 255),
          limit: LOCATION_SUGGESTION_LIMIT,
        }),
        signal: controller.signal,
      })

      const data = (await response.json().catch(() => ({}))) as Record<string, unknown>
      if (requestId !== requestIdRef.current) {
        return
      }

      if (!response.ok || !data.success) {
        setSuggestions([])
        setSuggestionsHint(String(data.message || 'Location suggestions unavailable right now.'))
        return
      }

      const rows = Array.isArray(data.suggestions) ? data.suggestions : []
      const normalized = rows
        .map((item) => normalizeLocationSuggestion(item))
        .filter((item): item is LocationSuggestion => item !== null)
      setSuggestions(normalized)
      setSuggestionsHint(normalized.length === 0 ? String(data.message || 'No matching addresses found yet.') : '')
    } catch (error) {
      if (requestId !== requestIdRef.current) {
        return
      }
      if (error instanceof DOMException && error.name === 'AbortError') {
        return
      }
      setSuggestions([])
      setSuggestionsHint('Location suggestions unavailable right now.')
    } finally {
      if (requestId === requestIdRef.current) {
        setLoadingSuggestions(false)
      }
    }
  }, [
    clearLocationSuggestions,
    locationQuery,
    targetForm.location_address,
    targetForm.location_city,
    targetForm.location_country,
    targetForm.location_enabled,
    targetForm.location_postal_code,
    targetForm.location_region,
  ])

  useEffect(() => {
    if (!targetForm.location_enabled) {
      if (suggestionsAbortRef.current) {
        suggestionsAbortRef.current.abort()
      }
      clearLocationSuggestions()
      userEditedLocationRef.current = false
      return
    }

    if (suppressNextSuggestionsRef.current) {
      suppressNextSuggestionsRef.current = false
      return
    }

    if (!userEditedLocationRef.current) {
      return
    }

    if (debounceTimerRef.current !== null) {
      window.clearTimeout(debounceTimerRef.current)
    }
    debounceTimerRef.current = window.setTimeout(() => {
      void requestLocationSuggestions()
    }, 340)

    return () => {
      if (debounceTimerRef.current !== null) {
        window.clearTimeout(debounceTimerRef.current)
      }
    }
  }, [
    clearLocationSuggestions,
    requestLocationSuggestions,
    targetForm.location_address,
    targetForm.location_city,
    targetForm.location_country,
    targetForm.location_enabled,
    targetForm.location_postal_code,
    targetForm.location_region,
  ])

  const updateLocationField = useCallback(
    (changes: Partial<TargetForm>) => {
      userEditedLocationRef.current = true
      onTargetFormChange((prev) => ({
        ...prev,
        ...changes,
        location_latitude: null,
        location_longitude: null,
      }))
    },
    [onTargetFormChange],
  )

  const applySuggestion = useCallback(
    (suggestion: LocationSuggestion) => {
      suppressNextSuggestionsRef.current = true
      userEditedLocationRef.current = false
      onTargetFormChange((prev) => ({
        ...prev,
        location_country: suggestion.location_country,
        location_region: suggestion.location_region,
        location_city: suggestion.location_city,
        location_postal_code: suggestion.location_postal_code,
        location_address: suggestion.location_address,
        location: suggestion.location,
        location_latitude: suggestion.location_latitude,
        location_longitude: suggestion.location_longitude,
      }))
      setSuggestions([])
      setSuggestionsHint('')
    },
    [onTargetFormChange],
  )

  return (
    <>
      <div className="nut_manager_editor_section">
        <label className="nut_manager_checkbox_wrap" htmlFor="multi_target_location_enabled">
          <input
            type="checkbox"
            id="multi_target_location_enabled"
            checked={Boolean(targetForm.location_enabled)}
            onChange={(event) =>
              onTargetFormChange((prev) => ({
                ...prev,
                location_enabled: event.target.checked,
                location: event.target.checked ? prev.location : '',
                location_country: event.target.checked ? prev.location_country : '',
                location_region: event.target.checked ? prev.location_region : '',
                location_city: event.target.checked ? prev.location_city : '',
                location_postal_code: event.target.checked ? prev.location_postal_code : '',
                location_address: event.target.checked ? prev.location_address : '',
                location_latitude: event.target.checked ? prev.location_latitude : null,
                location_longitude: event.target.checked ? prev.location_longitude : null,
              }))
            }
          />
          <span>Location</span>
        </label>
      </div>

      {targetForm.location_enabled ? (
        <div className="nut_manager_editor_section" style={{ marginTop: '-2px' }}>
          <div className="options_mail_form_grid">
            <div className="options_mail_form_group">
              <label htmlFor="multi_target_location_country">Country</label>
              <input
                type="text"
                id="multi_target_location_country"
                className="options_input"
                placeholder="Italy"
                value={targetForm.location_country || ''}
                onChange={(event) => updateLocationField({ location_country: event.target.value })}
              />
            </div>
            <div className="options_mail_form_group">
              <label htmlFor="multi_target_location_region">State/Region</label>
              <input
                type="text"
                id="multi_target_location_region"
                className="options_input"
                placeholder="Veneto"
                value={targetForm.location_region || ''}
                onChange={(event) => updateLocationField({ location_region: event.target.value })}
              />
            </div>
          </div>

          <div className="options_mail_form_grid">
            <div className="options_mail_form_group">
              <label htmlFor="multi_target_location_city">City</label>
              <input
                type="text"
                id="multi_target_location_city"
                className="options_input"
                placeholder="Treviso"
                value={targetForm.location_city || ''}
                onChange={(event) => updateLocationField({ location_city: event.target.value })}
              />
            </div>
            <div className="options_mail_form_group">
              <label htmlFor="multi_target_location_postal_code">Postal Code</label>
              <input
                type="text"
                id="multi_target_location_postal_code"
                className="options_input"
                placeholder="31100"
                value={targetForm.location_postal_code || ''}
                onChange={(event) => updateLocationField({ location_postal_code: event.target.value })}
              />
            </div>
          </div>

          <div className="options_mail_form_grid">
            <div className="options_mail_form_group">
              <label htmlFor="multi_target_location_address">Street Address</label>
              <input
                type="text"
                id="multi_target_location_address"
                className="options_input"
                placeholder="Via Roma 10"
                value={targetForm.location_address || ''}
                onChange={(event) => updateLocationField({ location_address: event.target.value })}
              />
              {suggestions.length > 0 ? (
                <div className="nut_manager_location_suggestions">
                  {suggestions.map((suggestion) => (
                    <button
                      key={`${suggestion.display_name}-${suggestion.location_latitude ?? 'x'}-${suggestion.location_longitude ?? 'x'}`}
                      type="button"
                      className="nut_manager_location_suggestion_btn"
                      onClick={() => applySuggestion(suggestion)}
                    >
                      <span className="nut_manager_location_suggestion_title">
                        {suggestion.location || suggestion.display_name}
                      </span>
                      <span className="nut_manager_location_suggestion_meta">
                        {suggestion.display_name}
                      </span>
                    </button>
                  ))}
                </div>
              ) : null}
              <div className="form-help">
                Start typing to get validated address suggestions.
              </div>
              {loadingSuggestions ? <div className="form-help">Loading suggestions...</div> : null}
              {suggestionsHint ? <div className="form-help">{suggestionsHint}</div> : null}
            </div>
          </div>

          <div className="options_mail_form_grid">
            <div className="options_mail_form_group">
              <label htmlFor="multi_target_location">Location (computed)</label>
              <input
                type="text"
                id="multi_target_location"
                className="options_input"
                value={computedLocation}
                readOnly
              />
              <div className="form-help">This is generated automatically from the fields above.</div>
              {hasResolvedCoordinates ? (
                <div className="form-help">
                  Coordinates resolved: lat {Number(targetForm.location_latitude).toFixed(6)}, lon {Number(targetForm.location_longitude).toFixed(6)}.
                </div>
              ) : (
                <div className="form-help">Coordinates will be validated when you save this target.</div>
              )}
            </div>
          </div>
        </div>
      ) : null}
    </>
  )
}
