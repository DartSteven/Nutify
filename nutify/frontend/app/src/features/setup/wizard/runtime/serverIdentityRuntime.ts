// @ts-nocheck

export function registerServerIdentityRuntime(ctx) {
  const { elements } = ctx

  ctx.actions.loadInitialServerName = async function loadInitialServerName() {
    if (!elements.serverNameField) {
      return
    }

    const fallbackValue = String(elements.serverNameField.value || '').trim() || 'Nutify'
    elements.serverNameField.dataset.defaultValue = fallbackValue

    try {
      const response = await fetch('/api/options/options-from-initial-setup', {
        credentials: 'same-origin',
      })
      const payload = await response.json().catch(() => ({}))
      if (!response.ok) {
        return
      }

      const loadedServerName = String(payload?.data?.server_name || '').trim() || fallbackValue
      elements.serverNameField.value = loadedServerName
      elements.serverNameField.dataset.defaultValue = loadedServerName
    } catch (error) {
      console.error('[setup] Failed to load initial server name', error)
    }
  }
}
