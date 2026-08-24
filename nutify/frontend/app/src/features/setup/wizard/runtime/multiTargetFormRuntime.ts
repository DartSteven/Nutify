// @ts-nocheck

export function registerMultiTargetFormRuntime(ctx) {
  const { elements, state } = ctx

  function moveMultiTargetUpsBlock(targetSlot) {
    const upsBlock = document.getElementById('multi-target-ups-name-block')
    if (!upsBlock || !targetSlot || upsBlock.parentElement === targetSlot) {
      return
    }
    targetSlot.appendChild(upsBlock)
  }

  ctx.actions.updateMultiTargetLocationUi = function updateMultiTargetLocationUi() {
    const locationEnabled = !!elements.multiTargetLocationEnabled?.checked
    if (elements.multiTargetLocationFields) {
      elements.multiTargetLocationFields.classList.toggle('hidden', !locationEnabled)
    }
    if (!locationEnabled) {
      state.multiTargetDraftLocationLatitude = null
      state.multiTargetDraftLocationLongitude = null
      if (state.locationSuggestionDebounceTimer) {
        clearTimeout(state.locationSuggestionDebounceTimer)
        state.locationSuggestionDebounceTimer = null
      }
      if (state.locationSuggestionsAbortController) {
        state.locationSuggestionsAbortController.abort()
        state.locationSuggestionsAbortController = null
      }
      ctx.actions.hideLocationSuggestions()
      ;[
        elements.multiTargetLocationCountry,
        elements.multiTargetLocationRegion,
        elements.multiTargetLocationCity,
        elements.multiTargetLocationPostalCode,
        elements.multiTargetLocationAddress,
        elements.multiTargetLocation,
      ].forEach((field) => {
        if (field) {
          field.value = ''
        }
      })
      return
    }
    ctx.actions.updateLocationComputedField()
  }

  ctx.actions.updateMultiTargetStorageStrategyUi = function updateMultiTargetStorageStrategyUi() {
    if (elements.multiTargetDbStrategy) {
      elements.multiTargetDbStrategy.value = 'shared'
    }
    if (elements.multiTargetShardGroup) {
      elements.multiTargetShardGroup.classList.add('hidden')
    }
    if (elements.multiTargetShard) {
      elements.multiTargetShard.disabled = true
      elements.multiTargetShard.value = 'month'
    }
    if (elements.multiTargetSeparateDbPathGroup) {
      elements.multiTargetSeparateDbPathGroup.classList.add('hidden')
    }
    if (elements.multiTargetSeparateDbPath) {
      elements.multiTargetSeparateDbPath.disabled = true
      elements.multiTargetSeparateDbPath.value = ''
    }
  }

  ctx.actions.invalidateMultiTargetTestState = function invalidateMultiTargetTestState(showHint = false) {
    state.lastTargetTestSuccess = false
    state.lastTargetTestSignature = null
    state.lastTargetTestConnectionSignature = null
    if (showHint) {
      ctx.actions.updateMultiTargetTestStatus('Target test required before saving.', false)
    }
  }

  ctx.actions.getAllowedConnectionTypesForCurrentTopology = function getAllowedConnectionTypesForCurrentTopology() {
    if (state.selectedProfile !== 'multi') {
      return ['remote_nut', 'local_usb_serial', 'local_network_driver']
    }
    if (state.selectedTopology === 'remote_only') {
      return ['remote_nut']
    }
    if (state.selectedTopology === 'local_only') {
      return ['local_usb_serial', 'local_network_driver']
    }
    if (state.selectedTopology === 'mixed') {
      return ['remote_nut']
    }
    return ['remote_nut', 'local_usb_serial', 'local_network_driver']
  }

  ctx.actions.getDefaultConnectionTypeForCurrentTopology = function getDefaultConnectionTypeForCurrentTopology() {
    const allowed = ctx.actions.getAllowedConnectionTypesForCurrentTopology()
    return allowed[0] || 'remote_nut'
  }

  ctx.actions.getRecommendedConnectionTypeForCurrentTopology = function getRecommendedConnectionTypeForCurrentTopology() {
    if (state.selectedProfile === 'multi' && state.selectedTopology === 'mixed' && state.selectedMode !== 'netclient' && state.primaryTargetPrepared) {
      return 'remote_nut'
    }
    return ctx.actions.getDefaultConnectionTypeForCurrentTopology()
  }

  ctx.actions.syncConnectionTypeSelectorForTopology = function syncConnectionTypeSelectorForTopology() {
    if (!elements.multiTargetConnectionType) {
      return
    }
    const allowed = new Set(ctx.actions.getAllowedConnectionTypesForCurrentTopology())
    Array.from(elements.multiTargetConnectionType.options || []).forEach((option) => {
      option.hidden = !allowed.has(String(option.value || '').toLowerCase())
    })
    const current = String(elements.multiTargetConnectionType.value || '').toLowerCase()
    if (!allowed.has(current)) {
      elements.multiTargetConnectionType.value = ctx.actions.getDefaultConnectionTypeForCurrentTopology()
    }
    if (elements.multiTargetConnectionTypeGroup) {
      const hideConnectionType = state.selectedProfile === 'multi' && allowed.size <= 1
      elements.multiTargetConnectionTypeGroup.classList.toggle('hidden', hideConnectionType)
    }
  }

  ctx.actions.updateMultiTargetConnectionUi = function updateMultiTargetConnectionUi() {
    ctx.actions.syncConnectionTypeSelectorForTopology()
    let connectionType = String(elements.multiTargetConnectionType?.value || ctx.actions.getDefaultConnectionTypeForCurrentTopology()).toLowerCase()

    if (state.selectedProfile === 'multi') {
      if (state.selectedTopology === 'remote_only') {
        connectionType = 'remote_nut'
        if (elements.multiTargetConnectionType) elements.multiTargetConnectionType.value = connectionType
      } else if (state.selectedTopology === 'local_only' && !['local_usb_serial', 'local_network_driver'].includes(connectionType)) {
        connectionType = 'local_usb_serial'
        if (elements.multiTargetConnectionType) elements.multiTargetConnectionType.value = connectionType
      }
    }

    const isRemote = connectionType === 'remote_nut'
    const remoteUpsSlot = document.getElementById('multi-target-remote-ups-slot')
    const generalUpsSlot = document.getElementById('multi-target-general-ups-slot')
    elements.multiTargetRemoteFields?.classList.toggle('hidden', !isRemote)
    elements.multiTargetLocalFields?.classList.toggle('hidden', isRemote)
    generalUpsSlot?.classList.toggle('hidden', isRemote)
    if (isRemote) {
      moveMultiTargetUpsBlock(remoteUpsSlot)
    } else {
      moveMultiTargetUpsBlock(generalUpsSlot)
    }

    if (!isRemote) {
      if (elements.multiTargetHost) elements.multiTargetHost.value = ''
      if (elements.multiTargetPort) elements.multiTargetPort.value = '3493'
      if (elements.multiTargetMonitorUsername) elements.multiTargetMonitorUsername.value = 'monuser'
      if (elements.multiTargetMonitorPassword) elements.multiTargetMonitorPassword.value = ''
      if (connectionType === 'local_network_driver') {
        if (elements.multiTargetLocalDriver && !elements.multiTargetLocalDriver.value) elements.multiTargetLocalDriver.value = 'snmp-ups'
        if (elements.multiTargetLocalPort && (!elements.multiTargetLocalPort.value || elements.multiTargetLocalPort.value === 'auto')) {
          elements.multiTargetLocalPort.value = ''
        }
      } else {
        if (elements.multiTargetLocalDriver && (!elements.multiTargetLocalDriver.value || elements.multiTargetLocalDriver.value === 'snmp-ups')) elements.multiTargetLocalDriver.value = 'usbhid-ups'
        if (elements.multiTargetLocalPort && !elements.multiTargetLocalPort.value) elements.multiTargetLocalPort.value = 'auto'
      }
    } else {
      if (elements.multiTargetPort) elements.multiTargetPort.value = elements.multiTargetPort.value || '3493'
      if (elements.multiTargetMonitorUsername) elements.multiTargetMonitorUsername.value = elements.multiTargetMonitorUsername.value || 'monuser'
    }
    ctx.actions.updateMultiTargetSnmpUi()
    ctx.actions.updateMultiTargetUsbPortPicker?.()
  }

  ctx.actions.resetMultiTargetForm = function resetMultiTargetForm(showTestHint = true) {
    if (!elements.multiTargetName) {
      return
    }
    ctx.actions.invalidateMultiTargetTestState(showTestHint)
    state.multiTargetDraftNominalPower = null
    elements.multiTargetName.value = ''
    elements.multiTargetUpsName.value = 'ups'
    if (elements.multiTargetConnectionType) elements.multiTargetConnectionType.value = ctx.actions.getRecommendedConnectionTypeForCurrentTopology()
    if (elements.multiTargetHost) elements.multiTargetHost.value = ''
    if (elements.multiTargetPort) elements.multiTargetPort.value = '3493'
    if (elements.multiTargetMonitorUsername) elements.multiTargetMonitorUsername.value = 'monuser'
    if (elements.multiTargetMonitorPassword) elements.multiTargetMonitorPassword.value = ''
    if (elements.multiTargetLocalDriver) elements.multiTargetLocalDriver.value = 'usbhid-ups'
    if (elements.multiTargetLocalPort) elements.multiTargetLocalPort.value = 'auto'
    ctx.actions.clearMultiTargetUsbSelection?.()
    if (elements.multiTargetLocalDesc) elements.multiTargetLocalDesc.value = ''
    if (elements.multiTargetTimezone) {
      elements.multiTargetTimezone.value = ctx.actions.normalizeSetupTimezone('UTC', 'UTC')
    }
    if (elements.multiTargetCurrency) {
      elements.multiTargetCurrency.value = ctx.actions.normalizeSetupCurrency('EUR', 'EUR')
    }
    ctx.actions.writeSnmpSettings('multi_target_')
    if (elements.multiTargetPolling) elements.multiTargetPolling.value = '1'
    if (elements.multiTargetDbStrategy) elements.multiTargetDbStrategy.value = 'shared'
    if (elements.multiTargetShard) elements.multiTargetShard.value = 'month'
    if (elements.multiTargetNotifyScope) elements.multiTargetNotifyScope.value = 'global'
    if (elements.multiTargetSeparateDbPath) elements.multiTargetSeparateDbPath.value = ''
    if (elements.multiTargetEnabled) elements.multiTargetEnabled.checked = true
    if (elements.multiTargetPrimary) elements.multiTargetPrimary.checked = false
    if (elements.multiTargetLocationEnabled) elements.multiTargetLocationEnabled.checked = false
    state.multiTargetDraftLocationLatitude = null
    state.multiTargetDraftLocationLongitude = null
    if (state.locationSuggestionDebounceTimer) clearTimeout(state.locationSuggestionDebounceTimer)
    if (state.locationSuggestionsAbortController) state.locationSuggestionsAbortController.abort()
    state.locationSuggestionDebounceTimer = null
    state.locationSuggestionsAbortController = null
    ctx.actions.hideLocationSuggestions()
    ;[
      elements.multiTargetLocation,
      elements.multiTargetLocationCountry,
      elements.multiTargetLocationRegion,
      elements.multiTargetLocationCity,
      elements.multiTargetLocationPostalCode,
      elements.multiTargetLocationAddress,
    ].forEach((field) => { if (field) field.value = '' })
    state.editingMultiTargetIndex = -1
    if (elements.multiTargetAddBtn) {
      elements.multiTargetAddBtn.innerHTML = '<i class="fas fa-save"></i> Save Target'
      elements.multiTargetAddBtn.style.display = 'none'
    }
    ctx.actions.updateMultiTargetConnectionUi()
    ctx.actions.updateMultiTargetStorageStrategyUi()
    ctx.actions.updateMultiTargetLocationUi()
    if (state.selectedProfile === 'multi' && state.selectedTopology === 'mixed' && state.selectedMode !== 'netclient' && state.primaryTargetPrepared) {
      ctx.actions.updateMultiTargetFlowHint('Primary UPS configured. Add the next remote UPS target.')
    } else {
      ctx.actions.updateMultiTargetFlowHint('')
    }
    ctx.actions.updateMultiTargetProgress()
  }

  ctx.actions.collectMultiTargetFromForm = function collectMultiTargetFromForm() {
    const editingTarget = state.editingMultiTargetIndex >= 0 && state.editingMultiTargetIndex < state.multiTargets.length ? state.multiTargets[state.editingMultiTargetIndex] : null
    const upsName = String(elements.multiTargetUpsName?.value || '').trim()
    const providedName = String(elements.multiTargetName?.value || '').trim()
    const connectionType = String(elements.multiTargetConnectionType?.value || 'remote_nut').toLowerCase()
    const isRemote = connectionType === 'remote_nut'
    const targetTimezone = ctx.actions.normalizeSetupTimezone(elements.multiTargetTimezone?.value, 'UTC')
    const targetCurrency = ctx.actions.normalizeSetupCurrency(elements.multiTargetCurrency?.value, 'EUR')

    if (!upsName) {
      ctx.actions.showAlert('Please enter a UPS name for the additional target.', 'error')
      return null
    }

    const allowedConnectionTypes = ctx.actions.getAllowedConnectionTypesForCurrentTopology()
    if (!allowedConnectionTypes.includes(connectionType)) {
      ctx.actions.showAlert('Please select a valid target connection type.', 'error')
      return null
    }

    let host = '127.0.0.1'
    let port = 3493
    let monitorUsername = 'monuser'
    let monitorPassword = ''
    let localDriver = ''
    let localPort = ''
    let localDescription = ''
    let snmpSettings = ctx.actions.readSnmpSettings('__disabled_')
    let usbVendorId = ''
    let usbProductId = ''
    let usbSerial = ''
    let usbVendor = ''
    let usbProduct = ''
    let usbBus = ''
    let usbDevice = ''
    let usbBusport = ''
    let derivedMode = 'netclient'

    if (isRemote) {
      host = String(elements.multiTargetHost?.value || '').trim()
      if (!host) {
        ctx.actions.showAlert('Please enter a remote host for the additional target.', 'error')
        return null
      }
      port = ctx.actions.parseIntClamped(elements.multiTargetPort?.value, 3493, 1, 65535)
      monitorUsername = String(elements.multiTargetMonitorUsername?.value || '').trim() || 'monuser'
      monitorPassword = String(elements.multiTargetMonitorPassword?.value || '').trim()
    } else {
      localDriver = String(elements.multiTargetLocalDriver?.value || '').trim()
      localPort = String(elements.multiTargetLocalPort?.value || '').trim()
      localDescription = String(elements.multiTargetLocalDesc?.value || '').trim()
      snmpSettings = ctx.actions.readSnmpSettings('multi_target_')
      if (!localDriver) {
        ctx.actions.showAlert('Please enter a local NUT driver for this target.', 'error')
        return null
      }
      if (!localPort) {
        ctx.actions.showAlert('Please enter the local driver port/device for this target.', 'error')
        return null
      }
      if (
        ctx.actions.inferLocalConnectionTypeFromDriver(localDriver) === 'local_network_driver' &&
        localPort.toLowerCase() === 'auto'
      ) {
        ctx.actions.showAlert('Enter the UPS hostname or IP address. Network drivers cannot use auto.', 'error')
        return null
      }
      if (ctx.actions.isSnmpDriver(localDriver)) {
        const snmpError = ctx.actions.validateSnmpSettings('multi_target_')
        if (snmpError) {
          ctx.actions.showAlert(snmpError, 'error')
          return null
        }
      }
      if (String(localDriver || '').trim().toLowerCase() === 'usbhid-ups') {
        const selectedUsbDevice = ctx.actions.getSelectedMultiTargetUsbDevice?.() || null
        const cachedUsbDeviceCount = Array.isArray(state.multiTargetUsbDevices) ? state.multiTargetUsbDevices.length : 0
        const existingUsbSerial = String(editingTarget?.usb_serial || '').trim()
        if (
          String(localPort || '').trim().toLowerCase() === 'auto' &&
          cachedUsbDeviceCount > 1 &&
          !selectedUsbDevice &&
          !existingUsbSerial
        ) {
          ctx.actions.showAlert('Multiple USB UPS devices were detected. Select one in "Detected USB Port" before testing or saving.', 'error')
          return null
        }
        usbVendorId = String(selectedUsbDevice?.vendorid || editingTarget?.usb_vendorid || '').trim()
        usbProductId = String(selectedUsbDevice?.productid || editingTarget?.usb_productid || '').trim()
        usbSerial = String(selectedUsbDevice?.serial || editingTarget?.usb_serial || '').trim()
        usbVendor = String(selectedUsbDevice?.vendor || editingTarget?.usb_vendor || '').trim()
        usbProduct = String(selectedUsbDevice?.model || selectedUsbDevice?.product || editingTarget?.usb_product || '').trim()
        usbBus = String(selectedUsbDevice?.bus || editingTarget?.usb_bus || '').trim()
        usbDevice = String(selectedUsbDevice?.device || editingTarget?.usb_device || '').trim()
        usbBusport = String(selectedUsbDevice?.busport || editingTarget?.usb_busport || '').trim()
      }
      derivedMode = state.selectedMode === 'netserver' ? 'netserver' : 'standalone'
    }

    if (state.selectedMode === 'netclient' && !isRemote) {
      ctx.actions.showAlert('Host mode Network Client supports only remote NUT targets. Select standalone/netserver for local targets.', 'error')
      return null
    }

    const name = providedName || `${upsName}@${host}`
    const pollingInterval = ctx.actions.parseIntClamped(elements.multiTargetPolling?.value, 1, 1, 60)
    const locationEnabled = !!elements.multiTargetLocationEnabled?.checked
    const locationDetails = locationEnabled
      ? ctx.actions.readLocationDetailsFromForm()
      : { location_country: '', location_region: '', location_city: '', location_postal_code: '', location_address: '', location: '' }

    if (locationEnabled && (!locationDetails.location_country || !locationDetails.location_city || !locationDetails.location_address)) {
      ctx.actions.showAlert('Location is enabled. Please provide country, city, and street address.', 'error')
      return null
    }

    const hasSameLocationAsEditing = Boolean(editingTarget && locationEnabled
      && String(editingTarget.location || '').trim() === locationDetails.location
      && String(editingTarget.location_country || '').trim() === locationDetails.location_country
      && String(editingTarget.location_region || '').trim() === locationDetails.location_region
      && String(editingTarget.location_city || '').trim() === locationDetails.location_city
      && String(editingTarget.location_postal_code || '').trim() === locationDetails.location_postal_code
      && String(editingTarget.location_address || '').trim() === locationDetails.location_address)
    const preservedLatitude = hasSameLocationAsEditing ? ctx.actions.coerceOptionalCoordinate(editingTarget?.location_latitude, -90, 90) : null
    const preservedLongitude = hasSameLocationAsEditing ? ctx.actions.coerceOptionalCoordinate(editingTarget?.location_longitude, -180, 180) : null
    const draftLatitude = locationEnabled ? ctx.actions.coerceOptionalCoordinate(state.multiTargetDraftLocationLatitude, -90, 90) : null
    const draftLongitude = locationEnabled ? ctx.actions.coerceOptionalCoordinate(state.multiTargetDraftLocationLongitude, -180, 180) : null

    return {
      name,
      ups_name: upsName,
      connection_type: connectionType,
      host,
      port,
      nut_mode: derivedMode,
      monitor_username: monitorUsername,
      monitor_password: monitorPassword,
      local_driver: localDriver,
      local_port: localPort,
      local_description: localDescription,
      ...snmpSettings,
      usb_vendorid: isRemote ? '' : usbVendorId,
      usb_productid: isRemote ? '' : usbProductId,
      usb_serial: isRemote ? '' : usbSerial,
      usb_vendor: isRemote ? '' : usbVendor,
      usb_product: isRemote ? '' : usbProduct,
      usb_bus: isRemote ? '' : usbBus,
      usb_device: isRemote ? '' : usbDevice,
      usb_busport: isRemote ? '' : usbBusport,
      db_strategy: 'shared',
      shard_granularity: 'month',
      polling_interval: pollingInterval,
      retention_days: 0,
      notify_scope: 'global',
      separate_db_path: '',
      location_enabled: locationEnabled,
      location: locationDetails.location,
      location_country: locationDetails.location_country,
      location_region: locationDetails.location_region,
      location_city: locationDetails.location_city,
      location_postal_code: locationDetails.location_postal_code,
      location_address: locationDetails.location_address,
      location_latitude: locationEnabled ? (draftLatitude ?? preservedLatitude) : null,
      location_longitude: locationEnabled ? (draftLongitude ?? preservedLongitude) : null,
      enabled: elements.multiTargetEnabled ? !!elements.multiTargetEnabled.checked : true,
      is_primary: !!elements.multiTargetPrimary?.checked,
      timezone: targetTimezone,
      currency: targetCurrency,
      ups_realpower_nominal: ctx.actions.coerceOptionalPositiveInt(state.multiTargetDraftNominalPower),
    }
  }
}
