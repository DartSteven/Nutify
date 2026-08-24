// @ts-nocheck

export function registerModalAlerts(ctx) {
  const { elements, state } = ctx

  ctx.actions.showAlert = function showAlert(message, type = 'info') {
    ctx.actions.clearAlerts()
    const alert = document.createElement('div')
    alert.className = `alert alert-${type}`
    alert.textContent = message

    const closeBtn = document.createElement('button')
    closeBtn.innerHTML = '&times;'
    closeBtn.className = 'close-alert'
    closeBtn.addEventListener('click', function removeAlert() {
      elements.alertsContainer.removeChild(alert)
    })

    alert.appendChild(closeBtn)
    elements.alertsContainer.appendChild(alert)
  }

  ctx.actions.clearAlerts = function clearAlerts() {
    elements.alertsContainer.innerHTML = ''
  }

  ctx.actions.resolveNominalPowerModal = function resolveNominalPowerModal(value) {
    if (elements.nominalPowerModal) {
      elements.nominalPowerModal.style.display = 'none'
    }
    if (state.pendingNominalPowerResolver) {
      const resolver = state.pendingNominalPowerResolver
      state.pendingNominalPowerResolver = null
      resolver(value)
    }
  }

  ctx.actions.closeNominalPowerModal = function closeNominalPowerModal() {
    ctx.actions.resolveNominalPowerModal(null)
  }

  ctx.actions.requestNominalPowerFromUser = function requestNominalPowerFromUser(targetLabel, currentNominalValue = null) {
    return new Promise((resolve) => {
      if (!elements.nominalPowerModal || !elements.nominalPowerModalInput) {
        resolve(ctx.actions.coerceOptionalPositiveInt(currentNominalValue))
        return
      }

      if (state.pendingNominalPowerResolver) {
        const resolver = state.pendingNominalPowerResolver
        state.pendingNominalPowerResolver = null
        resolver(null)
      }

      state.pendingNominalPowerResolver = resolve
      const safeTargetLabel = String(targetLabel || '').trim()
      const messagePrefix = safeTargetLabel ? `Target "${safeTargetLabel}"` : 'This target'
      if (elements.nominalPowerModalMessage) {
        elements.nominalPowerModalMessage.textContent = `${messagePrefix} does not expose ups.realpower.nominal. Insert the nominal UPS power in Watts to continue.`
      }

      const normalizedCurrentValue = ctx.actions.coerceOptionalPositiveInt(currentNominalValue)
      elements.nominalPowerModalInput.value = normalizedCurrentValue ? String(normalizedCurrentValue) : ''
      elements.nominalPowerModal.style.display = 'block'
      elements.nominalPowerModalInput.focus()
      elements.nominalPowerModalInput.select()
    })
  }

  ctx.actions.openModal = function openModal(isSuccess, message, output, nominalPower = null) {
    elements.testMessage.textContent = message

    if (elements.multiTargetTestList) {
      elements.multiTargetTestList.classList.add('hidden')
      elements.multiTargetTestList.innerHTML = ''
    }
    elements.upscOutput.classList.remove('hidden')
    elements.missingRealpowerForm.classList.add('hidden')
    elements.realpowerInput.value = ''

    if (output && output.startsWith('<div')) {
      elements.upscOutput.innerHTML = output
    } else {
      elements.upscOutput.textContent = output || ''
    }

    if (isSuccess && nominalPower?.requires_manual_input) {
      elements.missingRealpowerForm.classList.remove('hidden')
      elements.closeModalBtn.onclick = function storeNominalAndClose() {
        state.upsRealpowerNominal = ctx.actions.coerceOptionalPositiveInt(elements.realpowerInput.value)
        ctx.actions.closeModal()
      }
    } else {
      elements.closeModalBtn.onclick = ctx.actions.closeModal
    }

    elements.testMessage.className = isSuccess ? 'alert alert-success' : 'alert alert-error'
    elements.modal.style.display = 'block'
  }

  ctx.actions.closeModal = function closeModal() {
    elements.modal.style.display = 'none'
  }

  ctx.actions.closeTargetDetailModal = function closeTargetDetailModal() {
    if (elements.targetDetailModal) {
      elements.targetDetailModal.style.display = 'none'
    }
  }

  ctx.actions.updatePrimaryTargetWorkflowStatus = function updatePrimaryTargetWorkflowStatus(message, isSuccess) {
    if (!elements.primaryTargetWorkflowStatus) {
      return
    }
    const normalizedMessage = String(message || '').trim()
    elements.primaryTargetWorkflowStatus.textContent = normalizedMessage
    elements.primaryTargetWorkflowStatus.classList.toggle('hidden', !normalizedMessage)
    if (isSuccess === true) {
      elements.primaryTargetWorkflowStatus.style.color = '#16a34a'
    } else if (isSuccess === false) {
      elements.primaryTargetWorkflowStatus.style.color = '#b45309'
    } else {
      elements.primaryTargetWorkflowStatus.style.color = '#6b7280'
    }
  }

  ctx.actions.updateMultiTargetTestStatus = function updateMultiTargetTestStatus(message, isSuccess) {
    if (!elements.multiTargetTestStatus) {
      return
    }
    const normalizedMessage = String(message || '').trim()
    elements.multiTargetTestStatus.textContent = normalizedMessage
    elements.multiTargetTestStatus.classList.toggle('hidden', !normalizedMessage)
    if (isSuccess === true) {
      elements.multiTargetTestStatus.style.color = '#16a34a'
    } else if (isSuccess === false) {
      elements.multiTargetTestStatus.style.color = '#b45309'
    } else {
      elements.multiTargetTestStatus.style.color = '#6b7280'
    }
    if (elements.multiTargetAddBtn) {
      elements.multiTargetAddBtn.disabled = !isSuccess
      elements.multiTargetAddBtn.classList.toggle('hidden', !isSuccess)
      elements.multiTargetAddBtn.style.display = isSuccess ? '' : 'none'
    }
  }

  ctx.actions.updateMultiTargetFlowHint = function updateMultiTargetFlowHint(message) {
    if (!elements.multiTargetFlowHint) {
      return
    }
    const normalizedMessage = String(message || '').trim()
    elements.multiTargetFlowHint.textContent = normalizedMessage
    elements.multiTargetFlowHint.classList.toggle('hidden', !normalizedMessage)
  }

  ctx.actions.bindModalEvents = function bindModalEvents() {
    if (elements.modalClose) {
      elements.modalClose.addEventListener('click', ctx.actions.closeModal)
    }
    elements.closeModalBtn.onclick = ctx.actions.closeModal
    if (elements.targetDetailModalClose) {
      elements.targetDetailModalClose.addEventListener('click', ctx.actions.closeTargetDetailModal)
    }
    if (elements.targetDetailCloseBtn) {
      elements.targetDetailCloseBtn.addEventListener('click', ctx.actions.closeTargetDetailModal)
    }
    if (elements.nominalPowerModalClose) {
      elements.nominalPowerModalClose.addEventListener('click', ctx.actions.closeNominalPowerModal)
    }
    if (elements.nominalPowerModalCancelBtn) {
      elements.nominalPowerModalCancelBtn.addEventListener('click', ctx.actions.closeNominalPowerModal)
    }
    if (elements.nominalPowerModalSaveBtn) {
      elements.nominalPowerModalSaveBtn.addEventListener('click', function saveNominalPower() {
        const parsedNominal = ctx.actions.coerceOptionalPositiveInt(elements.nominalPowerModalInput?.value)
        if (!parsedNominal) {
          ctx.actions.showAlert('Please enter a valid nominal power value greater than zero.', 'error')
          return
        }
        ctx.actions.resolveNominalPowerModal(parsedNominal)
      })
    }
    if (elements.nominalPowerModalInput) {
      elements.nominalPowerModalInput.addEventListener('keydown', function onNominalKeydown(event) {
        if (event.key === 'Enter') {
          event.preventDefault()
          elements.nominalPowerModalSaveBtn?.click()
        }
      })
    }

    window.addEventListener('click', function onWindowClick(event) {
      if (event.target === elements.modal) {
        ctx.actions.closeModal()
      }
      if (event.target === elements.targetDetailModal) {
        ctx.actions.closeTargetDetailModal()
      }
      if (event.target === elements.nominalPowerModal) {
        ctx.actions.closeNominalPowerModal()
      }
    })
  }
}
