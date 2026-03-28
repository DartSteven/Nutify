// @ts-nocheck

export function registerPrimaryManualUsbRuntime(ctx) {
  const { elements, state } = ctx
  const USB_DRIVER_NAME = 'usbhid-ups'

  function ensureUsbDeviceMeta(device, index) {
    const port = String(device?.port || 'auto').trim() || 'auto'
    const serial = String(device?.serial || '').trim()
    const vendorId = String(device?.vendorid || '').trim()
    const productId = String(device?.productid || '').trim()
    const name = String(device?.name || 'device').trim() || 'device'
    return {
      ...device,
      _usbKey: `${serial}|${vendorId}|${productId}|${port}|${name}|${index}`,
      _usbPort: port,
    }
  }

  function getManualUsbModeElements(mode) {
    const isStandalone = mode === 'standalone'
    return {
      driverSelect: isStandalone ? elements.standaloneDriverSelect : elements.netserverDriverSelect,
      portInput: isStandalone ? elements.standalonePortInput : elements.netserverPortInput,
      manualRadio: isStandalone ? elements.manualStandaloneRadio : elements.manualNetserverRadio,
      autoRadio: isStandalone ? elements.autoStandaloneRadio : elements.autoNetserverRadio,
      upsNameInput: document.getElementById(isStandalone ? 'ups_name' : 'server_ups_name'),
      usbPicker: isStandalone ? elements.standaloneUsbPortPicker : elements.netserverUsbPortPicker,
      usbPortSelect: isStandalone ? elements.standaloneDetectedUsbPortSelect : elements.netserverDetectedUsbPortSelect,
      usbRefreshBtn: isStandalone ? elements.standaloneUsbPortRefreshBtn : elements.netserverUsbPortRefreshBtn,
      usbHelp: isStandalone ? elements.standaloneUsbPortPickerHelp : elements.netserverUsbPortPickerHelp,
    }
  }

  function getManualUsbCache() {
    if (!state.manualUsbDevicesByMode) {
      state.manualUsbDevicesByMode = {}
    }
    return state.manualUsbDevicesByMode
  }

  function getManualUsbSelectedCache() {
    if (!state.manualUsbSelectedDeviceByMode) {
      state.manualUsbSelectedDeviceByMode = {}
    }
    return state.manualUsbSelectedDeviceByMode
  }

  ctx.actions.getSelectedManualUsbDevice = function getSelectedManualUsbDevice(mode) {
    const selectedCache = getManualUsbSelectedCache()
    return selectedCache[mode] || null
  }

  ctx.actions.renderManualUsbPortOptions = function renderManualUsbPortOptions(mode, devices = [], helpMessage = '') {
    const modeElements = getManualUsbModeElements(mode)
    if (!modeElements.usbPortSelect) {
      return
    }

    const selectedCache = getManualUsbSelectedCache()
    const previousValue = String(modeElements.usbPortSelect.value || '').trim()
    const previousSelectedKey = String(selectedCache[mode]?._usbKey || '').trim()
    const currentPort = String(modeElements.portInput?.value || '').trim()
    modeElements.usbPortSelect.innerHTML = ''

    const defaultOption = document.createElement('option')
    defaultOption.value = ''
    defaultOption.textContent = 'Select a detected USB port'
    modeElements.usbPortSelect.appendChild(defaultOption)

    const normalizedDevices = Array.isArray(devices)
      ? devices.map((device, index) => ensureUsbDeviceMeta(device, index))
      : []
    const devicesByKey = new Map()

    normalizedDevices.forEach((device) => {
      devicesByKey.set(device._usbKey, device)
      const option = document.createElement('option')
      option.value = device._usbKey
      option.dataset.port = device._usbPort
      const labelParts = [device._usbPort]
      if (String(device?.serial || '').trim()) {
        labelParts.push(`S/N:${String(device.serial).trim()}`)
      }
      if (String(device?.vendorid || '').trim() && String(device?.productid || '').trim()) {
        labelParts.push(`VID:PID ${String(device.vendorid).trim()}:${String(device.productid).trim()}`)
      }
      if (!String(device?.serial || '').trim()) {
        const busport = String(device?.busport || '').trim()
        const bus = String(device?.bus || '').trim()
        const dev = String(device?.device || '').trim()
        if (busport) {
          labelParts.push(`BUSPORT:${busport}`)
        } else if (bus || dev) {
          labelParts.push(`BUS:DEV ${bus || '?'}:${dev || '?'}`)
        }
      }
      const name = String(device?.name || 'device').trim()
      option.textContent = `${labelParts.join(' | ')} (${name})`
      modeElements.usbPortSelect.appendChild(option)
    })

    if (normalizedDevices.length === 0) {
      const emptyOption = document.createElement('option')
      emptyOption.value = ''
      emptyOption.textContent = 'No USB UPS ports detected'
      emptyOption.disabled = true
      modeElements.usbPortSelect.appendChild(emptyOption)
      selectedCache[mode] = null
    }

    let selectedValue = ''
    if (previousSelectedKey && devicesByKey.has(previousSelectedKey)) {
      selectedValue = previousSelectedKey
    } else if (previousValue && devicesByKey.has(previousValue)) {
      selectedValue = previousValue
    } else if (currentPort) {
      const matchingByPort = normalizedDevices.filter((device) => device._usbPort === currentPort)
      if (matchingByPort.length === 1) {
        selectedValue = matchingByPort[0]._usbKey
      }
    }

    if (selectedValue && devicesByKey.has(selectedValue)) {
      modeElements.usbPortSelect.value = selectedValue
      selectedCache[mode] = devicesByKey.get(selectedValue)
    } else {
      modeElements.usbPortSelect.value = ''
      selectedCache[mode] = null
    }

    if (modeElements.usbHelp) {
      if (helpMessage) {
        modeElements.usbHelp.textContent = helpMessage
      } else if (normalizedDevices.length > 0) {
        modeElements.usbHelp.textContent = 'Choose the detected USB device for this UPS. Selecting one fills the Port field above and keeps USB identity details.'
      } else {
        modeElements.usbHelp.textContent = 'No USB port detected right now. Check the UPS cable and press Refresh.'
      }
    }
  }

  ctx.actions.scanManualUsbPorts = function scanManualUsbPorts(mode) {
    const modeElements = getManualUsbModeElements(mode)
    if (!modeElements.usbPortSelect || !modeElements.driverSelect) {
      return Promise.resolve()
    }

    if (modeElements.usbRefreshBtn) {
      modeElements.usbRefreshBtn.disabled = true
    }
    if (modeElements.usbHelp) {
      modeElements.usbHelp.textContent = 'Scanning USB ports...'
    }

    const currentUpsName = String(modeElements.upsNameInput?.value || '').trim() || 'ups'
    return fetch('/nut_config/api/setup/run-nut-scanner', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        scan_types: ['usb'],
        current_ups_name: currentUpsName,
      }),
    })
      .then((response) => response.json())
      .then((data) => {
        const devices = data?.status === 'success' && Array.isArray(data.devices)
          ? data.devices.map((device, index) => ensureUsbDeviceMeta(device, index))
          : []
        const cache = getManualUsbCache()
        cache[mode] = devices
        ctx.actions.renderManualUsbPortOptions(mode, devices)
      })
      .catch((error) => {
        console.error('Error scanning USB ports:', error)
        ctx.actions.renderManualUsbPortOptions(mode, [], `Unable to scan USB ports: ${error.message}`)
      })
      .finally(() => {
        if (modeElements.usbRefreshBtn) {
          modeElements.usbRefreshBtn.disabled = false
        }
      })
  }

  ctx.actions.updateManualUsbPortPicker = function updateManualUsbPortPicker(mode, forceRefresh = false) {
    const modeElements = getManualUsbModeElements(mode)
    if (!modeElements.driverSelect || !modeElements.usbPicker) {
      return
    }

    const isManual = !!modeElements.manualRadio?.checked && !modeElements.autoRadio?.checked
    const usesUsbDriver = String(modeElements.driverSelect.value || '').trim() === USB_DRIVER_NAME
    const shouldShow = isManual && usesUsbDriver
    modeElements.usbPicker.classList.toggle('hidden', !shouldShow)

    if (!shouldShow) {
      const selectedCache = getManualUsbSelectedCache()
      selectedCache[mode] = null
      return
    }

    const cache = getManualUsbCache()
    const cachedDevices = Array.isArray(cache[mode]) ? cache[mode] : []
    if (!forceRefresh && cachedDevices.length > 0) {
      ctx.actions.renderManualUsbPortOptions(mode, cachedDevices)
      return
    }
    if (!forceRefresh && cachedDevices.length === 0 && cache[mode]) {
      ctx.actions.renderManualUsbPortOptions(mode, cachedDevices)
      return
    }
    ctx.actions.scanManualUsbPorts(mode)
  }

  ctx.actions.syncManualUsbPickerWithPortInput = function syncManualUsbPickerWithPortInput(mode) {
    const modeElements = getManualUsbModeElements(mode)
    if (!modeElements.usbPortSelect || !modeElements.portInput) {
      return
    }

    const selectedCache = getManualUsbSelectedCache()
    const currentPort = String(modeElements.portInput.value || '').trim()
    if (!currentPort) {
      modeElements.usbPortSelect.value = ''
      selectedCache[mode] = null
      return
    }

    const matchingOptions = Array.from(modeElements.usbPortSelect.options).filter((option) => String(option.dataset.port || '').trim() === currentPort)
    if (matchingOptions.length === 1) {
      modeElements.usbPortSelect.value = matchingOptions[0].value
      const cache = getManualUsbCache()
      const matchedDevice = (Array.isArray(cache[mode]) ? cache[mode] : []).find((device) => String(device?._usbKey || '') === matchingOptions[0].value)
      selectedCache[mode] = matchedDevice || null
    } else {
      modeElements.usbPortSelect.value = ''
      selectedCache[mode] = null
    }
  }

  ctx.actions.setupManualUsbPortPickerHandlers = function setupManualUsbPortPickerHandlers() {
    if (elements.standaloneDetectedUsbPortSelect) {
      elements.standaloneDetectedUsbPortSelect.addEventListener('change', function onStandaloneUsbPortChange() {
        const selectedValue = String(this.value || '').trim()
        const selectedOption = this.options[this.selectedIndex]
        const selectedPort = String(selectedOption?.dataset?.port || '').trim()
        const cache = getManualUsbCache()
        const selectedCache = getManualUsbSelectedCache()
        selectedCache.standalone = (Array.isArray(cache.standalone) ? cache.standalone : []).find((device) => String(device?._usbKey || '') === selectedValue) || null
        if (selectedPort && elements.standalonePortInput) {
          elements.standalonePortInput.value = selectedPort
          if (state.primaryTargetPrepared) {
            ctx.actions.resetPrimaryTargetPreparedState(true)
          }
        }
      })
    }

    if (elements.netserverDetectedUsbPortSelect) {
      elements.netserverDetectedUsbPortSelect.addEventListener('change', function onNetserverUsbPortChange() {
        const selectedValue = String(this.value || '').trim()
        const selectedOption = this.options[this.selectedIndex]
        const selectedPort = String(selectedOption?.dataset?.port || '').trim()
        const cache = getManualUsbCache()
        const selectedCache = getManualUsbSelectedCache()
        selectedCache.netserver = (Array.isArray(cache.netserver) ? cache.netserver : []).find((device) => String(device?._usbKey || '') === selectedValue) || null
        if (selectedPort && elements.netserverPortInput) {
          elements.netserverPortInput.value = selectedPort
          if (state.primaryTargetPrepared) {
            ctx.actions.resetPrimaryTargetPreparedState(true)
          }
        }
      })
    }

    if (elements.standalonePortInput) {
      elements.standalonePortInput.addEventListener('input', () => ctx.actions.syncManualUsbPickerWithPortInput('standalone'))
      elements.standalonePortInput.addEventListener('change', () => ctx.actions.syncManualUsbPickerWithPortInput('standalone'))
    }

    if (elements.netserverPortInput) {
      elements.netserverPortInput.addEventListener('input', () => ctx.actions.syncManualUsbPickerWithPortInput('netserver'))
      elements.netserverPortInput.addEventListener('change', () => ctx.actions.syncManualUsbPickerWithPortInput('netserver'))
    }

    if (elements.standaloneUsbPortRefreshBtn) {
      elements.standaloneUsbPortRefreshBtn.addEventListener('click', () => {
        ctx.actions.scanManualUsbPorts('standalone')
      })
    }

    if (elements.netserverUsbPortRefreshBtn) {
      elements.netserverUsbPortRefreshBtn.addEventListener('click', () => {
        ctx.actions.scanManualUsbPorts('netserver')
      })
    }

    if (elements.manualStandaloneRadio) {
      elements.manualStandaloneRadio.addEventListener('change', () => ctx.actions.updateManualUsbPortPicker('standalone'))
    }
    if (elements.autoStandaloneRadio) {
      elements.autoStandaloneRadio.addEventListener('change', () => ctx.actions.updateManualUsbPortPicker('standalone'))
    }
    if (elements.manualNetserverRadio) {
      elements.manualNetserverRadio.addEventListener('change', () => ctx.actions.updateManualUsbPortPicker('netserver'))
    }
    if (elements.autoNetserverRadio) {
      elements.autoNetserverRadio.addEventListener('change', () => ctx.actions.updateManualUsbPortPicker('netserver'))
    }

    ctx.actions.updateManualUsbPortPicker('standalone')
    ctx.actions.updateManualUsbPortPicker('netserver')
  }
}
