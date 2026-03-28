// @ts-nocheck

export function registerSharedHelpers(ctx) {
  ctx.actions.parseIntClamped = function parseIntClamped(value, fallback, min, max) {
    const parsed = parseInt(value, 10)
    if (Number.isNaN(parsed)) {
      return fallback
    }
    return Math.max(min, Math.min(max, parsed))
  }

  ctx.actions.coerceOptionalPositiveInt = function coerceOptionalPositiveInt(value) {
    if (value === null || value === undefined) {
      return null
    }
    const normalized = String(value).trim()
    if (!normalized) {
      return null
    }
    const parsed = parseInt(normalized, 10)
    if (Number.isNaN(parsed) || parsed <= 0) {
      return null
    }
    return parsed
  }

  ctx.actions.normalizeSetupTimezone = function normalizeSetupTimezone(value, fallback = 'UTC') {
    const candidate = String(value || '').trim()
    if (!candidate) {
      return fallback
    }
    try {
      Intl.DateTimeFormat(undefined, { timeZone: candidate })
      return candidate
    } catch (_error) {
      return fallback
    }
  }

  ctx.actions.normalizeSetupCurrency = function normalizeSetupCurrency(value, fallback = 'EUR') {
    const candidate = String(value || '').trim().toUpperCase()
    if (!candidate) {
      return fallback
    }
    return /^[A-Z]{3}$/.test(candidate) ? candidate : fallback
  }

  ctx.actions.normalizeLocationText = function normalizeLocationText(value, maxLength = 120) {
    return String(value || '').trim().slice(0, maxLength)
  }

  ctx.actions.coerceOptionalCoordinate = function coerceOptionalCoordinate(value, minimum, maximum) {
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

  ctx.actions.escapeHtml = function escapeHtml(value) {
    return String(value ?? '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;')
  }

  ctx.actions.composeLocationString = function composeLocationString(address, city, region, postalCode, country) {
    return [address, city, region, postalCode, country]
      .map((value) => ctx.actions.normalizeLocationText(value, 120))
      .filter(Boolean)
      .join(', ')
  }

  ctx.actions.getSupportedTimezoneValues = function getSupportedTimezoneValues() {
    const defaultTimezones = [
      'UTC',
      'Europe/Rome',
      'Europe/London',
      'America/New_York',
      'America/Los_Angeles',
      'Asia/Tokyo',
      'Australia/Sydney',
    ]

    try {
      if (typeof Intl.supportedValuesOf === 'function') {
        const runtimeTimezones = Intl.supportedValuesOf('timeZone')
        return Array.from(new Set([...defaultTimezones, ...runtimeTimezones])).sort((left, right) => left.localeCompare(right))
      }
    } catch (_error) {
      // Fallback list is used when supportedValuesOf is unavailable.
    }

    return defaultTimezones
  }

  ctx.actions.populateSetupTimezones = function populateSetupTimezones() {
    const timezoneSelects = document.querySelectorAll('.setup-timezone-select')
    if (!timezoneSelects || timezoneSelects.length === 0) {
      return
    }

    const availableTimezones = ctx.actions.getSupportedTimezoneValues()
    const browserTimezone = ctx.actions.normalizeSetupTimezone(
      Intl.DateTimeFormat().resolvedOptions().timeZone,
      'UTC',
    )
    const preferredTimezone = availableTimezones.includes(browserTimezone) ? browserTimezone : 'UTC'

    timezoneSelects.forEach((select) => {
      const currentValue = ctx.actions.normalizeSetupTimezone(
        String(select.value || select.dataset.defaultValue || preferredTimezone || 'UTC'),
        preferredTimezone,
      )

      select.innerHTML = ''
      availableTimezones.forEach((timezoneValue) => {
        const option = document.createElement('option')
        option.value = timezoneValue
        option.textContent = timezoneValue
        select.appendChild(option)
      })

      select.value = availableTimezones.includes(currentValue) ? currentValue : preferredTimezone
    })
  }

  ctx.actions.isSnmpDriver = function isSnmpDriver(driverValue) {
    return String(driverValue || '').trim().toLowerCase().includes('snmp')
  }

  ctx.actions.getModeLabel = function getModeLabel(mode) {
    switch (mode) {
      case 'standalone':
        return 'Standalone (Local UPS only)'
      case 'netserver':
        return 'Network Server (Local UPS with remote access)'
      case 'netclient':
        return 'Network Client (Remote UPS monitoring)'
      default:
        return mode
    }
  }

  ctx.actions.getDriverLabel = function getDriverLabel(driver) {
    switch (driver) {
      case 'usbhid-ups':
        return 'USB UPS (usbhid-ups)'
      case 'blazer_usb':
        return 'Blazer USB'
      case 'apcsmart':
        return 'APC Smart Protocol'
      case 'bcmxcp_usb':
        return 'Powerware USB'
      case 'richcomm_usb':
        return 'Richcomm USB'
      case 'tripplite_usb':
        return 'Tripp Lite USB'
      default:
        return driver
    }
  }
}
