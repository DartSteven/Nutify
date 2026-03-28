// @ts-nocheck

export function registerNavigationRuntime(ctx) {
  const { elements, state } = ctx

  function moveMultiTargetActionsToCurrentSlot() {
    const currentActions = document.querySelector('#multi-target-actions-anchor .multi-target-actions')
    const anchor = document.getElementById('multi-target-actions-anchor')
    const extraActions = elements.wizardExtraActions
    const parkedActions = extraActions?.querySelector('.multi-target-actions')
    const actions = currentActions || parkedActions
    if (!actions || !anchor || !extraActions) {
      return
    }

    const isMultiStep = state.currentStep === 4 && state.selectedProfile === 'multi'
    const multiTargetsVisible = !!elements.multiTargetsSection && !elements.multiTargetsSection.classList.contains('hidden')
    const waitingPrimaryTestAction = isMultiStep && !!ctx.actions.isWaitingPrimaryTestSaveAction?.()
    const waitingContinueAction = isMultiStep
      && state.selectedMode !== 'netclient'
      && state.primaryTargetPrepared
      && !state.primaryNextStepUnlocked
      && ctx.actions.getAdditionalTargets().length === 0
    const shouldUseWizardBar = isMultiStep && multiTargetsVisible && !waitingPrimaryTestAction && !waitingContinueAction

    if (elements.multiTargetTestStatus) {
      elements.multiTargetTestStatus.classList.toggle('hidden', !shouldUseWizardBar)
    }
    if (elements.multiTargetFlowHint && !shouldUseWizardBar) {
      elements.multiTargetFlowHint.classList.add('hidden')
    }

    if (shouldUseWizardBar) {
      extraActions.classList.remove('hidden')
      if (parkedActions && currentActions && parkedActions !== currentActions) {
        parkedActions.remove()
      }
      if (actions.parentElement !== extraActions) {
        extraActions.appendChild(actions)
      }
      return
    }

    extraActions.classList.add('hidden')
    if (parkedActions && currentActions && parkedActions !== currentActions) {
      parkedActions.remove()
    }
    if (actions.parentElement !== anchor) {
      anchor.appendChild(actions)
    }
  }

  ctx.actions.resetConfigMethodSelection = function resetConfigMethodSelection() {
    document.querySelectorAll('input[name^="config-method-"]').forEach((radio) => {
      radio.checked = false
    })
    document.querySelectorAll('.config-method-option').forEach((option) => {
      option.classList.remove('selected')
    })
    document.querySelectorAll('.config-method-section').forEach((section) => {
      section.classList.add('hidden')
    })
    document.querySelectorAll('[id^="scan-results-"]').forEach((result) => {
      result.classList.add('hidden')
      result.querySelectorAll('.scan-device.selected').forEach((node) => node.classList.remove('selected'))
      const selectedHint = result.querySelector('.scan-selected-hint')
      if (selectedHint) {
        selectedHint.remove()
      }
    })
    document.querySelectorAll('#config-standalone, #config-netserver').forEach((section) => {
      section.classList.add('awaiting-method-choice')
    })
    ctx.actions.restorePrimaryAutoDetectLayout?.('standalone')
    ctx.actions.restorePrimaryAutoDetectLayout?.('netserver')
    ctx.actions.setPrimaryConfigCollapsed(false)
    ctx.actions.updatePrimarySnmpFieldVisibility()
  }

  ctx.actions.resetWizard = function resetWizard() {
    ctx.actions.goToStep(state.firstStep)
    state.selectedMode = null
    elements.primaryModeOptions.forEach((option) => {
      option.classList.remove('selected')
      const radio = option.querySelector('input[type="radio"]')
      if (radio) radio.checked = false
    })
    state.selectedTopology = null
    elements.topologyOptions.forEach((option) => option.classList.remove('selected'))
    state.selectedHostServiceMode = 'standalone'
    elements.hostModeOptions.forEach((option) => {
      const isStandalone = option.dataset.hostMode === 'standalone'
      option.classList.toggle('selected', isStandalone)
    })

    document.querySelectorAll('input, select').forEach((input) => {
      if (input.type === 'radio' || input.type === 'checkbox') {
        input.checked = false
      } else if (input.tagName === 'SELECT') {
        input.selectedIndex = 0
      } else if (input.name === 'ups_name' || input.name === 'server_ups_name' || input.name === 'remote_ups_name') {
        input.value = 'ups'
      } else if (input.name === 'ups_port' || input.name === 'server_ups_port') {
        input.value = 'auto'
      } else if (input.name === 'listen_address') {
        input.value = '0.0.0.0'
      } else if (input.name === 'listen_port' || input.name === 'remote_port') {
        input.value = '3493'
      } else if (input.name === 'dashboard_admin_username' || input.name === 'nut_admin_user') {
        input.value = 'admin'
      } else if (input.name === 'server_name') {
        input.value = input.dataset.defaultValue || 'Nutify'
      } else if (input.name === 'ups_target_display_name' || input.name === 'server_target_display_name' || input.name === 'remote_target_display_name') {
        input.value = ''
      } else if (input.name === 'remote_user') {
        input.value = 'monuser'
      } else if (input.name === 'ups_desc') {
        input.value = 'Local UPS'
      } else if (input.name === 'server_ups_desc') {
        input.value = 'Network UPS'
      } else if (input.name === 'ups_polling_interval' || input.name === 'server_polling_interval' || input.name === 'remote_polling_interval') {
        input.value = '1'
      } else if (
        input.name === 'remote_location' ||
        input.name === 'remote_location_country' ||
        input.name === 'remote_location_region' ||
        input.name === 'remote_location_city' ||
        input.name === 'remote_location_postal_code' ||
        input.name === 'remote_location_address'
      ) {
        input.value = ''
      } else if (input.type === 'password') {
        input.value = ''
      }
    })

    state.selectedProfile = 'single'
    elements.profileOptions.forEach((option) => {
      const radio = option.querySelector('input[type="radio"]')
      if (!radio) return
      const isSingle = radio.value === 'single'
      radio.checked = isSingle
      option.classList.toggle('selected', isSingle)
    })

    ctx.actions.syncScenarioSelection?.()
    ctx.actions.updateProfileUi()
    ctx.actions.updateStep2Layout()
    ctx.actions.updateSingleNetclientLocationUi?.()
    state.primaryTargetPrepared = false
    state.primaryNextStepUnlocked = false
    state.multiTargets = []
    ctx.actions.renderMultiTargets()
    ctx.actions.resetMultiTargetForm()
    ctx.actions.updatePrimaryTargetWorkflowUi()
    ctx.actions.clearAlerts()
    elements.configPreview.textContent = ''
    state.configFiles = {}
    state.editedFiles = {}
  }

  ctx.actions.goToPreviousStep = function goToPreviousStep() {
    if (state.currentStep === 6) {
      if (window.confirm('Are you sure you want to go back? This will delete the configuration files you just created.')) {
        fetch('/nut_config/api/delete-config', { method: 'POST', headers: { 'Content-Type': 'application/json' } })
          .then((response) => response.json())
          .catch((error) => console.error('Error deleting configuration:', error))
          .finally(() => {
            if (state.currentStep > state.firstStep) {
              ctx.actions.goToStep(state.currentStep - 1)
            }
          })
      }
      return
    }
    if (state.currentStep > state.firstStep) {
      ctx.actions.goToStep(state.currentStep - 1)
    }
  }

  ctx.actions.getCurrentStep = function getCurrentStep() {
    const visibleStepContent = document.querySelector('.wizard-step-content:not(.hidden)')
    if (visibleStepContent) {
      const stepMatch = visibleStepContent.id.match(/step-(\d+)/)
      if (stepMatch && stepMatch[1]) {
        return parseInt(stepMatch[1], 10)
      }
    }
    return state.currentStep
  }

  ctx.actions.updateStepIndicators = function updateStepIndicators(step) {
    elements.steps.forEach((stepEl, index) => {
      stepEl.classList.remove('active', 'completed')
      if (index + 1 < step) {
        stepEl.classList.add('completed')
      } else if (index + 1 === step) {
        stepEl.classList.add('active')
      }
    })

    elements.stepContents.forEach((content, index) => {
      content.classList.toggle('hidden', index + 1 !== step)
    })
    state.currentStep = step
  }

  ctx.actions.updateButtons = function updateButtons(step) {
    const setDefaultNextLabel = () => {
      elements.nextBtn.innerHTML = 'Next <i class="fas fa-arrow-right"></i>'
    }

    if (step === state.firstStep) {
      elements.prevBtn.classList.add('hidden')
      elements.nextBtn.classList.remove('hidden')
      setDefaultNextLabel()
      elements.saveBtn.classList.add('hidden')
      return
    }

    if (step === 5) {
      elements.prevBtn.classList.remove('hidden')
      elements.nextBtn.classList.add('hidden')
      setDefaultNextLabel()
      return
    }

    if (step === 6) {
      elements.prevBtn.classList.remove('hidden')
      elements.nextBtn.classList.add('hidden')
      setDefaultNextLabel()
      elements.saveBtn.classList.add('hidden')
      return
    }

    elements.prevBtn.classList.remove('hidden')
    if (step === 4 && state.selectedProfile === 'multi') {
      const waitingPrimaryTestAction = ctx.actions.isWaitingPrimaryTestSaveAction()
      if (waitingPrimaryTestAction) {
        elements.nextBtn.classList.remove('hidden')
        elements.nextBtn.innerHTML = '<i class="fas fa-check-circle"></i> Test &amp; Save Primary Target'
      } else {
        const waitingContinueAction = state.selectedMode !== 'netclient' && state.primaryTargetPrepared && !state.primaryNextStepUnlocked && ctx.actions.getAdditionalTargets().length === 0
        if (waitingContinueAction) {
          elements.nextBtn.classList.remove('hidden')
          elements.nextBtn.innerHTML = 'Continue With Next UPS <i class="fas fa-arrow-right"></i>'
        } else {
          const canProceed = ctx.actions.canProceedFromStep3MultiFlow()
          elements.nextBtn.classList.toggle('hidden', !canProceed)
          setDefaultNextLabel()
        }
      }
    } else {
      elements.nextBtn.classList.remove('hidden')
      setDefaultNextLabel()
    }
    elements.saveBtn.classList.add('hidden')
    moveMultiTargetActionsToCurrentSlot()
  }

  ctx.actions.goToStep = function goToStep(step) {
    if (step < state.firstStep) {
      step = state.firstStep
    }
    const previousStep = state.currentStep
    state.currentStep = step
    if (state.currentStep === 4 && previousStep !== 4) {
      ctx.actions.resetConfigMethodSelection()
    }
    ctx.actions.updateStepIndicators(state.currentStep)
    ctx.actions.updateButtons(state.currentStep)
    if (state.currentStep === 4) {
      ctx.actions.updatePrimaryTargetWorkflowUi()
      if (state.selectedProfile === 'multi') {
        ctx.actions.scheduleMultiScenarioDomRefresh?.()
      }
    }
    moveMultiTargetActionsToCurrentSlot()
    window.scrollTo(0, 0)
  }
}
