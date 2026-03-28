// @ts-nocheck

export function registerMultiTargetSequentialTestRuntime(ctx) {
  const { elements } = ctx

  ctx.actions.runSequentialMultiTargetTests = function runSequentialMultiTargetTests(targets, testResult) {
    const normalizedTargets = Array.isArray(targets) ? targets : []
    if (!normalizedTargets.length) {
      ctx.actions.openModal(false, 'Configuration test failed', 'No targets configured to test.')
      testResult.classList.remove('hidden')
      testResult.innerHTML = '<div class="alert alert-error"><i class="fas fa-times-circle"></i> No targets configured to test.</div>'
      return
    }

    elements.missingRealpowerForm.classList.add('hidden')
    elements.realpowerInput.value = ''
    elements.upscOutput.innerHTML = ''
    elements.upscOutput.classList.add('hidden')
    let targetListContainer = elements.multiTargetTestList
    if (!targetListContainer) {
      targetListContainer = document.createElement('div')
      targetListContainer.id = 'multi-target-test-list-runtime'
      if (elements.upscOutput?.parentElement) {
        elements.upscOutput.parentElement.insertBefore(targetListContainer, elements.upscOutput)
      }
    }
    if (!targetListContainer) {
      ctx.actions.openModal(false, 'Configuration test failed', 'Test list container not available.')
      return
    }

    targetListContainer.classList.remove('hidden')
    targetListContainer.innerHTML = ''
    elements.testMessage.className = 'alert alert-warning'
    elements.testMessage.textContent = 'Run each target test in sequence. Save is enabled only when all targets pass.'
    elements.modal.style.display = 'block'
    testResult.classList.add('hidden')
    testResult.innerHTML = ''
    elements.saveBtn.classList.add('hidden')

    const listView = document.createElement('div')
    listView.className = 'multi-target-test-list'
    const rowStates = normalizedTargets.map((target) => {
      const targetLabel = String(target?.name || '').trim() || `${target.ups_name}@${target.host}`
      const row = document.createElement('div')
      row.className = 'multi-target-item multi-target-test-row'
      row.innerHTML = `<div class="multi-target-test-title"><strong>${ctx.actions.escapeHtml(targetLabel)}</strong></div><div class="multi-target-item-controls multi-target-test-controls"><button class="nav-btn next-btn multi-target-test-btn" type="button"><i class="fas fa-check-circle"></i> Test Configuration</button><span class="multi-target-test-status pending">Pending</span><button class="nav-btn back-btn multi-target-info-btn hidden" type="button" title="View test details for ${ctx.actions.escapeHtml(targetLabel)}"><i class="fas fa-info-circle"></i></button></div>`
      const button = row.querySelector('.multi-target-test-btn')
      const status = row.querySelector('.multi-target-test-status')
      const infoBtn = row.querySelector('.multi-target-info-btn')
      listView.appendChild(row)
      return { target, targetLabel, button, status, infoBtn, passed: false, detailHtml: '', detailSuccess: false }
    })

    const setRowStatus = (rowState, mode) => {
      rowState.status.className = 'multi-target-test-status'
      rowState.status.classList.add(mode)
      rowState.status.textContent = mode === 'testing' ? 'Testing' : mode === 'passed' ? 'Passed' : mode === 'failed' ? 'Failed' : 'Pending'
    }
    const allPassed = () => rowStates.every((item) => item.passed)
    const showDetailModal = (targetLabel, isSuccess, htmlContent) => {
      if (!elements.targetDetailModal || !elements.targetDetailTitle || !elements.targetDetailMessage || !elements.targetDetailOutput) {
        ctx.actions.showAlert('Target details modal is unavailable in the current view.', 'error')
        return
      }
      elements.targetDetailTitle.textContent = `Target Result: ${targetLabel}`
      elements.targetDetailMessage.className = isSuccess ? 'alert alert-success' : 'alert alert-error'
      elements.targetDetailMessage.innerHTML = isSuccess ? '<i class="fas fa-check-circle"></i> Target test passed.' : '<i class="fas fa-times-circle"></i> Target test failed.'
      elements.targetDetailOutput.innerHTML = htmlContent
      elements.targetDetailModal.style.display = 'block'
    }

    const runTargetTest = async (index) => {
      const rowState = rowStates[index]
      if (!rowState) return
      rowState.button.disabled = true
      rowState.button.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Testing...'
      setRowStatus(rowState, 'testing')
      try {
        const response = await fetch('/nut_config/api/setup/test-target', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(ctx.actions.buildTargetTestPayload(rowState.target)),
        })
        const data = await response.json()
        const isSuccess = !!data?.success && response.ok
        rowState.detailHtml = ctx.actions.formatTargetTestDetails(rowState.targetLabel, data)
        rowState.detailSuccess = isSuccess
        if (isSuccess) {
          let targetNominalPower = ctx.actions.coerceOptionalPositiveInt(data?.nominal_power?.value) || ctx.actions.coerceOptionalPositiveInt(rowState.target.ups_realpower_nominal)
          if (ctx.actions.shouldRequestNominalPowerInput(data, targetNominalPower) && !targetNominalPower) {
            const manualNominalPower = await ctx.actions.requestNominalPowerFromUser(rowState.targetLabel, rowState.target.ups_realpower_nominal)
            if (!manualNominalPower) {
              rowState.passed = false
              setRowStatus(rowState, 'failed')
              rowState.button.disabled = false
              rowState.button.innerHTML = '<i class="fas fa-redo"></i> Re-test'
              rowState.infoBtn.classList.add('hidden')
              rowState.infoBtn.disabled = true
              elements.testMessage.className = 'alert alert-error'
              elements.testMessage.textContent = `Target "${rowState.targetLabel}" passed connectivity but requires UPS nominal power to continue.`
              testResult.classList.remove('hidden')
              testResult.innerHTML = `<div class="alert alert-error"><i class="fas fa-times-circle"></i> Target "${ctx.actions.escapeHtml(rowState.targetLabel)}" requires UPS nominal power.</div>`
              elements.saveBtn.classList.add('hidden')
              return
            }
            targetNominalPower = manualNominalPower
          }
          rowState.target.ups_realpower_nominal = targetNominalPower
          rowState.detailHtml = ctx.actions.formatTargetTestDetails(rowState.targetLabel, { ...data, nominal_power: { ...(data?.nominal_power || {}), found: Boolean(targetNominalPower), value: targetNominalPower, requires_manual_input: !targetNominalPower } })
          rowState.passed = true
          setRowStatus(rowState, 'passed')
          rowState.button.disabled = false
          rowState.button.innerHTML = '<i class="fas fa-redo"></i> Re-test'
          rowState.infoBtn.classList.remove('hidden')
          rowState.infoBtn.disabled = false
          if (allPassed()) {
            elements.testMessage.className = 'alert alert-success'
            elements.testMessage.textContent = `All ${rowStates.length} targets passed. You can now save the configuration.`
            testResult.classList.remove('hidden')
            testResult.innerHTML = '<div class="alert alert-success"><i class="fas fa-check-circle"></i> All targets passed.</div>'
            elements.saveBtn.classList.remove('hidden')
          }
          return
        }

        rowState.passed = false
        setRowStatus(rowState, 'failed')
        rowState.button.disabled = false
        rowState.button.innerHTML = '<i class="fas fa-redo"></i> Re-test'
        rowState.infoBtn.classList.add('hidden')
        rowState.infoBtn.disabled = true
        elements.testMessage.className = 'alert alert-error'
        elements.testMessage.textContent = `Target "${rowState.targetLabel}" failed. Fix it and retry this target.`
        testResult.classList.remove('hidden')
        testResult.innerHTML = `<div class="alert alert-error"><i class="fas fa-times-circle"></i> Target "${ctx.actions.escapeHtml(rowState.targetLabel)}" failed.</div>`
        elements.saveBtn.classList.add('hidden')
      } catch (error) {
        console.error('Error testing target:', error)
        rowState.detailHtml = '<div class="ups-data"><div class="ups-data-item"><strong>Error:</strong> Network error while testing target.</div></div>'
        rowState.detailSuccess = false
        rowState.passed = false
        setRowStatus(rowState, 'failed')
        rowState.button.disabled = false
        rowState.button.innerHTML = '<i class="fas fa-redo"></i> Re-test'
        rowState.infoBtn.classList.add('hidden')
        rowState.infoBtn.disabled = true
        elements.testMessage.className = 'alert alert-error'
        elements.testMessage.textContent = `Target "${rowState.targetLabel}" failed due to network error.`
        testResult.classList.remove('hidden')
        testResult.innerHTML = `<div class="alert alert-error"><i class="fas fa-times-circle"></i> Network error while testing "${ctx.actions.escapeHtml(rowState.targetLabel)}".</div>`
        elements.saveBtn.classList.add('hidden')
      }
    }

    rowStates.forEach((rowState, index) => {
      rowState.button.addEventListener('click', () => { void runTargetTest(index) })
      rowState.infoBtn.addEventListener('click', () => {
        if (rowState.detailHtml) {
          showDetailModal(rowState.targetLabel, rowState.detailSuccess, rowState.detailHtml)
        }
      })
    })

    targetListContainer.appendChild(listView)
    elements.closeModalBtn.textContent = 'Close'
    elements.closeModalBtn.onclick = ctx.actions.closeModal
  }
}
