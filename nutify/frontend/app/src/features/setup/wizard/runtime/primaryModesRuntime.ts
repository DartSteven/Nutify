// @ts-nocheck

export function registerPrimaryModesRuntime(ctx) {
  const { elements, state } = ctx

  function getAutoDetectedDeviceCache() {
    if (!state.autoDetectedDeviceByMode) {
      state.autoDetectedDeviceByMode = {}
    }
    return state.autoDetectedDeviceByMode
  }

  ctx.actions.getSelectedAutoDetectedDevice = function getSelectedAutoDetectedDevice(mode) {
    const cache = getAutoDetectedDeviceCache()
    return cache[mode] || null
  }

  ctx.actions.clearSelectedAutoDetectedDevice = function clearSelectedAutoDetectedDevice(mode) {
    const cache = getAutoDetectedDeviceCache()
    cache[mode] = null
  }

  function getModeElements(mode) {
    const isStandalone = mode === 'standalone'
    return {
      isStandalone,
      manualOption: document.getElementById(isStandalone ? 'manual-option-standalone' : 'manual-option-netserver'),
      autoOption: document.getElementById(isStandalone ? 'auto-option-standalone' : 'auto-option-netserver'),
      manualRadio: isStandalone ? elements.manualStandaloneRadio : elements.manualNetserverRadio,
      autoRadio: isStandalone ? elements.autoStandaloneRadio : elements.autoNetserverRadio,
      manualConfig: document.getElementById(isStandalone ? 'manual-config-standalone' : 'manual-config-netserver'),
      autoConfig: document.getElementById(isStandalone ? 'auto-config-standalone' : 'auto-config-netserver'),
      targetDisplayNameInput: document.getElementById(isStandalone ? 'ups_target_display_name' : 'server_target_display_name'),
      upsNameInput: document.getElementById(isStandalone ? 'ups_name' : 'server_ups_name'),
    }
  }


  ctx.actions.setAwaitingMethodChoice = function setAwaitingMethodChoice(mode, enabled) {
    const container = document.getElementById(`config-${mode}`)
    if (container) {
      container.classList.toggle('awaiting-method-choice', !!enabled)
    }
  }

  ctx.actions.clearAutoSelectionArtifacts = function clearAutoSelectionArtifacts(mode) {
    const scanResults = document.getElementById(`scan-results-${mode}`)
    if (scanResults) {
      scanResults.querySelectorAll('.scan-device.selected').forEach((node) => node.classList.remove('selected'))
      const selectedHint = scanResults.querySelector('.scan-selected-hint')
      if (selectedHint) {
        selectedHint.remove()
      }
    }
    ctx.actions.clearSelectedAutoDetectedDevice?.(mode)
  }

  ctx.actions.hideScannerArtifacts = function hideScannerArtifacts(mode) {
    const scanResults = document.getElementById(`scan-results-${mode}`)
    if (scanResults) {
      scanResults.classList.add('hidden')
    }
    ctx.actions.clearAutoSelectionArtifacts(mode)
  }

  ctx.actions.updatePrimarySnmpFieldVisibility = function updatePrimarySnmpFieldVisibility() {
    const standaloneUsesSnmp = ctx.actions.isSnmpDriver(elements.standaloneDriverSelect?.value)
    const netserverUsesSnmp = ctx.actions.isSnmpDriver(elements.netserverDriverSelect?.value)

    if (elements.standaloneSnmpFields) {
      elements.standaloneSnmpFields.classList.toggle('hidden', !standaloneUsesSnmp)
    }
    if (elements.standaloneSnmpCommunity && standaloneUsesSnmp && !String(elements.standaloneSnmpCommunity.value || '').trim()) {
      elements.standaloneSnmpCommunity.value = 'public'
    }
    if (elements.standaloneSnmpVersion && standaloneUsesSnmp && !String(elements.standaloneSnmpVersion.value || '').trim()) {
      elements.standaloneSnmpVersion.value = 'v1'
    }

    if (elements.netserverSnmpFields) {
      elements.netserverSnmpFields.classList.toggle('hidden', !netserverUsesSnmp)
    }
    if (elements.netserverSnmpCommunity && netserverUsesSnmp && !String(elements.netserverSnmpCommunity.value || '').trim()) {
      elements.netserverSnmpCommunity.value = 'public'
    }
    if (elements.netserverSnmpVersion && netserverUsesSnmp && !String(elements.netserverSnmpVersion.value || '').trim()) {
      elements.netserverSnmpVersion.value = 'v1'
    }
  }

  ctx.actions.updateMultiTargetSnmpUi = function updateMultiTargetSnmpUi() {
    const connectionType = String(elements.multiTargetConnectionType?.value || '').toLowerCase()
    const isLocalConnection = connectionType === 'local_usb_serial' || connectionType === 'local_network_driver'
    const usesSnmpDriver = isLocalConnection && ctx.actions.isSnmpDriver(elements.multiTargetLocalDriver?.value)

    if (elements.multiTargetSnmpFields) {
      elements.multiTargetSnmpFields.classList.toggle('hidden', !usesSnmpDriver)
    }
    if (usesSnmpDriver) {
      if (elements.multiTargetSnmpCommunity && !String(elements.multiTargetSnmpCommunity.value || '').trim()) {
        elements.multiTargetSnmpCommunity.value = 'public'
      }
      if (elements.multiTargetSnmpVersion && !String(elements.multiTargetSnmpVersion.value || '').trim()) {
        elements.multiTargetSnmpVersion.value = 'v1'
      }
    }
  }

  ctx.actions.setupSnmpFieldHandlers = function setupSnmpFieldHandlers() {
    if (elements.standaloneDriverSelect) {
      elements.standaloneDriverSelect.addEventListener('change', () => {
        ctx.actions.updatePrimarySnmpFieldVisibility()
        ctx.actions.updateManualUsbPortPicker('standalone')
      })
    }
    if (elements.netserverDriverSelect) {
      elements.netserverDriverSelect.addEventListener('change', () => {
        ctx.actions.updatePrimarySnmpFieldVisibility()
        ctx.actions.updateManualUsbPortPicker('netserver')
      })
    }
    if (elements.multiTargetLocalDriver) {
      elements.multiTargetLocalDriver.addEventListener('change', ctx.actions.updateMultiTargetSnmpUi)
      elements.multiTargetLocalDriver.addEventListener('input', ctx.actions.updateMultiTargetSnmpUi)
    }
    ctx.actions.setupManualUsbPortPickerHandlers?.()
    ctx.actions.updatePrimarySnmpFieldVisibility()
    ctx.actions.updateMultiTargetSnmpUi()
  }

  ctx.actions.runNutScanner = function runNutScanner(mode, currentUpsName) {
    const portInput = mode === 'standalone' ? document.getElementById('ups_port') : document.getElementById('server_ups_port')
    const driverSelect = mode === 'standalone' ? document.getElementById('ups_driver') : document.getElementById('server_ups_driver')
    const nameInput = mode === 'standalone' ? document.getElementById('ups_name') : document.getElementById('server_ups_name')
    const displayNameInput = mode === 'standalone'
      ? document.getElementById('ups_target_display_name')
      : document.getElementById('server_target_display_name')
    const descInput = mode === 'standalone' ? document.getElementById('ups_desc') : document.getElementById('server_ups_desc')
    const autoConfigSection = document.getElementById(`auto-config-${mode}`)

    let scanResults = document.getElementById(`scan-results-${mode}`)
    if (!scanResults && autoConfigSection) {
      scanResults = document.createElement('div')
      scanResults.id = `scan-results-${mode}`
      scanResults.className = 'scan-results'
      autoConfigSection.appendChild(scanResults)
    }
    if (!scanResults) {
      return
    }

    scanResults.innerHTML = '<div class="scan-loading"><i class="fas fa-spinner fa-spin"></i> Scanning for UPS devices...</div>'
    scanResults.classList.remove('hidden')
    ctx.actions.clearSelectedAutoDetectedDevice?.(mode)
    ctx.actions.showPrimaryAutoDetectFields?.(mode, false)

    if (!currentUpsName && nameInput.value.trim()) {
      currentUpsName = nameInput.value.trim()
    }

    fetch('/nut_config/api/setup/run-nut-scanner', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        scan_types: ['usb', 'snmp'],
        current_ups_name: currentUpsName || 'ups',
      }),
    })
      .then((response) => response.json())
      .then((data) => {
        if (data.status === 'success' && data.devices && data.devices.length > 0) {
          scanResults.innerHTML = '<div class="scan-results-title">Detected UPS Devices</div><div class="scan-results-hint">Please select one device.</div>'
          data.devices.forEach((device) => {
            const deviceElement = document.createElement('div')
            deviceElement.className = 'scan-device'
            deviceElement.__device = device
            deviceElement.innerHTML = `<div class="scan-device-name">${device.name}</div><div class="scan-device-details">Driver: ${device.driver || 'Unknown'}<br>Port: ${device.port || 'Unknown'}</div>`

            deviceElement.addEventListener('click', function selectDevice() {
              if (state.primaryTargetPrepared) {
                ctx.actions.resetPrimaryTargetPreparedState(true)
              }
              scanResults.querySelectorAll('.scan-device').forEach((node) => node.classList.remove('selected'))
              this.classList.add('selected')

              if (device.driver) {
                const driverOptions = Array.from(driverSelect.options)
                const matchingOption = driverOptions.find((option) => option.value === device.driver)
                if (matchingOption) {
                  driverSelect.value = device.driver
                  ctx.actions.updatePrimarySnmpFieldVisibility()
                }
              }
              if (device.port) {
                portInput.value = device.port
              }

              const latestUpsName = String(nameInput?.value || '').trim()
              const scannedUpsName = String(currentUpsName || '').trim()
              let resolvedUpsName = latestUpsName
              if (!resolvedUpsName) {
                if (scannedUpsName) {
                  resolvedUpsName = scannedUpsName
                } else if (device.name && device.name !== 'unknown') {
                  resolvedUpsName = String(device.name)
                } else if (device.model) {
                  resolvedUpsName = String(device.model).toLowerCase().replace(/[^a-z0-9]/g, '_')
                }
              }
              if (resolvedUpsName) {
                nameInput.value = resolvedUpsName
              }
              if (displayNameInput && !String(displayNameInput.value || '').trim() && resolvedUpsName) {
                displayNameInput.value = resolvedUpsName
              }

              const description = []
              if (device.model) description.push(device.model)
              if (device.vendor) description.push(device.vendor)
              if (device.serial) description.push(`S/N:${device.serial}`)
              descInput.value = description.length > 0 ? description.join(' ') : `Detected ${nameInput.value}`

              if (device.raw_config && state.configData) {
                state.configData.raw_ups_config = device.raw_config
              }
              const autoDeviceCache = getAutoDetectedDeviceCache()
              autoDeviceCache[mode] = device

              ctx.actions.showPrimaryAutoDetectFields?.(mode, true)

              const selectedHint = scanResults.querySelector('.scan-selected-hint')
              const hintText = `Selected: ${device.name || nameInput.value}. Review the target details below, then press Next.`
              if (selectedHint) {
                selectedHint.textContent = hintText
              } else {
                const selectedHintEl = document.createElement('div')
                selectedHintEl.className = 'scan-selected-hint'
                selectedHintEl.textContent = hintText
                scanResults.appendChild(selectedHintEl)
              }
            })

            scanResults.appendChild(deviceElement)
          })
          return
        }

        scanResults.innerHTML = '<div class="no-devices-found">No UPS devices detected. Try connecting your UPS and scan again.</div><div class="scan-results-hint">No devices found. Switch to Manual Configuration if needed.</div>'
        ctx.actions.clearSelectedAutoDetectedDevice?.(mode)
      })
      .catch((error) => {
        console.error('Error:', error)
        scanResults.innerHTML = `<div class="no-devices-found">Error scanning for UPS devices: ${error.message}</div>`
        ctx.actions.clearSelectedAutoDetectedDevice?.(mode)
      })
  }

  ctx.actions.loadAvailableDrivers = function loadAvailableDrivers() {
    fetch('/nut_config/api/setup/get-available-drivers')
      .then((response) => response.json())
      .then((data) => {
        if (data.status === 'success' && data.drivers && data.drivers.length > 0) {
          elements.standaloneDriverSelect.innerHTML = ''
          elements.netserverDriverSelect.innerHTML = ''
          let usbhidUpsFound = false

          data.drivers.forEach((driver) => {
            const isUsbhidUps = driver.name === 'usbhid-ups'
            if (isUsbhidUps) {
              usbhidUpsFound = true
            }

            const standaloneOption = document.createElement('option')
            standaloneOption.value = driver.name
            standaloneOption.textContent = `${driver.name}${driver.description ? ': ' + driver.description : ''}`
            standaloneOption.selected = isUsbhidUps
            elements.standaloneDriverSelect.appendChild(standaloneOption)

            const netserverOption = document.createElement('option')
            netserverOption.value = driver.name
            netserverOption.textContent = `${driver.name}${driver.description ? ': ' + driver.description : ''}`
            netserverOption.selected = isUsbhidUps
            elements.netserverDriverSelect.appendChild(netserverOption)
          })

          if (!usbhidUpsFound) {
            Array.from(elements.standaloneDriverSelect.options).forEach((option, index) => {
              if (option.value === 'usbhid-ups') {
                elements.standaloneDriverSelect.selectedIndex = index
              }
            })
            Array.from(elements.netserverDriverSelect.options).forEach((option, index) => {
              if (option.value === 'usbhid-ups') {
                elements.netserverDriverSelect.selectedIndex = index
              }
            })
          }
          return
        }

        const errorMsg = data.message || 'Failed to load drivers from server'
        ctx.actions.showAlert(`${errorMsg}. Check the driver directory settings in settings_path.txt file.`, 'error')

        ;['usbhid-ups', 'snmp-ups'].forEach((driverName) => {
          const standaloneOption = document.createElement('option')
          standaloneOption.value = driverName
          standaloneOption.textContent = driverName
          standaloneOption.selected = driverName === 'usbhid-ups'
          elements.standaloneDriverSelect.appendChild(standaloneOption)

          const netserverOption = document.createElement('option')
          netserverOption.value = driverName
          netserverOption.textContent = driverName
          netserverOption.selected = driverName === 'usbhid-ups'
          elements.netserverDriverSelect.appendChild(netserverOption)
        })
      })
      .catch((error) => {
        console.error('Error loading available drivers:', error)
        ctx.actions.showAlert(`Error loading drivers: ${error.message}. Check server logs for details.`, 'error')
        const defaultOption = document.createElement('option')
        defaultOption.value = 'usbhid-ups'
        defaultOption.textContent = 'USB UPS (usbhid-ups)'
        defaultOption.selected = true
        elements.standaloneDriverSelect.innerHTML = ''
        elements.netserverDriverSelect.innerHTML = ''
        elements.standaloneDriverSelect.appendChild(defaultOption.cloneNode(true))
        elements.netserverDriverSelect.appendChild(defaultOption)
      })
      .finally(() => {
        ctx.actions.updatePrimarySnmpFieldVisibility()
        ctx.actions.updateManualUsbPortPicker('standalone')
        ctx.actions.updateManualUsbPortPicker('netserver')
      })
  }

  ctx.actions.setupScanButtons = function setupScanButtons() {
    if (elements.scanStandaloneBtn) {
      elements.scanStandaloneBtn.addEventListener('click', function onStandaloneScan() {
        ctx.actions.runNutScanner('standalone')
      })
    }
    if (elements.scanNetserverBtn) {
      elements.scanNetserverBtn.addEventListener('click', function onNetserverScan() {
        ctx.actions.runNutScanner('netserver')
      })
    }
  }

  ctx.actions.setupConfigMethodRadios = function setupConfigMethodRadios() {
    const selectMethod = (mode, method) => {
      const modeElements = getModeElements(mode)
      if (!modeElements.manualOption || !modeElements.autoOption || !modeElements.manualRadio || !modeElements.autoRadio || !modeElements.manualConfig || !modeElements.autoConfig) {
        return
      }

      ctx.actions.resetPrimaryTargetPreparedState(true)
      const isManual = method === 'manual'
      modeElements.manualRadio.checked = isManual
      modeElements.autoRadio.checked = !isManual
      modeElements.manualOption.classList.toggle('selected', isManual)
      modeElements.autoOption.classList.toggle('selected', !isManual)
      modeElements.manualConfig.classList.toggle('hidden', !isManual)
      modeElements.autoConfig.classList.toggle('hidden', isManual)
      ctx.actions.syncPrimaryAutoDetectLayout?.(mode, method)
      ctx.actions.setAwaitingMethodChoice(mode, false)

      if (isManual) {
        ctx.actions.restorePrimaryAutoDetectLayout?.(mode)
        ctx.actions.hideScannerArtifacts(mode)
        ctx.actions.updatePrimarySnmpFieldVisibility()
        ctx.actions.updateManualUsbPortPicker(mode)
        ctx.actions.updatePrimaryTargetWorkflowUi()
        return
      }

      ctx.actions.clearAutoSelectionArtifacts(mode)
      const scanResults = document.getElementById(`scan-results-${mode}`)
      const hasExistingResults = !!scanResults && scanResults.querySelector('.scan-device')
      if (hasExistingResults) {
        scanResults.classList.remove('hidden')
      } else {
        const currentUpsName = String(modeElements.upsNameInput?.value || '').trim()
        ctx.actions.runNutScanner(mode, currentUpsName)
      }
      ctx.actions.updatePrimarySnmpFieldVisibility()
      ctx.actions.updateManualUsbPortPicker(mode)
      ctx.actions.updatePrimaryTargetWorkflowUi()
    }

    ;['standalone', 'netserver'].forEach((mode) => {
      const modeElements = getModeElements(mode)
      modeElements.manualConfig?.classList.add('hidden')
      modeElements.autoConfig?.classList.add('hidden')
      ctx.actions.hideScannerArtifacts(mode)
      ctx.actions.updateManualUsbPortPicker(mode)
      ctx.actions.setAwaitingMethodChoice(mode, true)

      modeElements.manualOption?.addEventListener('click', () => selectMethod(mode, 'manual'))
      modeElements.autoOption?.addEventListener('click', () => selectMethod(mode, 'auto'))
      modeElements.manualRadio?.addEventListener('change', function onManualChange() {
        if (this.checked) {
          selectMethod(mode, 'manual')
        }
      })
      modeElements.autoRadio?.addEventListener('change', function onAutoChange() {
        if (this.checked) {
          selectMethod(mode, 'auto')
        }
      })
    })
  }
}
