// @ts-nocheck

import { bindWizardEventOnce } from './domBindings'

export function registerMultiTargetUsbRuntime(ctx) {
  const { elements, state } = ctx

  function isMultiLocalUsbDriverMode() {
    const connectionType = String(elements.multiTargetConnectionType?.value || '').toLowerCase()
    const localDriver = String(elements.multiTargetLocalDriver?.value || '').trim().toLowerCase()
    return connectionType === 'local_usb_serial' && localDriver === 'usbhid-ups'
  }

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

  ctx.actions.clearMultiTargetUsbSelection = function clearMultiTargetUsbSelection() {
    state.multiTargetSelectedUsbDevice = null
    if (elements.multiTargetDetectedUsbPortSelect) {
      elements.multiTargetDetectedUsbPortSelect.value = ''
    }
  }

  ctx.actions.getSelectedMultiTargetUsbDevice = function getSelectedMultiTargetUsbDevice() {
    return state.multiTargetSelectedUsbDevice || null
  }

  ctx.actions.renderMultiTargetUsbPortOptions = function renderMultiTargetUsbPortOptions(devices = [], helpMessage = '') {
    if (!elements.multiTargetDetectedUsbPortSelect) {
      return
    }

    const currentPort = String(elements.multiTargetLocalPort?.value || '').trim()
    const previousSelectedKey = String(state.multiTargetSelectedUsbDevice?._usbKey || '').trim()
    const select = elements.multiTargetDetectedUsbPortSelect
    select.innerHTML = ''

    const defaultOption = document.createElement('option')
    defaultOption.value = ''
    defaultOption.textContent = 'Select a detected USB port'
    select.appendChild(defaultOption)

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
      option.textContent = `${labelParts.join(' | ')} (${String(device?.name || 'device').trim() || 'device'})`
      select.appendChild(option)
    })

    if (!normalizedDevices.length) {
      const emptyOption = document.createElement('option')
      emptyOption.value = ''
      emptyOption.textContent = 'No USB UPS ports detected'
      emptyOption.disabled = true
      select.appendChild(emptyOption)
      state.multiTargetSelectedUsbDevice = null
    }

    let selectedKey = ''
    if (previousSelectedKey && devicesByKey.has(previousSelectedKey)) {
      selectedKey = previousSelectedKey
    } else if (currentPort) {
      const matchedByPort = normalizedDevices.filter((device) => device._usbPort === currentPort)
      if (matchedByPort.length === 1) {
        selectedKey = matchedByPort[0]._usbKey
      }
    }

    if (selectedKey && devicesByKey.has(selectedKey)) {
      select.value = selectedKey
      state.multiTargetSelectedUsbDevice = devicesByKey.get(selectedKey)
    } else {
      select.value = ''
      state.multiTargetSelectedUsbDevice = null
    }

    if (elements.multiTargetUsbPortPickerHelp) {
      if (helpMessage) {
        elements.multiTargetUsbPortPickerHelp.textContent = helpMessage
      } else if (normalizedDevices.length > 0) {
        elements.multiTargetUsbPortPickerHelp.textContent = 'Choose the detected USB device for this target. Selecting one fills the local port field and preserves USB identity details.'
      } else {
        elements.multiTargetUsbPortPickerHelp.textContent = 'No USB port detected right now. Check UPS passthrough/cabling, then press Refresh.'
      }
    }
  }

  ctx.actions.scanMultiTargetUsbPorts = function scanMultiTargetUsbPorts() {
    if (!elements.multiTargetDetectedUsbPortSelect) {
      return Promise.resolve()
    }

    if (elements.multiTargetUsbPortRefreshBtn) {
      elements.multiTargetUsbPortRefreshBtn.disabled = true
    }
    if (elements.multiTargetUsbPortPickerHelp) {
      elements.multiTargetUsbPortPickerHelp.textContent = 'Scanning USB ports...'
    }

    const currentUpsName = String(elements.multiTargetUpsName?.value || '').trim() || 'ups'
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
        state.multiTargetUsbDevices = devices
        ctx.actions.renderMultiTargetUsbPortOptions(devices)
      })
      .catch((error) => {
        console.error('Error scanning USB ports for target draft:', error)
        state.multiTargetUsbDevices = []
        ctx.actions.renderMultiTargetUsbPortOptions([], `Unable to scan USB ports: ${error.message}`)
      })
      .finally(() => {
        if (elements.multiTargetUsbPortRefreshBtn) {
          elements.multiTargetUsbPortRefreshBtn.disabled = false
        }
      })
  }

  ctx.actions.syncMultiTargetUsbPickerWithPortInput = function syncMultiTargetUsbPickerWithPortInput() {
    if (!elements.multiTargetDetectedUsbPortSelect || !elements.multiTargetLocalPort) {
      return
    }
    const currentPort = String(elements.multiTargetLocalPort.value || '').trim()
    if (!currentPort) {
      ctx.actions.clearMultiTargetUsbSelection()
      return
    }

    const select = elements.multiTargetDetectedUsbPortSelect
    const matchingOptions = Array.from(select.options).filter((option) => String(option.dataset.port || '').trim() === currentPort)
    if (matchingOptions.length !== 1) {
      ctx.actions.clearMultiTargetUsbSelection()
      return
    }

    select.value = matchingOptions[0].value
    state.multiTargetSelectedUsbDevice = (Array.isArray(state.multiTargetUsbDevices) ? state.multiTargetUsbDevices : [])
      .find((device) => String(device?._usbKey || '') === matchingOptions[0].value) || null
  }

  ctx.actions.updateMultiTargetUsbPortPicker = function updateMultiTargetUsbPortPicker(forceRefresh = false) {
    if (!elements.multiTargetUsbPortPicker) {
      return
    }

    const shouldShow = isMultiLocalUsbDriverMode()
    elements.multiTargetUsbPortPicker.classList.toggle('hidden', !shouldShow)
    if (!shouldShow) {
      ctx.actions.clearMultiTargetUsbSelection()
      return
    }

    const cachedDevices = Array.isArray(state.multiTargetUsbDevices) ? state.multiTargetUsbDevices : []
    if (!forceRefresh && cachedDevices.length > 0) {
      ctx.actions.renderMultiTargetUsbPortOptions(cachedDevices)
      return
    }
    if (!forceRefresh && state.multiTargetUsbDevices && cachedDevices.length === 0) {
      ctx.actions.renderMultiTargetUsbPortOptions(cachedDevices)
      return
    }
    ctx.actions.scanMultiTargetUsbPorts()
  }

  ctx.actions.setupMultiTargetUsbPortPickerHandlers = function setupMultiTargetUsbPortPickerHandlers() {
    if (!elements.multiTargetUsbPortPicker) {
      return
    }

    bindWizardEventOnce(elements.multiTargetConnectionType, 'multi-target-usb-connection-type', 'change', () => {
      ctx.actions.updateMultiTargetUsbPortPicker()
    })
    bindWizardEventOnce(elements.multiTargetLocalDriver, 'multi-target-usb-driver', 'change', () => {
      ctx.actions.updateMultiTargetUsbPortPicker()
    })
    bindWizardEventOnce(elements.multiTargetLocalPort, 'multi-target-usb-port-input', 'input', () => {
      ctx.actions.syncMultiTargetUsbPickerWithPortInput()
    })
    bindWizardEventOnce(elements.multiTargetLocalPort, 'multi-target-usb-port-change', 'change', () => {
      ctx.actions.syncMultiTargetUsbPickerWithPortInput()
    })

    bindWizardEventOnce(elements.multiTargetDetectedUsbPortSelect, 'multi-target-usb-select-change', 'change', () => {
      const selectedKey = String(elements.multiTargetDetectedUsbPortSelect?.value || '').trim()
      const selectedOption = elements.multiTargetDetectedUsbPortSelect?.options?.[elements.multiTargetDetectedUsbPortSelect.selectedIndex]
      const selectedPort = String(selectedOption?.dataset?.port || '').trim()
      state.multiTargetSelectedUsbDevice = (Array.isArray(state.multiTargetUsbDevices) ? state.multiTargetUsbDevices : [])
        .find((device) => String(device?._usbKey || '') === selectedKey) || null
      if (selectedPort && elements.multiTargetLocalPort) {
        elements.multiTargetLocalPort.value = selectedPort
      }
      if (state.lastTargetTestSuccess) {
        ctx.actions.invalidateMultiTargetTestState(true)
      }
    })

    bindWizardEventOnce(elements.multiTargetUsbPortRefreshBtn, 'multi-target-usb-refresh', 'click', () => {
      ctx.actions.scanMultiTargetUsbPorts()
    })

    ctx.actions.updateMultiTargetUsbPortPicker()
  }
}
