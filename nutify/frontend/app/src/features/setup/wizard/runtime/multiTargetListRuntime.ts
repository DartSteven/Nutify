// @ts-nocheck

export function registerMultiTargetListRuntime(ctx) {
  const { elements, state } = ctx

  ctx.actions.renderMultiTargets = function renderMultiTargets() {
    if (!elements.multiTargetsList || !elements.multiTargetsEmpty) {
      return
    }

    const listSection = elements.multiTargetsList.closest('.multi-targets-list')
    const additionalTargetsCount = ctx.actions.getAdditionalTargets().length
    const hasPrimarySeed = (Array.isArray(state.multiTargets) ? state.multiTargets : []).some((target) => !!target?._is_primary_seed)
    if (additionalTargetsCount === 0 && !hasPrimarySeed) {
      if (listSection) {
        listSection.classList.add('hidden')
      }
      elements.multiTargetsList.innerHTML = ''
      elements.multiTargetsEmpty.classList.add('hidden')
      ctx.actions.updateMultiTargetProgress()
      return
    }
    if (listSection) {
      listSection.classList.remove('hidden')
    }

    const visibleTargets = (Array.isArray(state.multiTargets) ? state.multiTargets : []).map((target, index) => ({ target, index }))
    elements.multiTargetsList.innerHTML = ''
    if (!visibleTargets.length) {
      elements.multiTargetsEmpty.classList.remove('hidden')
      ctx.actions.updateMultiTargetProgress()
      return
    }

    elements.multiTargetsEmpty.classList.add('hidden')
    ctx.actions.updateMultiTargetProgress()

    visibleTargets.forEach(({ target, index }) => {
      const isPrimarySeed = !!target?._is_primary_seed
      const title = isPrimarySeed ? `${target.name} (Primary)` : target.name
      const controlsHtml = isPrimarySeed
        ? ''
        : `<div class="multi-target-item-controls"><button type="button" class="nav-btn back-btn multi-target-edit-btn" data-index="${index}"><i class="fas fa-pen"></i> Edit</button><button type="button" class="nav-btn cancel-btn multi-target-remove-btn" data-index="${index}"><i class="fas fa-trash"></i> Remove</button></div>`
      const wrapper = document.createElement('div')
      wrapper.className = 'multi-target-item'
      let usbIdentityMeta = ''
      if (target.connection_type === 'local_usb_serial' && (target.usb_serial || target.usb_vendorid || target.usb_productid || target.usb_busport || target.usb_bus || target.usb_device)) {
        if (target.usb_serial) {
          usbIdentityMeta = ` | usb: S/N ${target.usb_serial}`
        } else if (target.usb_busport) {
          usbIdentityMeta = ` | usb: busport ${target.usb_busport}`
        } else if (target.usb_bus || target.usb_device) {
          usbIdentityMeta = ` | usb: bus:device ${target.usb_bus || '?'}:${target.usb_device || '?'}`
        } else {
          usbIdentityMeta = ` | usb: ${target.usb_vendorid || '?'}:${target.usb_productid || '?'}`
        }
      }
      wrapper.innerHTML = `
        <div>
          <strong>${title}</strong>
          <div class="multi-target-item-meta">${target.ups_name}@${target.host}:${target.port} | connection: ${ctx.actions.getConnectionTypeLabel(target.connection_type)} | polling: ${target.polling_interval}s</div>
          <div class="multi-target-item-meta">enabled: ${target.enabled ? 'yes' : 'no'} | primary: ${target.is_primary ? 'yes' : 'no'} | timezone: ${target.timezone || 'UTC'} | currency: ${target.currency || 'EUR'}${target.ups_realpower_nominal ? ` | nominal: ${target.ups_realpower_nominal}W` : ''}${usbIdentityMeta}${target.location_enabled && target.location ? ` | location: ${target.location}` : ''}</div>
        </div>
        ${controlsHtml}
      `
      elements.multiTargetsList.appendChild(wrapper)
    })

    elements.multiTargetsList.querySelectorAll('.multi-target-edit-btn').forEach((button) => {
      button.addEventListener('click', function onEditTarget() {
        const index = parseInt(this.dataset.index, 10)
        const target = state.multiTargets[index]
        if (!target) {
          return
        }
        state.editingMultiTargetIndex = index
        if (elements.multiTargetName) elements.multiTargetName.value = target.name
        if (elements.multiTargetUpsName) elements.multiTargetUpsName.value = target.ups_name
        if (elements.multiTargetConnectionType) elements.multiTargetConnectionType.value = target.connection_type || 'remote_nut'
        if (elements.multiTargetHost) elements.multiTargetHost.value = target.host
        if (elements.multiTargetPort) elements.multiTargetPort.value = String(target.port)
        if (elements.multiTargetMonitorUsername) elements.multiTargetMonitorUsername.value = target.monitor_username || 'monuser'
        if (elements.multiTargetMonitorPassword) elements.multiTargetMonitorPassword.value = target.monitor_password || ''
        if (elements.multiTargetLocalDriver) elements.multiTargetLocalDriver.value = target.local_driver || 'usbhid-ups'
        if (elements.multiTargetLocalPort) elements.multiTargetLocalPort.value = target.local_port || 'auto'
        state.multiTargetSelectedUsbDevice = (target.usb_serial || target.usb_vendorid || target.usb_productid)
          ? {
            _usbKey: `saved|${target.usb_serial || ''}|${target.usb_vendorid || ''}|${target.usb_productid || ''}`,
            _usbPort: target.local_port || 'auto',
            serial: target.usb_serial || '',
            vendorid: target.usb_vendorid || '',
            productid: target.usb_productid || '',
            vendor: target.usb_vendor || '',
            model: target.usb_product || '',
            bus: target.usb_bus || '',
            device: target.usb_device || '',
            busport: target.usb_busport || '',
            port: target.local_port || 'auto',
            name: target.ups_name || 'device',
          }
          : null
        if (elements.multiTargetLocalDesc) elements.multiTargetLocalDesc.value = target.local_description || ''
        if (elements.multiTargetTimezone) elements.multiTargetTimezone.value = ctx.actions.normalizeSetupTimezone(target.timezone, 'UTC')
        if (elements.multiTargetCurrency) elements.multiTargetCurrency.value = ctx.actions.normalizeSetupCurrency(target.currency, 'EUR')
        ctx.actions.writeSnmpSettings('multi_target_', target)
        if (elements.multiTargetPolling) elements.multiTargetPolling.value = String(target.polling_interval)
        if (elements.multiTargetDbStrategy) elements.multiTargetDbStrategy.value = 'shared'
        if (elements.multiTargetShard) elements.multiTargetShard.value = 'month'
        if (elements.multiTargetNotifyScope) elements.multiTargetNotifyScope.value = target.notify_scope
        if (elements.multiTargetSeparateDbPath) elements.multiTargetSeparateDbPath.value = ''
        if (elements.multiTargetEnabled) elements.multiTargetEnabled.checked = !!target.enabled
        if (elements.multiTargetPrimary) elements.multiTargetPrimary.checked = !!target.is_primary
        if (elements.multiTargetLocationEnabled) elements.multiTargetLocationEnabled.checked = !!target.location_enabled
        if (elements.multiTargetLocationCountry) elements.multiTargetLocationCountry.value = target.location_country || ''
        if (elements.multiTargetLocationRegion) elements.multiTargetLocationRegion.value = target.location_region || ''
        if (elements.multiTargetLocationCity) elements.multiTargetLocationCity.value = target.location_city || ''
        if (elements.multiTargetLocationPostalCode) elements.multiTargetLocationPostalCode.value = target.location_postal_code || ''
        if (elements.multiTargetLocationAddress) elements.multiTargetLocationAddress.value = target.location_address || target.location || ''
        if (elements.multiTargetLocation) elements.multiTargetLocation.value = target.location || ''
        state.multiTargetDraftLocationLatitude = ctx.actions.coerceOptionalCoordinate(target.location_latitude, -90, 90)
        state.multiTargetDraftLocationLongitude = ctx.actions.coerceOptionalCoordinate(target.location_longitude, -180, 180)
        ctx.actions.hideLocationSuggestions()
        state.multiTargetDraftNominalPower = ctx.actions.coerceOptionalPositiveInt(target.ups_realpower_nominal)
        ctx.actions.updateMultiTargetConnectionUi()
        ctx.actions.syncMultiTargetUsbPickerWithPortInput?.()
        ctx.actions.updateMultiTargetStorageStrategyUi()
        ctx.actions.updateMultiTargetLocationUi()
        ctx.actions.invalidateMultiTargetTestState(true)
        ctx.actions.updateMultiTargetFlowHint('Editing target. Re-test, then update.')
        ctx.actions.updateMultiTargetProgress('Editing target draft')
        if (elements.multiTargetAddBtn) {
          elements.multiTargetAddBtn.innerHTML = '<i class="fas fa-save"></i> Update Target'
        }
      })
    })

    elements.multiTargetsList.querySelectorAll('.multi-target-remove-btn').forEach((button) => {
      button.addEventListener('click', function onRemoveTarget() {
        const index = parseInt(this.dataset.index, 10)
        if (Number.isNaN(index)) {
          return
        }
        state.multiTargets.splice(index, 1)
        if (state.multiTargets.length > 0 && !state.multiTargets.some((item) => item.is_primary)) {
          state.multiTargets[0].is_primary = true
        }
        if (state.editingMultiTargetIndex === index) {
          ctx.actions.resetMultiTargetForm()
        }
        ctx.actions.renderMultiTargets()
        ctx.actions.updateMultiTargetProgress()
      })
    })
  }
}
