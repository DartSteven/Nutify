// @ts-nocheck

import { createWizardRuntimeContext, refreshWizardRuntimeElements } from './runtime/context'
import { registerSharedHelpers } from './runtime/sharedHelpers'
import { registerServerIdentityRuntime } from './runtime/serverIdentityRuntime'
import { registerModalAlerts } from './runtime/modalAlerts'
import { registerPrimaryAutoDetectLayoutRuntime } from './runtime/primaryAutoDetectLayoutRuntime'
import { registerPrimaryManualUsbRuntime } from './runtime/primaryManualUsbRuntime'
import { registerPrimaryModesRuntime } from './runtime/primaryModesRuntime'
import { registerPrimaryTargetRuntime } from './runtime/primaryTargetRuntime'
import { registerSnmpRuntime } from './runtime/snmpRuntime'
import { registerSingleNetclientLocationRuntime } from './runtime/singleNetclientLocationRuntime'
import { registerMultiTargetLocationRuntime } from './runtime/multiTargetLocationRuntime'
import { registerMultiTargetCoreRuntime } from './runtime/multiTargetCoreRuntime'
import { registerMultiTargetFormRuntime } from './runtime/multiTargetFormRuntime'
import { registerMultiTargetUsbRuntime } from './runtime/multiTargetUsbRuntime'
import { registerMultiTargetListRuntime } from './runtime/multiTargetListRuntime'
import { registerMultiTargetHandlersRuntime } from './runtime/multiTargetHandlersRuntime'
import { registerProfileTopologyRuntime } from './runtime/profileTopologyRuntime'
import { registerNavigationRuntime } from './runtime/navigationRuntime'
import { registerStepFlowRuntime } from './runtime/stepFlowRuntime'
import { registerPreviewEditorRuntime } from './runtime/previewEditorRuntime'
import { registerConfigurationExecutionRuntime } from './runtime/configurationExecutionRuntime'

declare global {
  interface Window {
    __nutifySetupWizardInitialized?: boolean
  }
}

let pendingMultiScenarioRefreshFrame = 0

function hideAdminStepForAuthDisabled(ctx) {
  if (!ctx.state.authDisabled) {
    return
  }

  const adminStepIndicator = document.querySelector('.step[data-step="1"]')
  const adminStepContent = document.getElementById('step-1')
  if (adminStepIndicator) {
    adminStepIndicator.classList.add('hidden')
  }
  if (adminStepContent) {
    adminStepContent.classList.add('hidden')
  }

  let displayStep = 1
  ctx.elements.steps.forEach((stepEl) => {
    if (stepEl.classList.contains('hidden')) {
      return
    }
    const numberEl = stepEl.querySelector('.step-number')
    if (numberEl) {
      numberEl.textContent = displayStep
    }
    displayStep += 1
  })
}

function registerWizardModules(ctx) {
  registerSharedHelpers(ctx)
  registerServerIdentityRuntime(ctx)
  registerModalAlerts(ctx)
  registerPrimaryAutoDetectLayoutRuntime(ctx)
  registerPrimaryManualUsbRuntime(ctx)
  registerPrimaryModesRuntime(ctx)
  registerSnmpRuntime(ctx)
  registerPrimaryTargetRuntime(ctx)
  registerSingleNetclientLocationRuntime(ctx)
  registerMultiTargetLocationRuntime(ctx)
  registerMultiTargetCoreRuntime(ctx)
  registerMultiTargetFormRuntime(ctx)
  registerMultiTargetUsbRuntime(ctx)
  registerMultiTargetListRuntime(ctx)
  registerMultiTargetHandlersRuntime(ctx)
  registerProfileTopologyRuntime(ctx)
  registerNavigationRuntime(ctx)
  registerStepFlowRuntime(ctx)
  registerPreviewEditorRuntime(ctx)
  registerConfigurationExecutionRuntime(ctx)
}

function initNutifySetupWizard() {
  if (window.__nutifySetupWizardInitialized) {
    return
  }

  const ctx = createWizardRuntimeContext()
  if (!ctx) {
    return
  }

  window.__nutifySetupWizardInitialized = true
  registerWizardModules(ctx)
  hideAdminStepForAuthDisabled(ctx)

  ctx.actions.refreshMultiScenarioDom = function refreshMultiScenarioDom() {
    refreshWizardRuntimeElements(ctx)
    ctx.actions.populateSetupTimezones()
    ctx.actions.setupMultiTargetHandlers()
    ctx.actions.setupMultiTargetUsbPortPickerHandlers?.()
    ctx.actions.updateMultiTargetConnectionUi()
    ctx.actions.updateMultiTargetUsbPortPicker?.()
    ctx.actions.updateMultiTargetStorageStrategyUi()
    ctx.actions.updateMultiTargetLocationUi()
    ctx.actions.renderMultiTargets()
    ctx.actions.updatePrimaryTargetWorkflowUi()
    ctx.actions.updateButtons(ctx.state.currentStep)
  }

  ctx.actions.scheduleMultiScenarioDomRefresh = function scheduleMultiScenarioDomRefresh() {
    if (pendingMultiScenarioRefreshFrame) {
      cancelAnimationFrame(pendingMultiScenarioRefreshFrame)
    }
    pendingMultiScenarioRefreshFrame = requestAnimationFrame(() => {
      pendingMultiScenarioRefreshFrame = 0
      ctx.actions.refreshMultiScenarioDom()
    })
  }

  ctx.actions.loadAvailableDrivers()
  ctx.actions.loadInitialServerName()
  ctx.actions.populateSetupTimezones()
  ctx.actions.setupScanButtons()
  ctx.actions.setupConfigMethodRadios()
  ctx.actions.setupSnmpFieldHandlers()
  ctx.actions.bindModalEvents()
  ctx.actions.bindPreviewEditorHandlers()
  ctx.actions.bindExecutionHandlers()
  ctx.actions.bindProfileTopologyHandlers()
  ctx.actions.setupMultiTargetHandlers()
  ctx.actions.setupMultiTargetUsbPortPickerHandlers?.()
  ctx.actions.setupSingleNetclientLocationHandlers()
  ctx.actions.setupPrimaryTargetWorkflowHandlers()

  ctx.elements.prevBtn.addEventListener('click', ctx.actions.goToPreviousStep)
  ctx.elements.nextBtn.addEventListener('click', ctx.actions.goToNextStep)

  ctx.elements.saveBtn.classList.add('hidden')
  ctx.actions.updateStepIndicators(ctx.state.currentStep)
  ctx.actions.updateButtons(ctx.state.currentStep)

  const defaultProfileRadio = document.querySelector('input[name="monitoring_profile"]:checked')
  if (defaultProfileRadio) {
    ctx.state.selectedProfile = defaultProfileRadio.value === 'multi' ? 'multi' : 'single'
  }

  ctx.actions.syncScenarioSelection?.()
  ctx.actions.updateProfileUi()
  ctx.actions.updateStep2Layout()
  ctx.actions.resetMultiTargetForm()
  ctx.actions.renderMultiTargets()
}

function destroyNutifySetupWizard() {
  if (pendingMultiScenarioRefreshFrame) {
    cancelAnimationFrame(pendingMultiScenarioRefreshFrame)
    pendingMultiScenarioRefreshFrame = 0
  }
  window.__nutifySetupWizardInitialized = false
}

export { initNutifySetupWizard, destroyNutifySetupWizard }
