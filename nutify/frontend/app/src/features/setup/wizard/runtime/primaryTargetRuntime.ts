// @ts-nocheck

export function registerPrimaryTargetRuntime(ctx) {
  const { elements, state } = ctx

  ctx.actions.getSingleTargetDisplayName = function getSingleTargetDisplayName(mode = state.selectedMode, fallbackToIdentifier = true) {
    const fieldMap = {
      standalone: elements.standaloneTargetDisplayName,
      netserver: elements.netserverTargetDisplayName,
      netclient: elements.netclientTargetDisplayName,
    }
    const rawValue = String(fieldMap[mode]?.value || '').trim()
    if (rawValue) {
      return rawValue
    }
    if (!fallbackToIdentifier) {
      return ''
    }
    if (mode === 'netclient') {
      return String(document.getElementById('remote_ups_name')?.value || '').trim()
    }
    return String(document.getElementById(mode === 'standalone' ? 'ups_name' : 'server_ups_name')?.value || '').trim()
  }

  ctx.actions.shouldRequestNominalPowerInput = function shouldRequestNominalPowerInput(testResponse, currentNominalValue) {
    const nominalPayload = testResponse && typeof testResponse === 'object' ? testResponse.nominal_power : null
    const requiresManual = Boolean(nominalPayload?.requires_manual_input)
    if (!requiresManual || currentNominalValue) {
      return false
    }
    if (typeof nominalPayload?.inspected_upsc === 'boolean') {
      return nominalPayload.inspected_upsc
    }
    return Boolean(testResponse?.raw && typeof testResponse.raw === 'object')
  }

  ctx.actions.isPrimaryConfigMethodSelected = function isPrimaryConfigMethodSelected() {
    if (state.selectedMode === 'standalone') {
      return !!elements.manualStandaloneRadio?.checked || !!elements.autoStandaloneRadio?.checked
    }
    if (state.selectedMode === 'netserver') {
      return !!elements.manualNetserverRadio?.checked || !!elements.autoNetserverRadio?.checked
    }
    return false
  }

  ctx.actions.getAdditionalTargets = function getAdditionalTargets() {
    return (Array.isArray(state.multiTargets) ? state.multiTargets : []).filter((item) => !item?._is_primary_seed)
  }

  ctx.actions.setPrimaryConfigCollapsed = function setPrimaryConfigCollapsed(isCollapsed, showSummary = true) {
    const standaloneContainer = document.getElementById('config-standalone')
    const netserverContainer = document.getElementById('config-netserver')

    if (standaloneContainer) {
      standaloneContainer.classList.toggle('primary-config-collapsed', !!isCollapsed && state.selectedMode === 'standalone')
    }
    if (netserverContainer) {
      netserverContainer.classList.toggle('primary-config-collapsed', !!isCollapsed && state.selectedMode === 'netserver')
    }
    if (elements.primaryConfigSummaryStandalone) {
      const showStandaloneSummary = !!isCollapsed && !!showSummary && state.selectedMode === 'standalone'
      elements.primaryConfigSummaryStandalone.classList.toggle('hidden', !showStandaloneSummary)
    }
    if (elements.primaryConfigSummaryNetserver) {
      const showNetserverSummary = !!isCollapsed && !!showSummary && state.selectedMode === 'netserver'
      elements.primaryConfigSummaryNetserver.classList.toggle('hidden', !showNetserverSummary)
    }
  }

  ctx.actions.updatePrimaryTargetWorkflowUi = function updatePrimaryTargetWorkflowUi() {
    const isMulti = state.selectedProfile === 'multi'
    const requiresPrimaryWorkflow = isMulti && state.selectedMode !== 'netclient'
    const methodSelected = ctx.actions.isPrimaryConfigMethodSelected()
    const hasAdditionalTargets = ctx.actions.getAdditionalTargets().length > 0
    ctx.actions.updateMultiTargetFlowHint('')

    if (elements.primaryTargetWorkflow) {
      elements.primaryTargetWorkflow.classList.toggle('hidden', !requiresPrimaryWorkflow || !methodSelected)
    }
    if (elements.primaryTargetTestSaveBtn) {
      elements.primaryTargetTestSaveBtn.classList.add('hidden')
      elements.primaryTargetTestSaveBtn.style.display = 'none'
    }

    if (requiresPrimaryWorkflow && state.primaryTargetPrepared) {
      const showPrimarySummary = !state.primaryNextStepUnlocked && !hasAdditionalTargets
      ctx.actions.setPrimaryConfigCollapsed(true, showPrimarySummary)
    } else {
      ctx.actions.setPrimaryConfigCollapsed(false, false)
    }

    if (!elements.multiTargetsSection) {
      return
    }
    if (!isMulti) {
      elements.multiTargetsSection.classList.add('hidden')
      return
    }
    if (requiresPrimaryWorkflow) {
      const showMultiTargetDraft = methodSelected && state.primaryTargetPrepared && (state.primaryNextStepUnlocked || hasAdditionalTargets)
      elements.multiTargetsSection.classList.toggle('hidden', !showMultiTargetDraft)
      ctx.actions.updateButtons(state.currentStep)
      return
    }

    elements.multiTargetsSection.classList.remove('hidden')
    ctx.actions.updateButtons(state.currentStep)
  }

  ctx.actions.resetPrimaryTargetPreparedState = function resetPrimaryTargetPreparedState(showHint = false) {
    state.primaryTargetPrepared = false
    state.primaryNextStepUnlocked = false
    state.primaryTargetNominalPower = null
    if (showHint) {
      ctx.actions.updatePrimaryTargetWorkflowStatus('Primary target changed. Run Test & Save again.', false)
    }
    ctx.actions.updatePrimaryTargetWorkflowUi()
  }

  ctx.actions.inferLocalConnectionTypeFromDriver = function inferLocalConnectionTypeFromDriver(driverValue) {
    const normalized = String(driverValue || '').toLowerCase()
    if (!normalized) {
      return 'local_usb_serial'
    }
    if (normalized.includes('snmp') || normalized.includes('netxml') || normalized.includes('ipmi')) {
      return 'local_network_driver'
    }
    return 'local_usb_serial'
  }

  ctx.actions.collectPrimaryTargetFromCurrentMode = function collectPrimaryTargetFromCurrentMode() {
    if (state.selectedMode !== 'standalone' && state.selectedMode !== 'netserver') {
      ctx.actions.showAlert('Primary target workflow is available only for Standalone or Network Server host mode.', 'error')
      return null
    }

    const isStandalone = state.selectedMode === 'standalone'
    const targetDisplayName = ctx.actions.getSingleTargetDisplayName(state.selectedMode, false)
    const upsName = String(document.getElementById(isStandalone ? 'ups_name' : 'server_ups_name')?.value || '').trim()
    if (!upsName) {
      ctx.actions.showAlert('Please enter a UPS identifier for the primary target.', 'error')
      return null
    }
    if (!targetDisplayName) {
      ctx.actions.showAlert('Please enter a target display name for the primary target.', 'error')
      return null
    }

    const manualRadio = document.getElementById(isStandalone ? 'manual-standalone' : 'manual-netserver')
    const autoRadio = document.getElementById(isStandalone ? 'auto-standalone' : 'auto-netserver')
    const isManual = !!manualRadio?.checked
    const isAuto = !!autoRadio?.checked
    if (!isManual && !isAuto) {
      ctx.actions.showAlert('Please choose Manual Configuration or Auto-detect for the primary target.', 'error')
      return null
    }

    const driverValue = String(document.getElementById(isStandalone ? 'ups_driver' : 'server_ups_driver')?.value || '').trim()
    const localPortValue = String(document.getElementById(isStandalone ? 'ups_port' : 'server_ups_port')?.value || '').trim()
    const localDescription = String(document.getElementById(isStandalone ? 'ups_desc' : 'server_ups_desc')?.value || '').trim()
    const usbMode = isStandalone ? 'standalone' : 'netserver'
    const selectedManualUsbDevice = ctx.actions.getSelectedManualUsbDevice?.(usbMode) || null
    const selectedAutoUsbDevice = ctx.actions.getSelectedAutoDetectedDevice?.(usbMode) || null
    const selectedPrimaryUsbDevice = selectedManualUsbDevice || (isAuto ? selectedAutoUsbDevice : null)
    const manualUsbDeviceCount = Array.isArray(state.manualUsbDevicesByMode?.[usbMode])
      ? state.manualUsbDevicesByMode[usbMode].length
      : 0
    const targetTimezone = ctx.actions.normalizeSetupTimezone(isStandalone ? elements.standaloneTimezone?.value : elements.netserverTimezone?.value, 'UTC')
    const targetCurrency = ctx.actions.normalizeSetupCurrency(isStandalone ? elements.standaloneCurrency?.value : elements.netserverCurrency?.value, 'EUR')
    const snmpPrefix = isStandalone ? '' : 'server_'
    const snmpSettings = ctx.actions.readSnmpSettings(snmpPrefix)

    if (!driverValue) {
      ctx.actions.showAlert('Please select a UPS driver for the primary target.', 'error')
      return null
    }
    if (!localPortValue) {
      ctx.actions.showAlert('Please enter a UPS port/device for the primary target.', 'error')
      return null
    }
    if (
      ctx.actions.inferLocalConnectionTypeFromDriver(driverValue) === 'local_network_driver' &&
      localPortValue.toLowerCase() === 'auto'
    ) {
      ctx.actions.showAlert('Enter the UPS hostname or IP address. Network drivers cannot use auto.', 'error')
      return null
    }
    if (ctx.actions.isSnmpDriver(driverValue)) {
      const snmpError = ctx.actions.validateSnmpSettings(snmpPrefix)
      if (snmpError) {
        ctx.actions.showAlert(snmpError, 'error')
        return null
      }
    }
    if (
      isManual &&
      String(driverValue || '').trim().toLowerCase() === 'usbhid-ups' &&
      String(localPortValue || '').trim().toLowerCase() === 'auto' &&
      manualUsbDeviceCount > 1 &&
      !selectedManualUsbDevice
    ) {
      ctx.actions.showAlert('Multiple USB UPS devices were detected. Select one in "Detected USB Port" for the primary target.', 'error')
      return null
    }
    if (isAuto) {
      const scanResults = document.getElementById(isStandalone ? 'scan-results-standalone' : 'scan-results-netserver')
      if (!scanResults || !scanResults.querySelector('.scan-device.selected')) {
        ctx.actions.showAlert('Select one row in "Detected UPS Devices" before saving the primary target.', 'error')
        return null
      }
    }

    const hostValue = String(document.getElementById(isStandalone ? 'server_address' : 'server_address_ns')?.value || '127.0.0.1').trim() || '127.0.0.1'
    const pollingValue = String(isStandalone ? elements.standalonePollingInterval?.value : elements.netserverPollingInterval?.value).trim()

    let remotePort = 3493
    if (!isStandalone) {
      const listenPortValue = String(document.getElementById('listen_port')?.value || '3493').trim()
      remotePort = ctx.actions.parseIntClamped(listenPortValue, 3493, 1, 65535)
    }

    return {
      name: targetDisplayName,
      ups_name: upsName,
      connection_type: ctx.actions.inferLocalConnectionTypeFromDriver(driverValue),
      host: hostValue,
      port: remotePort,
      nut_mode: state.selectedMode,
      monitor_username: 'monuser',
      monitor_password: '',
      local_driver: driverValue,
      local_port: localPortValue,
      local_description: localDescription || 'Primary UPS',
      db_strategy: 'shared',
      shard_granularity: 'month',
      polling_interval: ctx.actions.parseIntClamped(pollingValue, 1, 1, 60),
      retention_days: 0,
      notify_scope: 'global',
      separate_db_path: '',
      location_enabled: false,
      location: '',
      location_country: '',
      location_region: '',
      location_city: '',
      location_postal_code: '',
      location_address: '',
      enabled: true,
      is_primary: true,
      timezone: targetTimezone,
      currency: targetCurrency,
      ...(ctx.actions.isSnmpDriver(driverValue) ? snmpSettings : ctx.actions.readSnmpSettings('__disabled_')),
      usb_vendorid: String(selectedPrimaryUsbDevice?.vendorid || '').trim(),
      usb_productid: String(selectedPrimaryUsbDevice?.productid || '').trim(),
      usb_serial: String(selectedPrimaryUsbDevice?.serial || '').trim(),
      usb_vendor: String(selectedPrimaryUsbDevice?.vendor || '').trim(),
      usb_product: String(selectedPrimaryUsbDevice?.model || selectedPrimaryUsbDevice?.product || '').trim(),
      usb_bus: String(selectedPrimaryUsbDevice?.bus || '').trim(),
      usb_device: String(selectedPrimaryUsbDevice?.device || '').trim(),
      usb_busport: String(selectedPrimaryUsbDevice?.busport || '').trim(),
      ups_realpower_nominal: ctx.actions.coerceOptionalPositiveInt(state.primaryTargetNominalPower),
    }
  }

  ctx.actions.upsertPrimaryTarget = function upsertPrimaryTarget(target, signature) {
    const primaryTarget = { ...target, _tested: true, _test_signature: signature, _is_primary_seed: true, is_primary: true }
    const secondaryTargets = (Array.isArray(state.multiTargets) ? state.multiTargets : [])
      .filter((item) => !item._is_primary_seed)
      .map((item) => ({ ...item, is_primary: false }))
    state.multiTargets = [primaryTarget, ...secondaryTargets]
  }

  ctx.actions.setupPrimaryTargetWorkflowHandlers = function setupPrimaryTargetWorkflowHandlers() {
    if (!elements.primaryTargetTestSaveBtn) {
      return
    }

    const primaryWatchedIds = [
      'ups_target_display_name', 'ups_name', 'ups_driver', 'ups_port', 'ups_desc', 'ups_timezone', 'ups_currency', 'ups_polling_interval',
      'snmp_community', 'snmp_version', 'snmp_sec_level', 'snmp_sec_name', 'snmp_auth_protocol',
      'snmp_auth_password', 'snmp_priv_protocol', 'snmp_priv_password', 'snmp_mibs',
      'server_address', 'manual-standalone', 'auto-standalone',
      'server_target_display_name', 'server_ups_name', 'server_ups_driver', 'server_ups_port', 'server_ups_desc', 'server_timezone',
      'server_currency', 'server_polling_interval', 'server_snmp_community', 'server_snmp_version',
      'server_snmp_sec_level', 'server_snmp_sec_name', 'server_snmp_auth_protocol',
      'server_snmp_auth_password', 'server_snmp_priv_protocol', 'server_snmp_priv_password', 'server_snmp_mibs',
      'server_address_ns', 'listen_address', 'listen_port', 'nut_admin_user', 'nut_admin_password',
      'manual-netserver', 'auto-netserver',
    ]

    primaryWatchedIds.forEach((id) => {
      const element = document.getElementById(id)
      if (!element) {
        return
      }
      const eventName = element.tagName === 'SELECT' || element.type === 'checkbox' || element.type === 'radio' ? 'change' : 'input'
      element.addEventListener(eventName, () => {
        if (!state.primaryTargetPrepared) {
          return
        }
        ctx.actions.resetPrimaryTargetPreparedState(true)
      })
    })

    elements.primaryTargetTestSaveBtn.addEventListener('click', function testAndSavePrimaryTarget() {
      ctx.actions.clearAlerts()
      const target = ctx.actions.collectPrimaryTargetFromCurrentMode()
      if (!target) {
        return
      }

      const payload = {
        ...target,
        host_mode: state.selectedMode,
        monitoring_profile: state.selectedProfile,
        topology: state.selectedTopology,
      }

      elements.primaryTargetTestSaveBtn.disabled = true
      elements.primaryTargetTestSaveBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Testing...'
      if (state.currentStep === 4 && ctx.actions.isWaitingPrimaryTestSaveAction()) {
        elements.nextBtn.disabled = true
        elements.nextBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Testing...'
      }
      ctx.actions.updatePrimaryTargetWorkflowStatus('Testing primary target connection...', null)

      fetch('/nut_config/api/setup/test-target', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })
        .then((response) => response.json().then((data) => ({ status: response.status, data })))
        .then(async ({ status, data }) => {
          const success = status >= 200 && status < 300 && !!data.success
          if (!success) {
            state.primaryTargetPrepared = false
            state.primaryNextStepUnlocked = false
            ctx.actions.updatePrimaryTargetWorkflowStatus('Primary target test failed. Fix fields and test again.', false)
            ctx.actions.updatePrimaryTargetWorkflowUi()
            ctx.actions.showAlert(data.message || data.error || 'Primary target test failed.', 'error')
            return
          }

          let targetNominalPower = ctx.actions.coerceOptionalPositiveInt(data?.nominal_power?.value)
            || ctx.actions.coerceOptionalPositiveInt(target.ups_realpower_nominal)
            || ctx.actions.coerceOptionalPositiveInt(state.primaryTargetNominalPower)
          const needsNominalInput = ctx.actions.shouldRequestNominalPowerInput(data, targetNominalPower)
          if (needsNominalInput && !targetNominalPower) {
            const manualNominalPower = await ctx.actions.requestNominalPowerFromUser(target.name || target.ups_name, state.primaryTargetNominalPower)
            if (!manualNominalPower) {
              state.primaryTargetPrepared = false
              state.primaryNextStepUnlocked = false
              ctx.actions.updatePrimaryTargetWorkflowStatus('Primary target requires UPS nominal power before it can be saved.', false)
              ctx.actions.showAlert('Primary target test passed, but UPS nominal power is required to continue.', 'error')
              return
            }
            targetNominalPower = manualNominalPower
          }

          state.primaryTargetNominalPower = targetNominalPower
          target.ups_realpower_nominal = targetNominalPower
          const signature = ctx.actions.getMultiTargetSignature(target)
          ctx.actions.upsertPrimaryTarget(target, signature)
          state.primaryTargetPrepared = true
          state.primaryNextStepUnlocked = false
          ctx.actions.renderMultiTargets()
          ctx.actions.resetMultiTargetForm()
          ctx.actions.updatePrimaryTargetWorkflowUi()
          ctx.actions.updatePrimaryTargetWorkflowStatus('', null)
          if (elements.multiTargetsSection && !elements.multiTargetsSection.classList.contains('hidden')) {
            elements.multiTargetsSection.scrollIntoView({ behavior: 'smooth', block: 'start' })
          }
        })
        .catch((error) => {
          state.primaryTargetPrepared = false
          state.primaryNextStepUnlocked = false
          ctx.actions.updatePrimaryTargetWorkflowStatus('Primary target test failed due to network error.', false)
          ctx.actions.updatePrimaryTargetWorkflowUi()
          ctx.actions.showAlert(`Primary target test error: ${error.message}`, 'error')
        })
        .finally(() => {
          elements.primaryTargetTestSaveBtn.disabled = false
          elements.primaryTargetTestSaveBtn.innerHTML = '<i class="fas fa-check-circle"></i> Test &amp; Save Primary Target'
          elements.nextBtn.disabled = false
          ctx.actions.updateButtons(state.currentStep)
        })
    })
  }
}
