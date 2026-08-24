// @ts-nocheck

export function registerMultiTargetCoreRuntime(ctx) {
  const { elements, state } = ctx

  ctx.actions.getConnectionTypeLabel = function getConnectionTypeLabel(connectionType) {
    switch (connectionType) {
      case 'local_usb_serial':
        return 'Local USB/Serial'
      case 'local_network_driver':
        return 'Local Network Driver'
      case 'remote_nut':
      default:
        return 'Remote NUT Server'
    }
  }

  ctx.actions.getTopologyLabel = function getTopologyLabel(topology) {
    switch (topology) {
      case 'remote_only':
        return 'Remote NUT Only'
      case 'local_only':
        return 'Local Targets Only'
      case 'mixed':
        return 'Mixed Local + Remote'
      default:
        return 'N/A'
    }
  }

  ctx.actions.getPrimaryFleetTarget = function getPrimaryFleetTarget() {
    if (!Array.isArray(state.multiTargets) || state.multiTargets.length === 0) {
      return null
    }
    return state.multiTargets.find((target) => !!target.is_primary) || state.multiTargets[0]
  }

  ctx.actions.applyFleetPrimaryToNetclientData = function applyFleetPrimaryToNetclientData(targetData) {
    const primaryTarget = ctx.actions.getPrimaryFleetTarget()
    if (!primaryTarget) {
      return false
    }

    const primaryHost = String(primaryTarget.host || '').trim()
    const primaryUpsName = String(primaryTarget.ups_name || '').trim()
    if (!primaryHost || !primaryUpsName) {
      return false
    }

    const primaryPort = ctx.actions.parseIntClamped(primaryTarget.port, 3493, 1, 65535)
    const primaryUser = String(primaryTarget.monitor_username || 'monuser').trim() || 'monuser'
    const primaryPassword = String(primaryTarget.monitor_password || '').trim()

    targetData.remote_ups_name = primaryUpsName
    targetData.remote_host = primaryHost
    targetData.remote_port = String(primaryPort)
    targetData.remote_user = primaryUser
    targetData.remote_password = primaryPassword
    targetData.ups_name = primaryUpsName
    targetData.ups_host = primaryHost
    targetData.timezone = ctx.actions.normalizeSetupTimezone(primaryTarget.timezone, 'UTC')
    targetData.currency = ctx.actions.normalizeSetupCurrency(primaryTarget.currency, 'EUR')
    targetData.ups_realpower_nominal = ctx.actions.coerceOptionalPositiveInt(primaryTarget.ups_realpower_nominal)
    return true
  }

  ctx.actions.getMultiTargetSignature = function getMultiTargetSignature(target) {
    if (!target) {
      return ''
    }
    return [
      target.name, target.ups_name, target.connection_type, target.host, target.port, target.monitor_username,
      target.monitor_password, target.local_driver, target.local_port, target.local_description,
      target.snmp_community, target.snmp_version, target.snmp_sec_level, target.snmp_sec_name,
      target.snmp_auth_protocol, target.snmp_auth_password, target.snmp_priv_protocol,
      target.snmp_priv_password, target.snmp_mibs, target.usb_vendorid, target.usb_productid,
      target.usb_serial, target.usb_vendor, target.usb_product, target.usb_bus, target.usb_device,
      target.usb_busport, target.db_strategy, target.shard_granularity,
      target.polling_interval, target.retention_days, target.notify_scope, target.separate_db_path,
      target.location_enabled, target.location, target.location_country, target.location_region,
      target.location_city, target.location_postal_code, target.location_address, target.enabled,
      target.is_primary, target.timezone, target.currency, target.ups_realpower_nominal,
    ].map((value) => String(value ?? '')).join('|')
  }

  ctx.actions.getMultiTargetConnectionSignature = function getMultiTargetConnectionSignature(target) {
    if (!target) {
      return ''
    }
    return [
      target.connection_type,
      target.host,
      target.port,
      target.ups_name,
      target.monitor_username,
      target.monitor_password,
      target.local_driver,
      target.local_port,
      target.local_description,
      target.snmp_community,
      target.snmp_version,
      target.snmp_sec_level,
      target.snmp_sec_name,
      target.snmp_auth_protocol,
      target.snmp_auth_password,
      target.snmp_priv_protocol,
      target.snmp_priv_password,
      target.snmp_mibs,
      target.usb_vendorid,
      target.usb_productid,
      target.usb_serial,
      target.usb_vendor,
      target.usb_product,
      target.usb_bus,
      target.usb_device,
      target.usb_busport,
      target.ups_realpower_nominal,
    ].map((value) => String(value ?? '')).join('|')
  }

  ctx.actions.buildMultiTargetsPayload = function buildMultiTargetsPayload() {
    return state.multiTargets.map((target) => ({
      name: target.name,
      ups_name: target.ups_name,
      connection_type: target.connection_type,
      host: target.host,
      port: target.port,
      nut_mode: target.nut_mode,
      monitor_username: target.monitor_username,
      monitor_password: target.monitor_password,
      local_driver: target.local_driver,
      local_port: target.local_port,
      local_description: target.local_description,
      snmp_community: target.snmp_community || '',
      snmp_version: target.snmp_version || 'v1',
      snmp_sec_level: target.snmp_sec_level || 'authPriv',
      snmp_sec_name: target.snmp_sec_name || '',
      snmp_auth_protocol: target.snmp_auth_protocol || 'SHA',
      snmp_auth_password: target.snmp_auth_password || '',
      snmp_priv_protocol: target.snmp_priv_protocol || 'AES',
      snmp_priv_password: target.snmp_priv_password || '',
      snmp_mibs: target.snmp_mibs || '',
      usb_vendorid: target.usb_vendorid || '',
      usb_productid: target.usb_productid || '',
      usb_serial: target.usb_serial || '',
      usb_vendor: target.usb_vendor || '',
      usb_product: target.usb_product || '',
      usb_bus: target.usb_bus || '',
      usb_device: target.usb_device || '',
      usb_busport: target.usb_busport || '',
      db_strategy: target.db_strategy,
      shard_granularity: target.shard_granularity,
      polling_interval: target.polling_interval,
      retention_days: target.retention_days,
      notify_scope: target.notify_scope,
      separate_db_path: target.separate_db_path,
      location_enabled: !!target.location_enabled,
      location: target.location || '',
      location_country: target.location_country || '',
      location_region: target.location_region || '',
      location_city: target.location_city || '',
      location_postal_code: target.location_postal_code || '',
      location_address: target.location_address || '',
      location_latitude: ctx.actions.coerceOptionalCoordinate(target.location_latitude, -90, 90),
      location_longitude: ctx.actions.coerceOptionalCoordinate(target.location_longitude, -180, 180),
      enabled: target.enabled,
      is_primary: target.is_primary,
      timezone: target.timezone || 'UTC',
      currency: target.currency || 'EUR',
      ups_realpower_nominal: ctx.actions.coerceOptionalPositiveInt(target.ups_realpower_nominal),
    }))
  }

  ctx.actions.getEffectiveSetupProfile = function getEffectiveSetupProfile() {
    const selectedProfileRadio = document.querySelector('input[name="monitoring_profile"]:checked')
    const radioProfile = selectedProfileRadio?.value === 'multi' ? 'multi' : 'single'
    const hasFleetTargets = ctx.actions.buildMultiTargetsPayload().length > 0
    state.selectedProfile = radioProfile === 'multi' || hasFleetTargets ? 'multi' : 'single'
    return state.selectedProfile
  }

  ctx.actions.buildTargetTestPayload = function buildTargetTestPayload(target) {
    return {
      name: target.name,
      ups_name: target.ups_name,
      connection_type: target.connection_type,
      host: target.host,
      port: target.port,
      nut_mode: target.nut_mode,
      monitor_username: target.monitor_username,
      monitor_password: target.monitor_password,
      local_driver: target.local_driver,
      local_port: target.local_port,
      local_description: target.local_description,
      snmp_community: target.snmp_community || '',
      snmp_version: target.snmp_version || 'v1',
      snmp_sec_level: target.snmp_sec_level || 'authPriv',
      snmp_sec_name: target.snmp_sec_name || '',
      snmp_auth_protocol: target.snmp_auth_protocol || 'SHA',
      snmp_auth_password: target.snmp_auth_password || '',
      snmp_priv_protocol: target.snmp_priv_protocol || 'AES',
      snmp_priv_password: target.snmp_priv_password || '',
      snmp_mibs: target.snmp_mibs || '',
      usb_vendorid: target.usb_vendorid || '',
      usb_productid: target.usb_productid || '',
      usb_serial: target.usb_serial || '',
      usb_vendor: target.usb_vendor || '',
      usb_product: target.usb_product || '',
      usb_bus: target.usb_bus || '',
      usb_device: target.usb_device || '',
      usb_busport: target.usb_busport || '',
      db_strategy: target.db_strategy,
      shard_granularity: target.shard_granularity,
      polling_interval: target.polling_interval,
      retention_days: target.retention_days,
      notify_scope: target.notify_scope,
      separate_db_path: target.separate_db_path,
      location_enabled: !!target.location_enabled,
      location: target.location || '',
      location_country: target.location_country || '',
      location_region: target.location_region || '',
      location_city: target.location_city || '',
      location_postal_code: target.location_postal_code || '',
      location_address: target.location_address || '',
      location_latitude: ctx.actions.coerceOptionalCoordinate(target.location_latitude, -90, 90),
      location_longitude: ctx.actions.coerceOptionalCoordinate(target.location_longitude, -180, 180),
      enabled: !!target.enabled,
      is_primary: !!target.is_primary,
      timezone: target.timezone || 'UTC',
      currency: target.currency || 'EUR',
      ups_realpower_nominal: ctx.actions.coerceOptionalPositiveInt(target.ups_realpower_nominal),
    }
  }

  ctx.actions.formatTargetTestDetails = function formatTargetTestDetails(targetLabel, data) {
    const lines = [`<div><strong>${ctx.actions.escapeHtml(targetLabel)}</strong></div>`, `<div>${ctx.actions.escapeHtml(data?.message || '')}</div>`]
    const metrics = data?.metrics && typeof data.metrics === 'object' ? data.metrics : {}
    const metricEntries = Object.entries(metrics).filter(([, value]) => value !== null && value !== undefined && value !== '')
    if (metricEntries.length > 0) {
      lines.push('<div class="ups-data">')
      metricEntries.forEach(([key, value]) => {
        lines.push(`<div class="ups-data-item"><strong>${ctx.actions.escapeHtml(key)}:</strong> ${ctx.actions.escapeHtml(value)}</div>`)
      })
      lines.push('</div>')
    }

    if (data?.nominal_power && typeof data.nominal_power === 'object') {
      const nominalValue = ctx.actions.coerceOptionalPositiveInt(data.nominal_power.value)
      const sourceLabel = String(data.nominal_power.source || '').trim()
      lines.push('<div style="margin-top: 8px;"><strong>Nominal power check:</strong></div><div class="ups-data">')
      if (nominalValue) {
        lines.push(`<div class="ups-data-item"><strong>ups.realpower.nominal:</strong> ${ctx.actions.escapeHtml(nominalValue)} W</div>`)
        if (sourceLabel) {
          lines.push(`<div class="ups-data-item"><strong>Source:</strong> ${ctx.actions.escapeHtml(sourceLabel)}</div>`)
        }
      } else {
        lines.push('<div class="ups-data-item"><strong>ups.realpower.nominal:</strong> Missing</div>')
        lines.push('<div class="ups-data-item"><strong>Status:</strong> Manual input required</div>')
      }
      lines.push('</div>')
    }

    if (data?.raw && typeof data.raw === 'object') {
      const rawEntries = Object.entries(data.raw).filter(([, value]) => value !== null && value !== undefined && value !== '')
      if (rawEntries.length > 0) {
        lines.push('<div style="margin-top: 8px;"><strong>Raw upsc:</strong></div><div class="ups-data">')
        rawEntries.forEach(([key, value]) => {
          lines.push(`<div class="ups-data-item"><strong>${ctx.actions.escapeHtml(key)}:</strong> ${ctx.actions.escapeHtml(value)}</div>`)
        })
        lines.push('</div>')
      }
    }

    return lines.join('')
  }

  ctx.actions.updateMultiTargetProgress = function updateMultiTargetProgress(message = '') {
    if (!elements.multiTargetProgress) {
      return
    }
    const totalCount = Array.isArray(state.multiTargets) ? state.multiTargets.length : 0
    const additionalCount = ctx.actions.getAdditionalTargets().length
    if (message) {
      elements.multiTargetProgress.textContent = message
    } else if (state.selectedProfile === 'multi' && state.selectedMode !== 'netclient' && state.primaryTargetPrepared && additionalCount === 0) {
      elements.multiTargetProgress.textContent = 'Configured targets: 1 (primary). Add the next UPS.'
    } else if (totalCount === 0) {
      elements.multiTargetProgress.textContent = 'Configured targets: 0'
    } else {
      elements.multiTargetProgress.textContent = `Configured targets: ${totalCount}`
    }
    ctx.actions.updateButtons(state.currentStep)
  }

  ctx.actions.hasPendingMultiTargetDraft = function hasPendingMultiTargetDraft() {
    if (!elements.multiTargetName) {
      return false
    }
    if (state.editingMultiTargetIndex >= 0) {
      return true
    }
    const hasText = (value) => String(value || '').trim().length > 0
    const normalizedConnectionType = String(
      elements.multiTargetConnectionType?.value || ctx.actions.getDefaultConnectionTypeForCurrentTopology?.() || 'remote_nut',
    ).toLowerCase()
    const isRemote = normalizedConnectionType === 'remote_nut'

    if (hasText(elements.multiTargetName.value)) {
      return true
    }

    const upsName = String(elements.multiTargetUpsName?.value || '').trim()
    if (upsName && upsName !== 'ups') {
      return true
    }

    const timezone = String(elements.multiTargetTimezone?.value || '').trim()
    if (timezone && timezone !== 'UTC') {
      return true
    }

    const currency = String(elements.multiTargetCurrency?.value || '').trim()
    if (currency && currency !== 'EUR') {
      return true
    }

    const polling = String(elements.multiTargetPolling?.value || '').trim()
    if (polling && polling !== '1') {
      return true
    }

    if (elements.multiTargetLocationEnabled?.checked) {
      return true
    }
    if (
      hasText(elements.multiTargetLocation?.value)
      || hasText(elements.multiTargetLocationCountry?.value)
      || hasText(elements.multiTargetLocationRegion?.value)
      || hasText(elements.multiTargetLocationCity?.value)
      || hasText(elements.multiTargetLocationPostalCode?.value)
      || hasText(elements.multiTargetLocationAddress?.value)
    ) {
      return true
    }

    if (elements.multiTargetPrimary?.checked) {
      return true
    }
    if (elements.multiTargetEnabled && !elements.multiTargetEnabled.checked) {
      return true
    }

    if (isRemote) {
      const host = String(elements.multiTargetHost?.value || '').trim()
      const port = String(elements.multiTargetPort?.value || '').trim()
      const monitorUsername = String(elements.multiTargetMonitorUsername?.value || '').trim()
      const monitorPassword = String(elements.multiTargetMonitorPassword?.value || '').trim()
      if (host) {
        return true
      }
      if (port && port !== '3493') {
        return true
      }
      if (monitorUsername && monitorUsername !== 'monuser') {
        return true
      }
      if (monitorPassword) {
        return true
      }
      return false
    }

    const localDriver = String(elements.multiTargetLocalDriver?.value || '').trim()
    const localPort = String(elements.multiTargetLocalPort?.value || '').trim()
    const localDescription = String(elements.multiTargetLocalDesc?.value || '').trim()
    const snmpCommunity = String(elements.multiTargetSnmpCommunity?.value || '').trim()
    const snmpVersion = String(elements.multiTargetSnmpVersion?.value || '').trim()
    if (localDriver && localDriver !== 'usbhid-ups') {
      return true
    }
    if (localPort && localPort !== 'auto') {
      return true
    }
    if (localDescription) {
      return true
    }
    if (snmpCommunity && snmpCommunity !== 'public') {
      return true
    }
    if (snmpVersion && snmpVersion !== 'v1') {
      return true
    }
    return false
  }

  ctx.actions.canProceedFromStep3MultiFlow = function canProceedFromStep3MultiFlow() {
    if (state.selectedProfile !== 'multi') {
      return true
    }
    const additionalTargetsCount = ctx.actions.getAdditionalTargets().length
    if (state.selectedMode !== 'netclient' && !state.primaryTargetPrepared) {
      return false
    }
    if (additionalTargetsCount === 0) {
      return false
    }
    if (ctx.actions.hasPendingMultiTargetDraft()) {
      return false
    }
    return true
  }

  ctx.actions.isWaitingPrimaryTestSaveAction = function isWaitingPrimaryTestSaveAction() {
    if (state.selectedProfile !== 'multi' || state.selectedMode === 'netclient') {
      return false
    }
    if (!ctx.actions.isPrimaryConfigMethodSelected()) {
      return false
    }
    return !state.primaryTargetPrepared
  }

}
