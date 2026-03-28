// @ts-nocheck

import { syncWizardScenarioSelection } from '../wizardScenarioStore'

export function registerProfileTopologyRuntime(ctx) {
  const { elements, state } = ctx

  ctx.actions.syncScenarioSelection = function syncScenarioSelection() {
    syncWizardScenarioSelection({
      profile: state.selectedProfile,
      mode: state.selectedMode,
      topology: state.selectedTopology,
      hostServiceMode: state.selectedHostServiceMode,
    })
  }

  ctx.actions.updateProfileUi = function updateProfileUi() {
    const isMulti = state.selectedProfile === 'multi'
    if (elements.singleProfileHint) {
      elements.singleProfileHint.classList.toggle('hidden', isMulti)
    }
    if (elements.multiProfileHint) {
      elements.multiProfileHint.classList.toggle('hidden', !isMulti)
    }
    ctx.actions.updatePrimaryTargetWorkflowUi()
  }

  ctx.actions.deriveHostModeFromSelections = function deriveHostModeFromSelections() {
    if (state.selectedProfile === 'single') {
      return state.selectedMode
    }
    if (state.selectedTopology === 'remote_only') {
      return 'netclient'
    }
    if (state.selectedTopology === 'local_only' || state.selectedTopology === 'mixed') {
      if (state.selectedHostServiceMode === 'standalone' || state.selectedHostServiceMode === 'netserver') {
        return state.selectedHostServiceMode
      }
      return null
    }
    return null
  }

  ctx.actions.updateDerivedHostModeInfo = function updateDerivedHostModeInfo() {
    if (!elements.multiDerivedHostMode) {
      return
    }
    if (state.selectedProfile !== 'multi' || !state.selectedTopology) {
      elements.multiDerivedHostMode.classList.add('hidden')
      elements.multiDerivedHostMode.textContent = ''
      return
    }
    const derivedMode = ctx.actions.deriveHostModeFromSelections()
    if (!derivedMode) {
      elements.multiDerivedHostMode.classList.add('hidden')
      elements.multiDerivedHostMode.textContent = ''
      return
    }
    elements.multiDerivedHostMode.classList.remove('hidden')
    elements.multiDerivedHostMode.textContent = `Derived host NUT mode: ${derivedMode}`
  }

  ctx.actions.updateStep2Layout = function updateStep2Layout() {
    const isMulti = state.selectedProfile === 'multi'
    if (elements.singleModeSelection) {
      elements.singleModeSelection.classList.toggle('hidden', isMulti)
    }
    if (elements.multiTopologySelection) {
      elements.multiTopologySelection.classList.toggle('hidden', !isMulti)
    }

    const needsLocalServiceMode = state.selectedTopology === 'local_only' || state.selectedTopology === 'mixed'
    if (elements.multiHostServiceSelection) {
      elements.multiHostServiceSelection.classList.toggle('hidden', !(isMulti && needsLocalServiceMode))
    }

    if (!isMulti) {
      state.selectedTopology = null
      ctx.actions.resetPrimaryTargetPreparedState(false)
    }

    ctx.actions.syncScenarioSelection()
    ctx.actions.updateDerivedHostModeInfo()
    ctx.actions.updateMultiTargetConnectionUi()
    ctx.actions.updatePrimaryTargetWorkflowUi()
  }

  ctx.actions.bindProfileTopologyHandlers = function bindProfileTopologyHandlers() {
    elements.primaryModeOptions.forEach((option) => {
      option.addEventListener('click', function onPrimaryModeClick() {
        ctx.actions.resetPrimaryTargetPreparedState(true)
        const radio = this.querySelector('input[type="radio"]')
        if (radio) {
          radio.checked = true
        }
        elements.primaryModeOptions.forEach((item) => item.classList.remove('selected'))
        this.classList.add('selected')
        state.selectedMode = this.dataset.mode
        ctx.actions.syncScenarioSelection()
      })
    })

    elements.topologyOptions.forEach((option) => {
      option.addEventListener('click', function onTopologyClick() {
        ctx.actions.resetPrimaryTargetPreparedState(true)
        elements.topologyOptions.forEach((item) => item.classList.remove('selected'))
        this.classList.add('selected')
        state.selectedTopology = this.dataset.topology || null
        ctx.actions.invalidateMultiTargetTestState(true)
        ctx.actions.updateStep2Layout()
        ctx.actions.syncScenarioSelection()
      })
    })

    elements.hostModeOptions.forEach((option) => {
      option.addEventListener('click', function onHostModeClick() {
        ctx.actions.resetPrimaryTargetPreparedState(true)
        elements.hostModeOptions.forEach((item) => item.classList.remove('selected'))
        this.classList.add('selected')
        state.selectedHostServiceMode = this.dataset.hostMode || 'standalone'
        ctx.actions.invalidateMultiTargetTestState(true)
        ctx.actions.updateDerivedHostModeInfo()
        ctx.actions.syncScenarioSelection()
      })
    })

    elements.profileOptions.forEach((option) => {
      option.addEventListener('click', function onProfileClick() {
        ctx.actions.resetPrimaryTargetPreparedState(true)
        const radio = this.querySelector('input[type="radio"]')
        if (radio) {
          radio.checked = true
        }
        elements.profileOptions.forEach((item) => item.classList.remove('selected'))
        this.classList.add('selected')
        state.selectedProfile = this.dataset.profile === 'multi' ? 'multi' : 'single'
        ctx.actions.invalidateMultiTargetTestState(true)
        ctx.actions.updateProfileUi()
        ctx.actions.updateStep2Layout()
        ctx.actions.syncScenarioSelection()
      })
    })
  }
}
