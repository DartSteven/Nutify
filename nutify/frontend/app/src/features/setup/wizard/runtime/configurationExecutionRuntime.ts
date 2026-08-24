// @ts-nocheck

export function registerConfigurationExecutionRuntime(ctx) {
  const { elements, state } = ctx

  ctx.actions.applyConfiguration = function applyConfiguration() {
    ctx.actions.updateStepIndicators(6)
    ctx.actions.updateButtons(6)
    ctx.actions.showAlert('Configuration is ready to be saved.', 'success')
  }

  ctx.actions.testConfiguration = function testConfiguration() {
    elements.testConfigBtn.disabled = true
    elements.testConfigBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Testing...'
    const testResult = document.getElementById('test-result')
    testResult.classList.add('hidden')
    elements.saveBtn.classList.add('hidden')

    const effectiveProfile = ctx.actions.getEffectiveSetupProfile()
    const effectiveMultiTargets = ctx.actions.buildMultiTargetsPayload()
    fetch('/nut_config/api/setup/test-configuration', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        nut_conf: state.editedFiles['nut.conf'] || state.configFiles['nut.conf'] || '',
        ups_conf: state.editedFiles['ups.conf'] || state.configFiles['ups.conf'] || '',
        upsd_conf: state.editedFiles['upsd.conf'] || state.configFiles['upsd.conf'] || '',
        upsd_users: state.editedFiles['upsd.users'] || state.configFiles['upsd.users'] || '',
        upsmon_conf: state.editedFiles['upsmon.conf'] || state.configFiles['upsmon.conf'] || '',
        monitoring_profile: effectiveProfile,
        multi_targets: effectiveMultiTargets,
      }),
    })
      .then((response) => response.json())
      .then(async (data) => {
        elements.testConfigBtn.disabled = false
        elements.testConfigBtn.innerHTML = '<i class="fas fa-check-circle"></i> Test Configuration'
        if (data.status === 'success') {
          if (effectiveProfile === 'multi') {
            const targetResults = Array.isArray(data.target_results) ? data.target_results : []
            for (let index = 0; index < targetResults.length; index += 1) {
              const targetResult = targetResults[index]
              const targetSpec = String(targetResult?.target || '').trim()
              const matchedTarget = state.multiTargets.find((target) => {
                const host = String(target.host || '').trim()
                const port = ctx.actions.parseIntClamped(target.port, 3493, 1, 65535)
                const candidateSpec = `${String(target.ups_name || '').trim()}@${host}${port === 3493 ? '' : `:${port}`}`
                return candidateSpec === targetSpec
              }) || state.multiTargets[index]
              if (!matchedTarget) {
                continue
              }

              let targetNominalPower = ctx.actions.coerceOptionalPositiveInt(targetResult?.nominal_power?.value)
                || ctx.actions.coerceOptionalPositiveInt(matchedTarget.ups_realpower_nominal)
              if (targetResult?.nominal_power?.requires_manual_input && !targetNominalPower) {
                targetNominalPower = await ctx.actions.requestNominalPowerFromUser(
                  matchedTarget.name || targetSpec,
                  matchedTarget.ups_realpower_nominal,
                )
                if (!targetNominalPower) {
                  ctx.actions.openModal(
                    false,
                    'Configuration test incomplete',
                    `Target "${matchedTarget.name || targetSpec}" requires UPS nominal power.`,
                  )
                  testResult.classList.remove('hidden')
                  testResult.innerHTML = '<div class="alert alert-error"><i class="fas fa-times-circle"></i> UPS nominal power is required before saving.</div>'
                  elements.saveBtn.classList.add('hidden')
                  return
                }
              }
              if (targetNominalPower) {
                matchedTarget.ups_realpower_nominal = targetNominalPower
              }
            }
          }

          const detectedNominalPower = ctx.actions.coerceOptionalPositiveInt(data?.nominal_power?.value)
          const existingNominalPower = ctx.actions.coerceOptionalPositiveInt(state.upsRealpowerNominal)
            || ctx.actions.coerceOptionalPositiveInt(state.primaryTargetNominalPower)
          const effectiveNominalPower = detectedNominalPower || existingNominalPower
          const nominalPower = data?.nominal_power && typeof data.nominal_power === 'object'
            ? {
                ...data.nominal_power,
                found: Boolean(effectiveNominalPower),
                value: effectiveNominalPower || null,
                requires_manual_input: Boolean(data.nominal_power.requires_manual_input && !effectiveNominalPower),
              }
            : null
          if (effectiveNominalPower) {
            state.upsRealpowerNominal = effectiveNominalPower
          }
          let output = data.upsc_output || data.test_details || ''
          if (output && output !== 'Connection successful') {
            output = `<div class="ups-data">${output.split('\n').map((line) => {
              if (line.includes(':')) {
                const [key, value] = line.split(':', 2)
                return `<div class="ups-data-item"><strong>${key.trim()}:</strong> ${value.trim()}</div>`
              }
              return line
            }).join('')}</div>`
          }
          ctx.actions.openModal(true, 'Configuration test successful!', output, nominalPower)
          testResult.classList.remove('hidden')
          testResult.innerHTML = '<div class="alert alert-success"><i class="fas fa-check-circle"></i> Configuration test successful!</div>'
          elements.saveBtn.classList.remove('hidden')
          return
        }

        let errorMessage = data.message || 'Unknown error'
        if (data.errors && data.errors.length > 0) {
          errorMessage = data.errors.join('\n')
        }
        ctx.actions.openModal(false, 'Configuration test failed', errorMessage)
        testResult.classList.remove('hidden')
        testResult.innerHTML = `<div class="alert alert-error"><i class="fas fa-times-circle"></i> Configuration test failed:<br>${errorMessage.replace(/\n/g, '<br>')}</div>`
        elements.saveBtn.classList.add('hidden')
      })
      .catch((error) => {
        console.error('Error:', error)
        elements.testConfigBtn.disabled = false
        elements.testConfigBtn.innerHTML = '<i class="fas fa-check-circle"></i> Test Configuration'
        ctx.actions.openModal(false, 'Error testing configuration', 'Network error occurred while testing.')
        testResult.classList.remove('hidden')
        testResult.innerHTML = '<div class="alert alert-error"><i class="fas fa-times-circle"></i> Error testing configuration: Network error</div>'
        elements.saveBtn.classList.add('hidden')
      })
  }

  ctx.actions.restartServer = function restartServer() {
    elements.restartServerBtn.disabled = true
    const overlay = document.createElement('div')
    overlay.className = 'countdown-overlay'
    document.body.appendChild(overlay)

    const countdownContainer = document.createElement('div')
    countdownContainer.className = 'countdown-container'
    countdownContainer.innerHTML = `
      <div class="countdown-circle-container">
        <svg class="countdown-circle" viewBox="0 0 36 36">
          <path class="countdown-circle-bg" d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831" fill="none" />
          <path class="countdown-circle-progress" d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831" fill="none" stroke-dasharray="100, 100" />
        </svg>
        <div class="countdown-number">30</div>
      </div>
      <div class="countdown-text">Server restarting, please wait...</div>
    `
    document.body.appendChild(countdownContainer)

    const totalSeconds = 30
    let secondsLeft = totalSeconds
    const countdownNumber = countdownContainer.querySelector('.countdown-number')
    const progressCircle = countdownContainer.querySelector('.countdown-circle-progress')
    const circumference = 2 * Math.PI * 15.9155
    progressCircle.style.strokeDasharray = `${circumference} ${circumference}`
    progressCircle.style.strokeDashoffset = '0'

    const countdownInterval = setInterval(() => {
      secondsLeft -= 1
      countdownNumber.textContent = secondsLeft
      const progress = (secondsLeft / totalSeconds) * circumference
      progressCircle.style.strokeDashoffset = circumference - progress
      if (secondsLeft <= 0) {
        clearInterval(countdownInterval)
        window.location.href = '/'
      }
    }, 1000)

    ctx.actions.showAlert('The server is restarting. Please wait...', 'info')
    fetch('/nut_config/api/restart', { method: 'POST' })
      .then((response) => response.json())
      .then((data) => {
        if (data.success) {
          return
        }
        clearInterval(countdownInterval)
        ctx.actions.showAlert('Error restarting server: ' + data.message, 'error')
        document.body.removeChild(countdownContainer)
        document.body.removeChild(overlay)
        elements.restartServerBtn.disabled = false
        elements.restartServerBtn.innerHTML = '<i class="fas fa-sync"></i> Restart Server'
      })
      .catch((error) => {
        console.error('Error:', error)
      })
  }

  ctx.actions.saveConfiguration = function saveConfiguration() {
    elements.saveBtn.disabled = true
    elements.saveBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Saving...'

    const effectiveProfile = ctx.actions.getEffectiveSetupProfile()
    const effectiveMultiTargets = ctx.actions.buildMultiTargetsPayload()
    let configurationData = {
      server_name: String(document.getElementById('server_name')?.value || '').trim() || 'Nutify',
      nut_mode: state.selectedMode,
      connection_scenario: state.selectedMode === 'netclient' ? 'remote_nut' : 'local_usb',
      monitoring_profile: effectiveProfile,
      multi_topology: effectiveProfile === 'multi' ? state.selectedTopology : null,
      host_service_mode: effectiveProfile === 'multi' ? state.selectedHostServiceMode : null,
      multi_targets: effectiveMultiTargets,
      nut_conf: state.editedFiles['nut.conf'] || state.configFiles['nut.conf'] || '',
      ups_conf: state.editedFiles['ups.conf'] || state.configFiles['ups.conf'] || '',
      upsd_conf: state.editedFiles['upsd.conf'] || state.configFiles['upsd.conf'] || '',
      upsd_users: state.editedFiles['upsd.users'] || state.configFiles['upsd.users'] || '',
      upsmon_conf: state.editedFiles['upsmon.conf'] || state.configFiles['upsmon.conf'] || '',
    }

    if (state.upsRealpowerNominal) {
      configurationData.ups_realpower_nominal = state.upsRealpowerNominal
    }

    const adminUsernameField = document.getElementById('dashboard_admin_username')
    const adminPasswordField = document.getElementById('dashboard_admin_password')
    if (adminUsernameField && adminPasswordField) {
      const adminUsername = adminUsernameField.value.trim()
      const adminPassword = adminPasswordField.value.trim()
      if (adminUsername && adminPassword) {
        configurationData.dashboard_admin_username = adminUsername
        configurationData.dashboard_admin_password = adminPassword
      }
    }

    if (state.selectedMode === 'standalone') {
      const selectedManualUsb = ctx.actions.getSelectedManualUsbDevice?.('standalone') || null
      const selectedAutoUsb = ctx.actions.getSelectedAutoDetectedDevice?.('standalone') || null
      const selectedPrimaryUsb = selectedManualUsb || selectedAutoUsb
      configurationData = {
        ...configurationData,
        target_display_name: ctx.actions.getSingleTargetDisplayName('standalone'),
        name: ctx.actions.getSingleTargetDisplayName('standalone'),
        ups_name: document.getElementById('ups_name').value.trim(),
        ups_driver: document.getElementById('ups_driver').value,
        ups_port: document.getElementById('ups_port').value.trim(),
        ups_desc: document.getElementById('ups_desc').value.trim(),
        timezone: ctx.actions.normalizeSetupTimezone(elements.standaloneTimezone?.value, 'UTC'),
        currency: ctx.actions.normalizeSetupCurrency(elements.standaloneCurrency?.value, 'EUR'),
        polling_interval: ctx.actions.parseIntClamped(elements.standalonePollingInterval?.value, 1, 1, 60),
        ...ctx.actions.readSnmpSettings(''),
        usb_vendorid: String(selectedPrimaryUsb?.vendorid || '').trim(),
        usb_productid: String(selectedPrimaryUsb?.productid || '').trim(),
        usb_serial: String(selectedPrimaryUsb?.serial || '').trim(),
        usb_vendor: String(selectedPrimaryUsb?.vendor || '').trim(),
        usb_product: String(selectedPrimaryUsb?.model || selectedPrimaryUsb?.product || '').trim(),
        usb_bus: String(selectedPrimaryUsb?.bus || '').trim(),
        usb_device: String(selectedPrimaryUsb?.device || '').trim(),
        usb_busport: String(selectedPrimaryUsb?.busport || '').trim(),
        ups_realpower_nominal: ctx.actions.coerceOptionalPositiveInt(state.upsRealpowerNominal),
        server_address: document.getElementById('server_address').value.trim() || '127.0.0.1',
        upsc_command: 'upsc',
        upscmd_command: 'upscmd',
      }
    } else if (state.selectedMode === 'netserver') {
      const selectedManualUsb = ctx.actions.getSelectedManualUsbDevice?.('netserver') || null
      const selectedAutoUsb = ctx.actions.getSelectedAutoDetectedDevice?.('netserver') || null
      const selectedPrimaryUsb = selectedManualUsb || selectedAutoUsb
      configurationData = {
        ...configurationData,
        target_display_name: ctx.actions.getSingleTargetDisplayName('netserver'),
        name: ctx.actions.getSingleTargetDisplayName('netserver'),
        ups_name: document.getElementById('server_ups_name').value.trim(),
        ups_driver: document.getElementById('server_ups_driver').value,
        ups_port: document.getElementById('server_ups_port').value.trim(),
        ups_desc: document.getElementById('server_ups_desc').value.trim(),
        timezone: ctx.actions.normalizeSetupTimezone(elements.netserverTimezone?.value, 'UTC'),
        currency: ctx.actions.normalizeSetupCurrency(elements.netserverCurrency?.value, 'EUR'),
        polling_interval: ctx.actions.parseIntClamped(elements.netserverPollingInterval?.value, 1, 1, 60),
        ...ctx.actions.readSnmpSettings('server_'),
        usb_vendorid: String(selectedPrimaryUsb?.vendorid || '').trim(),
        usb_productid: String(selectedPrimaryUsb?.productid || '').trim(),
        usb_serial: String(selectedPrimaryUsb?.serial || '').trim(),
        usb_vendor: String(selectedPrimaryUsb?.vendor || '').trim(),
        usb_product: String(selectedPrimaryUsb?.model || selectedPrimaryUsb?.product || '').trim(),
        usb_bus: String(selectedPrimaryUsb?.bus || '').trim(),
        usb_device: String(selectedPrimaryUsb?.device || '').trim(),
        usb_busport: String(selectedPrimaryUsb?.busport || '').trim(),
        ups_realpower_nominal: ctx.actions.coerceOptionalPositiveInt(state.upsRealpowerNominal),
        server_address: document.getElementById('server_address_ns').value.trim() || '127.0.0.1',
        listen_address: document.getElementById('listen_address').value.trim() || '0.0.0.0',
        listen_port: document.getElementById('listen_port').value.trim() || '3493',
        admin_user: document.getElementById('nut_admin_user').value.trim() || 'admin',
        admin_password: document.getElementById('nut_admin_password').value.trim() || 'adminpass',
        upsc_command: 'upsc',
        upscmd_command: 'upscmd',
        upscmd_user: document.getElementById('nut_admin_user').value.trim() || 'admin',
        upscmd_password: document.getElementById('nut_admin_password').value.trim() || 'adminpass',
      }
    } else if (state.selectedMode === 'netclient') {
      if (state.selectedProfile === 'multi') {
        const applied = ctx.actions.applyFleetPrimaryToNetclientData(configurationData)
        if (!applied) {
          elements.saveBtn.disabled = false
          elements.saveBtn.innerHTML = '<i class="fas fa-save"></i> Save Configuration'
          ctx.actions.showAlert('Unable to derive primary remote UPS from fleet targets. Add at least one valid remote target.', 'error')
          return
        }
        configurationData = {
          ...configurationData,
          upsc_command: 'upsc',
          upscmd_command: 'upscmd',
          upscmd_user: configurationData.remote_user,
          upscmd_password: configurationData.remote_password,
        }
      } else {
        configurationData = {
          ...configurationData,
          target_display_name: ctx.actions.getSingleTargetDisplayName('netclient'),
          name: ctx.actions.getSingleTargetDisplayName('netclient'),
          remote_ups_name: document.getElementById('remote_ups_name').value.trim(),
          remote_host: document.getElementById('remote_host').value.trim(),
          ups_name: document.getElementById('remote_ups_name').value.trim(),
          ups_host: document.getElementById('remote_host').value.trim(),
          remote_port: document.getElementById('remote_port').value.trim() || '3493',
          remote_user: document.getElementById('remote_user').value.trim(),
          remote_password: document.getElementById('remote_password').value.trim(),
          timezone: ctx.actions.normalizeSetupTimezone(elements.netclientTimezone?.value, 'UTC'),
          currency: ctx.actions.normalizeSetupCurrency(elements.netclientCurrency?.value, 'EUR'),
          polling_interval: ctx.actions.parseIntClamped(elements.netclientPollingInterval?.value, 1, 1, 60),
          location_enabled: !!elements.netclientLocationEnabled?.checked,
          location: String(elements.netclientLocation?.value || '').trim(),
          location_country: String(elements.netclientLocationCountry?.value || '').trim(),
          location_region: String(elements.netclientLocationRegion?.value || '').trim(),
          location_city: String(elements.netclientLocationCity?.value || '').trim(),
          location_postal_code: String(elements.netclientLocationPostalCode?.value || '').trim(),
          location_address: String(elements.netclientLocationAddress?.value || '').trim(),
          ups_realpower_nominal: ctx.actions.coerceOptionalPositiveInt(state.upsRealpowerNominal),
          upsc_command: 'upsc',
          upscmd_command: 'upscmd',
          upscmd_user: document.getElementById('remote_user').value.trim(),
          upscmd_password: document.getElementById('remote_password').value.trim(),
        }
      }
    }

    if (configurationData.timezone) configurationData.timezone_explicit = true
    if (configurationData.currency) configurationData.currency_explicit = true

    fetch('/nut_config/api/setup/save-config', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(configurationData),
    })
      .then((response) => response.json())
      .then((data) => {
        elements.saveBtn.disabled = false
        elements.saveBtn.innerHTML = '<i class="fas fa-save"></i> Save Configuration'
        if (data.status === 'success') {
          ctx.actions.showAlert('Configuration saved successfully!', 'success')
          ctx.actions.goToStep(6)
          document.getElementById('complete-success').classList.remove('hidden')
          document.getElementById('complete-error').classList.add('hidden')
          if (data.redirect) {
            window.location.href = data.redirect
          }
          return
        }
        ctx.actions.showAlert('Error saving configuration: ' + data.message, 'error')
        ctx.actions.goToStep(6)
        document.getElementById('complete-error').classList.remove('hidden')
        document.getElementById('complete-success').classList.add('hidden')
        document.getElementById('error-message').textContent = data.message
      })
      .catch((error) => {
        console.error('Error:', error)
        elements.saveBtn.disabled = false
        elements.saveBtn.innerHTML = '<i class="fas fa-save"></i> Save Configuration'
        ctx.actions.showAlert('Network error while saving configuration.', 'error')
      })
  }

  ctx.actions.bindExecutionHandlers = function bindExecutionHandlers() {
    elements.testConfigBtn.addEventListener('click', ctx.actions.testConfiguration)
    elements.saveBtn.addEventListener('click', ctx.actions.saveConfiguration)
    elements.restartBtn.addEventListener('click', ctx.actions.resetWizard)
    elements.restartServerBtn?.addEventListener('click', ctx.actions.restartServer)
  }
}
