// @ts-nocheck

export function registerPreviewEditorRuntime(ctx) {
  const { elements, state } = ctx

  ctx.actions.initializeEditor = function initializeEditor() {
    if (!state.editor) {
      const editorTextarea = document.getElementById('config-editor')
      if (editorTextarea) {
        state.editor = CodeMirror.fromTextArea(editorTextarea, {
          lineNumbers: true,
          mode: 'shell',
          theme: 'monokai',
          lineWrapping: true,
          indentUnit: 4,
          smartIndent: true,
          tabSize: 4,
        })
        state.editor.setSize('100%', '400px')
        state.editor.isActive = false
        state.editor.on('change', function onEditorChange() {
          const activeTab = document.querySelector('.config-tab.active')
          if (activeTab && !activeTab.classList.contains('modified-tab')) {
            activeTab.classList.add('modified-tab')
          }
        })
      }
    }
  }

  ctx.actions.hasEditorChanges = function hasEditorChanges() {
    if (!state.editor || !state.currentFile) return false
    const currentContent = state.editor.getValue()
    const originalContent = state.editedFiles[state.currentFile] || state.configFiles[state.currentFile] || ''
    return currentContent !== originalContent
  }

  ctx.actions.toggleEditor = function toggleEditor() {
    ctx.actions.initializeEditor()
    if (state.editor.isActive) {
      if (ctx.actions.hasEditorChanges() && !window.confirm('You have unsaved changes. Are you sure you want to close the editor without saving?')) {
        return
      }
      elements.configEditorContainer.classList.add('hidden')
      elements.configPreviewElement.classList.remove('hidden')
      elements.editorActions.classList.add('hidden')
      elements.editConfigBtn.innerHTML = '<i class="fas fa-edit"></i> Edit'
      state.editor.isActive = false
      elements.testConfigBtn?.classList.remove('hidden')
      return
    }

    elements.configPreviewElement.classList.add('hidden')
    elements.configEditorContainer.classList.remove('hidden')
    elements.editorActions.classList.remove('hidden')
    elements.editConfigBtn.innerHTML = '<i class="fas fa-eye"></i> Preview'
    state.editor.isActive = true
    elements.testConfigBtn?.classList.add('hidden')
    if (state.currentFile && state.configFiles[state.currentFile]) {
      state.editor.setValue(state.editedFiles[state.currentFile] || state.configFiles[state.currentFile])
      state.editor.refresh()
    }
  }

  ctx.actions.saveEditorChanges = function saveEditorChanges() {
    if (!state.editor || !state.currentFile) return
    const content = state.editor.getValue()
    if (content === state.configFiles[state.currentFile]) {
      if (state.editedFiles[state.currentFile]) {
        delete state.editedFiles[state.currentFile]
        const tab = document.querySelector(`.config-tab[data-file="${state.currentFile}"]`)
        if (tab) tab.classList.remove('modified-tab')
      }
    } else {
      state.editedFiles[state.currentFile] = content
    }

    elements.configEditorContainer.classList.add('hidden')
    elements.configPreviewElement.classList.remove('hidden')
    elements.editorActions.classList.add('hidden')
    elements.editConfigBtn.innerHTML = '<i class="fas fa-edit"></i> Edit'
    state.editor.isActive = false
    elements.testConfigBtn?.classList.remove('hidden')
    elements.configPreview.textContent = state.editedFiles[state.currentFile] || state.configFiles[state.currentFile]
    ctx.actions.showAlert(`Changes to ${state.currentFile} saved`, 'success')
  }

  ctx.actions.cancelEditorChanges = function cancelEditorChanges() {
    if (!state.editor || !state.currentFile) return
    state.editor.setValue(state.editedFiles[state.currentFile] || state.configFiles[state.currentFile])
    elements.configEditorContainer.classList.add('hidden')
    elements.configPreviewElement.classList.remove('hidden')
    elements.editorActions.classList.add('hidden')
    elements.editConfigBtn.innerHTML = '<i class="fas fa-edit"></i> Edit'
    state.editor.isActive = false
    elements.testConfigBtn?.classList.remove('hidden')
    ctx.actions.showAlert('Edit cancelled', 'info')
  }

  ctx.actions.createSummaryItem = function createSummaryItem(label, value) {
    const item = document.createElement('div')
    item.className = 'summary-item'
    item.innerHTML = `<div class="summary-label">${label}</div><div class="summary-value">${value || 'N/A'}</div>`
    return item
  }

  ctx.actions.generateConfigPreview = function generateConfigPreview() {
    state.configData = {
      server_name: String(document.getElementById('server_name')?.value || '').trim() || 'Nutify',
      mode: state.selectedMode,
      monitoring_profile: state.selectedProfile,
      multi_topology: state.selectedProfile === 'multi' ? state.selectedTopology : null,
      host_service_mode: state.selectedProfile === 'multi' ? state.selectedHostServiceMode : null,
      multi_targets: state.selectedProfile === 'multi' ? ctx.actions.buildMultiTargetsPayload() : [],
    }

    if (state.selectedMode === 'standalone') {
      const autoRadio = document.getElementById('auto-standalone')
      const isAutoMode = autoRadio && autoRadio.checked
      const selectedManualUsb = ctx.actions.getSelectedManualUsbDevice?.('standalone') || null
      const selectedAutoUsb = ctx.actions.getSelectedAutoDetectedDevice?.('standalone') || null
      const selectedPrimaryUsb = selectedManualUsb || selectedAutoUsb
      Object.assign(state.configData, {
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
        monitor_username: 'monuser',
        monitor_password: 'monpass',
        admin_user: 'admin',
        admin_password: 'adminpass',
      })
      if (isAutoMode) {
        const scanResults = document.getElementById('scan-results-standalone')
        const selectedDevice = scanResults?.querySelector('.scan-device.selected')
        if (selectedDevice) {
          const index = Array.from(scanResults.querySelectorAll('.scan-device')).indexOf(selectedDevice)
          const deviceElements = scanResults.querySelectorAll('.scan-device')
          if (index >= 0 && deviceElements[index].__device?.raw_config) {
            state.configData.raw_ups_config = deviceElements[index].__device.raw_config
          }
        }
      }
    } else if (state.selectedMode === 'netserver') {
      const autoRadio = document.getElementById('auto-netserver')
      const isAutoMode = autoRadio && autoRadio.checked
      const selectedManualUsb = ctx.actions.getSelectedManualUsbDevice?.('netserver') || null
      const selectedAutoUsb = ctx.actions.getSelectedAutoDetectedDevice?.('netserver') || null
      const selectedPrimaryUsb = selectedManualUsb || selectedAutoUsb
      Object.assign(state.configData, {
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
        monitor_username: 'monuser',
        monitor_password: 'monpass',
      })
      if (isAutoMode) {
        const scanResults = document.getElementById('scan-results-netserver')
        const selectedDevice = scanResults?.querySelector('.scan-device.selected')
        if (selectedDevice) {
          const index = Array.from(scanResults.querySelectorAll('.scan-device')).indexOf(selectedDevice)
          const deviceElements = scanResults.querySelectorAll('.scan-device')
          if (index >= 0 && deviceElements[index].__device?.raw_config) {
            state.configData.raw_ups_config = deviceElements[index].__device.raw_config
          }
        }
      }
    } else if (state.selectedMode === 'netclient') {
      if (state.selectedProfile === 'multi') {
        const applied = ctx.actions.applyFleetPrimaryToNetclientData(state.configData)
        if (!applied) {
          ctx.actions.showAlert('Unable to derive primary remote UPS from fleet targets. Add at least one valid remote target.', 'error')
          return
        }
      } else {
        Object.assign(state.configData, {
          target_display_name: ctx.actions.getSingleTargetDisplayName('netclient'),
          name: ctx.actions.getSingleTargetDisplayName('netclient'),
          remote_ups_name: document.getElementById('remote_ups_name').value.trim(),
          remote_host: document.getElementById('remote_host').value.trim(),
          remote_port: document.getElementById('remote_port').value.trim(),
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
        })
      }
    }

    fetch('/nut_config/api/setup/generate-preview', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(state.configData),
    })
      .then((response) => response.json())
      .then((data) => {
        if (data.status !== 'success') {
          ctx.actions.showAlert('Failed to generate configuration: ' + data.message, 'error')
          return
        }

        const upsmonEdits = state.editedFiles['upsmon.conf']
        state.configFiles = data.config_files
        state.editedFiles = {}
        if (upsmonEdits) {
          state.editedFiles['upsmon.conf'] = upsmonEdits
          const upsmonTab = document.querySelector('.config-tab[data-file="upsmon.conf"]')
          if (upsmonTab) upsmonTab.classList.add('modified-tab')
          ctx.actions.showAlert('Your edits to upsmon.conf have been preserved.', 'info')
        }

        const summary = document.querySelector('.config-summary')
        summary.innerHTML = ''
        summary.appendChild(ctx.actions.createSummaryItem('Server Name:', state.configData.server_name))
        summary.appendChild(ctx.actions.createSummaryItem('Mode:', ctx.actions.getModeLabel(state.selectedMode)))
        summary.appendChild(ctx.actions.createSummaryItem('Monitoring Profile:', state.selectedProfile === 'multi' ? 'Multi Monitor' : 'Single Monitor'))
        if (state.selectedProfile === 'multi') {
          summary.appendChild(ctx.actions.createSummaryItem('Fleet Topology:', ctx.actions.getTopologyLabel(state.selectedTopology)))
          summary.appendChild(ctx.actions.createSummaryItem('Derived Host Mode:', state.selectedMode || 'N/A'))
          summary.appendChild(ctx.actions.createSummaryItem('UPS Targets:', `${state.multiTargets.length}`))
        }

        if (state.selectedProfile !== 'multi' && (state.selectedMode === 'standalone' || state.selectedMode === 'netserver')) {
          const isNetServer = state.selectedMode === 'netserver'
          summary.appendChild(ctx.actions.createSummaryItem('Target Display Name:', state.configData.target_display_name))
          summary.appendChild(ctx.actions.createSummaryItem('UPS Identifier:', state.configData.ups_name))
          summary.appendChild(ctx.actions.createSummaryItem('UPS Driver:', ctx.actions.getDriverLabel(state.configData.ups_driver)))
          summary.appendChild(ctx.actions.createSummaryItem('Port/Device:', state.configData.ups_port))
          summary.appendChild(ctx.actions.createSummaryItem('Server Address:', state.configData.server_address))
          if (isNetServer) {
            summary.appendChild(ctx.actions.createSummaryItem('Listen Address:', state.configData.listen_address))
            summary.appendChild(ctx.actions.createSummaryItem('Listen Port:', state.configData.listen_port))
            summary.appendChild(ctx.actions.createSummaryItem('NUT Admin User:', state.configData.admin_user))
            summary.appendChild(ctx.actions.createSummaryItem('NUT Admin Password:', '********'))
          }
        } else if (state.selectedMode === 'netclient' && state.selectedProfile !== 'multi') {
          summary.appendChild(ctx.actions.createSummaryItem('Target Display Name:', state.configData.target_display_name))
          summary.appendChild(ctx.actions.createSummaryItem('UPS Identifier:', state.configData.remote_ups_name))
          summary.appendChild(ctx.actions.createSummaryItem('Remote Server:', state.configData.remote_host))
          summary.appendChild(ctx.actions.createSummaryItem('Remote Port:', state.configData.remote_port))
          summary.appendChild(ctx.actions.createSummaryItem('Remote User:', state.configData.remote_user))
          summary.appendChild(ctx.actions.createSummaryItem('Polling Interval:', `${state.configData.polling_interval || 1}s`))
          if (state.configData.location_enabled && state.configData.location) {
            summary.appendChild(ctx.actions.createSummaryItem('Location:', state.configData.location))
          }
          if (state.configData.remote_password) {
            summary.appendChild(ctx.actions.createSummaryItem('Remote Password:', '********'))
          }
        }

        elements.configTabs[0]?.click()
        elements.configTabs.forEach((tab) => tab.classList.remove('modified-tab'))
      })
      .catch((error) => {
        console.error('Error:', error)
        ctx.actions.showAlert('An error occurred while generating configuration preview.', 'error')
      })
  }

  ctx.actions.bindPreviewEditorHandlers = function bindPreviewEditorHandlers() {
    elements.configTabs.forEach((tab) => {
      tab.addEventListener('click', function onTabClick() {
        elements.configTabs.forEach((node) => node.classList.remove('active'))
        this.classList.add('active')
        const filename = this.dataset.file
        state.currentFile = filename
        if (state.configFiles[filename]) {
          if (state.editor && state.editor.isActive) {
            state.editor.setValue(state.editedFiles[filename] || state.configFiles[filename])
          } else {
            elements.configPreview.textContent = state.editedFiles[filename] || state.configFiles[filename]
          }
        }
      })
    })

    elements.editConfigBtn?.addEventListener('click', ctx.actions.toggleEditor)
    elements.saveEditBtn?.addEventListener('click', ctx.actions.saveEditorChanges)
    elements.cancelEditBtn?.addEventListener('click', ctx.actions.cancelEditorChanges)
  }
}
