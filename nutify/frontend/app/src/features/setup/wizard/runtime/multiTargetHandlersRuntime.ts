// @ts-nocheck

import { bindWizardEventOnce } from './domBindings'

export function registerMultiTargetHandlersRuntime(ctx) {
  const { elements, state } = ctx

  ctx.actions.setupMultiTargetHandlers = function setupMultiTargetHandlers() {
    if (!elements.multiTargetAddBtn || !elements.multiTargetResetBtn || !elements.multiTargetTestBtn) {
      return
    }

    const invalidateOnChangeInputs = [
      elements.multiTargetName,
      elements.multiTargetUpsName,
      elements.multiTargetConnectionType,
      elements.multiTargetHost,
      elements.multiTargetPort,
      elements.multiTargetMonitorUsername,
      elements.multiTargetMonitorPassword,
      elements.multiTargetLocalDriver,
      elements.multiTargetLocalPort,
      elements.multiTargetDetectedUsbPortSelect,
      elements.multiTargetLocalDesc,
      elements.multiTargetTimezone,
      elements.multiTargetCurrency,
      elements.multiTargetSnmpCommunity,
      elements.multiTargetSnmpVersion,
      elements.multiTargetPolling,
      elements.multiTargetDbStrategy,
      elements.multiTargetShard,
      elements.multiTargetNotifyScope,
      elements.multiTargetSeparateDbPath,
      elements.multiTargetEnabled,
      elements.multiTargetPrimary,
      elements.multiTargetLocationEnabled,
      elements.multiTargetLocation,
      elements.multiTargetLocationCountry,
      elements.multiTargetLocationRegion,
      elements.multiTargetLocationCity,
      elements.multiTargetLocationPostalCode,
      elements.multiTargetLocationAddress,
    ]

    invalidateOnChangeInputs.forEach((element) => {
      if (!element) {
        return
      }
      const eventName = element.tagName === 'SELECT' || element.type === 'checkbox' ? 'change' : 'input'
      const bindingId = `${element.id || element.name || element.type || 'field'}-invalidate-${eventName}`
      bindWizardEventOnce(element, bindingId, eventName, () => ctx.actions.invalidateMultiTargetTestState(true))
    })

    if (elements.multiTargetConnectionType) {
      bindWizardEventOnce(
        elements.multiTargetConnectionType,
        'multi-target-connection-type-change',
        'change',
        ctx.actions.updateMultiTargetConnectionUi,
      )
    }
    if (elements.multiTargetDbStrategy) {
      bindWizardEventOnce(elements.multiTargetDbStrategy, 'multi-target-db-strategy-change', 'change', function onDbStrategyChange() {
        ctx.actions.updateMultiTargetStorageStrategyUi()
        ctx.actions.invalidateMultiTargetTestState(true)
      })
    }
    if (elements.multiTargetLocationEnabled) {
      bindWizardEventOnce(elements.multiTargetLocationEnabled, 'multi-target-location-toggle', 'change', function onLocationToggle() {
        ctx.actions.updateMultiTargetLocationUi()
        ctx.actions.invalidateMultiTargetTestState(true)
      })
    }

    ;[
      elements.multiTargetLocationCountry,
      elements.multiTargetLocationRegion,
      elements.multiTargetLocationCity,
      elements.multiTargetLocationPostalCode,
      elements.multiTargetLocationAddress,
    ].filter(Boolean).forEach((input) => {
      bindWizardEventOnce(input, `${input.id}-location-input`, 'input', function onLocationInput() {
        ctx.actions.updateLocationComputedField()
        ctx.actions.queueLocationSuggestions()
      })
      bindWizardEventOnce(input, `${input.id}-location-focus`, 'focus', function onLocationFocus() {
        ctx.actions.queueLocationSuggestions()
      })
    })

    bindWizardEventOnce(elements.multiTargetTestBtn, 'multi-target-test-button', 'click', async function onTestTarget() {
      ctx.actions.clearAlerts()
      let target = ctx.actions.collectMultiTargetFromForm()
      if (!target) {
        return
      }

      const preValidation = await ctx.actions.validateMultiTargetLocation(target, { promptOnFailure: false })
      target = preValidation.target
      state.multiTargetDraftLocationLatitude = ctx.actions.coerceOptionalCoordinate(target.location_latitude, -90, 90)
      state.multiTargetDraftLocationLongitude = ctx.actions.coerceOptionalCoordinate(target.location_longitude, -180, 180)

      const payload = {
        ...target,
        host_mode: state.selectedMode,
        monitoring_profile: state.selectedProfile,
        topology: state.selectedTopology,
      }

      elements.multiTargetTestBtn.disabled = true
      elements.multiTargetTestBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Testing...'
      ctx.actions.updateMultiTargetTestStatus('Testing target connection...', false)

      fetch('/nut_config/api/setup/test-target', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })
        .then((response) => response.json().then((data) => ({ status: response.status, data })))
        .then(async ({ status, data }) => {
          const success = status >= 200 && status < 300 && !!data.success
          if (success) {
            let draftNominalPower = ctx.actions.coerceOptionalPositiveInt(data?.nominal_power?.value)
              || ctx.actions.coerceOptionalPositiveInt(target.ups_realpower_nominal)
              || ctx.actions.coerceOptionalPositiveInt(state.multiTargetDraftNominalPower)
            const needsNominalInput = ctx.actions.shouldRequestNominalPowerInput(data, draftNominalPower)
            if (needsNominalInput && !draftNominalPower) {
              const manualNominalPower = await ctx.actions.requestNominalPowerFromUser(target.name || target.ups_name, state.multiTargetDraftNominalPower)
              if (!manualNominalPower) {
                state.lastTargetTestSuccess = false
                state.lastTargetTestSignature = null
                state.lastTargetTestConnectionSignature = null
                ctx.actions.updateMultiTargetTestStatus('Target requires UPS nominal power before saving.', false)
                ctx.actions.updateMultiTargetFlowHint('Insert nominal power, then test again.')
                ctx.actions.showAlert('Target test passed, but UPS nominal power is required to continue.', 'error')
                return
              }
              draftNominalPower = manualNominalPower
            }

            state.multiTargetDraftNominalPower = draftNominalPower
            target.ups_realpower_nominal = draftNominalPower
            const signature = ctx.actions.getMultiTargetSignature(target)
            const connectionSignature = ctx.actions.getMultiTargetConnectionSignature(target)
            state.lastTargetTestSuccess = true
            state.lastTargetTestSignature = signature
            state.lastTargetTestConnectionSignature = connectionSignature
            ctx.actions.updateMultiTargetTestStatus('Target test passed. You can now save this target.', true)
            const saveActionLabel = state.editingMultiTargetIndex >= 0 ? 'Update Target' : 'Save Target'
            ctx.actions.updateMultiTargetFlowHint(`Target tested. Click ${saveActionLabel}.`)
            if (target.location_enabled && !preValidation.found) {
              ctx.actions.showAlert('Target test passed, but location was not fully validated. You can still save and confirm manually.', 'warning')
            } else {
              ctx.actions.showAlert(data.message || 'Target test passed.', 'success')
            }
            return
          }

          state.lastTargetTestSuccess = false
          state.lastTargetTestSignature = null
          state.lastTargetTestConnectionSignature = null
          state.multiTargetDraftNominalPower = null
          ctx.actions.updateMultiTargetTestStatus('Target test failed. Fix fields and test again.', false)
          ctx.actions.updateMultiTargetFlowHint('Target test failed. Fix fields and retry.')
          ctx.actions.showAlert(data.message || data.error || 'Target test failed.', 'error')
        })
        .catch((error) => {
          state.lastTargetTestSuccess = false
          state.lastTargetTestSignature = null
          state.lastTargetTestConnectionSignature = null
          state.multiTargetDraftNominalPower = null
          ctx.actions.updateMultiTargetTestStatus('Target test failed due to network error.', false)
          ctx.actions.updateMultiTargetFlowHint('Network error. Verify fields and retry.')
          ctx.actions.showAlert(`Target test error: ${error.message}`, 'error')
        })
        .finally(() => {
          elements.multiTargetTestBtn.disabled = false
          elements.multiTargetTestBtn.innerHTML = '<i class="fas fa-network-wired"></i> Test Target'
        })
    })

    bindWizardEventOnce(elements.multiTargetAddBtn, 'multi-target-save-button', 'click', async function onSaveTarget() {
      ctx.actions.clearAlerts()
      const target = ctx.actions.collectMultiTargetFromForm()
      if (!target) {
        return
      }

      const signature = ctx.actions.getMultiTargetSignature(target)
      const connectionSignature = ctx.actions.getMultiTargetConnectionSignature(target)
      if (!state.lastTargetTestSuccess) {
        ctx.actions.showAlert('Run Test Target and get a successful result before saving this target.', 'error')
        ctx.actions.updateMultiTargetTestStatus('Target test required before saving.', false)
        ctx.actions.updateMultiTargetFlowHint('Run Test Target, then save this target.')
        return
      }

      if (state.lastTargetTestConnectionSignature !== connectionSignature) {
        ctx.actions.showAlert('Connection settings changed after the last successful test. Run Test Target again before saving.', 'error')
        ctx.actions.updateMultiTargetTestStatus('Target test required before saving.', false)
        ctx.actions.updateMultiTargetFlowHint('Connection changed. Re-test target before saving.')
        return
      }

      if (state.lastTargetTestSignature !== signature) {
        state.lastTargetTestSignature = signature
      }

      const locationValidation = await ctx.actions.validateMultiTargetLocation(target)
      if (!locationValidation.confirmed) {
        ctx.actions.updateMultiTargetFlowHint('Location confirmation canceled.')
        ctx.actions.updateMultiTargetProgress('Target not saved')
        ctx.actions.showAlert('Target was not saved because location validation was canceled.', 'error')
        return
      }

      const validatedTarget = locationValidation.target
      validatedTarget.db_strategy = 'shared'
      validatedTarget.shard_granularity = 'month'
      validatedTarget.separate_db_path = ''

      if (validatedTarget.is_primary) {
        state.multiTargets = state.multiTargets.map((item) => ({ ...item, is_primary: false }))
      }

      if (state.editingMultiTargetIndex >= 0 && state.editingMultiTargetIndex < state.multiTargets.length) {
        validatedTarget._tested = true
        validatedTarget._test_signature = signature
        state.multiTargets[state.editingMultiTargetIndex] = validatedTarget
      } else {
        if (!validatedTarget.is_primary && state.multiTargets.length === 0) {
          validatedTarget.is_primary = true
        }
        validatedTarget._tested = true
        validatedTarget._test_signature = signature
        state.multiTargets.push(validatedTarget)
      }

      if (state.multiTargets.length > 0 && !state.multiTargets.some((item) => item.is_primary)) {
        state.multiTargets[0].is_primary = true
      }

      ctx.actions.resetMultiTargetForm(false)
      ctx.actions.updateMultiTargetTestStatus('', null)
      ctx.actions.renderMultiTargets()
      ctx.actions.updateMultiTargetFlowHint('Target saved. Configure the next target or click Next to continue.')
      ctx.actions.updateMultiTargetProgress()
    })

    bindWizardEventOnce(elements.multiTargetResetBtn, 'multi-target-reset-button', 'click', function onResetTargetForm() {
      ctx.actions.resetMultiTargetForm()
    })

    ctx.actions.updateMultiTargetStorageStrategyUi()
    ctx.actions.updateMultiTargetProgress()
  }
}
