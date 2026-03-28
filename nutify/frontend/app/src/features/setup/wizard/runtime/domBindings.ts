// @ts-nocheck

function toBindingKey(bindingId) {
  return `wizardBound${String(bindingId || '')
    .replace(/[^a-zA-Z0-9]+(.)/g, (_match, char) => String(char || '').toUpperCase())
    .replace(/[^a-zA-Z0-9]/g, '')}`
}

export function bindWizardEventOnce(element, bindingId, eventName, handler) {
  if (!element) {
    return
  }

  const datasetKey = toBindingKey(bindingId)
  if (element.dataset?.[datasetKey] === 'true') {
    return
  }

  element.addEventListener(eventName, handler)
  if (element.dataset) {
    element.dataset[datasetKey] = 'true'
  }
}
