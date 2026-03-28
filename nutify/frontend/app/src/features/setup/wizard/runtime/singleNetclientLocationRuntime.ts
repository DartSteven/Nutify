// @ts-nocheck

function buildLocationLabel(parts) {
  return parts
    .map((part) => String(part || '').trim())
    .filter(Boolean)
    .join(', ')
}

export function registerSingleNetclientLocationRuntime(ctx) {
  const { elements } = ctx

  ctx.actions.updateSingleNetclientLocationValue = function updateSingleNetclientLocationValue() {
    const computedLocation = buildLocationLabel([
      elements.netclientLocationAddress?.value,
      elements.netclientLocationCity?.value,
      elements.netclientLocationRegion?.value,
      elements.netclientLocationPostalCode?.value,
      elements.netclientLocationCountry?.value,
    ])
    if (elements.netclientLocation) {
      elements.netclientLocation.value = computedLocation
    }
  }

  ctx.actions.updateSingleNetclientLocationUi = function updateSingleNetclientLocationUi() {
    const enabled = !!elements.netclientLocationEnabled?.checked
    if (elements.netclientLocationFields) {
      elements.netclientLocationFields.classList.toggle('hidden', !enabled)
    }
    if (!enabled && elements.netclientLocation) {
      elements.netclientLocation.value = ''
    }
    if (enabled) {
      ctx.actions.updateSingleNetclientLocationValue()
    }
  }

  ctx.actions.setupSingleNetclientLocationHandlers = function setupSingleNetclientLocationHandlers() {
    if (elements.netclientLocationEnabled && !elements.netclientLocationEnabled.dataset.boundWizardLocationToggle) {
      elements.netclientLocationEnabled.dataset.boundWizardLocationToggle = 'true'
      elements.netclientLocationEnabled.addEventListener('change', function onSingleNetclientLocationToggle() {
        ctx.actions.updateSingleNetclientLocationUi()
      })
    }

    ;[
      elements.netclientLocationCountry,
      elements.netclientLocationRegion,
      elements.netclientLocationCity,
      elements.netclientLocationPostalCode,
      elements.netclientLocationAddress,
    ]
      .filter(Boolean)
      .forEach((input) => {
        if (input.dataset.boundWizardLocationInput) {
          return
        }
        input.dataset.boundWizardLocationInput = 'true'
        input.addEventListener('input', function onSingleNetclientLocationInput() {
          ctx.actions.updateSingleNetclientLocationValue()
        })
      })

    ctx.actions.updateSingleNetclientLocationUi()
  }
}
