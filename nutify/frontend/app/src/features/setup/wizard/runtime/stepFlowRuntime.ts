// @ts-nocheck

export function registerStepFlowRuntime(ctx) {
  const { elements, state } = ctx

  function validateAdminStep() {
    if (state.authDisabled) {
      ctx.actions.goToStep(state.currentStep + 1)
      return true
    }

    const adminUsername = document.getElementById('dashboard_admin_username').value.trim()
    const adminPassword = document.getElementById('dashboard_admin_password').value.trim()
    const adminPasswordConfirm = document.getElementById('dashboard_admin_password_confirm').value.trim()

    if (!adminUsername) {
      ctx.actions.showAlert('Please enter an admin username.', 'error')
      return false
    }
    if (adminUsername.length < 3) {
      ctx.actions.showAlert('Admin username must be at least 3 characters long.', 'error')
      return false
    }
    if (!adminPassword) {
      ctx.actions.showAlert('Please enter an admin password.', 'error')
      return false
    }
    if (adminPassword.length < 6) {
      ctx.actions.showAlert('Admin password must be at least 6 characters long.', 'error')
      return false
    }
    if (adminPassword !== adminPasswordConfirm) {
      ctx.actions.showAlert('Passwords do not match. Please check your password confirmation.', 'error')
      return false
    }

    state.configData = state.configData || {}
    state.configData.dashboard_admin_username = adminUsername
    state.configData.dashboard_admin_password = adminPassword
    return true
  }

  function validateServerIdentityStep() {
    const serverName = String(document.getElementById('server_name')?.value || '').trim()
    if (!serverName) {
      ctx.actions.showAlert('Please enter a server name.', 'error')
      return false
    }
    if (serverName.length < 2) {
      ctx.actions.showAlert('Server name must be at least 2 characters long.', 'error')
      return false
    }

    state.configData = state.configData || {}
    state.configData.server_name = serverName
    return true
  }

  function validateStep3AndPrepareStep4() {
    const selectedProfileRadio = document.querySelector('input[name="monitoring_profile"]:checked')
    if (!selectedProfileRadio) {
      ctx.actions.showAlert('Please select a monitoring profile before continuing.', 'error')
      return false
    }

    state.selectedProfile = selectedProfileRadio.value === 'multi' ? 'multi' : 'single'
    ctx.actions.updateProfileUi()
    ctx.actions.updateStep2Layout()

    if (state.selectedProfile === 'single') {
      if (!state.selectedMode) {
        ctx.actions.showAlert('Please select a host mode before continuing.', 'error')
        return false
      }
    } else {
      if (!state.selectedTopology) {
        ctx.actions.showAlert('Please select a fleet topology before continuing.', 'error')
        return false
      }
      const derivedMode = ctx.actions.deriveHostModeFromSelections()
      if (!derivedMode) {
        ctx.actions.showAlert('Please select the local host service mode for this topology.', 'error')
        return false
      }
      state.selectedMode = derivedMode
    }

    ctx.actions.syncScenarioSelection?.()

    ctx.actions.resetConfigMethodSelection()
    document.querySelectorAll('.mode-config').forEach((node) => node.classList.add('hidden'))
    const showPrimaryModeConfig = !(state.selectedProfile === 'multi' && state.selectedMode === 'netclient')
    if (showPrimaryModeConfig) {
      document.getElementById(`config-${state.selectedMode}`)?.classList.remove('hidden')
    }

    if (state.selectedProfile !== 'multi') {
      state.primaryTargetPrepared = false
      state.primaryNextStepUnlocked = false
      state.multiTargets = []
      ctx.actions.renderMultiTargets()
      ctx.actions.resetMultiTargetForm()
    } else if (state.selectedMode === 'netclient') {
      state.primaryTargetPrepared = true
      state.primaryNextStepUnlocked = true
    } else {
      state.primaryTargetPrepared = state.multiTargets.some((item) => !!item._is_primary_seed)
      state.primaryNextStepUnlocked = ctx.actions.getAdditionalTargets().length > 0
      if (!state.primaryTargetPrepared) {
        state.primaryNextStepUnlocked = false
        state.multiTargets = state.multiTargets.filter((item) => !item._is_primary_seed)
        ctx.actions.renderMultiTargets()
        ctx.actions.resetMultiTargetForm()
      }
    }

    ctx.actions.updatePrimarySnmpFieldVisibility()
    ctx.actions.updatePrimaryTargetWorkflowUi()
    if (elements.stepTitle) {
      elements.stepTitle.textContent = `Step ${state.currentStep + 1}: Primary Target Configuration`
    }
    return true
  }

  function validateStandaloneStep3() {
    const targetDisplayName = ctx.actions.getSingleTargetDisplayName('standalone', false)
    const upsName = document.getElementById('ups_name').value.trim()
    if (!targetDisplayName) {
      ctx.actions.showAlert('Please enter a target display name.', 'error')
      return false
    }
    if (!upsName) {
      ctx.actions.showAlert('Please enter a UPS identifier.', 'error')
      return false
    }
    const manualRadio = document.getElementById('manual-standalone')
    const autoRadio = document.getElementById('auto-standalone')
    if (!manualRadio.checked && !autoRadio.checked) {
      ctx.actions.showAlert('Please select a configuration method (Manual or Auto-detect).', 'error')
      return false
    }
    const upsDriver = document.getElementById('ups_driver').value
    if (manualRadio.checked) {
      const upsPort = document.getElementById('ups_port').value.trim()
      if (!upsDriver) {
        ctx.actions.showAlert('Please select a UPS driver.', 'error')
        return false
      }
      if (!upsPort) {
        ctx.actions.showAlert('Please enter a port for the UPS connection.', 'error')
        return false
      }
      if (ctx.actions.isSnmpDriver(upsDriver) && !String(elements.standaloneSnmpCommunity?.value || '').trim()) {
        ctx.actions.showAlert('SNMP community is required when using snmp-ups.', 'error')
        return false
      }
    }
    if (autoRadio.checked) {
      const scanResults = document.getElementById('scan-results-standalone')
      if (!scanResults || !scanResults.querySelector('.scan-device.selected')) {
        ctx.actions.showAlert('Select one row in "Detected UPS Devices", or switch to Manual Configuration.', 'error')
        return false
      }
      if (ctx.actions.isSnmpDriver(upsDriver) && !String(elements.standaloneSnmpCommunity?.value || '').trim()) {
        ctx.actions.showAlert('SNMP community is required when using snmp-ups.', 'error')
        return false
      }
    }
    return true
  }

  function validateNetserverStep3() {
    const targetDisplayName = ctx.actions.getSingleTargetDisplayName('netserver', false)
    const upsName = document.getElementById('server_ups_name').value.trim()
    if (!targetDisplayName) {
      ctx.actions.showAlert('Please enter a target display name.', 'error')
      return false
    }
    if (!upsName) {
      ctx.actions.showAlert('Please enter a UPS identifier.', 'error')
      return false
    }
    const manualRadio = document.getElementById('manual-netserver')
    const autoRadio = document.getElementById('auto-netserver')
    if (!manualRadio.checked && !autoRadio.checked) {
      ctx.actions.showAlert('Please select a configuration method (Manual or Auto-detect).', 'error')
      return false
    }
    const upsDriver = document.getElementById('server_ups_driver').value
    if (manualRadio.checked) {
      const upsPort = document.getElementById('server_ups_port').value.trim()
      const adminUser = document.getElementById('nut_admin_user').value.trim()
      const adminPassword = document.getElementById('nut_admin_password').value.trim()
      if (!upsDriver) {
        ctx.actions.showAlert('Please select a UPS driver.', 'error')
        return false
      }
      if (!upsPort) {
        ctx.actions.showAlert('Please enter a port for the UPS connection.', 'error')
        return false
      }
      if (!adminUser) {
        ctx.actions.showAlert('Please enter a NUT admin username.', 'error')
        return false
      }
      if (!adminPassword) {
        ctx.actions.showAlert('Please enter a NUT admin password.', 'error')
        return false
      }
      if (ctx.actions.isSnmpDriver(upsDriver) && !String(elements.netserverSnmpCommunity?.value || '').trim()) {
        ctx.actions.showAlert('SNMP community is required when using snmp-ups.', 'error')
        return false
      }
    }
    if (autoRadio.checked) {
      const scanResults = document.getElementById('scan-results-netserver')
      if (!scanResults || !scanResults.querySelector('.scan-device.selected')) {
        ctx.actions.showAlert('Select one row in "Detected UPS Devices", or switch to Manual Configuration.', 'error')
        return false
      }
      if (ctx.actions.isSnmpDriver(upsDriver) && !String(elements.netserverSnmpCommunity?.value || '').trim()) {
        ctx.actions.showAlert('SNMP community is required when using snmp-ups.', 'error')
        return false
      }
    }
    return true
  }

  function validateNetclientStep3() {
    const targetDisplayName = ctx.actions.getSingleTargetDisplayName('netclient', false)
    const remoteUpsName = document.getElementById('remote_ups_name').value.trim()
    const remoteHost = document.getElementById('remote_host').value.trim()
    const remoteUser = document.getElementById('remote_user').value.trim()
    if (!targetDisplayName) {
      ctx.actions.showAlert('Please enter a target display name.', 'error')
      return false
    }
    if (!remoteUpsName) {
      ctx.actions.showAlert('Please enter the UPS identifier.', 'error')
      return false
    }
    if (!remoteHost) {
      ctx.actions.showAlert('Please enter the remote server address.', 'error')
      return false
    }
    if (!remoteUser) {
      ctx.actions.showAlert('Please enter the remote username.', 'error')
      return false
    }
    return true
  }

  function validateMultiStep3() {
    const additionalTargets = ctx.actions.getAdditionalTargets()
    if (state.selectedMode !== 'netclient' && !state.primaryTargetPrepared) {
      ctx.actions.showAlert('Test and save the primary target before adding or reviewing additional targets.', 'error')
      return false
    }
    if (additionalTargets.length === 0) {
      ctx.actions.showAlert('Add and save the next UPS target before continuing.', 'error')
      return false
    }
    if (ctx.actions.hasPendingMultiTargetDraft()) {
      ctx.actions.showAlert('Complete the current target draft: Test Target, Save Target, then continue.', 'error')
      return false
    }
    const duplicateNames = new Set()
    for (const target of additionalTargets) {
      const normalizedName = String(target.name || '').trim().toLowerCase()
      if (!normalizedName) {
        ctx.actions.showAlert('Each additional target must have a valid name.', 'error')
        return false
      }
      if (duplicateNames.has(normalizedName)) {
        ctx.actions.showAlert('Target names must be unique.', 'error')
        return false
      }
      duplicateNames.add(normalizedName)
    }
    return true
  }

  ctx.actions.goToNextStep = function goToNextStep() {
    ctx.actions.clearAlerts()

    if (state.currentStep === 4 && ctx.actions.isWaitingPrimaryTestSaveAction()) {
      elements.primaryTargetTestSaveBtn?.click()
      return
    }

    if (state.currentStep === 1) {
      if (!validateAdminStep()) {
        return
      }
    } else if (state.currentStep === 2) {
      if (!validateServerIdentityStep()) {
        return
      }
    } else if (state.currentStep === 3) {
      if (!validateStep3AndPrepareStep4()) {
        return
      }
    } else if (state.currentStep === 4) {
      if (state.selectedProfile === 'multi' && state.selectedMode !== 'netclient' && state.primaryTargetPrepared && !state.primaryNextStepUnlocked && ctx.actions.getAdditionalTargets().length === 0) {
        state.primaryNextStepUnlocked = true
        ctx.actions.updatePrimaryTargetWorkflowUi()
        if (elements.multiTargetsSection && !elements.multiTargetsSection.classList.contains('hidden')) {
          elements.multiTargetsSection.scrollIntoView({ behavior: 'smooth', block: 'start' })
        }
        return
      }

      if (state.selectedProfile === 'multi') {
        if (!validateMultiStep3()) {
          return
        }
      } else {
        if (state.selectedMode === 'standalone' && !validateStandaloneStep3()) {
          return
        }
        if (state.selectedMode === 'netserver' && !validateNetserverStep3()) {
          return
        }
        if (state.selectedMode === 'netclient' && !validateNetclientStep3()) {
          return
        }
      }

      ctx.actions.generateConfigPreview()
    } else if (state.currentStep === 5) {
      elements.nextBtn.classList.add('hidden')
      elements.saveBtn.classList.remove('hidden')
      return
    }

    ctx.actions.goToStep(state.currentStep + 1)
  }
}
