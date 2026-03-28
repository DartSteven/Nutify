// @ts-nocheck

function getModeDom(mode) {
  const prefix = mode === 'standalone' ? 'standalone' : 'netserver'
  return {
    displayNameBlock: document.getElementById(`${prefix}-primary-display-name-block`),
    nameBlock: document.getElementById(`${prefix}-primary-name-block`),
    timezoneBlock: document.getElementById(`${prefix}-primary-timezone-block`),
    currencyBlock: document.getElementById(`${prefix}-primary-currency-block`),
    pollingBlock: document.getElementById(`${prefix}-primary-polling-block`),
    displayNameAnchor: document.getElementById(`${prefix}-primary-display-name-anchor`),
    nameAnchor: document.getElementById(`${prefix}-primary-name-anchor`),
    timezoneAnchor: document.getElementById(`${prefix}-primary-timezone-anchor`),
    currencyAnchor: document.getElementById(`${prefix}-primary-currency-anchor`),
    pollingAnchor: document.getElementById(`${prefix}-primary-polling-anchor`),
    autoFields: document.getElementById(`${prefix}-auto-primary-fields`),
    autoDisplayNameSlot: document.getElementById(`${prefix}-auto-display-name-slot`),
    autoNameSlot: document.getElementById(`${prefix}-auto-name-slot`),
    autoTimezoneSlot: document.getElementById(`${prefix}-auto-timezone-slot`),
    autoCurrencySlot: document.getElementById(`${prefix}-auto-currency-slot`),
    autoPollingSlot: document.getElementById(`${prefix}-auto-polling-slot`),
  }
}

function moveBlock(block, target) {
  if (!block || !target || block.parentElement === target) {
    return
  }
  target.appendChild(block)
}

function hideBlock(block) {
  block?.classList.add('hidden')
}

function showBlock(block) {
  block?.classList.remove('hidden')
}

function getManagedBlocks(dom) {
  return [dom.displayNameBlock, dom.nameBlock, dom.timezoneBlock, dom.currencyBlock, dom.pollingBlock]
}

export function registerPrimaryAutoDetectLayoutRuntime(ctx) {
  ctx.actions.showPrimaryAutoDetectFields = function showPrimaryAutoDetectFields(mode, visible) {
    const dom = getModeDom(mode)
    if (!dom.autoFields) {
      return
    }

    if (!visible) {
      dom.autoFields.classList.add('hidden')
      getManagedBlocks(dom).forEach(hideBlock)
      return
    }

    moveBlock(dom.displayNameBlock, dom.autoDisplayNameSlot)
    moveBlock(dom.nameBlock, dom.autoNameSlot)
    moveBlock(dom.timezoneBlock, dom.autoTimezoneSlot)
    moveBlock(dom.currencyBlock, dom.autoCurrencySlot)
    moveBlock(dom.pollingBlock, dom.autoPollingSlot)
    dom.autoFields.classList.remove('hidden')
    getManagedBlocks(dom).forEach(showBlock)
  }

  ctx.actions.restorePrimaryAutoDetectLayout = function restorePrimaryAutoDetectLayout(mode) {
    const dom = getModeDom(mode)
    if (!dom.nameBlock) {
      return
    }

    moveBlock(dom.displayNameBlock, dom.displayNameAnchor)
    moveBlock(dom.nameBlock, dom.nameAnchor)
    moveBlock(dom.timezoneBlock, dom.timezoneAnchor)
    moveBlock(dom.currencyBlock, dom.currencyAnchor)
    moveBlock(dom.pollingBlock, dom.pollingAnchor)
    getManagedBlocks(dom).forEach(showBlock)
    dom.autoFields?.classList.add('hidden')
  }

  ctx.actions.resetPrimaryAutoDetectSelectionUi = function resetPrimaryAutoDetectSelectionUi(mode) {
    const dom = getModeDom(mode)
    dom.autoFields?.classList.add('hidden')
    getManagedBlocks(dom).forEach(hideBlock)
  }

  ctx.actions.syncPrimaryAutoDetectLayout = function syncPrimaryAutoDetectLayout(mode, method) {
    if (method === 'manual') {
      ctx.actions.restorePrimaryAutoDetectLayout(mode)
      return
    }
    if (method === 'auto') {
      ctx.actions.showPrimaryAutoDetectFields(mode, false)
      return
    }
    ctx.actions.restorePrimaryAutoDetectLayout(mode)
  }

  ;['standalone', 'netserver'].forEach((mode) => {
    ctx.actions.restorePrimaryAutoDetectLayout(mode)
  })
}
